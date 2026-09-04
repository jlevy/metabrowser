"""The shell carries the tree's first rows, so the reader does not wait for a fetch.

Time to first row was DOMContentLoaded plus the whole ``/api/tree`` request, and
during a walk that request is the slow one. Measured on a 300,000-file tree,
median of three cold loads: 1,604 ms to 242 ms. See
explorations/performance-loop/experiments/exp-004.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from metabrowser import server
from tests.inventory_harness import inventory_harness

STATIC_ROOT = Path(server.__file__).resolve().parent / "static"


async def _index_html(root: Path) -> str:
    async with inventory_harness(root) as harness:
        request = SimpleNamespace(app=harness.app)
        return bytes((await server.index(cast(Any, request))).body).decode("utf-8")


def _inline_payload(html: str) -> dict[str, object] | None:
    match = re.search(r"window\.METABROWSER_INITIAL_TREE=(\{.*?\});</script>", html)
    if match is None:
        return None
    parsed: dict[str, object] = json.loads(match.group(1))
    return parsed


def test_the_shell_carries_the_roots_first_rows(tmp_path: Path) -> None:
    previous_root = server._resolved_root_dir()
    try:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta.md").write_text("# beta\n")
        server._set_root_dir(tmp_path)
        payload = _inline_payload(asyncio.run(_index_html(tmp_path)))
    finally:
        server._set_root_dir(previous_root)

    assert payload is not None, "the shell no longer inlines the first rows"
    tree = payload["tree"]
    assert isinstance(tree, list) and tree, "inlined an empty tree"
    names = {str(node.get("name")) for node in tree if isinstance(node, dict)}
    assert {"alpha", "beta.md"} <= names


def test_the_inline_is_bounded_rather_than_the_whole_level() -> None:
    """It rides in the HTML, so every byte is on the critical path for every
    reader — including one whose root holds ten thousand entries."""
    assert server._INLINE_INITIAL_TREE_ROWS > 0
    assert server._INLINE_INITIAL_TREE_ROWS <= 500


def test_the_inline_rows_are_painted_once_and_only_unfiltered() -> None:
    """A filter is client state the server did not have when it rendered the
    page, so these rows do not describe it; and the fetch that follows is
    authoritative, so painting from the snapshot twice would be a regression
    rather than a shortcut."""
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    block = app[app.index("function renderInitialTreeRows()") :]
    block = block[: block.index("async function loadTree()")]

    assert "_inlineTreeRows = null;" in block, "the inline rows must be consumed once"
    assert "_inlineTreeBaseline = painted ? rows : null;" in block
    assert "treeFilterKey()" in block, "a filtered view must not paint server-rendered rows"
    assert "filesPanelUsesRecentSource()" in block
    assert "if (!Array.isArray(rows) || rows.length === 0 || _lastTreeRender)" in block

    # And loadTree still owns the authoritative render that follows.
    load_tree = app[app.index("async function loadTree()") : app.index("function treeSummaryHtml")]
    assert "renderInitialTreeRows()" in load_tree
    assert "if (_inlineTreeBaseline)" in load_tree
    init = app[app.index("// ── Init") :]
    assert init.index("renderInitialTreeRows();") < init.index(
        'document.addEventListener("DOMContentLoaded"'
    )
    assert "await fetch(treeUrl(" in load_tree


def test_the_fetched_tree_reconciles_an_inline_paint_in_place() -> None:
    """The fast shell paint must not be paid for with a second root rebuild."""
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    load_tree = app[app.index("async function loadTree()") : app.index("function treeSummaryHtml")]
    reconcile = app[
        app.index("function reconcileTreeContainer") : app.index("function treeTruncationNoteHtml")
    ]

    assert "reconcileInlineTree(data.tree" in load_tree
    assert "reconcileTreeNodes:root" in reconcile
    assert "nextNodes.slice(0, TREE_PAGE_SIZE)" in reconcile
    assert "deferredTreePageHtml(tail" in reconcile
    assert "subtreeCache.set(subtreeCacheKey(node.path), node.children)" in reconcile
    assert "panel.innerHTML =" not in reconcile


def test_collapsed_inline_descendants_stay_cached_out_of_the_dom() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    render = app[app.index("function renderTreeNodes") : app.index("// ── Lazy subtree loading")]

    assert "Array.isArray(node.children) && expanded" in render
    assert "subtreeCache.set(subtreeCacheKey(node.path), node.children)" in render
    assert "data-tree-lazy-stub" in render
