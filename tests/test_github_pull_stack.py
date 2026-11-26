"""A stack's comparison: its identity, which files it keeps, and which layers change each.

The routes are ``tests/test_cli_github_stack_golden.py``'s, on the GitHub stand-in. These
are the rules on manifests of their own: a file two layers change, a file one layer renames
and another changes, a key that moves with every member's pins and with the list, and the
earlier comparisons a stack keeps admitted after it moves, and what a member's move adds.
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
    retained_stack_digest,
    retained_stack_pair,
)
from metabrowser.builtin_plugins.github.pull_stacks import NativeStack
from metabrowser.cache.paths import source_pulls_directory, source_stack_snapshots
from metabrowser.diff.format import ChangeSetManifest, EntrySide, FileChange, Totals
from metabrowser.git.process import RepositoryStoreTarget
from metabrowser.home import ensure_home, ensure_private_directory
from metabrowser.view_routes import decode_safe_stack_route, format_stack_href
from tests.diff_fixture_repo import git
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import stand as stand

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


def test_only_a_comparison_that_is_its_plain_diff_is_measured() -> None:
    # The size measures the two commits' plain diff, so it is said only where the stack's
    # comparison is that diff whole, and the size and the file count describe one diff.
    plain = _manifest(_change("f1", "a.txt", "a.txt"), _change("f2", "b.txt", "b.txt"))
    every = ((30, 1, {"a.txt": "a.txt", "b.txt": "b.txt"}),)
    some = ((30, 1, {"a.txt": "a.txt"}),)
    assert pull_stack._sized(plain, pull_stack._restricted(plain, every))
    assert not pull_stack._sized(plain, pull_stack._restricted(plain, some))
    cut = plain.model_copy(update={"truncated": True})
    assert not pull_stack._sized(cut, pull_stack._restricted(cut, every))
    # Past its bound, measured to cost more than the listing it follows, none is measured.
    many = _manifest(
        *(
            _change(f"f{at}", f"f{at}.txt", f"f{at}.txt")
            for at in range(pull_stack.MAX_SIZED_STACK_FILES + 1)
        )
    )
    named = {f"f{at}.txt": f"f{at}.txt" for at in range(pull_stack.MAX_SIZED_STACK_FILES + 1)}
    assert not pull_stack._sized(many, pull_stack._restricted(many, ((30, 1, named),)))
    fewer = _manifest(*many.files[:-1])
    assert pull_stack._sized(fewer, pull_stack._restricted(fewer, ((30, 1, named),)))


@pytest.mark.parametrize(
    ("raw", "route"),
    [
        (b"/stack/7", (7, "", "")),
        (b"/stack/7/", (7, "", "")),
        (b"/stack/7/guided", (7, "guided", "")),
        # Its files are the header's Diff summary: there is no Files tab.
        (b"/stack/7/files", None),
        (b"/stack/7/docs", (7, "docs", "")),
        (b"/stack/7/changes", (7, "changes", "")),
        (b"/stack/7/changes/docs/a%20b.md", (7, "changes", "docs/a b.md")),
        (b"/stack/7/files/docs/a.md", None),
        (b"/stack/7/docs/a.md", None),
        (b"/stack/7/guided/docs/a.md", None),
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
        (7, "conversation", ""),
        (7, "guided", "a.md"),
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
    # The stack route's ``since`` finds a drawn pair by its digest alone, for its reader.
    assert retained_stack_digest(published, 7, "gh:alice", first.digest) == first
    assert retained_stack_digest(published, 7, "gh:bob", first.digest) is None
    assert retained_stack_digest(published, 7, "gh:alice", "0" * 32) is None


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


def test_a_stack_keeps_the_pair_its_page_draws_while_the_page_polls(tmp_path: Path) -> None:
    # A page drew the first pair and names it in each poll (`since`): every write keeps it,
    # and the oldest of the others goes, so it outlives the moves of a stack whose members'
    # records arrive one by one.
    published = _published(tmp_path)
    drawn = _pair(C)
    pull_stack_retained.retain_stack_pair(published, drawn, "gh:alice")
    heads = [f"{index:040x}" for index in range(1, 2 * MAX_RETAINED_STACK_PAIRS + 1)]
    for head in heads:
        pull_stack_retained.retain_stack_pair(published, _pair(head), "gh:alice", drawn.digest)
    assert retained_stack_pair(published, 7, "gh:alice", A, C, drawn.digest) == drawn
    assert retained_stack_digest(published, 7, "gh:alice", drawn.digest) == drawn
    kept = heads[-(MAX_RETAINED_STACK_PAIRS - 1) :]
    for head in heads:
        expected = _pair(head) if head in kept else None
        assert retained_stack_pair(published, 7, None, A, head, None) == expected
    # Once no page names it, it goes when it is the oldest, as any pair does.
    later = [f"{index:040x}" for index in range(100, 100 + MAX_RETAINED_STACK_PAIRS - 1)]
    for head in later:
        assert retained_stack_pair(published, 7, "gh:alice", A, C, drawn.digest) == drawn
        pull_stack_retained.retain_stack_pair(published, _pair(head), "gh:alice")
    assert retained_stack_pair(published, 7, "gh:alice", A, C, drawn.digest) is None

    # Another reader's pair starts the history over, whatever a page of the first draws.
    pull_stack_retained.retain_stack_pair(published, _pair(C), "gh:bob", drawn.digest)
    assert retained_stack_pair(published, 7, None, A, heads[-1], None) is None
    assert retained_stack_pair(published, 7, "gh:bob", A, C, None) == _pair(C)


def test_two_pages_on_one_stack_each_keep_the_pair_they_draw(tmp_path: Path) -> None:
    # Page one draws X and page two Y. At each move page one's poll answers the new pair
    # first, so the file already ends with it when page two's poll names Y: that poll writes
    # too, keeping Y, and a poll that names the pair the last write kept writes nothing.
    published = _published(tmp_path)
    first, second = _pair("1" * 40), _pair("2" * 40)
    pull_stack_retained.retain_stack_pair(published, first, "gh:alice")
    pull_stack_retained.retain_stack_pair(published, second, "gh:alice", first.digest)
    path = tmp_path / source_stack_snapshots(_SLUG, 7)
    for move in range(1, 2 * MAX_RETAINED_STACK_PAIRS + 1):
        pair = _pair(f"{100 + move:040x}")
        pull_stack_retained.retain_stack_pair(published, pair, "gh:alice", first.digest)
        pull_stack_retained.retain_stack_pair(published, pair, "gh:alice", second.digest)
        stamp = path.stat().st_mtime_ns
        pull_stack_retained.retain_stack_pair(published, pair, "gh:alice", second.digest)
        assert path.stat().st_mtime_ns == stamp, "a poll that names the same pair writes nothing"
        for drawn in (first, second):
            found = retained_stack_digest(published, 7, "gh:alice", drawn.digest)
            assert found == drawn, f"move {move}: the pair a polling page draws is kept"


def test_a_moved_member_counts_the_commits_the_drawn_comparison_did_not_show(
    tmp_path: Path,
) -> None:
    # 8's record lagged when the page drew the stack: it named a1, while 10, the top, already
    # held b1, 8's head on GitHub. Then 8 gains c1, and 10 is restacked on it.
    work = tmp_path / "repo"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")

    def commit(name: str) -> str:
        (work / "file.txt").write_text(f"{name}\n")
        git(work, "add", "file.txt")
        git(work, "commit", "-qm", name)
        return git(work, "rev-parse", "HEAD").decode().strip()

    base, a1, b1, t1 = (commit(name) for name in ("base", "a1", "b1", "t1"))
    # A record older still named a head 8's branch has since been rebased past.
    git(work, "checkout", "-q", base)
    a0 = commit("a0")
    git(work, "checkout", "-q", b1)
    c1, t2 = commit("c1"), commit("t2")
    drawn_members = ((8, base, a1), (10, b1, t1))
    moved_members = ((8, base, c1), (10, c1, t2))
    drawn = StackPair(70, base, t1, stack_digest(drawn_members), drawn_members, (True, True))
    moved = StackPair(70, base, t2, stack_digest(moved_members), moved_members, (True, True))
    target = RepositoryStoreTarget(work / ".git", "sha1")

    # b1 was in the comparison drawn, so 8 has one new commit, not two; 10's earlier head is
    # not in its new one's history, so it was rewritten, and no count says what is new.
    assert asyncio.run(pull_stack.stack_moves(target, drawn, moved)) == [
        {"number": 8, "commits": 1},
        {"number": 10, "commits": None},
    ]
    assert asyncio.run(pull_stack.stack_moves(target, drawn, drawn)) == []

    # 8's record catches up to b1, which the drawn top held, as does one that had named a0:
    # nothing is new to the reader, so each counts 0 rather than being called rewritten.
    caught_members = ((8, base, b1), (10, b1, t1))
    caught = StackPair(70, base, t1, stack_digest(caught_members), caught_members, (True, True))
    assert asyncio.run(pull_stack.stack_moves(target, drawn, caught)) == [
        {"number": 8, "commits": 0}
    ]
    older_members = ((8, base, a0), (10, b1, t1))
    older = StackPair(70, base, t1, stack_digest(older_members), older_members, (True, True))
    assert asyncio.run(pull_stack.stack_moves(target, older, caught)) == [
        {"number": 8, "commits": 0}
    ]
    # 10, the top, is reset to b1: the drawn top held its new head and its earlier one, so
    # its record did not catch up; its branch was rewritten, and no count says what is new.
    reset_members = ((8, base, b1), (10, b1, b1))
    reset = StackPair(70, base, b1, stack_digest(reset_members), reset_members, (True, True))
    assert asyncio.run(pull_stack.stack_moves(target, caught, reset)) == [
        {"number": 10, "commits": None}
    ]


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
                number=number,
                record=None,
                revision=None,
                title=None,
                state="open",
                author=None,
                avatar=None,
                moved=False,
                details=pull_stack._Details(),  # pyright: ignore[reportPrivateUsage]
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


def test_a_member_with_no_record_takes_its_author_from_the_cached_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A member's author ends its row on the stack's page as on the stack menu: its record's,
    # and with no record its cached list row's, as its title is and as the stacks route
    # reads it; none where neither holds the member.
    from metabrowser.builtin_plugins.github import pull_files_route, pull_list_route, pull_route
    from metabrowser.builtin_plugins.github.pull_list import PullListRow

    row = PullListRow(
        number=1,
        title="Count to two",
        state="open",
        draft=False,
        merged_at=None,
        author="octo",
        author_avatar_url="https://avatars.githubusercontent.com/u/1?v=4",
        created_at="2026-09-16T12:00:00Z",
        updated_at="2026-09-17T12:00:00Z",
        closed_at=None,
        base_ref="topic",
        head_ref="work",
        head_repository="octo/demo",
        labels=(),
    )
    monkeypatch.setattr(
        pull_route, "cached_pull_record", lambda _home, _slug, _n: (None, b"", None)
    )
    monkeypatch.setattr(
        pull_list_route, "cached_list_row", lambda _home, _slug, n: row if n == 1 else None
    )
    monkeypatch.setattr(pull_files_route, "known_head", lambda _home, _slug, _n: (None, None))
    place = cast(Any, SimpleNamespace(home=Path("home"), slug="demo"))
    members = pull_stack._read_members(  # pyright: ignore[reportPrivateUsage]
        place, place, NativeStack(number=7, base_ref="main", open=True, pulls=(1, 2)), None
    )
    assert [(member.title, member.author, member.avatar) for member in members] == [
        # The row's avatar as the catalog keeps it, sized for a row.
        ("Count to two", "octo", "https://avatars.githubusercontent.com/u/1?s=40"),
        (None, None, None),
    ]


def test_both_stack_routes_name_a_members_labels_by_one_rule() -> None:
    # A stack's page decides at first paint whether it has a labels row from the stacks
    # route's names, and keeps it from its own answer's, so the two must agree even when the
    # member's record and its list row disagree, as after a label change neither marks.
    from metabrowser.builtin_plugins.github.pull_list import PullListRow
    from metabrowser.builtin_plugins.github.pull_stacks_route import member_identity

    def label(name: str) -> Any:
        return SimpleNamespace(name=name, color="ededed", description=None)

    pull = SimpleNamespace(
        title="Count to two",
        author="octo",
        author_avatar_url=None,
        created_at=None,
        updated_at=None,
        labels=(label("stale"), label("kept")),
        commits=1,
        merged=False,
        merged_by=None,
        merged_by_avatar_url=None,
    )
    record = cast(Any, SimpleNamespace(pull=pull))

    def row(*labels: str) -> PullListRow:
        return PullListRow(
            number=1,
            title="Count to two",
            state="open",
            draft=False,
            merged_at=None,
            author="octo",
            author_avatar_url=None,
            created_at="2026-09-16T12:00:00Z",
            updated_at="2026-09-17T12:00:00Z",
            closed_at=None,
            base_ref="topic",
            head_ref="work",
            head_repository="octo/demo",
            labels=labels,
        )

    # The stacks route reads a record only for a member the list does not hold.
    for listed in (row(), row("kept"), row("kept", "new"), None):
        named = member_identity(record if listed is None else None, listed).labels
        drawn = pull_stack._details(record, listed).labels  # pyright: ignore[reportPrivateUsage]
        assert named == tuple(wire["name"] for wire in drawn)
        assert member_identity(record, listed).labels == named


def _one_layer(stand: _Stand) -> tuple[Any, StackPair]:
    """A stack of one layer in the stand-in's store: pull request 7 at the commit under its
    head, a pair no refresh has measured."""

    record = stand.refresh(7)
    assert record.comparison is not None
    base, head = record.comparison.base, stand.origin["fork_earlier"]
    members = ((7, base, head),)
    return stand.published, StackPair(7, base, head, stack_digest(members), members, (True,))


def _size_work(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The Git a size costs, as it runs: each listing of a diff and each measurement."""

    from metabrowser.diff.adapters.git import GitDiffSource
    from metabrowser.git import change_size as sizes

    work: list[str] = []
    listing = GitDiffSource.manifest
    measuring = sizes.measure_change

    async def listed(source: GitDiffSource, resolved: Any) -> Any:
        work.append("list")
        return await listing(source, resolved)

    async def measured(location: Any, left: str | None, right: str) -> Any:
        work.append("measure")
        return await measuring(location, left, right)

    monkeypatch.setattr(GitDiffSource, "manifest", listed)
    monkeypatch.setattr(sizes, "measure_change", measured)
    return work


def _layer_paths(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, *, whole: bool = True
) -> tuple[Any, StackPair]:
    """``_one_layer`` with its member's paths read once, so a read lists nothing for them:
    all of them, or none, which leaves the comparison restricted to fewer files than its
    plain diff."""

    published, pair = _one_layer(stand)
    paths = asyncio.run(pull_stack._member_paths(published, pair))
    assert all(named for _number, _place, named in paths)
    if not whole:
        paths = tuple((number, place, {}) for number, place, _named in paths)

    async def member_paths(_published: Any, _pair: StackPair) -> Any:
        return paths

    monkeypatch.setattr(pull_stack, "_member_paths", member_paths)
    return published, pair


def _read_in_a_new_process(published: Any, pair: StackPair) -> Any:
    """One read of the stack's comparison and its size as a process of its own makes it, as
    every ``metab --api`` read is: a loop of its own and no size held in memory, so only
    what is kept beside the store is left of the reads before."""

    from metabrowser.git import change_size as sizes

    sizes.KEPT_SIZES.clear()

    async def both() -> Any:
        await pull_stack.combined(published, pair)
        return await pull_stack._size(published, pair)

    return asyncio.run(both())


@pytest.mark.parametrize("outcome", ["measured", "too_costly", "restricted", "over_cap"])
def test_a_later_process_runs_no_git_for_a_size_asked_to_an_answer(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Whatever the answer, a size, none because the measurement ran out of time, or none
    because the comparison is not one that is measured, it is kept beside the store, so a
    process that starts with nothing in memory neither lists nor measures (A1 of review A
    on #867). The later process has time and room to measure, so one that asked again would
    show it."""

    from metabrowser.git import change_size as sizes

    published, pair = _layer_paths(stand, monkeypatch, whole=outcome != "restricted")
    work = _size_work(monkeypatch)
    cap = pull_stack.MAX_SIZED_STACK_FILES
    if outcome == "too_costly":
        monkeypatch.setattr(sizes, "MEASURE_TIMEOUT_S", 0.0)
    if outcome == "over_cap":
        monkeypatch.setattr(pull_stack, "MAX_SIZED_STACK_FILES", 0)
    first = _read_in_a_new_process(published, pair)
    assert work == (["list", "measure"] if outcome in ("measured", "too_costly") else ["list"])
    assert (first is not None) == (outcome == "measured")
    monkeypatch.setattr(sizes, "MEASURE_TIMEOUT_S", 15.0)
    monkeypatch.setattr(pull_stack, "MAX_SIZED_STACK_FILES", cap)
    work.clear()
    assert _read_in_a_new_process(published, pair) == first
    assert work == []


def test_a_comparison_kept_before_its_size_was_asked_is_asked_once(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A manifest a build that measured nothing kept has no size and no mark, so the read
    that finds it lists its plain diff once more and measures it (B6 of review B on #861),
    and no process after that does either."""

    published, pair = _layer_paths(stand, monkeypatch)
    work = _size_work(monkeypatch)
    settle = pull_stack._settle_size

    async def never(*_args: Any) -> None:
        return None

    monkeypatch.setattr(pull_stack, "_settle_size", never)
    assert _read_in_a_new_process(published, pair) is None
    assert work == ["list"]
    monkeypatch.setattr(pull_stack, "_settle_size", settle)
    work.clear()
    size = _read_in_a_new_process(published, pair)
    assert size is not None and size["diff_bytes"] > 0
    assert work == ["list", "measure"]
    work.clear()
    assert _read_in_a_new_process(published, pair) == size
    assert work == []


@pytest.mark.parametrize("ending", ["git_failed", "cancelled"])
def test_a_size_that_reached_no_answer_is_asked_again(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    """A measurement Git failed, or one whose read was cancelled, is no answer, so nothing
    is marked and the next read asks again (A4 of review A on #867), listing the plain diff
    once more since the comparison itself is kept."""

    from metabrowser.git import change_size as sizes
    from metabrowser.git.process import GitError

    published, pair = _layer_paths(stand, monkeypatch)
    work = _size_work(monkeypatch)
    measuring = sizes.change_size

    async def ended(_location: Any, _left: str, _right: str) -> Any:
        raise GitError("no answer") if ending == "git_failed" else asyncio.CancelledError

    monkeypatch.setattr(sizes, "change_size", ended)
    if ending == "git_failed":
        assert _read_in_a_new_process(published, pair) is None
    else:
        with pytest.raises(asyncio.CancelledError):
            _read_in_a_new_process(published, pair)
    assert work == ["list"]
    monkeypatch.setattr(sizes, "change_size", measuring)
    work.clear()
    assert _read_in_a_new_process(published, pair) is not None
    assert work == ["list", "measure"]
