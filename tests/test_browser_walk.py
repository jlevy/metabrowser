"""Golden + safety tests for the walk debugging tool and the
symlink-containment guard on ``rewalk_subtree``.

The walk report drives the real inventory walker, so it doubles as a
regression guard for the phantom-subtree bug: a symlink (to a file, to
an in-tree dir, escaping the root, or pointing at an ancestor) must
appear as a *leaf* and never be followed. ``test_walk_report_golden``
pins the exact rendered shape; ``test_rewalk_subtree_refuses_*`` proves
the watcher's incremental path won't graft a symlink target's subtree
into the index either.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from metabrowser.inventory import InventoryIndex
from metabrowser.walk import (
    build_tree_envelope,
    collect_stream,
    dump_tree,
    render_report,
    walk_collect,
    walk_report,
)


def _strip_volatile(obj: Any) -> Any:
    """Drop mtime/generation fields so wire dumps compare deterministically
    (file sizes are fixed by the fixture; timestamps are not)."""

    volatile = {"mtime", "mtime_ns", "newest_mtime_ns", "generation", "mtime_hash"}
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in volatile}
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def _build_symlink_fixture(tmp_path: Path) -> Path:
    """Fixed-name fixture root with files, nested dirs, and four kinds
    of symlink. Returns the root (``tmp_path/fixture``) so the report's
    root-name line is deterministic."""

    root = tmp_path / "fixture"
    root.mkdir()
    (root / "a.txt").write_bytes(b"a" * 10)
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_bytes(b"b" * 20)
    (root / "sub" / "deep").mkdir()
    (root / "sub" / "deep" / "c.txt").write_bytes(b"c" * 30)
    (root / "extra").mkdir()
    (root / "extra" / "secret.txt").write_bytes(b"s" * 5)
    # Four symlinks, all with relative targets so readlink values are
    # stable across machines/tmp dirs:
    os.symlink("sub/b.txt", root / "link_to_file")  # in-tree file
    os.symlink("sub", root / "link_to_dir")  # in-tree dir — must stay a leaf
    os.symlink("../external", root / "link_escape")  # escapes the root
    os.symlink("..", root / "link_ancestor")  # points at the root's parent
    return root


_EXPECTED_ALL = """\
walk: fixture
status: done
counts: files=4 dirs=4 symlinks=4
totals: total_files=8 total_size=90

entries:
  . [dir] files=8 size=90
  a.txt [file] size=10
  extra [dir] files=1 size=5
  extra/secret.txt [file] size=5
  link_ancestor [symlink] -> ..
  link_escape [symlink] -> ../external
  link_to_dir [symlink] -> sub
  link_to_file [symlink] -> sub/b.txt
  sub [dir] files=2 size=50
  sub/b.txt [file] size=20
  sub/deep [dir] files=1 size=30
  sub/deep/c.txt [file] size=30
"""


def test_walk_report_golden(tmp_path: Path) -> None:
    """The full ``--detail all`` report matches the golden exactly.

    Crucially: every symlink renders as a ``[symlink]`` leaf and none
    produce descendant rows (no ``link_to_dir/...`` / ``link_escape/...``
    / ``link_ancestor/...`` paths). That absence is the phantom-subtree
    bug not happening.
    """

    root = _build_symlink_fixture(tmp_path)
    assert walk_report(root, detail="all") == _EXPECTED_ALL
    # No symlink was descended into.
    for link in ("link_to_dir", "link_escape", "link_ancestor", "link_to_file"):
        assert f"{link}/" not in _EXPECTED_ALL


def test_walk_report_detail_levels(tmp_path: Path) -> None:
    """``summary`` is the header block; ``dirs`` drops file/symlink
    rows but keeps directories."""

    root = _build_symlink_fixture(tmp_path)

    summary = walk_report(root, detail="summary")
    assert summary.splitlines() == [
        "walk: fixture",
        "status: done",
        "counts: files=4 dirs=4 symlinks=4",
        "totals: total_files=8 total_size=90",
    ]

    dirs = walk_report(root, detail="dirs")
    assert "[symlink]" not in dirs
    assert "a.txt" not in dirs
    assert "sub [dir] files=2 size=50" in dirs
    assert "sub/deep [dir] files=1 size=30" in dirs


def test_walk_counts_symlinks_separately(tmp_path: Path) -> None:
    """``WalkResult`` separates real files from symlinks even though
    the walker folds symlinks into its file-aggregate totals."""

    root = _build_symlink_fixture(tmp_path)
    result = asyncio.run(walk_collect(root))
    assert result.file_count == 4
    assert result.dir_count == 4
    assert result.symlink_count == 4
    # Every symlink row is a leaf with no children represented.
    symlink_paths = {r.path for r in result.rows if r.is_symlink}
    assert symlink_paths == {
        "link_to_file",
        "link_to_dir",
        "link_escape",
        "link_ancestor",
    }
    # render is stable regardless of detail validity guard
    assert render_report(result, detail="summary").startswith("walk: fixture")


# ── machine-readable dumps (the nav-panel wire data) ──────────────


_EXPECTED_TREE = [
    {
        "name": "extra",
        "path": "extra",
        "type": "dir",
        "total_files": 1,
        "total_size": 5,
        "has_children": True,
        "children": [{"name": "secret.txt", "path": "extra/secret.txt", "type": "file", "size": 5}],
    },
    {
        "name": "sub",
        "path": "sub",
        "type": "dir",
        "total_files": 2,
        "total_size": 50,
        "has_children": True,
        "children": [
            {
                "name": "deep",
                "path": "sub/deep",
                "type": "dir",
                "total_files": 1,
                "total_size": 30,
                "has_children": True,
                "children": [
                    {"name": "c.txt", "path": "sub/deep/c.txt", "type": "file", "size": 30}
                ],
            },
            {"name": "b.txt", "path": "sub/b.txt", "type": "file", "size": 20},
        ],
    },
    {"name": "a.txt", "path": "a.txt", "type": "file", "size": 10},
    # The four symlinks: leaf file-entries, never expanded into subtrees.
    {"name": "link_ancestor", "path": "link_ancestor", "type": "file", "size": 2},
    {"name": "link_escape", "path": "link_escape", "type": "file", "size": 11},
    {"name": "link_to_dir", "path": "link_to_dir", "type": "file", "size": 3},
    {"name": "link_to_file", "path": "link_to_file", "type": "file", "size": 9},
]


def test_dump_tree_envelope_golden(tmp_path: Path) -> None:
    """The all-at-once ``/api/tree`` envelope — exactly what the nav
    panel fetches — matches the golden, with every symlink a leaf and
    no node that re-includes the served root."""

    root = _build_symlink_fixture(tmp_path)
    envelope = asyncio.run(build_tree_envelope(root, max_depth=20))
    normalized = _strip_volatile(envelope)

    assert normalized["root"] == str(root)
    assert normalized["tally_cache_status"] == "done"
    assert normalized["tree"] == _EXPECTED_TREE

    # Phantom-subtree guard: no node anywhere is named "fixture" (the
    # served root's own name) and no symlink produced descendants.
    def _walk(nodes: list[dict[str, Any]]):
        for n in nodes:
            yield n
            for c in n.get("children") or []:
                yield from _walk([c])

    names = [n["name"] for n in _walk(normalized["tree"])]
    assert "fixture" not in names
    paths = [n["path"] for n in _walk(normalized["tree"])]
    assert not any(p.startswith(("link_to_dir/", "link_escape/", "link_ancestor/")) for p in paths)


def test_dump_tree_json_and_yaml_round_trip(tmp_path: Path) -> None:
    """``dump_tree`` emits parseable JSON and YAML with identical
    (normalized) content."""

    root = _build_symlink_fixture(tmp_path)
    as_json = _strip_volatile(_json.loads(dump_tree(root, fmt="json")))
    as_yaml = _strip_volatile(yaml.safe_load(dump_tree(root, fmt="yaml")))
    assert as_json["tree"] == _EXPECTED_TREE
    assert as_yaml == as_json


def test_stream_records(tmp_path: Path) -> None:
    """The streaming surface yields the root record first (named after
    the served dir), every symlink as a leaf file record, and never a
    record describing a symlink's contents."""

    root = _build_symlink_fixture(tmp_path)
    records = [_strip_volatile(r) for r in collect_stream(root)]

    first = records[0]
    assert first["path"] == ""
    assert first["name"] == "fixture"
    assert first["type"] == "dir"

    # Symlinks appear exactly once each, as file records, no descendants.
    by_path: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_path.setdefault(r["path"], []).append(r)
    for link in ("link_to_file", "link_to_dir", "link_escape", "link_ancestor"):
        assert link in by_path, f"missing {link}"
        assert all(r["type"] == "file" for r in by_path[link])
    assert not any(
        p.startswith(("link_to_dir/", "link_escape/", "link_ancestor/", "link_to_file/"))
        for p in by_path
    )


# ── rewalk_subtree containment guard ──────────────────────────────


async def _booted_inventory(root: Path) -> InventoryIndex:
    inv = InventoryIndex()
    inv.start(root)
    await inv.wait_until_done(timeout=10)
    return inv


def test_rewalk_subtree_refuses_symlinked_dir(tmp_path: Path) -> None:
    """A watch event on an in-tree symlinked directory must not graft
    the target's subtree under the link path."""

    root = _build_symlink_fixture(tmp_path)

    async def _run() -> dict[str, int]:
        inv = await _booted_inventory(root)
        before = len(inv._entries)
        await inv.rewalk_subtree("link_to_dir")
        # No path under the link should have been created — i.e. the
        # link target's contents ("b.txt", "deep/…") are not rebased
        # under "link_to_dir/".
        grafted = [p for p in inv._entries if p.startswith("link_to_dir/")]
        return {"before": before, "after": len(inv._entries), "grafted": len(grafted)}

    res = asyncio.run(_run())
    assert res["grafted"] == 0
    assert res["after"] == res["before"]


class _ListHandler(logging.Handler):
    """Capture records directly off a named logger, independent of
    propagation (the ``metabrowser`` logger sets ``propagate=False``
    once the server module loads, which defeats pytest's ``caplog``)."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_rewalk_subtree_refuses_escaping_and_ancestor_symlinks(tmp_path: Path) -> None:
    """Links that resolve outside the served root (an escaping link and
    one pointing at the root's parent) are refused with a warning, and
    add nothing to the index."""

    root = _build_symlink_fixture(tmp_path)
    handler = _ListHandler()
    inv_logger = logging.getLogger("metabrowser.inventory")

    async def _run() -> int:
        inv = await _booted_inventory(root)
        before = len(inv._entries)
        inv_logger.addHandler(handler)
        try:
            await inv.rewalk_subtree("link_escape")
            await inv.rewalk_subtree("link_ancestor")
        finally:
            inv_logger.removeHandler(handler)
        after = len(inv._entries)
        # Nothing grafted under either link.
        grafted = [p for p in inv._entries if p.startswith(("link_escape/", "link_ancestor/"))]
        assert grafted == []
        return after - before

    delta = asyncio.run(_run())
    assert delta == 0
    assert any("refusing rewalk" in m for m in handler.messages), handler.messages
