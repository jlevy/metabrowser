"""Structural tests for the Recent view and its DOM contract.

Follows the test_browser_v2.py convention: parse the static
HTML/JS/CSS sources and assert structural invariants. End-to-end
testable without a browser.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _read_styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text()


# ── Tab strip in index template ────────────────────────────────


def _render_index_html() -> str:
    """Render the / route once and return the HTML body."""

    class _FakeQuery:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeReq:
        def __init__(self) -> None:
            self.query_params = _FakeQuery()
            self.headers: dict[str, str] = {}

    resp = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    return resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else str(resp.body)


def test_index_template_renders_files_and_recent_tab_bar() -> None:
    html = _render_index_html()
    assert 'class="tab-bar nav-tab-bar"' in html
    assert 'data-tab="files"' in html
    assert 'data-tab="recent"' in html
    # Aria attributes for screen readers.
    assert 'role="tablist"' in html
    assert 'aria-selected="true"' in html


def test_index_template_renders_tab_files_and_tab_recent_panels() -> None:
    html = _render_index_html()
    assert 'id="tab-files"' in html
    assert 'id="tab-recent"' in html
    # Files initially visible; Recent hidden.
    assert 'data-tab-content="files"' in html
    assert 'data-tab-content="recent"' in html
    # Recent starts hidden.
    assert 'id="tab-recent" data-tab-content="recent" style="display:none;"' in html


def test_index_template_renders_index_progress_footer() -> None:
    html = _render_index_html()
    assert 'id="index-progress"' in html
    assert 'class="index-progress-spinner"' in html
    assert 'aria-live="polite"' in html


def test_index_template_versions_core_static_assets() -> None:
    html = _render_index_html()
    assert 'href="/static/styles.css?v=' in html
    assert 'src="/static/plugin_sdk.js?v=' in html
    assert 'src="/static/icons.js?v=' in html
    assert 'src="/static/tree_expansion.js?v=' in html
    assert 'src="/static/app.js?v=' in html
    assert html.index("/static/tree_expansion.js") < html.index("/static/app.js")


# ── DOM contract: every JS-referenced id present in HTML ───────


def test_dom_contract_all_referenced_ids_exist_in_rendered_html() -> None:
    html = _render_index_html()
    referenced_ids = {
        "index-progress",
        "tree-content",
        "tab-files",
        "tab-recent",
        "tree-pane",
        "tree-resize",
        "preview-pane",
    }
    for ident in referenced_ids:
        assert f'id="{ident}"' in html, f"missing JS-referenced id={ident!r} in rendered HTML"


def test_dom_contract_tab_panels_are_direct_children_of_tree_content() -> None:
    """A refactor that nests #tab-files inside another element
    would silently break selectors like '#tab-files > .tree-item'.
    Catch it via structural assertion."""

    html = _render_index_html()
    # The Files panel must immediately follow the opening
    # #tree-content tag (whitespace allowed).
    tree_content_open = html.index('id="tree-content"')
    after_open = html[tree_content_open : tree_content_open + 200]
    # tab-files comes before tab-recent and both before any
    # other top-level child.
    assert after_open.index('id="tab-files"') < after_open.index('id="tab-recent"')


# ── Client wiring ──────────────────────────────────────────────


def test_init_nav_tabs_function_exists_and_wires_tab_bar() -> None:
    js = _read_app_js()
    assert "function initNavTabs()" in js
    fn_start = js.index("function initNavTabs()")
    fn_block = js[fn_start : fn_start + 1500]
    assert "nav-tab-bar" in fn_block
    assert "data-tab-content" in fn_block


def test_load_recent_fetches_api_recent_for_full_window_coverage() -> None:
    """Recent is hybrid: chip change fetches
    ``/api/recent`` so the panel covers files outside the SSE
    ``root-depth-2`` scope (24h/7d/30d/all used to silently
    truncate to whatever happened to be in FileStore). Live
    fs.change ops still flow through the local re-cluster path
    via the ``recentBaseEntries`` overlay."""

    js = _read_app_js()
    fn_start = js.index("function loadRecent(windowKey)")
    fn_block = js[fn_start : fn_start + 1500]
    # The chip-change path delegates to fetchRecent.
    assert "fetchRecent(windowKey)" in fn_block
    # fetchRecent is the function that hits the endpoint.
    fr_start = js.index("function fetchRecent(windowKey)")
    fr_block = js[fr_start : fr_start + 2500]
    assert '"/api/recent?window=' in fr_block
    # Aborts an in-flight chip fetch so a fast double-click doesn't
    # race two responses against each other.
    assert "AbortController" in fr_block


def test_recent_entries_from_base_filters_window_ext_prefix() -> None:
    """Recent reads from the chip-fetched ``recentBaseEntries``
    map, not from the SSE-scoped FileStore. Live
    fs.change ops in the active window are merged in via
    ``recentBaseApplyOp``."""

    js = _read_app_js()
    fn_start = js.index("function recentEntriesFromBase(opts)")
    fn_block = js[fn_start : fn_start + 2500]
    assert "recentBaseEntries.forEach" in fn_block
    assert "_RECENT_WINDOW_SECONDS" in fn_block
    assert "extFilter" in fn_block
    assert "prefixFilter" in fn_block
    # newest-first sort on recent-flat (mtime in seconds, not ns).
    assert "(b.mtime || 0) - (a.mtime || 0)" in fn_block


def test_recent_base_apply_op_handles_upsert_remove_move() -> None:
    """fs.change ops mutate ``recentBaseEntries`` in place so
    files written after the chip fetch show up live without a
    /api/recent refetch."""

    js = _read_app_js()
    fn_start = js.index("function recentBaseApplyOp(op)")
    fn_block = js[fn_start : fn_start + 2500]
    assert 'op.op === "upsert"' in fn_block
    assert 'op.op === "remove"' in fn_block
    assert 'op.op === "move"' in fn_block
    # Out-of-window upserts are dropped; the active-window cutoff
    # is checked against ``_RECENT_WINDOW_SECONDS[currentRecentWindow]``.
    assert "_RECENT_WINDOW_SECONDS[currentRecentWindow]" in fn_block


def test_file_store_apply_change_mirrors_into_recent_overlay() -> None:
    """The Recent overlay only stays in sync if every fs.change op
    fans out to ``recentBaseApplyOp``. Tests guard the wiring."""

    js = _read_app_js()
    fn_start = js.index("function fileStoreApplyChange(ops)")
    fn_block = js[fn_start : fn_start + 1500]
    assert "recentBaseApplyOp(op)" in fn_block


def test_cluster_recent_tree_js_pure_function_present() -> None:
    """``clusterRecentTreeJs`` is the authoritative implementation
    of Recent clustering — single-dir compaction + cluster-collapse
    are presentation rules and live in the SPA. The server filters
    leaves and resolves gitignore but does not cluster."""

    js = _read_app_js()
    assert "function clusterRecentTreeJs(files, nowSec, pct)" in js
    assert "function _agesWithinPctJs(ages, pct)" in js


def test_recent_recompute_is_debounced() -> None:
    """A burst of fs.change ops shouldn't render-thrash. Cap is
    pinned via RECENT_RECLUSTER_DEBOUNCE_MS (read from
    window.METABROWSER_SETTINGS, default 100)."""

    js = _read_app_js()
    assert "RECENT_RECLUSTER_DEBOUNCE_MS" in js
    fn_start = js.index("function _scheduleRecentRecompute()")
    fn_block = js[fn_start : fn_start + 1000]
    assert "setTimeout" in fn_block
    # Debounce: skip if a recompute is already pending.
    assert "_recentRecomputeHandle" in fn_block


def test_recent_recompute_called_from_fs_change_handler() -> None:
    """Every fs.change op triggers a (debounced) Recent re-cluster."""

    js = _read_app_js()
    fn_start = js.index("function _createInventoryEventSource()")
    fn_block = js[fn_start : fn_start + 3000]
    assert "_scheduleRecentRecompute()" in fn_block


def test_render_recent_list_uses_dir_metric_count_mode() -> None:
    js = _read_app_js()
    fn_start = js.index("function renderRecentList(data)")
    fn_block = js[fn_start : fn_start + 1200]
    # isRoot=true so Recent uses the same viewport-bounded expansion
    # planner as the Files panel.
    assert "renderTreeNodes(tree, true, { dirMetric: TREE_DIR_METRIC_COUNT })" in fn_block


def test_render_tree_nodes_dir_metric_switches_chip_html() -> None:
    """renderTreeNodes keeps the dir chip display configurable:
    Files defaults to size, Recent opts into count."""

    js = _read_app_js()
    fn_start = js.index("function renderTreeNodes(nodes, isRoot, options)")
    fn_block = js[fn_start : fn_start + 2500]
    assert "options.dirMetric" in js
    assert "TREE_DIR_METRIC_COUNT" in js
    assert "TREE_DIR_METRIC_SIZE" in js
    assert "treeDirChipHtml(node.total_files, node.total_size, options)" in fn_block
    chip_start = js.index("function treeDirChipHtml(totalFiles, totalSize, options)")
    chip_block = js[chip_start : chip_start + 700]
    assert "countHtml(totalFiles" in chip_block
    assert "sizeHtml(totalSize" in chip_block


def test_window_chips_read_from_settings_with_fallback() -> None:
    """RECENT_WINDOWS now reads from window.METABROWSER_SETTINGS
    (injected by the index template via client_settings_dict).
    The fallback literal preserves behaviour when settings are
    missing (e.g. unit tests that load app.js without the
    template)."""

    js = _read_app_js()
    assert "_METABROWSER_SETTINGS.RECENT_WINDOWS" in js
    assert '["1h", "24h", "7d", "30d", "all"]' in js
    assert "var currentRecentWindow" in js


def test_window_chip_click_dedups_against_current_window() -> None:
    """Picking the same chip again is a no-op so a stray click
    doesn't trigger an extra fetch."""

    js = _read_app_js()
    # Anchor on the click-delegate registration; the closer
    # 'closest("[data-action=' anchor finds the chip handler
    # body specifically (the other "recent-window" occurrence is
    # in renderRecentControls).
    handler_start = js.index("closest(\"[data-action='recent-window']\")")
    handler_block = js[handler_start : handler_start + 600]
    assert "if (w === currentRecentWindow)" in handler_block


def test_load_recent_locks_window_synchronously_first() -> None:
    """The chip-click handler dedups against currentRecentWindow.
    The window assignment must come before any DOM mutation AND
    before fetchRecent kicks off so a fast user double-click
    doesn't race two fetches that resolve in the wrong order."""

    js = _read_app_js()
    fn_start = js.index("function loadRecent(windowKey)")
    fn_block = js[fn_start : fn_start + 1500]
    assign_idx = fn_block.index("currentRecentWindow = windowKey;")
    # ensureRecentScaffold is the first DOM-touching call.
    scaffold_idx = fn_block.index("ensureRecentScaffold()")
    fetch_idx = fn_block.index("fetchRecent(windowKey)")
    assert assign_idx < scaffold_idx
    assert assign_idx < fetch_idx


# ── Cross-panel selection ──────────────────────────────────────


def test_set_selected_path_helper_exists_and_is_used() -> None:
    js = _read_app_js()
    assert "function setSelectedPath(path)" in js
    # Replaced inline mutation in tree-pane click handler and
    # revealInTree.
    fn_start = js.index("function setSelectedPath(path)")
    fn_block = js[fn_start : fn_start + 800]
    assert 'queryHtmlAll(".tree-item.selected")' in fn_block
    assert 'queryHtmlAll(".tree-item")' in fn_block


def test_set_selected_path_clears_when_path_falsy() -> None:
    js = _read_app_js()
    fn_start = js.index("function setSelectedPath(path)")
    fn_block = js[fn_start : fn_start + 800]
    assert "if (!path)" in fn_block


def test_set_selected_path_called_from_click_handler_and_reveal() -> None:
    """Both the tree-pane click delegate's 'select' branch AND
    revealInTree should funnel through setSelectedPath; otherwise
    cross-panel selection breaks."""

    js = _read_app_js()
    # The select-branch use is right after the action === "select".
    select_branch = js.index('action === "select"')
    select_block = js[select_branch : select_branch + 500]
    assert "setSelectedPath(item.dataset.path)" in select_block

    # revealInTree uses it.
    reveal_start = js.index("async function revealInTree(path)")
    reveal_block = js[reveal_start : reveal_start + 1500]
    assert "setSelectedPath(path)" in reveal_block


# ── Auto-expand behavior ───────────────────────────────────────


def test_render_tree_nodes_auto_expand_uses_bounded_path_set() -> None:
    """Default expansion comes from the viewport-bounded planner."""

    js = _read_app_js()
    fn_start = js.index("function renderTreeNodes(nodes, isRoot, options)")
    fn_block = js[fn_start : fn_start + 2500]
    assert "defaultExpandedPaths" in fn_block
    assert "defaultExpandedPaths.has(node.path)" in fn_block


def test_render_tree_nodes_explicit_expanded_overrides_default() -> None:
    """Recent panel sets node.expanded explicitly to drive
    cluster-collapse; the explicit boolean must win over the
    default isRoot/isSpecial rule."""

    js = _read_app_js()
    fn_start = js.index("function renderTreeNodes(nodes, isRoot, options)")
    fn_block = js[fn_start : fn_start + 2500]
    assert 'typeof node.expanded === "boolean" ? node.expanded : defaultExpanded' in fn_block


# ── CSS ────────────────────────────────────────────────────────


def test_styles_css_promotes_tab_active_color_to_root() -> None:
    css = _read_styles_css()
    assert "--tab-active-color:" in css
    assert "--tab-active-border-width:" in css


def test_styles_css_keeps_tab_padding_compact() -> None:
    css = _read_styles_css()
    assert "--file-tab-padding-y: 4px;" in css


def test_styles_css_defines_recent_controls_and_chip() -> None:
    css = _read_styles_css()
    assert ".recent-controls {" in css
    assert ".recent-chip {" in css
    assert ".recent-chip.active {" in css
    assert ".recent-empty {" in css
    assert ".tab-bar.nav-tab-bar {" in css


def test_styles_css_recent_chip_active_uses_tab_active_color_token() -> None:
    """Active chip colour reuses the same token the active tab
    button uses, keeping the two surfaces visually locked."""

    css = _read_styles_css()
    rule_start = css.index(".recent-chip.active {")
    rule_block = css[rule_start : rule_start + 500]
    assert "var(--tab-active-color)" in rule_block


# ── findRootReadme follows the tab refactor ─────────────────


def test_find_root_readme_targets_tab_files_panel() -> None:
    """The selector must match files inside #tab-files, not the
    old #tree-content > selector that broke after the tab refactor."""

    js = _read_app_js()
    fn_start = js.index("function findRootReadme()")
    fn_block = js[fn_start : fn_start + 800]
    assert "#tab-files > .tree-item.tree-file" in fn_block


# ── DOMContentLoaded wiring ─────────────────────────────────


def test_dom_content_loaded_calls_init_nav_tabs() -> None:
    js = _read_app_js()
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "initNavTabs();" in handler_block
