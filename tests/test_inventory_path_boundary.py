"""One canonical path spelling crosses the provider boundary.

Clients spell a directory freely: ``docs``, ``docs/``, ``./docs``, and ``.`` or
``""`` for the root. The provider contract accepts exactly one of those, so
something has to translate — and the thing that translates must be above the
boundary, not inside each provider.

That placement is the point of these tests. If normalization lived in the
reference provider, a native provider would have to reimplement it, and the two
would disagree on the spellings nobody wrote a test for: one resolving ``.`` to
the root, the other reporting a miss. The route would look correct against
either and the difference would surface as a browser bug attributed to the
engine swap.

So the invariant asserted here is not "the routes are lenient". It is that
:func:`canonical_inventory_path` is total over client input, that everything it
accepts is already canonical by :func:`require_canonical_inventory_path`, and
that equivalent spellings are indistinguishable at the wire — leaving providers
one input shape to implement.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser import server
from metabrowser.inventory_engine.contract import (
    canonical_inventory_path,
    require_canonical_inventory_path,
)
from tests.inventory_harness import InventoryHarness, inventory_harness

# Spellings a browser, a command line, or a hand-written curl produces for a
# path that does name something under the root, paired with the one key the
# contract accepts for it.
EQUIVALENT_SPELLINGS: tuple[tuple[str, str], ...] = (
    ("", ""),
    (".", ""),
    ("./", ""),
    ("docs", "docs"),
    ("docs/", "docs"),
    ("./docs", "docs"),
    ("docs/.", "docs"),
    ("docs//", "docs"),
    ("./docs/", "docs"),
)

# Values that cannot name anything under the root. These must resolve to a
# miss, never to an exception: every one of them is reachable from a query
# string, so a raised error is a crash on client input.
UNNAMEABLE: tuple[str, ...] = (
    "..",
    "../",
    "../etc",
    "docs/..",
    "docs/../docs",
    "/etc/passwd",
    "/",
    "a\\b",
    "docs\x00",
)


def _build_tree(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("nested\n")
    (root / "README.md").write_text("# Sample\n")


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(app: object, params: dict[str, str]) -> Any:
    return SimpleNamespace(app=app, query_params=_FakeQuery(params), headers={})


async def _json(harness: InventoryHarness, route: Any, params: dict[str, str]) -> Any:
    response = await route(_request(harness.app, params))
    return response.status_code, json.loads(bytes(response.body))


# ── The translation itself ────────────────────────────────────


@pytest.mark.parametrize(("spelling", "expected"), EQUIVALENT_SPELLINGS)
def test_client_spellings_translate_to_the_contract_key(spelling: str, expected: str) -> None:
    assert canonical_inventory_path(spelling) == expected


@pytest.mark.parametrize("value", UNNAMEABLE)
def test_unnameable_paths_are_a_miss_not_an_exception(value: str) -> None:
    """A query string cannot be made to raise out of the translation."""

    assert canonical_inventory_path(value) is None


@pytest.mark.parametrize("spelling", [pair[0] for pair in EQUIVALENT_SPELLINGS])
def test_translation_output_is_accepted_by_the_contract(spelling: str) -> None:
    """The invariant a provider depends on: what comes out is already canonical.

    A provider implemented in another language validates its input against the
    same rule. If the translation could emit something that rule rejects, every
    provider would need its own repair step, which is the duplication this
    boundary exists to prevent.
    """

    canonical = canonical_inventory_path(spelling)
    assert canonical is not None
    require_canonical_inventory_path(canonical, "path", allow_root=True)


@pytest.mark.parametrize("spelling", [pair[0] for pair in EQUIVALENT_SPELLINGS])
def test_translation_is_idempotent(spelling: str) -> None:
    once = canonical_inventory_path(spelling)
    assert once is not None
    assert canonical_inventory_path(once) == once


def test_dot_is_not_a_canonical_path() -> None:
    """``.`` reads as canonical to ``PurePosixPath`` and is not.

    Its ``parts`` are empty and its ``as_posix()`` is itself, so the two
    structural checks both pass. The root's only key is ``""``; admitting a
    second spelling of it is what let ``.`` reach a provider as a path that
    matches nothing and report an empty tree instead of the whole one.
    """

    with pytest.raises(ValueError, match="canonical"):
        require_canonical_inventory_path(".", "path", allow_root=True)


# ── The same answer through the routes ────────────────────────


def test_equivalent_spellings_are_indistinguishable_at_the_tree_route(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    async def _run() -> list[Any]:
        async with inventory_harness(tmp_path) as harness:
            return [
                await _json(harness, server.api_tree, {"path": spelling})
                for spelling, _ in EQUIVALENT_SPELLINGS
                if _ == "docs"
            ]

    answers = asyncio.run(_run())
    statuses = {status for status, _ in answers}
    assert statuses == {200}
    assert all(body == answers[0][1] for _status, body in answers)


def test_equivalent_root_spellings_are_indistinguishable_at_the_rollup_route(
    tmp_path: Path,
) -> None:
    _build_tree(tmp_path)

    async def _run() -> list[Any]:
        async with inventory_harness(tmp_path) as harness:
            return [
                await _json(harness, server.api_rollup, {"path": spelling, "depth": "1"})
                for spelling in ("", ".", "./")
            ]

    answers = asyncio.run(_run())
    assert {status for status, _ in answers} == {200}
    # The root rollup names the root, not a shell with a null node: reporting
    # `node: null` for a settled index is the pending answer, and a client
    # renders it as a treemap that never arrives.
    assert answers[0][1]["node"] is not None
    assert all(body == answers[0][1] for _status, body in answers)


@pytest.mark.parametrize("value", UNNAMEABLE)
def test_unnameable_paths_are_refused_by_the_routes(tmp_path: Path, value: str) -> None:
    """A refusal, not a 500.

    Each of these is client-supplied, so an unhandled contract error is a crash
    reachable from a query string rather than a bad request.
    """

    _build_tree(tmp_path)

    async def _run() -> list[Any]:
        async with inventory_harness(tmp_path) as harness:
            return [
                await _json(harness, server.api_tree, {"path": value}),
                await _json(harness, server.api_rollup, {"path": value, "depth": "1"}),
            ]

    for status, body in asyncio.run(_run()):
        assert status == 404
        assert body == {"error": "Not found"}
