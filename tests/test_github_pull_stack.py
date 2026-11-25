"""A stack's comparison: its identity, which files it keeps, and which layers change each.

The routes are ``tests/test_cli_github_stack_golden.py``'s, on the GitHub stand-in. These
are the rules on manifests of their own: a file two layers change, a file one layer renames
and another changes, a key that moves with every member's pins and with the list, and the
earlier comparisons a stack keeps admitted after it moves.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from metabrowser.builtin_plugins.github import pull_stack, pull_stack_retained
from metabrowser.builtin_plugins.github.pull_stack import StackPair, stack_digest, stack_scope
from metabrowser.builtin_plugins.github.pull_stack_retained import (
    MAX_RETAINED_STACK_PAIRS,
    retained_stack_pair,
)
from metabrowser.builtin_plugins.github.pull_stacks import NativeStack
from metabrowser.cache.paths import source_pulls_directory, source_stack_snapshots
from metabrowser.diff.format import ChangeSetManifest, EntrySide, FileChange, Totals
from metabrowser.home import ensure_home, ensure_private_directory
from metabrowser.view_routes import decode_safe_stack_route, format_stack_href

A, B, C, D = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)


def _change(file_id: str, old: str | None, new: str | None, added: int = 1) -> FileChange:
    kind = "added" if old is None else "deleted" if new is None else "modified"
    if old is not None and new is not None and old != new:
        kind = "renamed"
    return FileChange.model_construct(
        id=file_id,
        kind=kind,
        old=None if old is None else EntrySide.model_construct(path=old),
        new=None if new is None else EntrySide.model_construct(path=new),
        binary=False,
        additions=added,
        deletions=0,
    )


def _manifest(*changes: FileChange) -> ChangeSetManifest:
    return ChangeSetManifest.model_construct(
        files=changes,
        totals=Totals.model_construct(
            files=len(changes), additions=None, deletions=None, exact=False
        ),
        truncated=False,
    )


def test_the_key_moves_with_any_member_and_with_the_list() -> None:
    members = ((1, A, B), (2, B, C))
    digest = stack_digest(members)
    moved = {
        "a member's head": ((1, A, D), (2, B, C)),
        "a member's base": ((1, D, B), (2, B, C)),
        "the top's head": ((1, A, B), (2, B, D)),
        "a member added": ((1, A, B), (2, B, C), (3, C, D)),
        "a member gone": ((2, B, C),),
        "the order": ((2, B, C), (1, A, B)),
        "a renumbered member": ((1, A, B), (5, B, C)),
    }
    for why, other in moved.items():
        assert stack_digest(other) != digest, why
    assert stack_digest(((1, A, B), (2, B, C))) == digest
    pair = StackPair(7, A, C, digest, members, (True, True))
    # The restricted listing names itself apart from the two commits' own comparison.
    assert stack_scope(pair) == (f"stack-files-v1:{digest}",)


def test_only_the_layers_files_are_kept_and_each_names_its_layers() -> None:
    # Base to top: a file no layer changes (the base branch moved it, merged into a layer),
    # one two layers change, and one the bottom renames that the top then changes.
    combined = _manifest(
        _change("f1", "README.md", "README.md"),
        _change("f2", "src/app.py", "src/app.py", 3),
        _change("f3", "docs/old.md", "docs/new.md", 2),
    )
    members = (
        (
            10,
            1,
            {
                "src/app.py": "src/app.py",
                "docs/old.md": "docs/new.md",
                "docs/new.md": "docs/new.md",
            },
        ),
        (11, 2, {"src/app.py": "src/app.py", "docs/new.md": "docs/new.md"}),
    )
    kept = pull_stack._restricted(combined, members)
    assert [change.id for change in kept.files] == ["f2", "f3"]
    assert (kept.totals.files, kept.totals.additions, kept.totals.exact) == (2, 5, True)
    layers = pull_stack._layers(kept, members)
    assert [
        (
            entry["path"],
            [(layer["number"], layer["place"], layer["path"]) for layer in entry["layers"]],
        )
        for entry in layers
    ] == [
        ("src/app.py", [(10, 1, "src/app.py"), (11, 2, "src/app.py")]),
        ("docs/new.md", [(10, 1, "docs/new.md"), (11, 2, "docs/new.md")]),
    ]


def test_a_layer_names_a_file_by_its_own_path() -> None:
    # The bottom changes `lib.py` and the top renames it: the bottom's chip opens the path
    # its own Changes has, the old one.
    combined = _manifest(_change("f1", "lib.py", "core.py"))
    members = (
        (20, 1, {"lib.py": "lib.py"}),
        (21, 2, {"lib.py": "core.py", "core.py": "core.py"}),
    )
    [entry] = pull_stack._layers(pull_stack._restricted(combined, members), members)
    assert [(layer["number"], layer["path"]) for layer in entry["layers"]] == [
        (20, "lib.py"),
        (21, "core.py"),
    ]


def test_a_member_the_top_lacks_adds_no_file() -> None:
    combined = _manifest(_change("f1", "a.txt", "a.txt"), _change("f2", "b.txt", "b.txt"))
    # Only the members the top contains are read (`_member_paths`); a lacking one's own
    # file is in no member's paths here, so the comparison leaves it out.
    members = ((30, 1, {"a.txt": "a.txt"}),)
    kept = pull_stack._restricted(combined, members)
    assert [change.id for change in kept.files] == ["f1"]


@pytest.mark.parametrize(
    ("raw", "route"),
    [
        (b"/stack/7", (7, "", "")),
        (b"/stack/7/", (7, "", "")),
        (b"/stack/7/files", (7, "files", "")),
        (b"/stack/7/docs", (7, "docs", "")),
        (b"/stack/7/changes", (7, "changes", "")),
        (b"/stack/7/changes/docs/a%20b.md", (7, "changes", "docs/a b.md")),
        (b"/stack/7/files/docs/a.md", None),
        (b"/stack/7/docs/a.md", None),
        (b"/stack/7/guided", None),
        (b"/stack/7/conversation", None),
        (b"/stack/07", None),
        (b"/stack/7/changes/../x", None),
        (b"/stack/7/changes/a/", None),
        (b"/pull/7", None),
    ],
)
def test_the_stack_route_grammar(raw: bytes, route: Any) -> None:
    decoded = decode_safe_stack_route(raw)
    assert decoded == (None if route is None else tuple(route))
    if decoded is not None and (decoded.tab, decoded.file) != ("", "") and not raw.endswith(b"/"):
        assert format_stack_href(*decoded).encode() == raw


def test_format_stack_href_refuses_what_the_route_does_not_parse() -> None:
    for number, tab, file in (
        (0, "", ""),
        (7, "guided", ""),
        (7, "files", "a.md"),
        (7, "changes", "../a"),
    ):
        with pytest.raises(ValueError):
            format_stack_href(number, tab, file)


_SLUG = "github-com-octo-demo-01234567890"


def _published(home: Path, store: str = "store-1") -> Any:
    """What retention reads of a published source: its home, slug and store, in an
    application home (whose locks the write takes) with the directory its pull records,
    which a stack's comparison is drawn from, are kept in."""

    ensure_home(home)
    ensure_private_directory(home, source_pulls_directory(_SLUG))
    return SimpleNamespace(home=home, slug=_SLUG, store_id=store)


def _pair(head: str, number: int = 7) -> StackPair:
    members = ((1, A, B), (number, B, head))
    return StackPair(number, A, head, stack_digest(members), members, (True, True))


def test_a_drawn_stack_pair_stays_admitted_for_its_store_and_reader(tmp_path: Path) -> None:
    published = _published(tmp_path)
    first, moved = _pair(C), _pair(D)
    pull_stack_retained.retain_stack_pair(published, first, "gh:alice")
    pull_stack_retained.retain_stack_pair(published, moved, "gh:alice")

    # The earlier pair answers by its commits, with its members, as long as it is kept.
    assert retained_stack_pair(published, 7, "gh:alice", A, C, first.digest) == first
    assert retained_stack_pair(published, 7, None, A, C, None) == first
    assert retained_stack_pair(published, 7, "gh:alice", A, D, None) == moved
    # Another digest, reader, store, or stack admits nothing.
    assert retained_stack_pair(published, 7, "gh:alice", A, C, moved.digest) is None
    assert retained_stack_pair(published, 7, "gh:bob", A, C, None) is None
    assert retained_stack_pair(_published(tmp_path, "store-2"), 7, None, A, C, None) is None
    assert retained_stack_pair(published, 8, None, A, C, None) is None


def test_a_stack_keeps_its_last_eight_pairs_and_one_reader(tmp_path: Path) -> None:
    published = _published(tmp_path)
    heads = [f"{index:040x}" for index in range(1, MAX_RETAINED_STACK_PAIRS + 2)]
    for head in heads:
        pull_stack_retained.retain_stack_pair(published, _pair(head), "gh:alice")
    assert retained_stack_pair(published, 7, None, A, heads[0], None) is None
    for head in heads[1:]:
        assert retained_stack_pair(published, 7, None, A, head, None) == _pair(head)

    # Another reader's pair starts the history over.
    pull_stack_retained.retain_stack_pair(published, _pair(C), "gh:bob")
    assert retained_stack_pair(published, 7, None, A, heads[-1], None) is None
    assert retained_stack_pair(published, 7, "gh:bob", A, C, None) == _pair(C)


def test_an_unreadable_file_answers_unknown_and_a_malformed_one_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = _published(tmp_path)
    pull_stack_retained.retain_stack_pair(published, _pair(C), "gh:alice")
    with monkeypatch.context() as patch:

        def unreadable(*_args: object, **_kwargs: object) -> bytes:
            raise PermissionError("denied")

        patch.setattr(pull_stack_retained, "read_bytes_bounded", unreadable)
        assert retained_stack_pair(published, 7, None, A, C, None) == "unknown"

    path = tmp_path / source_stack_snapshots(_SLUG, 7)
    path.write_text('[{"store": "store-1"}]')
    assert retained_stack_pair(published, 7, None, A, C, None) is None


def test_a_pair_is_written_again_after_its_file_is_removed(tmp_path: Path) -> None:
    # A cache clear empties the pulls directory while a page stays open on its comparison.
    published = _published(tmp_path)
    drawn, moved = _pair(C), _pair(D)
    pull_stack_retained.retain_stack_pair(published, drawn, "gh:alice")
    path = tmp_path / source_stack_snapshots(_SLUG, 7)
    path.unlink()
    pull_stack_retained.retain_stack_pair(published, drawn, "gh:alice")
    assert path.exists()
    pull_stack_retained.retain_stack_pair(published, moved, "gh:alice")
    assert retained_stack_pair(published, 7, "gh:alice", A, C, drawn.digest) == drawn


def test_a_pair_is_written_under_the_source_alias_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = _published(tmp_path)
    held: list[str] = []
    real_lock = pull_stack_retained.source_alias_lock
    real_write = pull_stack_retained.write_private_file_atomic

    @contextmanager
    def lock(home: Path, slug: str) -> Generator[None]:
        with real_lock(home, slug):
            held.append(slug)
            try:
                yield
            finally:
                held.remove(slug)

    def write(home: Path, relative: str, data: bytes) -> None:
        assert held == [_SLUG], "written outside the source's alias lock"
        real_write(home, relative, data)

    monkeypatch.setattr(pull_stack_retained, "source_alias_lock", lock)
    monkeypatch.setattr(pull_stack_retained, "write_private_file_atomic", write)
    pull_stack_retained.retain_stack_pair(published, _pair(C), "gh:alice")
    assert retained_stack_pair(published, 7, "gh:alice", A, C, None) == _pair(C)


def test_a_fetch_that_ends_while_the_records_are_read_is_answered_as_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Member 1's refresh is running when the stack is read, and ends, without a usable
    # record, while the records are read; member 2 has none running. The running state is
    # taken before the records are read, so the answer cannot say member 1's fetch ended
    # while lacking the record it may have written.
    stack = NativeStack(number=7, base_ref="main", open=True, pulls=(1, 2))
    running = {1}

    def records(
        _repository: object, _published: object, found: NativeStack, _reader: object
    ) -> tuple[Any, ...]:
        running.clear()
        return tuple(
            pull_stack._Member(  # pyright: ignore[reportPrivateUsage]
                number=number, record=None, revision=None, title=None, state="open", moved=False
            )
            for number in found.pulls
        )

    monkeypatch.setattr(pull_stack, "_snapshot_stack", lambda _repository, _number: stack)
    monkeypatch.setattr(pull_stack, "_read_members", records)
    repository = cast(Any, SimpleNamespace(source="https://github.com/octo/demo"))
    envelope = asyncio.run(
        pull_stack.stack_envelope(repository, cast(Any, object()), 7, None, running.__contains__)
    )
    assert envelope["state"] == "pending"
    assert [(member["number"], member["fetching"]) for member in envelope["members"]] == [
        (1, True),
        (2, False),
    ]
