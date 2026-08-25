"""The filtered tree projection: what survives a filter, and what it adds up to.

These are the two questions the navigation panel used to answer from the rows it
had already mounted, which meant it kept every folder whose children had not
loaded and then removed them once expanding proved they held nothing. Answering
from the index instead is what this module tests, so the behaviour is pinned
without a browser.

Fixture trees are walked by the real inventory walker, so what these assert is
the same projection ``/api/tree`` and ``metab --walk --type`` return.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from metabrowser.events import FsEntry
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryHandle
from metabrowser.tree import build_filtered_inventory_tree
from metabrowser.tree_filter import (
    TreeFilter,
    cached_rollups,
    filtered_rollups,
    leaf_matches,
    matches_for,
    parse_size_floor,
    parse_types,
    type_matches,
)

_ROOT_MD = "README.md"


def _build_fixture(root: Path) -> None:
    """A tree where each dimension has something to say.

    ``logs/`` holds no Markdown at any depth, so a type filter must remove it
    outright. ``notes/deep/`` holds Markdown two levels down, so its ancestors
    have to survive on a match neither of them contains directly.
    """

    (root / _ROOT_MD).write_text("# Sample\n\nHello.\n")
    (root / "notes" / "deep").mkdir(parents=True)
    (root / "notes" / "deep" / "plan.md").write_text("# Plan\n")
    (root / "notes" / "deep" / "notes.min.js").write_text("var a=1;\n")
    (root / "logs").mkdir()
    (root / "logs" / "run.log").write_text("line one\nline two\n")
    (root / "logs" / "big.bin").write_text("0123456789abcdef" * 8)


def _walk(root: Path) -> PythonInventoryHandle:
    async def drive() -> PythonInventoryHandle:
        inv = PythonInventoryHandle()
        inv.start(root)
        await inv.wait_until_done(timeout=5.0)
        return inv

    return asyncio.run(drive())


def _filtered(
    inv: PythonInventoryHandle,
    root: Path,
    tree_filter: TreeFilter,
    *,
    depth: int = 20,
    subpath: str = "",
):
    return build_filtered_inventory_tree(
        entries=inv.entries(scope="all-known"),
        children_of=inv.children_of,
        parent_rel=subpath,
        max_depth=depth,
        root_abs=root,
        parent_ignored=False,
        tree_filter=tree_filter,
        now_sec=time.time(),
    )


def _by_path(nodes: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Flatten a tree into path -> node, so assertions can name a row."""

    flat: dict[str, dict[str, object]] = {}
    for node in nodes:
        flat[str(node["path"])] = node
        children = node.get("children")
        if isinstance(children, list):
            flat.update(_by_path(children))
    return flat


def test_the_filtered_path_reads_structure_from_the_index(tmp_path: Path) -> None:
    """Two reads, two reasons: the rollup needs every entry, the tree shape
    needs one subtree. Grouping the snapshot by parent answers the second with
    a full index pass, which is the cost ``PythonInventoryHandle.children_of`` exists to
    remove — 63 ms to 7 ms for a folder expansion at 117k entries.

    This branch and the child index landed on separate branches, and the
    natural way to resolve the conflict between them was to pick a side. This
    fails if the per-request grouping ever comes back."""

    source = (Path(__file__).resolve().parents[1] / "src/metabrowser/tree.py").read_text()
    assert "by_parent" not in source
    assert "children_of: Callable[[str], Sequence[Any]]" in source

    # And the filtered builder threads it through rather than rebuilding one.
    start = source.index("def build_filtered_inventory_tree(")
    block = source[start : source.index("\ndef ", start + 1)]
    assert "children_of=children_of" in block
    assert "entries" in block  # the rollup still needs the whole index

    # Behaviour, not only shape: a caller that hands over a child map covering
    # one subtree still gets that subtree, so nothing depends on the map being
    # complete.
    _build_fixture(tmp_path)
    inv = _walk(tmp_path)
    seen: list[str] = []

    def counting_children_of(parent: str):
        seen.append(parent)
        return inv.children_of(parent)

    result = build_filtered_inventory_tree(
        entries=inv.entries(scope="all-known"),
        children_of=counting_children_of,
        parent_rel="notes",
        max_depth=20,
        root_abs=tmp_path,
        parent_ignored=False,
        tree_filter=TreeFilter(types=(".md",)),
        now_sec=time.time(),
    )
    assert result.matched_files == 1
    # Only the requested subtree is walked, never the root.
    assert "" not in seen
    assert all(path == "notes" or path.startswith("notes/") for path in seen), seen


# ── The predicate ────────────────────────────────────────────────


def test_a_bare_token_matches_a_whole_filename() -> None:
    """The one convention the filter menu relies on to offer README and
    LICENSE next to .md and .txt: files that carry no extension at all would
    otherwise be unreachable."""

    assert type_matches("README", "", ("readme",))
    assert not type_matches("README.md", ".md", ("license",))


def test_a_compound_tail_matches_the_token_it_was_counted_under() -> None:
    """The menu tallies the index's compound tail, so reducing a row to its
    last dotted suffix would make a ".min.js" pick match nothing it offered."""

    assert type_matches("app.min.js", ".min.js", (".min.js",))
    assert not type_matches("app.js", ".js", (".min.js",))


def test_a_family_suffix_matches_its_members() -> None:
    """`.md` has to keep selecting `.runbook.md`; the registry decides which
    suffixes work that way, so an arbitrary tail match cannot sneak in."""

    assert type_matches("ops.runbook.md", ".runbook.md", (".md",))
    assert not type_matches("archive.tar.md5", ".tar.md5", (".md",))


def test_a_symlink_survives_only_while_nothing_file_specific_is_asked() -> None:
    """A link is a filesystem reference, not a member of a type or size
    bucket. The browser's predicate says the same, and the two have to agree
    because rows arriving live are still judged there."""

    link = FsEntry(
        path="link",
        parent="",
        name="link",
        type="symlink",
        ext="",
        kind="symlink",
        size=0,
        mtime_ns=1,
        mtime_hash="",
        active=False,
    )
    assert leaf_matches(link, TreeFilter(), 0.0)
    assert not leaf_matches(link, TreeFilter(types=(".md",)), 0.0)
    assert not leaf_matches(link, TreeFilter(min_size=1), 0.0)


def test_an_unparseable_size_or_type_means_no_constraint() -> None:
    """A client from another revision should see more, not a 400."""

    assert parse_size_floor("nonsense") == 0
    assert parse_size_floor("-5") == 0
    assert parse_types([" ", ".", ""]) == ()
    assert parse_types([".MD, .py", ".md"]) == (".md", ".py")


# ── Rollups ──────────────────────────────────────────────────────


def test_a_folder_totals_its_matches_not_its_contents(tmp_path: Path) -> None:
    """The chip under a filter answers "what of what I asked for is in here".
    ``notes`` holds a 7-byte plan.md and a larger .min.js; under a Markdown
    filter it is 1 file and 7 bytes."""

    _build_fixture(tmp_path)
    inv = _walk(tmp_path)

    result = _filtered(inv, tmp_path, TreeFilter(types=(".md",)))
    rows = _by_path(result.tree)

    assert rows["notes"]["total_files"] == 1
    assert rows["notes"]["total_size"] == len("# Plan\n")
    assert rows["notes/deep"]["total_size"] == len("# Plan\n")
    assert result.matched_files == 2
    assert result.matched_size == len("# Plan\n") + len("# Sample\n\nHello.\n")


def test_a_folder_with_no_match_anywhere_below_it_is_absent(tmp_path: Path) -> None:
    """The bug this projection exists for: ``logs`` was listed under a
    Markdown filter because its children had not loaded, then vanished the
    moment expanding it proved there was nothing to see."""

    _build_fixture(tmp_path)
    inv = _walk(tmp_path)

    rows = _by_path(_filtered(inv, tmp_path, TreeFilter(types=(".md",))).tree)
    assert "logs" not in rows
    assert "logs/run.log" not in rows


def test_a_folder_survives_on_a_match_below_the_depth_cap(tmp_path: Path) -> None:
    """Presence cannot be decided from the rows a response carries. At depth
    1 the client is sent ``notes`` and nothing under it, and ``notes`` is
    listed on the strength of a file two levels down."""

    _build_fixture(tmp_path)
    inv = _walk(tmp_path)

    result = _filtered(inv, tmp_path, TreeFilter(types=(".md",)), depth=1)
    rows = _by_path(result.tree)
    assert "notes" in rows
    assert rows["notes"]["children"] is None
    assert rows["notes"]["has_children"] is True
    assert "logs" not in rows
    # And the totals still describe the whole subtree, not the slice sent.
    assert rows["notes"]["total_files"] == 1


def test_a_filtered_folder_is_never_reported_empty(tmp_path: Path) -> None:
    """``empty`` dims a row and makes it refuse to expand. A folder listed
    under a filter has a match below it by construction, so the flag would be
    a contradiction — and a dimmed row that ignores every click is how the
    old behaviour read to a reader."""

    _build_fixture(tmp_path)
    inv = _walk(tmp_path)

    for node in _by_path(_filtered(inv, tmp_path, TreeFilter(types=(".md",))).tree).values():
        assert "empty" not in node


def test_a_size_floor_keeps_the_folders_holding_something_that_large(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    inv = _walk(tmp_path)

    rows = _by_path(_filtered(inv, tmp_path, TreeFilter(min_size=100)).tree)
    assert "logs" in rows
    assert "logs/big.bin" in rows
    assert "logs/run.log" not in rows
    assert "notes" not in rows


def test_an_unfiltered_projection_is_not_requested(tmp_path: Path) -> None:
    """``active`` is the single test the route branches on, so a default
    selection must never take the filtered path and start pruning."""

    assert not TreeFilter().active
    assert TreeFilter(types=(".md",)).active
    assert TreeFilter(include_ignored=False).active


# ── Recency and gitignore, over synthetic entries ───────────────
#
# Both dimensions need control over values the filesystem does not hand out
# on demand: an mtime far enough in the past, and a gitignored ancestor
# without a git repository in the fixture.


def _entry(
    path: str,
    *,
    kind: str = "file",
    size: int = 10,
    mtime_ns: int = 0,
    gitignored: bool = False,
) -> FsEntry:
    name = path.rsplit("/", 1)[-1]
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    dot = name.rfind(".")
    return FsEntry(
        path=path,
        parent=parent,
        name=name,
        type="dir" if kind == "dir" else kind,  # pyright: ignore[reportArgumentType]
        ext=name[dot:].lower() if dot > 0 else "",
        kind=kind,
        size=0 if kind == "dir" else size,
        mtime_ns=mtime_ns,
        mtime_hash="",
        active=False,
        gitignored=gitignored,
    )


def test_recency_bounds_which_leaves_count(tmp_path: Path) -> None:
    now = 1_000_000.0
    entries = [
        _entry("", kind="dir"),
        _entry("fresh", kind="dir"),
        _entry("fresh/new.md", mtime_ns=int((now - 10) * 1e9)),
        _entry("stale", kind="dir"),
        _entry("stale/old.md", mtime_ns=int((now - 90_000) * 1e9)),
    ]
    totals = filtered_rollups(entries, tree_filter=TreeFilter(recency_seconds=3600), now_sec=now)

    assert matches_for(totals, "fresh").files == 1
    assert matches_for(totals, "stale").files == 0
    assert matches_for(totals, "").files == 1


def test_excluding_gitignored_entries_takes_their_folders_with_them() -> None:
    """A folder listed only because of a gitignored file has to go when those
    are excluded, and the flag propagates to a subtree the walker stamped only
    at the top."""

    entries = [
        _entry("", kind="dir"),
        _entry("vendor", kind="dir", gitignored=True),
        _entry("vendor/nested", kind="dir"),
        _entry("vendor/nested/lib.md", size=11),
        _entry("src", kind="dir"),
        _entry("src/notes.md", size=7),
    ]

    shown = filtered_rollups(entries, tree_filter=TreeFilter(types=(".md",)), now_sec=0.0)
    assert matches_for(shown, "vendor").files == 1
    assert matches_for(shown, "").files == 2

    hidden = filtered_rollups(
        entries,
        tree_filter=TreeFilter(types=(".md",), include_ignored=False),
        now_sec=0.0,
    )
    assert matches_for(hidden, "vendor").files == 0
    assert matches_for(hidden, "").files == 1
    assert matches_for(hidden, "").size == 7


def test_the_rollup_memo_answers_the_same_question_only_once() -> None:
    """One filter change fans out into a tree request plus a subtree request
    per lazy stub the prefetch sweep warms, all needing the same rollup. The
    memo is keyed by index generation, so a write invalidates it."""

    entries = [_entry("", kind="dir"), _entry("a", kind="dir"), _entry("a/x.md", size=3)]
    tree_filter = TreeFilter(types=(".md",))
    first = cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=7)
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=7) is first
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=8) is not first


def test_the_memo_is_reset_through_the_one_test_door() -> None:
    """The key's uniqueness rests on revisions being process-wide, which is
    The Python provider owns this rather than the response cache. The reset makes that
    dependency something a test discharges instead of something that has to
    stay true by luck — and routing it through the server's hook means a test
    resets every response-shaped cache at once.

    Fails if the hook stops clearing this cache, which is the way the coupling
    would otherwise break: silently, in tests first."""

    from metabrowser import server
    from metabrowser.tree_filter import reset_rollup_cache_for_tests

    entries = [_entry("", kind="dir"), _entry("a", kind="dir"), _entry("a/x.md", size=3)]
    tree_filter = TreeFilter(types=(".md",))
    first = cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=1)
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=1) is first

    reset_rollup_cache_for_tests()
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=1) is not first

    warmed = cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=1)
    server.reset_response_caches_for_tests()
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=1) is not warmed


def test_a_recency_filter_is_never_memoized() -> None:
    """Its verdicts move with the clock, so a reused answer would be a
    different question's."""

    entries = [_entry("", kind="dir"), _entry("a", kind="dir"), _entry("a/x.md", mtime_ns=1)]
    tree_filter = TreeFilter(recency_seconds=3600)
    first = cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=7)
    assert cached_rollups(entries, tree_filter=tree_filter, now_sec=0.0, generation=7) is not first


def test_rollups_reach_every_ancestor_of_a_deep_match() -> None:
    """One fold per directory, deepest first, so a match at depth five is
    counted once by each of its five ancestors and not by anyone else."""

    entries = [
        _entry("", kind="dir"),
        _entry("a", kind="dir"),
        _entry("a/b", kind="dir"),
        _entry("a/b/c", kind="dir"),
        _entry("a/b/c/deep.md", size=5),
        _entry("other", kind="dir"),
    ]
    totals = filtered_rollups(entries, tree_filter=TreeFilter(types=(".md",)), now_sec=0.0)

    for path in ("", "a", "a/b", "a/b/c"):
        assert matches_for(totals, path).files == 1, path
        assert matches_for(totals, path).size == 5, path
    assert matches_for(totals, "other").files == 0
