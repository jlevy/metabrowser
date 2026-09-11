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
from pathlib import Path
from typing import Any, cast

from metabrowser import __version__
from metabrowser import server as proc_browser
from metabrowser.build_version import display_version_line


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _read_tree_filter_model() -> str:
    return proc_browser.STATIC_DIR.joinpath("tree-filter-model.js").read_text()


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


def test_settings_menu_ends_with_the_cli_formatted_version() -> None:
    html = _render_index_html()
    expected = display_version_line("metab", __version__)
    markup = f'<div class="menu-version">{expected}</div>'

    assert markup in html
    assert html.index('id="app-font-select"') < html.index(markup)

    css = _read_styles_css()
    start = css.index(".menu-version {")
    rule = css[start : css.index("}", start)]
    assert "color: var(--muted);" in rule
    assert "font-size: var(--ui-small-font-size);" in rule
    assert "letter-spacing: 0;" in rule
    assert "text-transform: none;" in rule


def test_index_template_versions_core_static_assets() -> None:
    html = _render_index_html()
    assert 'href="/static/styles.css?v=' in html
    assert '<link rel="preload" href="/static/app.js?v=' not in html
    assets = (
        "/static/document-width.js",
        "/static/plugin-sdk.js",
        "/static/icons.js",
        "/static/tree-expansion.js",
        "/static/tree-filter-model.js",
        "/static/app.js",
    )
    positions = []
    for asset in assets:
        assert f'src="{asset}?v=' in html
        positions.append(html.index(f'<script src="{asset}?v='))
    assert positions == sorted(positions)
    deferred_assets = (
        "/static/known-file-catalog.js",
        "/static/catalog-feed.js",
        "/static/file-fuzzy-match.js",
        "/static/search-controller.js",
        "/static/keyboard-shortcuts.js",
        "/static/overlay-layer.js",
        "/static/keyboard-help.js",
        "/static/tree-keyboard-navigation.js",
        "/static/search-palette.js",
    )
    assert all(asset in html for asset in deferred_assets)
    assert all(f'<script src="{asset}' not in html for asset in deferred_assets)


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
    fn_start = js.index("function loadRecent(cursor)")
    fn_block = js[fn_start : fn_start + 1500]
    # The chip-change path delegates the exact filter cursor to fetchRecent.
    assert "fetchRecent(cursor)" in fn_block
    # fetchRecent launches the cursor-selected production request.
    fr_start = js.index("function fetchRecent(cursor, preserveRows)")
    fr_block = js[fr_start : fr_start + 2500]
    assert "treeFilterModel.beginRecentRequest(recentContinuity, cursor" in fr_block
    # Aborts an in-flight chip fetch so a fast double-click doesn't
    # race two responses against each other.
    assert "AbortController" in fr_block


def test_recent_view_filters_complete_leaves_before_clustering() -> None:
    """Recent reads the complete fetched-and-overlaid leaf map through the
    production model before any bounded DOM rendering occurs."""

    js = _read_app_js()
    fn_start = js.index("function renderRecentFromBase()")
    fn_block = js[fn_start : fn_start + 1900]
    assert "treeFilterModel.renderRecentView(" in fn_block
    assert "Array.from(recentBaseEntries.values())" in fn_block
    assert "paintRecentView(results, state, inputCount, view)" in fn_block
    assert "querySelectorAll" not in fn_block
    paint = _function_source(js, "paintRecentView")
    assert "renderRecentList({ tree: view.tree })" in paint
    assert "querySelectorAll" not in paint
    assert "rowMatches" not in paint

    model = _read_tree_filter_model()
    projection = model[
        model.index("function renderRecentView") : model.index("function runRecentRepair")
    ]
    assert projection.index("recentView(entries, options)") < projection.index("render(view)")


def test_recent_window_cutoffs_come_from_the_server_settings() -> None:
    js = _read_app_js()
    assert "const _RECENT_WINDOW_SECONDS = _METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS || {};" in js
    start = js.index("const _RECENT_WINDOW_SECONDS")
    assert '"1h": 60 * 60' not in js[start : start + 500]


def test_recent_change_batch_handles_the_real_wire_operations() -> None:
    """The shared model accepts only events.py's upsert/remove contract."""

    batch = _function_source(_read_tree_filter_model(), "applyRecentChangeBatch")
    assert 'operation.op === "upsert"' in batch
    assert 'operation.op === "remove"' in batch
    assert 'operation.op === "move"' not in batch
    assert 'wireEntry.type !== "file"' in batch
    assert "options.previousEntries.get(upsertPath)" in batch


def test_file_store_apply_change_mirrors_into_recent_overlay() -> None:
    """The app delegates one complete batch before mutating FileStore."""

    js = _read_app_js()
    change = _function_source(js, "fileStoreApplyChangeInner")
    assert change.count("treeFilterModel.applyRecentChangeBatch(") == 1
    assert "previousEntries: fileStore" in change
    assert change.index("treeFilterModel.applyRecentChangeBatch(") < change.index(
        "for (var i = 0; i < ops.length; i++)"
    )
    assert "recentBaseApplyOp" not in js


def test_change_during_recent_request_invalidates_the_snapshot() -> None:
    """An HTTP snapshot has no cursor comparable with the SSE stream.

    A change received after the request starts therefore invalidates the whole
    response; replaying that delta could resurrect a path removed and recreated
    in a different order.
    """

    js = _read_app_js()
    change_start = js.index("function fileStoreApplyChangeInner(ops)")
    change_block = js[change_start : change_start + 500]
    assert "recentContinuity.dirtyActiveRequest()" in change_block
    snapshot_start = js.index("function fileStoreApplySnapshotInner(scope, entries)")
    snapshot_block = js[snapshot_start : snapshot_start + 500]
    assert "recentContinuity.dirtyActiveRequest()" in snapshot_block

    fetch_block = _function_source(js, "fetchRecent")
    assert "treeFilterModel.beginRecentRequest(recentContinuity, cursor" in fetch_block
    assert "treeFilterModel.settleRecentSuccess(" in fetch_block
    assert "treeFilterModel.settleRecentFailure(" in fetch_block
    assert fetch_block.count("recentFilterKey() === load.url") == 2
    model = _read_tree_filter_model()
    begin = model[
        model.index("function beginRecentRequest") : model.index("function createRecentRequest")
    ]
    assert "continuity.abandonRequest()" in begin
    assert "continuity.startRequest(cursor.recentRequestKey)" in begin
    success = model[
        model.index("function settleRecentSuccess") : model.index("function settleRecentFailure")
    ]
    assert "continuity.settleRequest(request)" in success
    assert 'disposition === "refetch"' in success
    assert "continuity.scheduleRepair(repair)" in success


def test_failed_dirty_recent_request_retries_only_after_it_settles() -> None:
    """Failure cannot consume the one-bit invalidation or overlap its repair."""

    fetch = _function_source(_read_app_js(), "fetchRecent")
    catch = fetch[fetch.index(".catch((err) => {") : fetch.index(".finally(() => {")]
    assert "treeFilterModel.settleRecentFailure(" in catch
    assert "fetchRecent(" not in catch
    model = _read_tree_filter_model()
    failure = model[
        model.index("function settleRecentFailure") : model.index("function invalidateRecent")
    ]
    assert "continuity.settleRequest(request)" in failure
    assert 'disposition === "refetch"' in failure
    assert "continuity.repairFailed(repair, failure.retryable)" in failure
    assert "continuity.scheduleRepair(repair)" in failure


def test_recent_request_settles_before_commit_render_can_schedule_expiry() -> None:
    model = _read_tree_filter_model()
    success = model[
        model.index("function settleRecentSuccess") : model.index("function settleRecentFailure")
    ]
    settled = success.index("continuity.settleRequest(request)")
    committed = success.index("continuity.repairSucceeded(repair)")
    rendered = success.index("context.render()")
    assert settled < committed < rendered


def test_recent_cluster_is_in_the_headless_production_model() -> None:
    """The browser and the CLI session execute the same clustering code."""

    js = _read_app_js()
    model = (proc_browser.STATIC_DIR / "tree-filter-model.js").read_text()
    assert "function clusterRecentTree(files, nowSec, pct, ignoredDirectoryPaths)" in model
    assert "function agesWithinPct(ages, pct)" in model
    assert "function clusterRecentTree" not in js


def test_recent_recompute_is_debounced() -> None:
    """A burst of fs.change ops shouldn't render-thrash. Cap is
    pinned via RECENT_RECLUSTER_DEBOUNCE_MS (read from
    window.METABROWSER_SETTINGS, default 100)."""

    js = _read_app_js()
    assert "RECENT_RECLUSTER_DEBOUNCE_MS" in js
    fn_start = js.index("function _scheduleRecentRecompute()")
    fn_block = js[fn_start : fn_start + 1000]
    assert "recentRecompute.schedule(" in fn_block
    assert "currentRecentFilterCursor()" in fn_block

    model = _function_source(_read_tree_filter_model(), "createRecentRecomputeScheduler")
    assert "clock.setTimeout" in model
    assert "handle !== null && pending" in model
    assert 'return "coalesced"' in model


def test_authoritative_recent_repairs_are_constant_state_and_coalesced() -> None:
    """Live invalidation dirties one active request or schedules one repair.

    It never retains an operation log, and a pending filter fetch already
    covers the same provider state.
    """

    js = _read_app_js()
    fn_block = _function_source(js, "scheduleRecentAuthoritativeRefetch")
    assert "treeFilterModel.invalidateRecent(recentContinuity" in fn_block
    assert "recentRepairDescriptor()" in fn_block
    assert "for (" not in fn_block


def test_deep_catalog_changes_repair_recent_without_widening_tree_sse() -> None:
    """The unscoped catalog companion exposes paths omitted from fs.change."""

    js = _read_app_js()
    source = _function_source(js, "_createInventoryEventSource")
    catalog = source[
        source.index('addEventListener("catalog.change"') : source.index(
            'addEventListener("capability.update"'
        )
    ]
    assert "treeFilterModel.applyRecentCatalogChange(recentBaseEntries, data" in catalog
    assert "markRecentTotalAsRetainedLowerBound(" in catalog
    assert "recentCatalogEffect.retainedLowerBound" in catalog
    assert "scheduleRecentAuthoritativeRefetch()" in catalog
    assert 'new EventSource("/api/events?scope=root-depth-2")' in source
    model = _function_source(_read_tree_filter_model(), "applyRecentCatalogChange")
    assert "change.non_file_paths" in model
    assert "removeRecentEntriesByPrefix(entries, removalPrefixes)" in model
    assert "recentMatchingCount(Array.from(entries.values()), matchOptions)" in model


def test_recent_recompute_timers_are_cancelled_and_identity_guarded() -> None:
    """A queued live repaint cannot overwrite a newer source or request."""

    js = _read_app_js()
    scheduler = _function_source(_read_tree_filter_model(), "createRecentRecomputeScheduler")
    assert "generation" in scheduler
    assert "isCurrent(request)" in scheduler

    recompute = _function_source(js, "_scheduleRecentRecompute")
    assert "recentRecompute.schedule(" in recompute
    assert "currentRecentFilterCursor()" in recompute

    fetch = _function_source(js, "fetchRecent")
    assert "recentRecompute.cancel()" in fetch
    filter_change = _function_source(js, "onFilterStateChange")
    assert filter_change.count("recentRecompute.cancel()") >= 2


def test_resync_invalidates_recent_before_reconnecting() -> None:
    """A transport gap dirties an active request or repairs a settled view."""

    source = _function_source(_read_app_js(), "_createInventoryEventSource")
    resync = source[
        source.index('addEventListener("fs.resync_required"') : source.index(
            "inventoryEventSource.onopen"
        )
    ]
    assert "recentRecompute.cancel()" in resync
    assert "scheduleRecentAuthoritativeRefetch()" in resync
    assert resync.index("scheduleRecentAuthoritativeRefetch()") < resync.index(
        "_scheduleInventoryReconnect()"
    )


def test_every_sentinel_repairs_prebaseline_or_reconnect_recent_state() -> None:
    js = _read_app_js()
    source = _function_source(js, "_createInventoryEventSource")
    snapshot = source[
        source.index('addEventListener("fs.snapshot"') : source.index(
            'addEventListener("fs.change"'
        )
    ]
    assert "treeFilterModel.observeRecentSentinel(recentContinuity" in snapshot
    assert "recentEverLoaded && filesPanelUsesRecentSource()" in snapshot
    assert "recentFilterRefetch.pending()" in snapshot
    assert "_inventorySentinelSeen" not in js


def test_capped_recent_page_repairs_subtractive_changes_and_expiry() -> None:
    js = _read_app_js()
    change = _function_source(js, "fileStoreApplyChangeInner")
    assert "recentEffect?.needsAuthoritativeRepair" in change
    assert "recentTruncated = recentEffect.truncated" in change
    assert "scheduleRecentAuthoritativeRefetch()" in change

    paint = _function_source(js, "paintRecentView")
    assert "view.matchingCount < inputCount" in paint
    assert "recentTruncated && lostKnownMember && entries.length < RECENT_LIMIT" in paint
    assert "scheduleRecentAuthoritativeRefetch()" in paint


def test_capped_recent_page_repairs_every_ambiguous_unseen_op_shape() -> None:
    """A missing page row is unknown, not evidence that it never matched."""

    model = _read_tree_filter_model()
    batch = _function_source(model, "applyRecentChangeBatch")
    assert "recentUnseenBeforeMayMatch(" in batch
    assert "recentReplacementNeedsBackfill(" in batch
    assert "!previous && unseenBeforeMayMatch" in batch
    assert "removalPrefixes.push(operation.path)" in batch
    assert "removeRecentEntriesByPrefix(entries, removalPrefixes)" in batch
    assert 'operation.op === "move"' not in batch

    # The golden session executes this same production function over eligible
    # and ineligible unseen files, unknown and subtree removes, file-to-dir,
    # ordinary directory aggregates, and the known/uncapped fast paths.
    session = (Path(__file__).parent / "dom" / "recent-filter-session.js").read_text()
    for case in (
        "eligibleUnseenFileUpsert",
        "ineligibleUnseenFileUpsert",
        "unknownRemove",
        "unseenFileToDirectory",
        "subtreeRemove",
        "ordinaryDirectoryAggregate",
        "ordinaryKnownWrite",
        "knownRankRegression",
        "uncappedEligibleUpsert",
    ):
        assert case in session


def test_ambiguous_recent_count_downgrades_to_a_safe_bounded_lower_bound() -> None:
    js = _read_app_js()
    lower_bound = _function_source(js, "markRecentTotalAsRetainedLowerBound")
    assert "recentTotalMatching = lowerBound" in lower_bound
    assert "recentTotalMatchingExact = false" in lower_bound
    assert "_renderFilteredTally(panel, state, recentTotalMatching)" in lower_bound
    assert "for (" not in lower_bound

    change = _function_source(js, "fileStoreApplyChangeInner")
    assert "recentEffect.retainedLowerBound ?? 0" in change
    assert change.index("markRecentTotalAsRetainedLowerBound(") < change.index(
        "scheduleRecentAuthoritativeRefetch()"
    )

    batch = _function_source(_read_tree_filter_model(), "applyRecentChangeBatch")
    assert "needsAuthoritativeRepair" in batch
    assert "recentMatchingCount(Array.from(entries.values()), matchOptions)" in batch


def test_recent_live_overlay_is_pruned_to_the_route_cap() -> None:
    js = _read_app_js()
    paint = _function_source(js, "paintRecentView")
    assert "recentBaseEntries = new Map(entries.map(" in paint
    change = _function_source(js, "fileStoreApplyChangeInner")
    assert change.count("treeFilterModel.applyRecentChangeBatch(") == 1
    model = _read_tree_filter_model()
    batch = _function_source(model, "applyRecentChangeBatch")
    assert batch.count("trimRecentEntriesToLimit(entries, options.limit)") == 1
    assert batch.index("trimRecentEntriesToLimit(entries, options.limit)") > batch.index(
        "for (const operation of operations)"
    )


def test_upsert_only_recent_batch_skips_the_retained_subtree_scan() -> None:
    batch = _function_source(_read_tree_filter_model(), "applyRecentChangeBatch")
    guarded_prune = (
        "removalPrefixes.length > 0 ? removeRecentEntriesByPrefix(entries, removalPrefixes) : 0"
    )
    assert guarded_prune in batch


def test_background_recent_repair_preserves_the_reader_view() -> None:
    js = _read_app_js()
    fetch = _function_source(js, "fetchRecent")
    assert "results && preserveRows !== true" in fetch
    assert "recentViewCommitted = false" in fetch
    assert "treeFilterModel.settleRecentFailure(" in fetch
    commit = _function_source(js, "commitRecentResponse")
    assert "recentViewCommitted = true" in commit
    repair_setup = js[
        js.index("var recentContinuity") : js.index("function scheduleRecentAuthoritativeRefetch")
    ]
    assert "treeFilterModel.runRecentRepair(recentContinuity, request" in repair_setup
    model = _read_tree_filter_model()
    repair = model[
        model.index("function runRecentRepair") : model.index("function settleRecentSuccess")
    ]
    assert "continuity.repairReady(" in repair
    assert "request.preserveRows === true && context.viewCommitted" in repair


def test_background_recent_failure_retries_with_visible_stale_state() -> None:
    js = _read_app_js()
    assert "const RECENT_REPAIR_MAX_RETRIES = 4;" in js
    assert "maxRetries: RECENT_REPAIR_MAX_RETRIES" in js
    fetch = _function_source(js, "fetchRecent")
    assert "classify: window.MetabrowserRequestErrors.classifyRequestError" in fetch
    assert "treeFilterModel.settleRecentFailure(" in fetch
    model = _read_tree_filter_model()
    failure = model[
        model.index("function settleRecentFailure") : model.index("function invalidateRecent")
    ]
    assert "continuity.repairFailed(repair, failure.retryable)" in failure
    assert "if (repair.preserveRows === true)" in failure
    status = _function_source(js, "setRecentContinuityStatus")
    assert 'note.setAttribute("role", "status")' in status
    assert "Recent files may be out of date; retrying…" in status
    assert "Change the filter or refresh to try again." in status
    assert ".recent-stale-note" in _read_styles_css()


def test_recent_context_changes_cancel_retry_and_stale_state() -> None:
    js = _read_app_js()
    load = _function_source(js, "loadRecent")
    assert "recentContinuity.cancelRepairs()" in load
    change = _function_source(js, "onFilterStateChange")
    assert change.count("recentContinuity.cancelRepairs()") >= 2
    assert change.count("recentContinuity.abandonRequest()") >= 2


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
    start = js.index("function loadRecent(cursor)")
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


def test_recency_refetch_dedups_against_the_full_request() -> None:
    """An unchanged selection does not refetch, while any server-owned
    dimension changes the request identity."""

    js = _read_app_js()
    fn_block = _function_source(js, "onFilterStateChange")
    assert "treeFilterModel.recentFilterTransition(" in fn_block
    assert 'transition.action === "load-recent"' in fn_block
    assert 'transition.action === "refetch-recent"' in fn_block
    assert "loadRecent(transition.current)" in fn_block
    assert "recentFilterRefetch.schedule(" in fn_block


def test_load_recent_locks_window_synchronously_before_fetching() -> None:
    """The window assignment must land before fetchRecent kicks off
    so a fast double-click doesn't race two fetches that resolve in
    the wrong order."""

    js = _read_app_js()
    fn_start = js.index("function loadRecent(cursor)")
    fn_block = js[fn_start : fn_start + 1500]
    assign_idx = fn_block.index("currentRecentWindow = cursor.windowKey;")
    fetch_idx = fn_block.index("fetchRecent(cursor)")
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


def test_startup_gives_the_tree_request_priority_over_preview_plugins() -> None:
    js = _read_app_js()
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]

    assert handler_block.index("await loadTree();") < handler_block.index(
        "navigationController.start()"
    )
