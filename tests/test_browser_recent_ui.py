"""Structural tests for the recency data path and its DOM contract.

Recency is a filter dimension rather than a tab: the Files panel
renders ``/api/recent`` whenever a recency window is set and the
treatment is hide. The fetch, overlay, clustering, and debounce
machinery below is unchanged by that move — only the panel it paints
into is. Filter-bar and chip-family structure lives in
test_browser_filter_ui.py.

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


def test_index_template_renders_single_files_tab() -> None:
    """Recent is a filter now, so the nav pane never needs switching."""

    html = _render_index_html()
    assert 'class="tab-bar nav-tab-bar"' in html
    assert 'data-tab="files"' in html
    assert 'data-tab="recent"' not in html
    # Aria attributes for screen readers.
    assert 'role="tablist"' in html
    assert 'aria-selected="true"' in html


def test_index_template_renders_only_the_files_panel() -> None:
    html = _render_index_html()
    assert 'id="tab-files"' in html
    assert 'data-tab-content="files"' in html
    assert 'id="tab-recent"' not in html
    assert 'data-tab-content="recent"' not in html


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
        "nav-filter-bar",
        "tree-pane",
        "tree-resize",
        "preview-pane",
    }
    for ident in referenced_ids:
        assert f'id="{ident}"' in html, f"missing JS-referenced id={ident!r} in rendered HTML"


def test_dom_contract_files_panel_is_direct_child_of_tree_content() -> None:
    """A refactor that nests #tab-files inside another element
    would silently break selectors like '#tab-files > .tree-item'.
    Catch it via structural assertion."""

    html = _render_index_html()
    # The Files panel must immediately follow the opening
    # #tree-content tag (whitespace allowed).
    tree_content_open = html.index('id="tree-content"')
    after_open = html[tree_content_open : tree_content_open + 200]
    assert 'id="tab-files"' in after_open


def test_dom_contract_filter_bar_sits_outside_the_scrolling_tree() -> None:
    """The bar must not live inside #tab-files (a tree reload
    replaces that container wholesale) nor inside #tree-content (the
    scroll owner, which would scroll the bar away)."""

    html = _render_index_html()
    assert html.index('id="nav-filter-bar"') < html.index('id="tree-content"')
    assert html.index('class="tab-bar nav-tab-bar"') < html.index('id="nav-filter-bar"')


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
    ``root-depth-2`` scope (including Live, which applies to every
    file rather than only specialized tracker paths). New
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


def test_recent_window_cutoffs_come_from_the_server_settings() -> None:
    js = _read_app_js()
    assert "const _RECENT_WINDOW_SECONDS = _METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS || {};" in js
    start = js.index("const _RECENT_WINDOW_SECONDS")
    assert '"1h": 60 * 60' not in js[start : start + 500]


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


def test_recent_windows_repaint_when_the_oldest_file_expires() -> None:
    """Without an expiry timer, Live could display a file forever if
    no later filesystem event arrived to trigger another render."""

    js = _read_app_js()
    assert "function scheduleRecentExpiryRecheck(entries)" in js
    render_start = js.index("function renderRecentFromBase()")
    render_block = js[render_start : render_start + 1800]
    assert "scheduleRecentExpiryRecheck(entries)" in render_block
    assert "RECENT_EXPIRY_MAX_DELAY_MS" in js
    schedule_start = js.index("function scheduleRecentExpiryRecheck(entries)")
    schedule_block = js[schedule_start : schedule_start + 1200]
    assert "var due = Math.min(" in schedule_block
    assert "RECENT_EXPIRY_MAX_DELAY_MS" in schedule_block


def test_loading_a_recent_window_cancels_the_previous_expiry_timer() -> None:
    """A timer from the previous window must not repaint its cached
    rows while the replacement request is still loading."""

    js = _read_app_js()
    start = js.index("function loadRecent(windowKey)")
    block = js[start : start + 500]
    assert "clearRecentExpiryRecheck();" in block


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


def test_recency_refetch_dedups_against_the_current_window() -> None:
    """Re-selecting the same recency window must not refetch. The
    filter-change handler compares against the last window it acted
    on before delegating to loadRecent."""

    js = _read_app_js()
    fn_start = js.index("function onFilterStateChange(state)")
    fn_block = js[fn_start : fn_start + 1200]
    assert "_filterLastRecency !== state.recency" in fn_block
    assert "loadRecent(state.recency)" in fn_block


def test_load_recent_locks_window_synchronously_before_fetching() -> None:
    """The window assignment must land before fetchRecent kicks off
    so a fast double-click doesn't race two fetches that resolve in
    the wrong order."""

    js = _read_app_js()
    fn_start = js.index("function loadRecent(windowKey)")
    fn_block = js[fn_start : fn_start + 1500]
    assign_idx = fn_block.index("currentRecentWindow = windowKey;")
    fetch_idx = fn_block.index("fetchRecent(windowKey)")
    assert assign_idx < fetch_idx


def test_recency_source_needs_a_window() -> None:
    """/api/recent is the source whenever any time window is set,
    including the general 90-second Live window."""

    js = _read_app_js()
    fn_start = js.index("function filesPanelUsesRecentSource()")
    fn_block = js[fn_start : fn_start + 600]
    assert 'st.recency !== "all"' in fn_block
    assert 'st.recency !== "live"' not in fn_block


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


def test_folder_row_click_selects_opens_and_toggles_the_folder() -> None:
    """A folder row is one target, including its chevron hotspot.

    Every activation must keep navigation and disclosure together: open the
    folder Overview, then toggle the immediate subtree in either direction.
    """

    js = _read_app_js()
    handler_start = js.index('treePane.addEventListener("click"')
    handler_block = js[handler_start : handler_start + 3400]
    select_dir_start = handler_block.index('action === "select-dir"')
    select_dir_block = handler_block[select_dir_start : select_dir_start + 500]
    assert "setSelectedPath(item.dataset.path)" in select_dir_block
    assert "navigateToPath(item.dataset.path" in select_dir_block
    assert "toggleTreeFolder(item, e.shiftKey)" in select_dir_block
    assert "isToggleHotspot" not in handler_block


def test_initial_and_live_folder_rows_share_the_select_dir_action() -> None:
    """Live inserts must not regress to chevron-only folder behavior."""

    js = _read_app_js()
    assert js.count('data-action="select-dir"') == 2
    assert 'data-action="toggle"' not in js


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


def test_styles_css_keeps_recency_list_states() -> None:
    css = _read_styles_css()
    assert ".recent-empty {" in css
    assert ".recent-truncated-note {" in css
    assert ".tab-bar.nav-tab-bar {" in css


def test_styles_css_drops_the_superseded_recent_chip() -> None:
    """.recent-chip was one of four near-identical pill controls; the
    shared .chip family replaced it."""

    css = _read_styles_css()
    assert ".recent-chip" not in css
    assert ".recent-controls" not in css


# ── Default folder route ─────────────────────────────────────


def test_startup_selects_only_what_the_canonical_route_names() -> None:
    """The shell never picks a root document the URL did not ask for.

    ``/`` redirects to ``/view/`` at the server, so the browser only ever reads a
    canonical route, and startup selection comes from that route alone.
    """

    js = _read_app_js()
    assert "function findRootReadme()" not in js
    assert "window.MetabrowserNavigationRoute.parse(" in js
    assert "navigationController.start()" in js


# ── DOMContentLoaded wiring ─────────────────────────────────


def test_dom_content_loaded_calls_init_nav_tabs() -> None:
    js = _read_app_js()
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "initNavTabs();" in handler_block
