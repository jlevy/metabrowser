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


def _function_source(js: str, name: str) -> str:
    """Return one top-level function's source, up to the next definition.

    These assertions used a fixed character window, which made them fail
    for the wrong reason: adding an unrelated line near the top of a
    function pushed the asserted call past the cutoff even though the
    behavior was intact. Nested functions are indented, so the next
    column-zero ``function`` is the end of this one.
    """
    start = js.index(f"function {name}(")
    end = js.find("\nfunction ", start + 1)
    return js[start:] if end == -1 else js[start:end]


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
    hints = html.index('id="nav-shortcut-hints"')
    progress = html.index('id="index-progress"')
    hint_tag = html[hints : html.index(">", hints)]
    assert hints < progress
    # A name needs a role that can carry it: ARIA forbids naming a generic
    # element, so the label would be dropped from a bare div.
    assert 'role="group"' in hint_tag
    assert 'aria-label="Keyboard shortcuts"' in hint_tag
    assert "aria-live" not in hint_tag
    assert 'id="index-progress"' in html
    assert 'class="index-progress-spinner"' in html
    assert 'aria-live="polite"' in html


def test_index_template_versions_core_static_assets() -> None:
    html = _render_index_html()
    assert 'href="/static/styles.css?v=' in html
    assets = (
        "/static/plugin_sdk.js",
        "/static/icons.js",
        "/static/tree_expansion.js",
        "/static/known_file_catalog.js",
        "/static/catalog_feed.js",
        "/static/file_fuzzy_match.js",
        "/static/search_controller.js",
        "/static/keyboard_shortcuts.js",
        "/static/overlay_layer.js",
        "/static/keyboard_help.js",
        "/static/tree_keyboard_navigation.js",
        "/static/search_palette.js",
        "/static/app.js",
    )
    positions = []
    for asset in assets:
        assert f'src="{asset}?v=' in html
        positions.append(html.index(asset))
    assert positions == sorted(positions)


def test_files_panel_owns_one_generated_tree_with_concise_row_names() -> None:
    html = _render_index_html()
    js = _read_app_js()
    tab_start = html.index('id="tab-files"')
    tab_tag = html[tab_start : html.index(">", tab_start)]
    assert 'role="tree"' not in tab_tag
    assert 'role="tree" aria-label="Files"' in js
    assert "return isRoot ? treeRootHtml(content) : content;" in js
    assert 'role="group"' in js
    assert "aria-labelledby" in js
    assert "data-tree-level" in js
    assert "data-tree-position" in js
    assert "data-tree-set-size" in js


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
    """Nav tabs are a registry, not a hardcoded click handler.

    ``initNavTabs`` declares the server-rendered panels and binds each
    tab button; ``activateNavPanel`` owns the visibility toggle. The
    split is what lets a conditional panel (Git, which only exists in a
    repository) register itself later without duplicating either half.
    """

    js = _read_app_js()
    assert "function initNavTabs()" in js
    init_block = _function_source(js, "initNavTabs")
    assert "nav-tab-bar" in init_block
    # Files is declared here rather than discovered from the DOM, so a
    # panel can carry its own lazy first-show hook.
    assert 'registerNavPanel({ id: "files"' in init_block
    assert "activateNavPanel(panelId)" in init_block

    activate_block = _function_source(js, "activateNavPanel")
    assert "data-tab-content" in activate_block
    assert "aria-selected" in activate_block


def test_recent_is_not_a_registered_nav_panel() -> None:
    """Recent stopped being a tab when the filter work folded it into
    the Files pane as the recency dimension.

    Registering it would not merely be dead code. ``registerNavPanel``
    creates the button for any panel the server-rendered markup does not
    already carry — that is what lets Git add itself — so a leftover
    registration puts the retired tab back on screen. The HTML
    assertions above cannot catch that, because the tab would be built
    at runtime.
    """

    js = _read_app_js()
    init_block = _function_source(js, "initNavTabs")
    assert 'id: "recent"' not in init_block
    assert "loadRecent" not in init_block


def test_switching_panels_hides_the_file_filter_bar() -> None:
    """The filter bar sits outside the tab containers on purpose: a tree
    reload replaces #tab-files wholesale, and the bar has to survive that
    and stay put while the tree scrolls. Being outside means the
    visibility loop does not reach it, so a panel that is not Files would
    otherwise show file filters above content they cannot filter."""

    js = _read_app_js()
    activate_block = _function_source(js, "activateNavPanel")
    assert 'getElementById("nav-filter-bar")' in activate_block
    assert 'panelId === "files" ? "" : "none"' in activate_block


def test_the_scroll_shadow_follows_the_visible_chrome() -> None:
    """The shadow marks the boundary of the scrolling region, so it has
    to sit on the bottom-most chrome that is actually visible. Resolved
    once at startup it stayed on the filter bar, which a non-Files panel
    hides — leaving the scroll cue on a hidden element."""

    js = _read_app_js()
    block = _function_source(js, "initNavScrollShadow")
    assert "offsetParent !== null" in block
    # The loser is cleared, so a tab switch cannot arm two shadows.
    assert 'other?.classList.remove("scrolled")' in block
    # A tab switch fires no scroll event, so activation re-runs it.
    activate_block = _function_source(js, "activateNavPanel")
    assert "navScrollShadowUpdate?.()" in activate_block


def test_nav_panels_support_an_every_show_retry_hook() -> None:
    js = _read_app_js()
    activate_block = _function_source(js, "activateNavPanel")
    assert "panel?.onShow?.()" in activate_block
    assert activate_block.index("panel?.onFirstShow?.()") < activate_block.index(
        "panel?.onShow?.()"
    )


def test_preview_shell_uses_generation_claims_across_owners() -> None:
    js = _read_app_js()
    assert "function claimPreview(owner)" in js
    assert "function isPreviewClaimCurrent(claim)" in js
    activate_block = _function_source(js, "activateNavPanel")
    assert "claimPreview(`nav:${panelId}`)" in activate_block
    shell_block = js[js.index("window.MetabrowserShell = Object.freeze") :][:600]
    assert "claimPreview" in shell_block
    assert "isPreviewClaimCurrent" in shell_block


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


def test_set_selected_path_called_from_shared_activation_and_reveal() -> None:
    """Pointer and keyboard activation share selection with deep-link reveal."""

    js = _read_app_js()
    # The select branch lives in the shared pointer/keyboard action.
    select_branch = js.index('action === "select"')
    select_block = js[select_branch : select_branch + 500]
    assert "setSelectedPath(row.dataset.path)" in select_block

    # revealInTree uses it.
    reveal_start = js.index("async function revealInTree(path)")
    reveal_block = js[reveal_start : reveal_start + 1500]
    assert "setSelectedPath(path)" in reveal_block


def test_folder_row_activation_selects_opens_and_toggles_the_folder() -> None:
    """A folder row is one target, including its chevron hotspot.

    Every activation must keep navigation and disclosure together: open the
    folder Overview, then toggle the immediate subtree in either direction.
    Pointer and keyboard share one entry point, so the contract lives in
    activateTreeRow rather than in the click delegate.
    """

    js = _read_app_js()
    activate_start = js.index("async function activateTreeRow(row, options)")
    activate_block = js[activate_start : activate_start + 900]
    select_dir_start = activate_block.index('action === "select-dir"')
    select_dir_block = activate_block[select_dir_start : activate_block.index('action === "page')]
    assert "setSelectedPath(row.dataset.path)" in select_dir_block
    # Folder activation goes through the canonical /view/ route; the trailing
    # slash is what makes it a folder rather than a file.
    assert "navigateToPath(`${row.dataset.path}/`)" in select_dir_block
    assert "toggleTreeFolder(row, options)" in select_dir_block
    # Guarded like the select branch: a pathless row must not clear selection.
    assert "if (row.dataset.path) {" in select_dir_block

    # The click delegate routes every row through that one action, and the
    # chevron never becomes a second hotspot with its own semantics.
    handler_start = js.index('treePane.addEventListener("click"')
    handler_block = js[handler_start : handler_start + 3400]
    assert "activateTreeRow(item, { recursive: e.shiftKey })" in handler_block
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
