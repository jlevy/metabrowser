"""A literal ``%`` in a filename, end to end through every inbound surface.

These are ordinary files. ``report%20final.txt`` is what a URL-derived download is
called, and ``100%.md`` is a name people type. They are also the plain-ASCII case that
proves the canonical identity has to be reversible: the escape publishes them as
``report%2520final.txt`` and ``100%25.md``, and before the inverse existed those
identities resolved to nothing at all -- the folder listed, the directory expanded to
zero children, and an entry query reported the file absent while it sat on disk.

The coverage is deliberately by *surface* rather than by assertion count. The store is
keyed by the canonical identity, so a lookup that forgot to speak it does not raise --
it silently finds nothing, and only a query that actually crosses the boundary shows it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import (
    DirectoryProjection,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    canonical_inventory_name,
    native_inventory_name,
)
from tests.inventory_harness import inventory_harness, wait_until_settled

# native name on disk -> the identity the inventory publishes for it
PERCENT_NAMES = {
    "report%20final.txt": "report%2520final.txt",
    "100%.md": "100%25.md",
    "%41": "%2541",
}


def _build_tree(root: Path) -> None:
    (root / "d%1").mkdir()
    (root / "d%1" / "a.txt").write_text("a")
    (root / "plain").mkdir()
    (root / "plain" / "b.txt").write_text("b")
    for native in PERCENT_NAMES:
        (root / native).write_text("x")


def test_the_escape_and_its_inverse_agree_on_these_names() -> None:
    for native, canonical in PERCENT_NAMES.items():
        assert canonical_inventory_name(native) == canonical
        assert native_inventory_name(canonical) == native


def test_percent_named_entries_resolve_on_every_inbound_surface(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)

    async def exercise() -> None:
        async with inventory_harness(root, settle=False) as harness:
            await wait_until_settled(harness.runtime, timeout=20)
            coordinator = harness.runtime.coordinator

            async with coordinator.read_session() as session:
                top = await session.read(
                    ReadRequest(queries=(DirectoryQuery(query_id="top", path="", max_depth=1),))
                )
                listing = top.result.projection("top")
                assert isinstance(listing, DirectoryProjection)
                published = {entry.name for entry in listing.entries}
                assert set(PERCENT_NAMES.values()) <= published
                assert "d%251" in published

                # The directory whose name holds a `%` still has its child. Before the
                # inverse this expanded to zero rows, which is the failure a reader sees.
                expanded = await session.read(
                    ReadRequest(
                        queries=(DirectoryQuery(query_id="sub", path="d%251", max_depth=1),)
                    )
                )
                children = expanded.result.projection("sub")
                assert isinstance(children, DirectoryProjection)
                assert [e.name for e in children.entries] == ["a.txt"]

                # Every published identity resolves as an entry.
                for canonical in (*PERCENT_NAMES.values(), "d%251"):
                    got = await session.read(
                        ReadRequest(queries=(EntryQuery(query_id="e", path=canonical),))
                    )
                    projection = got.result.projection("e")
                    assert isinstance(projection, EntryProjection)
                    assert projection.presence is EntryPresence.PRESENT, canonical
                    assert projection.entry is not None
                    assert projection.entry.path == canonical

                # And the aggregate surface agrees the subtree is non-empty.
                rolled = await session.read(
                    ReadRequest(queries=(RollupQuery(query_id="r", path="d%251", max_depth=1),))
                )
                rollup = rolled.result.projection("r")
                assert isinstance(rollup, RollupProjection)
                payload = rollup.payload
                assert payload is not None
                assert payload["node"]["total_files"] == 1

            # A refresh receipt must not claim it verified a path it could not reach.
            receipt = await coordinator.refresh(
                RefreshRequest(
                    observations=tuple(
                        RefreshObservation(path=canonical, kind=ObservationKind.MODIFIED)
                        for canonical in PERCENT_NAMES.values()
                    )
                )
            )
            assert set(receipt.accepted_paths) == set(PERCENT_NAMES.values())
            assert not receipt.rejected_paths

            # The entries survive the refresh rather than being removed as missing,
            # which is what happens when the verify step looks up the wrong name.
            async with coordinator.read_session() as session:
                for canonical in PERCENT_NAMES.values():
                    got = await session.read(
                        ReadRequest(queries=(EntryQuery(query_id="e", path=canonical),))
                    )
                    entry_projection = got.result.projection("e")
                    assert isinstance(entry_projection, EntryProjection)
                    assert entry_projection.presence is EntryPresence.PRESENT, canonical

    asyncio.run(exercise())


def test_an_identity_outside_the_escapers_image_misses_rather_than_matching(
    tmp_path: Path,
) -> None:
    """``%41`` names a real file here, and is also not a valid identity.

    The file on disk is called ``%41``; its identity is ``%2541``. A query for the bare
    ``%41`` must therefore find nothing -- resolving it by passing the string through
    unchanged would hand back a file the caller did not ask for.
    """

    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)

    async def exercise() -> None:
        async with inventory_harness(root, settle=False) as harness:
            await wait_until_settled(harness.runtime, timeout=20)
            async with harness.runtime.coordinator.read_session() as session:
                got = await session.read(
                    ReadRequest(queries=(EntryQuery(query_id="e", path="%41"),))
                )
                projection = got.result.projection("e")
                assert isinstance(projection, EntryProjection)
                assert projection.presence is not EntryPresence.PRESENT

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Turkish dotless i: `str.lower()` maps `İ` to `i̇` (i plus a combining dot),
        # `ascii_casefold` leaves it alone. The divergence is invisible on an English
        # corpus and decides matches on any other.
        ("İ.jpg", "İ.jpg"),
        # Ü and Ç are left alone; only the ASCII letters fold. That is the divergence:
        # `str.lower()` would return "archive.türkçe" and drop a match fdu keeps.
        ("archive.TÜRKÇE", "archive.tÜrkÇe"),
        ("PHOTO.JPG", "photo.jpg"),
        ("Ünicode.MD", "Ünicode.md"),
    ],
)
def test_ascii_casefold_folds_ascii_only(name: str, expected: str) -> None:
    """The fold the contract pins, and the reason it is not ``str.lower()``.

    Two providers agree only if the alphabet is stated. fdu folds with
    ``eq_ignore_ascii_case``; ``str.lower()`` folds all of Unicode, so the same filter
    matched in one implementation and dropped in the other.
    """

    from metabrowser.inventory_engine.contract import ascii_casefold

    assert ascii_casefold(name) == expected
    # Identical on ASCII, which is why the split went unnoticed.
    if name.isascii():
        assert ascii_casefold(name) == name.lower()


@pytest.mark.parametrize(
    "value",
    [
        "a/",  # trailing separator
        "a//",  # trailing plus doubled
        "a//b",  # doubled in the middle
        "./a",  # leading dot segment
        "a/./b",
        "a/../b",
        "..",
        ".",
        "",
        "/a",  # absolute
        "a\\b",  # backslash
        "a\x00b",  # NUL
    ],
)
def test_the_validator_refuses_every_non_canonical_spelling(value: str) -> None:
    """Cases the rewritten validator now decides alone.

    The rewrite replaced ``PurePosixPath`` construction with string checks. A trailing
    or doubled separator was previously rejected by ``as_posix() != value`` -- an
    implication that is easy to lose when the implementation stops going through
    ``PurePosixPath`` at all.
    """

    from metabrowser.inventory_engine.contract import require_canonical_inventory_path

    if value == "":
        require_canonical_inventory_path(value, "path", allow_root=True)
        with pytest.raises(ValueError):
            require_canonical_inventory_path(value, "path", allow_root=False)
        return
    with pytest.raises(ValueError):
        require_canonical_inventory_path(value, "path", allow_root=True)


@pytest.mark.parametrize("value", ["café/naïve.txt", "a/b", "a", "x%FFy.txt", "%2541"])
def test_the_validator_accepts_canonical_non_ascii(value: str) -> None:
    """Non-ASCII but surrogate-free is the case the ``isascii`` fast path skips past.

    The gate is sound because every surrogate is non-ASCII, so an ASCII string cannot
    hold one -- but that makes the accepting non-ASCII path the one nothing else covers.
    """

    from metabrowser.inventory_engine.contract import require_canonical_inventory_path

    require_canonical_inventory_path(value, "path", allow_root=False)


def test_the_escape_inverts_over_every_short_name() -> None:
    """Exhaustive round-trip: the property the identity model rests on.

    The escape is only an identity if it is reversible, and only reversible if it is
    injective. Both are claims about every name, not about the examples above, so this
    enumerates them: `%` (which must escape first for injectivity to hold), `/` (which no
    escape may produce or consume), surrogates at every position, and the hex digits an
    escape is made of, which is where an off-by-one in the parser would show.
    """

    from itertools import product

    alphabet = ("a", "%", "/", ".", "\udc80", "\udcff", "2", "5", "F", "0")
    checked = 0
    for length in range(5):
        for combination in product(alphabet, repeat=length):
            native = "".join(combination)
            assert native_inventory_name(canonical_inventory_name(native)) == native
            checked += 1
    assert checked == sum(len(alphabet) ** n for n in range(5))


@pytest.mark.parametrize(
    "value",
    ["%", "%2", "%zz", "%41", "%7F", "%GG", "a%", "a%1", "%%", "%25%", "%00"],
)
def test_strings_outside_the_escapers_image_decode_to_none(value: str) -> None:
    """Not every string is an identity, and the inverse says so rather than guessing.

    `%41` is the sharp case: it is not something the escaper can emit, because a literal
    `%` becomes `%25` first. Returning it unchanged would resolve to a file genuinely
    named `%41`, which is a different file from the one the caller named.
    """

    assert native_inventory_name(value) is None
