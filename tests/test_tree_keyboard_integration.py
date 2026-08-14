"""Structural seams for accessible tree rendering and focus repair."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


def _app() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _index() -> str:
    class _FakeQuery:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeReq:
        def __init__(self) -> None:
            self.query_params = _FakeQuery()
            self.headers: dict[str, str] = {}

    response = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    return (
        response.body.decode()
        if isinstance(response.body, (bytes, bytearray))
        else str(response.body)
    )


def _function(source: str, name: str, length: int = 3000) -> str:
    start = source.index(f"function {name}")
    return source[start : start + length]


def test_tree_navigator_loads_after_registry_and_before_app() -> None:
    html = _index()
    assets = (
        "/static/keyboard_shortcuts.js",
        "/static/tree_keyboard_navigation.js",
        "/static/search_palette.js",
        "/static/app.js",
    )
    positions = [html.index(asset) for asset in assets]
    assert positions == sorted(positions)


def test_renderers_share_one_tree_semantics_helper() -> None:
    source = _app()
    assert "function treeRootHtml(content)" in source
    assert "function treeDomId(prefix, identity)" in source
    assert "function treeItemAttributes(options)" in source
    render = _function(source, "renderTreeNodes", 12_000)
    live = _function(source, "_buildRowHtml", 7000)
    for block in (render, live):
        assert "treeItemAttributes(" in block
        assert 'role="treeitem"' in source
        assert "aria-labelledby" in source
        assert "data-tree-position" in source
        assert "data-tree-set-size" in source
    assert 'role="group"' in render
    assert 'role="tree" aria-label="Files"' in source
    assert 'kind: "page"' in render


def test_tree_actions_are_shared_by_pointer_and_keyboard() -> None:
    source = _app()
    for name in (
        "setFolderExpanded",
        "toggleTreeFolder",
        "mountNextTreePage",
        "activateTreeRow",
    ):
        assert f"function {name}" in source
    click = source[source.index('treePane.addEventListener("click"') :][:1800]
    assert "treeKeyboard?.setAnchor" in click
    assert "activateTreeRow" in click
    init = _function(source, "initKeyboardInfrastructure", 2500)
    assert "MetabrowserTreeKeyboardNavigation.create" in init
    assert "activate: activateTreeRow" in init
    assert "setFolderExpanded: setFolderExpanded" in init


def test_every_tree_mutation_path_synchronizes_focus() -> None:
    source = _app()
    for name, length in (
        ("renderFilesFromTree", 1200),
        ("renderRecentFromBase", 1500),
        ("loadSubtree", 3500),
        ("applyTreeFilters", 5000),
        ("setSelectedPath", 1000),
        ("revealInTree", 2200),
        ("applyCellPatch", 6500),
        ("_removeRenderedRows", 2600),
        ("_removeRenderedRowsImmediately", 1500),
    ):
        body = _function(source, name, length)
        assert (
            "treeKeyboard" in body or "TreeSynchronize" in body or "synchronizeTreeNow" in body
        ), name
    assert "treeKeyboard?.prepareForMutation()" in source


def test_tree_synchronization_has_exactly_two_entry_points() -> None:
    """Every repair goes through the scheduler or its immediate twin.

    A bare treeKeyboard.synchronize() call outside those two helpers would
    bypass the coalescing window and reintroduce a per-event tree walk.
    """

    source = _app()
    # The two helpers are adjacent, so one slice covers both bodies exactly.
    helpers_start = source.index("function scheduleTreeSynchronize")
    helpers_end = source.index("\n}\n", source.index("function synchronizeTreeNow")) + len("\n}\n")
    helpers = source[helpers_start:helpers_end]
    assert "setTimeout(" in helpers
    assert "clearTimeout(" in helpers
    assert helpers.count("treeKeyboard?.synchronize(") == 2

    # The optional-call form is how every real call site reaches the navigator;
    # prose above the helpers mentions the method by name, so match the syntax.
    outside = source[:helpers_start] + source[helpers_end:]
    assert "?.synchronize(" not in outside


def test_live_inventory_paths_coalesce_their_tree_synchronization() -> None:
    """Event-driven mutations must not walk the tree once per event.

    fileStoreApplySnapshot replays a whole snapshot through applyCellPatch on
    every reconnect, so an immediate repair per entry would walk the painted
    tree thousands of times in one turn.
    """

    source = _app()
    for name, length in (
        ("applyCellPatch", 6500),
        ("_insertRowSorted", 4000),
        ("_synchronizeDeferredTreePage", 1600),
    ):
        body = _function(source, name, length)
        assert "scheduleTreeSynchronize(" in body, name
        assert "synchronizeTreeNow()" not in body, name

    filters = _function(source, "applyTreeFilters", 5000)
    assert "scheduleTreeSynchronize()" in filters
    assert "synchronizeTreeNow();" not in filters


def test_animated_removal_retains_its_focus_repair_snapshot() -> None:
    source = _app()
    remove = _function(source, "_removeRenderedRows", 2800)
    assert "var removalMutation = treeKeyboard?.prepareForMutation();" in remove
    assert "scheduleTreeSynchronize(removalMutation);" in remove


def test_recursive_expand_and_collapse_batch_tree_synchronization() -> None:
    """Both directions pay one repair for the whole walk, not one per folder."""

    source = _app()
    collapse = _function(source, "collapseAllDescendants", 700)
    assert "setFolderExpanded(folder, false, { synchronize: false });" in collapse
    assert "synchronizeTreeNow()" not in collapse

    expand = _function(source, "expandAllDescendants", 700)
    assert "setFolderExpanded(folder, true, { synchronize: false });" in expand
    assert "synchronizeTreeNow()" not in expand

    toggle = _function(source, "toggleTreeFolder", 1400)
    recursive_collapse = toggle[
        toggle.index("if (options.recursive && expanded)") : toggle.index(
            "} else if (options.recursive)"
        )
    ]
    assert "setFolderExpanded(row, false, { synchronize: false });" in recursive_collapse
    recursive_expand = toggle[
        toggle.index("} else if (options.recursive)") : toggle.index("} else {")
    ]
    assert "setFolderExpanded(row, true, { synchronize: false });" in recursive_expand
    assert toggle.count("synchronizeTreeNow();") == 1


def test_lazy_load_inside_a_batched_expand_stays_batched() -> None:
    """The deferred subtree repair honors the same opt-out as its caller."""

    source = _app()
    expanded = _function(source, "setFolderExpanded", 900)
    lazy = expanded[expanded.index("tree-lazy-placeholder") :]
    assert "options.synchronize !== false" in lazy


def test_tree_focus_ring_is_token_based_and_preview_has_no_tree_listener() -> None:
    css = proc_browser.STATIC_DIR.joinpath("styles.css").read_text()
    start = css.index(".tree-item:focus-visible")
    block = css[start : css.index("}", start)]
    assert "var(--link)" in block
    assert "outline" in block
    assert "#" not in block

    source = _app()
    assert 'previewElement.addEventListener("keydown"' not in source
    assert 'queryHtml("#preview-pane").addEventListener("keydown"' not in source
