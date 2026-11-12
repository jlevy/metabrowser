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
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.md").write_text("# beta\n")
    server._set_root_dir(tmp_path)
    payload = _inline_payload(asyncio.run(_index_html(tmp_path)))

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
    block = block[: block.index("async function loadTree(")]

    assert "_inlineTreeRows = null;" in block, "the inline rows must be consumed once"
    assert "_inlineTreeBaseline = painted ? rows : null;" in block
    assert "treeFilterKey()" in block, "a filtered view must not paint server-rendered rows"
    assert "filesPanelUsesRecentSource()" in block
    assert "if (!Array.isArray(rows) || rows.length === 0 || _lastTreeRender)" in block

    # And loadTree still owns the authoritative render that follows.
    load_tree = app[app.index("async function loadTree(") : app.index("function treeSummaryHtml")]
    assert "renderInitialTreeRows()" in load_tree
    assert "if (_inlineTreeBaseline || reconcileMountedRoot)" in load_tree
    init = app[app.index("// ── Init") :]
    assert init.index("renderInitialTreeRows();") < init.index(
        'document.addEventListener("DOMContentLoaded"'
    )
    assert "await fetch(treeUrl(" in load_tree


def test_the_fetched_tree_reconciles_an_inline_paint_in_place() -> None:
    """The fast shell paint must not be paid for with a second root rebuild."""
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    load_tree = app[app.index("async function loadTree(") : app.index("function treeSummaryHtml")]
    reconcile = app[
        app.index("function reconcileTreeContainer") : app.index("function treeTruncationNoteHtml")
    ]

    assert "reconcileMountedTree(data.tree" in load_tree
    assert "reconcileTreeNodes:root" in reconcile
    assert "nextNodes.slice(0, TREE_PAGE_SIZE)" in reconcile
    assert "deferredTreePageHtml(tail" in reconcile
    assert "subtreeCache.set(subtreeCacheKey(node.path), node.children)" in reconcile
    assert "panel.innerHTML =" not in reconcile


def test_discovery_completion_reconciles_the_mounted_tree_in_place() -> None:
    """A partial progressive tree must not become a second whole-region paint."""
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    progress_start = app.index("async function refreshTreeIfPendingTallies()")
    progress = app[
        progress_start : app.index("async function refreshIndexProgress", progress_start)
    ]
    diagnostic_start = app.index("async function refreshAfterPendingTallyDiagnostic")
    diagnostic = app[
        diagnostic_start : app.index(
            "async function reportPendingTallyDiagnostic", diagnostic_start
        )
    ]

    expected = "await loadTree({ reconcileMountedRoot: true });"
    assert expected in progress
    assert expected in diagnostic


def test_collapsed_inline_descendants_stay_cached_out_of_the_dom() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    render = app[app.index("function renderTreeNodes") : app.index("// ── Lazy subtree loading")]

    assert "Array.isArray(node.children) && expanded" in render
    assert "subtreeCache.set(subtreeCacheKey(node.path), node.children)" in render
    assert "data-tree-lazy-stub" in render


async def _landing_html(root: Path, view_path: str) -> str:
    async with inventory_harness(root) as harness:
        request = SimpleNamespace(app=harness.app)
        response = await server.index(cast(Any, request), view_path=view_path)
        return bytes(response.body).decode("utf-8")


def _node(nodes: object, path: str) -> dict[str, Any]:
    assert isinstance(nodes, list), nodes
    found = [node for node in nodes if isinstance(node, dict) and node.get("path") == path]
    assert found, f"{path} is not among {[n.get('path') for n in nodes if isinstance(n, dict)]}"
    return cast(dict[str, Any], found[0])


def _deep_tree(root: Path) -> None:
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "c.md").write_text("# c\n")
    (root / "a" / "b" / "d.md").write_text("# d\n")
    (root / "a" / "e.md").write_text("# e\n")
    (root / "z").mkdir()
    (root / "z" / "y.md").write_text("# y\n")
    (root / "README.md").write_text("# root\n")


def test_a_deep_landing_inlines_its_folders_expanded_and_names_its_row(tmp_path: Path) -> None:
    """The reveal that opened a deep landing's folders after the tree's first paint moved
    the tree with no input. The shell carries each folder's rows, expanded, so the first
    paint already shows the path's row and the page has no folder to fetch or open."""

    _deep_tree(tmp_path)
    server._set_root_dir(tmp_path)
    payload = _inline_payload(asyncio.run(_landing_html(tmp_path, "a/b/c.md")))

    assert payload is not None
    assert payload["path"] == "a/b/c.md"
    a = _node(payload["tree"], "a")
    assert a["expanded"] is True
    b = _node(a["children"], "a/b")
    assert b["expanded"] is True
    assert {node["path"] for node in b["children"]} == {"a/b/c.md", "a/b/d.md"}
    # Only the path's folders: a sibling folder stays collapsed and unloaded.
    z = _node(payload["tree"], "z")
    assert "expanded" not in z and z["children"] is None


def test_a_landing_on_a_folder_opens_its_parents_and_names_the_folder(tmp_path: Path) -> None:
    _deep_tree(tmp_path)
    server._set_root_dir(tmp_path)
    payload = _inline_payload(asyncio.run(_landing_html(tmp_path, "a/b/")))

    assert payload is not None
    assert payload["path"] == "a/b"
    b = _node(_node(payload["tree"], "a")["children"], "a/b")
    # The folder itself is the selection, not one of the folders to open.
    assert "expanded" not in b and b["children"] is None


def test_a_landing_the_inline_cannot_reach_names_no_row(tmp_path: Path) -> None:
    """A path whose folder is missing keeps the root rows and leaves the reveal to the page."""

    _deep_tree(tmp_path)
    server._set_root_dir(tmp_path)
    for view_path in ("missing/x.md", "a/missing/x.md", ""):
        payload = _inline_payload(asyncio.run(_landing_html(tmp_path, view_path)))
        assert payload is not None, view_path
        assert "path" not in payload, view_path
        _node(payload["tree"], "README.md")
    root_file = _inline_payload(asyncio.run(_landing_html(tmp_path, "README.md")))
    assert root_file is not None and root_file["path"] == "README.md"


def test_the_landing_inline_is_bounded() -> None:
    """Each folder's listing is capped like the root's, and only so many folders ride."""

    assert 1 <= server._INLINE_LANDING_DEPTH <= 16
    source = Path(server.__file__).read_text(encoding="utf-8")
    block = source[source.index("landing_parts = [") :]
    block = block[: block.index("initial_tree_block = (")]
    assert "min(len(landing_parts) - 1, _INLINE_LANDING_DEPTH)" in block
    assert block.count("max_rows=_INLINE_INITIAL_TREE_ROWS") == 1
    assert block.count("max_entries=_INLINE_INITIAL_TREE_ROWS") == 1


def test_the_first_tree_paint_selects_and_shows_a_landings_row() -> None:
    """The row the shell names is selected and scrolled into view by the same synchronous
    paint as the inline rows, so the reveal after it opens and scrolls nothing."""

    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    block = app[app.index("function renderInitialTreeRows()") :]
    block = block[: block.index("async function loadTree(")]
    assert "window.METABROWSER_INITIAL_TREE?.path" in block
    assert "setSelectedPath(landed)" in block
    assert 'scrollIntoView({\n      block: "nearest",' in block
    # A reveal the reader caused during the session (Quick Search, a link) is movement from
    # their input: it opens the folders without travel and shows the new selection, in one
    # frame. Nothing between the last folder opening and the scroll yields to the browser.
    reveal = app[app.index("async function revealInTree(") :]
    reveal = reveal[: reveal.index("\n}\n")]
    assert "setFolderExpanded(folder, true, { instant: true })" in reveal
    tail = reveal[reveal.rindex("setFolderExpanded(folder, true, { instant: true })") :]
    tail = tail[tail.index("\n") :]
    assert "await" not in tail, "the reveal yields a frame before it shows the selection"
    assert tail.index("setSelectedPath(path)") < tail.index(
        'target.scrollIntoView({ block: "nearest" })'
    )
    assert "scroll = true" in reveal, "a reveal shows its selection unless told not to"
    assert "scrollTop +=" not in reveal and "held" not in reveal
