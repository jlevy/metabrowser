"""Structural tests for the FileStore and EventSource client wiring.

Follows the test_browser_v2.py convention: parse the static
``app.js`` source as text and assert specific structural
invariants. We don't run the JS — testing the structure catches
the kinds of regressions a refactor most often introduces (a
helper renamed, a selector moved, a listener removed).

Coverage:

* ``sizeHtml(null)``, ``countHtml(null)``, and ``formatAge(null)`` produce
  ``tally-pending`` skeleton cells (the spec contract for
  walker-in-progress dir aggregates).
* ``startInventoryEventStream()`` opens an ``EventSource``
  against ``/api/events?scope=root-depth-2`` and registers
  listeners for ``fs.snapshot`` / ``fs.change`` /
  ``fs.resync_required``.
* ``computeCellPatch`` is a pure function that returns a
  ``{sizeHtml, ageHtml, ...}`` shape; ``applyCellPatch`` calls
  it and mutates the DOM.
* ``fileStoreApplySnapshot`` rebuilds the store atomically
  before notifying subscribers.
* ``DOMContentLoaded`` calls ``startInventoryEventStream()``
  after ``loadTree``.
* ``DOMContentLoaded`` starts lightweight index-progress polling
  before ``loadTree`` so a slow first tree render still shows
  crawl liveness.
* The ``.tally-pending`` CSS rule + ``--tally-skeleton-bg``
  token exist in styles.css.
"""

from __future__ import annotations

from metabrowser import server as proc_browser


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _read_styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text()


def _read_design_system_md() -> str:
    return proc_browser.STATIC_DIR.parents[2].joinpath("docs/design-system.md").read_text()


# ── sizeHtml / countHtml / formatAge null handling ────────────


def test_size_html_renders_tally_pending_for_null() -> None:
    js = _read_app_js()
    # Anchor on the function definition; assert the null branch
    # is structured and emits the expected class.
    fn_start = js.index("function sizeHtml(bytes, extraClass)")
    fn_block = js[fn_start : fn_start + 800]
    assert "if (bytes === null || bytes === undefined)" in fn_block
    assert "tally-pending" in fn_block


def test_count_html_renders_tally_pending_for_null() -> None:
    js = _read_app_js()
    fn_start = js.index("function countHtml(n, extraClass)")
    fn_block = js[fn_start : fn_start + 800]
    assert "if (isPendingNumber(n))" in fn_block
    assert "count tally-pending" in fn_block
    assert "formatCount(n)" in fn_block


def test_format_age_renders_tally_pending_for_null() -> None:
    js = _read_app_js()
    fn_start = js.index("function formatAge(mtimeSec)")
    fn_block = js[fn_start : fn_start + 600]
    assert "if (mtimeSec === null)" in fn_block
    assert "tally-pending tally-pending-narrow" in fn_block


# ── EventSource wiring ────────────────────────────────────────


def test_event_source_opens_against_api_events_scope_root_depth_2() -> None:
    js = _read_app_js()
    fn_start = js.index("function _createInventoryEventSource()")
    fn_block = js[fn_start : fn_start + 3000]
    assert 'new EventSource("/api/events?scope=root-depth-2")' in fn_block


def test_event_source_registers_fs_snapshot_listener() -> None:
    js = _read_app_js()
    fn_start = js.index("function _createInventoryEventSource()")
    fn_block = js[fn_start : fn_start + 3000]
    assert 'addEventListener("fs.snapshot"' in fn_block
    assert 'addEventListener("fs.change"' in fn_block
    assert 'addEventListener("fs.resync_required"' in fn_block


def test_resync_event_reconnects_for_a_fresh_snapshot() -> None:
    js = _read_app_js()
    start = js.index('addEventListener("fs.resync_required"')
    block = js[start : start + 900]
    assert "_scheduleInventoryReconnect()" in block
    assert "_resetEsCircuitBreaker()" not in block
    assert "_createInventoryEventSource()" not in block
    assert block.index("quickFileCatalogFeed?.onResync()") < block.index(
        "_scheduleInventoryReconnect()"
    )


def test_event_source_backoff_resets_only_after_a_stable_interval() -> None:
    js = _read_app_js()
    reconnect_start = js.index("function _scheduleInventoryReconnect()")
    reconnect_block = js[reconnect_start : reconnect_start + 1000]
    assert "var delay = _esBackoffMs" in reconnect_block
    assert "_esBackoffMs * 2" in reconnect_block
    assert "_ES_BACKOFF_CAP_MS" in reconnect_block
    assert reconnect_block.index("_esConsecutiveErrors = 0") < reconnect_block.index(
        "_createInventoryEventSource()"
    )
    assert "_esBackoffMs = 2000" not in reconnect_block

    stable_start = js.index("function _scheduleEsStableReset()")
    stable_block = js[stable_start : stable_start + 500]
    assert "_ES_STABLE_CONNECTION_MS" in stable_block
    assert "_resetEsCircuitBreaker()" in stable_block

    source_start = js.index("function _createInventoryEventSource()")
    source_block = js[source_start : source_start + 4500]
    assert "inventoryEventSource.onopen" in source_block
    assert "_scheduleEsStableReset()" in source_block
    for event_name in ("fs.snapshot", "fs.change", "catalog.change", "capability.update"):
        event_start = source_block.index(f'addEventListener("{event_name}"')
        event_block = source_block[event_start : event_start + 250]
        assert "_resetEsCircuitBreaker()" not in event_block


def test_event_source_handles_typeof_undefined_for_graceful_fallback() -> None:
    """When EventSource isn't supported (older browsers, some
    SSE-stripping proxies), startInventoryEventStream short-
    circuits without crashing — /api/activity polling stays in
    place as the fallback."""

    js = _read_app_js()
    fn_start = js.index("function startInventoryEventStream()")
    fn_block = js[fn_start : fn_start + 800]
    assert 'typeof EventSource === "undefined"' in fn_block


# ── FileStore atomicity ───────────────────────────────────────


def test_apply_snapshot_rebuilds_store_before_notifying() -> None:
    """``fileStoreApplySnapshot`` must replace the store first,
    then call subscribers — never the other way around. Tests
    verify by ordering of code inside the function body."""

    js = _read_app_js()
    fn_start = js.index("function fileStoreApplySnapshot(scope, entries)")
    fn_block = js[fn_start : fn_start + 900]
    # ``fileStore = new Map()`` must appear before the subscribers call.
    assert fn_block.index("fileStore = new Map()") < fn_block.index("notifyFileStoreSubscribers")
    assert "applyCellPatch(entries[i])" in fn_block
    assert fn_block.index("applyCellPatch(entries[i])") < fn_block.index(
        "notifyFileStoreSubscribers"
    )


def test_apply_change_handles_upsert_and_remove_ops() -> None:
    """``fileStoreApplyChange`` consumes the two op shapes the wire
    schema defines after the metabrowser-stability spec dropped
    ``FsMove``: ``upsert`` and ``remove``. A future rename-detection
    contract can re-introduce ``move``."""
    js = _read_app_js()
    fn_start = js.index("function fileStoreApplyChange(ops)")
    fn_block = js[fn_start : fn_start + 1200]
    assert 'op.op === "upsert"' in fn_block
    assert 'op.op === "remove"' in fn_block
    assert 'op.op === "move"' not in fn_block


# ── computeCellPatch / applyCellPatch ─────────────────────────


def test_compute_cell_patch_is_pure_returns_html_shape() -> None:
    js = _read_app_js()
    fn_start = js.index("function computeCellPatch(entry, options)")
    fn_block = js[fn_start : fn_start + 1200]
    # Returns the patch object with the keys applyCellPatch reads.
    assert "sizeHtml:" in fn_block
    assert "ageHtml:" in fn_block
    assert "tipFiles:" in fn_block
    assert "tipSize:" in fn_block
    assert "tipMtime:" in fn_block


def test_dir_metric_patch_preserves_pending_state() -> None:
    js = _read_app_js()
    fn_start = js.index("function computeCellPatch(entry, options)")
    fn_block = js[fn_start : fn_start + 1400]
    assert "treeDirChipHtml(totalFiles, totalSize, options)" in fn_block
    assert "countHtml(totalFiles == null ? 0 : totalFiles" not in fn_block
    assert "tipFiles: nullableDataValue(totalFiles)" in fn_block
    assert "tipSize: nullableDataValue(totalSize)" in fn_block


def test_tree_tooltips_do_not_coerce_pending_aggregates_to_zero() -> None:
    js = _read_app_js()
    assert "function parseTipNumber(value)" in js
    assert "function nullableDataValue(n)" in js
    assert "+d.tipFiles" not in js
    assert "+d.tipSize" not in js
    assert 'data-tip-files="${nullableDataValue(node.total_files)}' in js
    assert 'data-tip-size="${nullableDataValue(node.total_size)}' in js
    assert "Loading file count…" in js
    assert "Loading size…" in js


def test_tree_tooltips_omit_duplicative_name() -> None:
    js = _read_app_js()
    # treeTooltipNameHtml still supports an optional name (the header path tooltip
    # uses it); passing includeName === false drops the name.
    assert "function treeTooltipNameHtml(name, includeName)" in js
    assert "includeName === false" in js

    listener_start = js.index('treePane.addEventListener(\n  "mouseenter"')
    listener_block = js[listener_start : listener_start + 1400]
    # Every tree row already shows its name, so the hover tooltip omits it and
    # shows size + date only (never duplicative).
    assert "var includeName = false" in listener_block
    assert "folderTooltipHtml(" in listener_block
    assert "fileTooltipHtml(" in listener_block


def test_apply_cell_patch_targets_data_path_rows_in_dom() -> None:
    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 2500]
    # data-path attribute selector lookup
    assert '.tree-folder[data-path="' in fn_block
    # idempotent: only mutate when content differs
    assert "outerHTML !== patch.sizeHtml" in fn_block


def test_apply_cell_patch_uses_subtree_empty_state_for_empty_class() -> None:
    """A dir initially painted gray during inventory startup
    (walker-pending ``total_files=null`` historically conflated
    with ``0`` server-side) used to keep its ``tree-item-empty``
    class even after fs.change delivered a positive count. File totals
    cannot identify link-only folders, so live patches use the explicit
    subtree-empty field and retain a positive-count fallback for older
    event payloads."""

    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 3600]
    assert 'classList.toggle("tree-item-empty"' in fn_block
    assert 'typeof entry.empty === "boolean"' in fn_block
    assert "entry.empty" in fn_block
    assert "totalFiles > 0" in fn_block
    assert "totalFiles === 0" not in fn_block


def test_apply_cell_patch_syncs_gitignored_class() -> None:
    """The muted ``tree-item-gitignored`` class was set at first
    paint and never updated. Sync it on every patch so a
    .gitignore edit (or a freshly-arrived row whose ignored
    state differs from any cached DOM state) reflects in the UI
    without a hard reload."""

    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 3600]
    assert 'classList.toggle("tree-item-gitignored"' in fn_block


def test_apply_cell_patch_called_from_apply_change_upsert() -> None:
    """The fs.change handler should trigger applyCellPatch on
    each upsert. Otherwise skeleton cells never get filled."""

    js = _read_app_js()
    fn_start = js.index("function fileStoreApplyChange(ops)")
    fn_block = js[fn_start : fn_start + 1200]
    assert "applyCellPatch(op.entry)" in fn_block


def test_apply_cell_patch_skips_root_entry() -> None:
    """The root (path "") is the implicit tree container, never a row.
    The fs.snapshot includes it for aggregate totals, but applyCellPatch
    must early-return on the empty path — otherwise it falls through to
    the insert branch (the root's parent resolves to the panel root) and
    grafts a phantom row for the served dir *inside itself*, flashed
    yellow like a new file on every (re)connect."""

    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    # The guard must be the first thing the function does, before the
    # data-path selector that would otherwise match nothing and fall
    # through to insertion.
    fn_block = js[fn_start : js.index("function _removeRenderedRows(path)", fn_start)]
    assert "if (!entry.path)" in fn_block
    assert fn_block.index("if (!entry.path)") < fn_block.index("escapePathForSelector(entry.path)")


def test_root_entry_refreshes_summary_and_tooltip_before_row_guard() -> None:
    js = _read_app_js()
    helper_start = js.index("function updateRootAggregatePresentation(entry)")
    helper_block = js[helper_start : helper_start + 1800]
    assert 'queryHtml(".tree-summary-count")' in helper_block
    assert 'queryHtml(".tree-summary-size")' in helper_block
    assert 'queryHtml(".header-path")' in helper_block
    assert "countHtml(totalFiles)" in helper_block
    assert "sizeHtml(totalSize)" in helper_block
    assert "pathEl.dataset.tipFiles" in helper_block
    assert "pathEl.dataset.tipSize" in helper_block

    patch_start = js.index("function applyCellPatch(entry)")
    patch_block = js[patch_start : patch_start + 700]
    assert patch_block.index("updateRootAggregatePresentation(entry)") < patch_block.index("return")


# ── DOMContentLoaded ──────────────────────────────────────────


def test_dom_content_loaded_starts_inventory_event_stream() -> None:
    js = _read_app_js()
    # The DOMContentLoaded async handler near the bottom of
    # app.js wires startInventoryEventStream() AFTER loadTree
    # so the snapshot can populate the just-rendered cells.
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "await loadTree();" in handler_block
    assert "startInventoryEventStream();" in handler_block
    # Order matters — start the stream after the initial render
    # so applyCellPatch has cells to mutate.
    assert handler_block.index("await loadTree();") < handler_block.index(
        "startInventoryEventStream();"
    )


def test_dom_content_loaded_starts_index_progress_before_load_tree() -> None:
    js = _read_app_js()
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "startIndexProgressPolling();" in handler_block
    assert "await loadTree();" in handler_block
    assert handler_block.index("startIndexProgressPolling();") < handler_block.index(
        "await loadTree();"
    )


def test_index_progress_polling_uses_lightweight_progress_endpoint() -> None:
    js = _read_app_js()
    fn_start = js.index("function refreshIndexProgress(force)")
    fn_block = js[fn_start : fn_start + 2000]
    assert 'fetch("/api/index/progress"' in fn_block
    assert 'cache: "no-store"' in fn_block
    assert '"If-None-Match"' not in fn_block
    assert "indexProgressEtag" not in js
    assert "resp.status === 304" in fn_block


def test_index_progress_completion_refreshes_pending_tallies() -> None:
    js = _read_app_js()
    assert "function refreshTreeIfPendingTallies()" in js
    fn_start = js.index("function refreshTreeIfPendingTallies()")
    fn_block = js[fn_start : fn_start + 900]
    assert 'document.querySelector("#tab-files .tally-pending")' in fn_block
    tree_refresh = fn_block.index("await loadTree();")
    current_recency = fn_block.index("filterState.get().recency")
    assert tree_refresh < current_recency
    assert "loadRecent(recency);" in fn_block

    progress_start = js.index("async function refreshIndexProgress(force)")
    progress_block = js[progress_start : progress_start + 2000]
    assert "await refreshTreeIfPendingTallies();" in progress_block
    assert progress_block.index("renderIndexProgress(meta);") < progress_block.index(
        "await refreshTreeIfPendingTallies();"
    )


def test_pending_tally_watchdog_is_wired_to_client_and_server_logging() -> None:
    js = _read_app_js()
    assert "MetabrowserPendingTallyDiagnostics.create" in js
    assert "Folder totals are still loading after ${delaySeconds} seconds" in js
    assert 'fetch("/api/diagnostics/pending-tallies"' in js
    assert "reconcilePendingTallyDiagnostics();" in js


def test_pending_tally_recovery_rechecks_recency_after_tree_refresh() -> None:
    """A filter change during the tree request must win over its old window."""

    js = _read_app_js()
    start = js.index("async function refreshAfterPendingTallyDiagnostic")
    block = js[start : js.index("async function reportPendingTallyDiagnostic", start)]
    tree_refresh = block.index("await loadTree();")
    current_recency = block.index("filterState.get().recency")
    assert tree_refresh < current_recency
    assert "loadRecent(recency);" in block


def test_load_tree_renders_single_file_tally() -> None:
    """The root file count + total bytes render once, in the scrollable
    tree-summary row above the file tree. The header-stats line that
    duplicated the same totals below the top-level path was removed (it
    showed twice). During an active scan (envelope
    `tally_cache_status === "scanning"`) the summary forces a pending
    state instead of a partial "0 files / 0 B" snapshot."""

    js = _read_app_js()
    fn_start = js.index("async function loadTree()")
    fn_block = js[fn_start : js.index("function treeSummaryHtml", fn_start)]
    summary_start = js.index("function treeSummaryHtml")
    summary_block = js[
        summary_start : js.index("function scheduleRootSummaryRefresh", summary_start)
    ]
    # The single tally lives in the tree-summary row.
    assert (
        'var stableSummary = data.tally_cache_status === "scanning" ? null : data.summary;'
        in fn_block
    )
    assert "treeSummaryHtml(stableSummary, summaryFiles, summarySize)" in fn_block
    assert '"tree-summary"' in summary_block
    assert "tree-summary-count" in summary_block
    assert "tree-summary-size" in summary_block
    # The duplicate header tally must not come back.
    assert "updateHeaderStats" not in js
    assert "header-stats" not in js
    # The scanning-state pending gate stays.
    assert 'data.tally_cache_status === "scanning"' in fn_block
    scanning_start = fn_block.index('if (data.tally_cache_status === "scanning")')
    scanning_end = fn_block.index("// Carry aggregates", scanning_start)
    assert "startIndexProgressPolling();" in fn_block[scanning_start:scanning_end]


def test_styles_css_has_no_duplicate_header_stats() -> None:
    css = _read_styles_css()
    assert ".header-stat" not in css


def test_lazy_subtree_keeps_spinner_for_scanning_empty_subtree() -> None:
    js = _read_app_js()
    assert "function treeLazyLoadingHtml(message)" in js
    assert 'class="spinner spinner-sm"' in js
    assert "const subtreeRetryTimers = new WeakMap()" in js


def test_render_index_progress_gates_count_on_positive_value() -> None:
    """``renderIndexProgress`` shows ``"Scanning…"`` until the scan reports
    a positive ``indexed_files`` count; rendering ``"~0 files scanned"``
    reads as a stuck scan.
    """

    js = _read_app_js()
    fn_start = js.index("function renderIndexProgress(meta)")
    fn_block = js[fn_start : fn_start + 2000]
    # Positive-count gate present.
    assert "rawFiles > 0" in fn_block
    # The "Scanning…" label is the fallback when no positive count exists.
    assert '"Scanning…"' in fn_block or "'Scanning…'" in fn_block


def test_enhance_after_optional_asset_only_runs_highlight() -> None:
    """Optional visual libraries must not trigger a second document render."""

    js = _read_app_js()
    fn_start = js.index("function enhanceCurrentFileAfterOptionalAsset()")
    fn_block = js[fn_start : fn_start + 160]
    assert "highlightCode();" in fn_block
    assert "renderFile(" not in fn_block


def test_user_visible_strings_dropped_crawling_label() -> None:
    """The user-visible UI says ``"scanning"`` everywhere; ``"crawling"``
    was the previous label. Asserting absence pins the
    rename so a partial revert is caught here.
    """

    js = _read_app_js()
    css = _read_styles_css()
    for haystack, label in [(js, "app.js"), (css, "styles.css")]:
        assert "Crawling" not in haystack, f"{label} still contains 'Crawling'"
        assert "crawling" not in haystack, f"{label} still contains 'crawling'"

    fn_start = js.index("async function loadSubtree(path, childrenEl, options)")
    fn_block = js[fn_start : fn_start + 2200]
    assert 'childrenEl.innerHTML = treeLazyLoadingHtml("Loading folder…")' in fn_block
    assert 'data.tally_cache_status === "scanning"' in fn_block
    assert 'treeLazyLoadingHtml("Still scanning this folder…")' in fn_block
    assert "scheduleSubtreeRetry(path, childrenEl)" in fn_block
    assert fn_block.index('data.tally_cache_status === "scanning"') < fn_block.index(
        "subtreeCache.set(path, tree)"
    )


def test_lazy_subtree_reports_failures_without_plain_failed_load() -> None:
    js = _read_app_js()
    fn_start = js.index("async function loadSubtree(path, childrenEl, options)")
    fn_block = js[fn_start : fn_start + 2400]
    assert "if (!resp.ok)" in fn_block
    assert "throw new Error(`HTTP ${resp.status}`)" in fn_block
    assert "treeLazyFailureHtml(" in fn_block
    assert "Could not load this folder. Collapse and reopen it to try again." in fn_block
    assert "Failed to load</div>" not in fn_block


def test_inserted_rows_clear_lazy_placeholder() -> None:
    js = _read_app_js()
    fn_start = js.index("function _insertRowSorted(container, entry, options)")
    fn_block = js[fn_start : fn_start + 1000]
    assert 'querySelectorAll(":scope > .tree-lazy-placeholder")' in fn_block
    assert "el.remove()" in fn_block


def test_index_progress_updates_by_file_count_bucket() -> None:
    js = _read_app_js()
    assert "INDEX_PROGRESS_UPDATE_FILES" in js
    fn_start = js.index("function shouldRenderIndexProgress(meta, force)")
    fn_block = js[fn_start : fn_start + 1000]
    assert "indexProgressBucket(meta.indexed_files)" in fn_block


def test_styles_css_defines_index_progress_footer() -> None:
    css = _read_styles_css()
    assert ".index-progress {" in css
    assert ".index-progress-spinner {" in css
    assert ".tree-lazy-error {" in css
    spinner_start = css.index(".index-progress-spinner {")
    spinner_block = css[spinner_start : spinner_start + 400]
    assert "border: 2px solid var(--spinner-track)" in spinner_block
    assert "border-top-color: var(--spinner-accent)" in spinner_block
    assert "animation: spin 0.8s linear infinite" in spinner_block
    assert "var(--link)" not in spinner_block
    assert "@keyframes index-progress-spin" not in css


def test_progress_spinners_use_neutral_gray_tokens() -> None:
    css = _read_styles_css()
    design_system = _read_design_system_md()

    assert "--spinner-track: hsl(0 0% 90%)" in css
    assert "--spinner-accent: hsl(0 0% 55%)" in css
    assert "--spinner-mini-track: hsl(0 0% 87%)" in css
    assert "--spinner-mini-accent: hsl(0 0% 55%)" in css
    assert "--spinner-mini-accent: hsl(39" not in css
    assert "Progress Spinners Stay Neutral" in design_system


# ── CSS skeleton tokens ───────────────────────────────────────


def test_styles_css_defines_tally_skeleton_bg_token() -> None:
    css = _read_styles_css()
    # :root token exists.
    assert "--tally-skeleton-bg:" in css


def test_styles_css_defines_tally_pending_class() -> None:
    css = _read_styles_css()
    # Rule body present and references the token.
    assert ".tally-pending {" in css
    assert "var(--tally-skeleton-bg)" in css
    # Slow opacity pulse, not a spinner.
    assert "@keyframes tally-pending-pulse" in css
    # Narrow variant for inline age cells.
    assert ".tally-pending.tally-pending-narrow {" in css
    assert ".tip-loading {" in css


# ── Activity poll fallback retained ──────────────────────────


def test_activity_polling_retired_in_favor_of_fs_change_ops() -> None:
    """The SPA no longer polls /api/activity; the inventory's
    background ActiveFileTracker emits fs.change ops with
    active/labels populated, mirrored into activeFiles via
    _mirrorActiveFromFsEntry."""

    js = _read_app_js()
    # No setInterval kicking pollActivity, no fetch("/api/activity").
    assert "setInterval(pollActivity" not in js
    assert 'fetch("/api/activity")' not in js
    # The new path: fs.change → _mirrorActiveFromFsEntry → active set.
    assert "_mirrorActiveFromFsEntry" in js
    assert "function refreshActivityBadge(path)" in js


def test_mirror_active_from_fs_entry_handles_transitions() -> None:
    """active→inactive flips trigger cache invalidation; the
    inactive→active flip switches the header badge to Live and
    can open a live stream. These behaviours moved out of
    pollActivity into the fs.change pipe."""

    js = _read_app_js()
    fn_start = js.index("function _mirrorActiveFromFsEntry(entry)")
    fn_block = js[fn_start : fn_start + 5000]
    # Inactive→active: switch badge + maybeOpenLiveStream
    assert "badge-running" in fn_block
    assert "maybeOpenLiveStream" in fn_block
    # Active→inactive: cache invalidation + revalidate
    assert "fileNeedsRevalidate.add" in fn_block


# ── Renderer filesystem-entry live update path ────────────────


def test_compute_cell_patch_returns_each_filesystem_row_shape() -> None:
    """Pre-fix, ``computeCellPatch`` returned ``null`` for any
    entry whose ``type !== "dir"`` — so file ops were silently
    dropped by ``applyCellPatch``. The fix routes file entries
    through their own patch shape (size + age + active class)."""

    js = _read_app_js()
    fn_start = js.index("function computeCellPatch(entry, options)")
    fn_block = js[fn_start : fn_start + 2500]
    # Each inventory type returns its own populated patch object.
    assert 'kind: "dir"' in fn_block
    assert 'kind: "symlink"' in fn_block
    assert 'kind: "file"' in fn_block


def test_apply_cell_patch_handles_every_tree_row_type() -> None:
    """Pre-fix, ``applyCellPatch`` only looked up
    ``.tree-folder[data-path=…]``. The fix picks the right
    selector by entry.type so existing file rows update on touch."""

    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 3000]
    assert ".tree-folder[data-path=" in fn_block
    assert ".tree-symlink[data-path=" in fn_block
    assert ".tree-file[data-path=" in fn_block
    assert "computeCellPatch(entry, treeRenderOptionsForElement(row))" in fn_block


def test_apply_cell_patch_replaces_a_stale_differently_typed_row() -> None:
    """A watcher may report file-to-link replacement as one upsert.

    The old row must leave synchronously so path de-duplication cannot reject
    the replacement. Former folders also lose their rendered child container.
    """

    js = _read_app_js()
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 1800]
    assert 'queryHtmlAll(`.tree-item[data-path="${safePath}"]`)' in fn_block
    assert "pathRows.length !== rows.length || removingRow" in fn_block
    assert "_removeRenderedRowsImmediately(entry.path)" in fn_block

    remove_start = js.index("function _removeRenderedRowsImmediately(path)")
    remove_block = js[remove_start : remove_start + 800]
    assert "tree-folder" in remove_block
    assert "tree-children" in remove_block
    assert "row.remove()" in remove_block


def test_apply_cell_patch_inserts_new_rows_under_expanded_parent() -> None:
    """When the entry's parent is rendered AND expanded, a new
    row is inserted in sorted position. Locks in the helper
    functions that compose this."""

    js = _read_app_js()
    # Helpers exist:
    assert "function _findChildContainerFor(parentRel, panelEl)" in js
    assert "function _insertRowSorted(container, entry, options)" in js
    assert "function _buildRowHtml(entry, options)" in js
    # applyCellPatch references them when no row exists.
    fn_start = js.index("function applyCellPatch(entry)")
    fn_block = js[fn_start : fn_start + 5000]
    assert "_findChildContainerFor" in fn_block
    assert "_insertRowSorted" in fn_block
    assert "_insertRowSorted(container, entry, treeRenderOptionsForElement(panel))" in fn_block


def test_remove_rendered_rows_is_called_from_fs_change_remove_branch() -> None:
    """The remove branch in ``fileStoreApplyChange`` must drop
    the rendered row(s) for the path (and any descendant rows
    when a folder is removed)."""

    js = _read_app_js()
    assert "function _removeRenderedRows(path)" in js
    fn_start = js.index("function fileStoreApplyChange(ops)")
    fn_block = js[fn_start : fn_start + 1500]
    assert "_removeRenderedRows(op.path)" in fn_block


def test_insert_row_sorted_respects_dirs_first_then_name_order() -> None:
    """The walker and ``_dir_tree`` both order children dirs-first
    then by name; the live insert path must match so a freshly
    inserted file lands in the same position the next ``/api/tree``
    fetch would put it."""

    js = _read_app_js()
    fn_start = js.index("function _treeSortKey(node)")
    fn_block = js[fn_start : fn_start + 600]
    # dirs map to 0, files to 1 — the comparator yields dirs first.
    assert 'node.type === "dir" ? 0 : 1' in fn_block


def test_remove_rendered_rows_drops_descendant_subtree_on_folder_remove() -> None:
    """When a directory row is removed, its sibling
    ``.tree-children`` subtree must go too — otherwise the rows
    remain visible (as orphans) even though the FileStore Map has
    dropped them."""

    js = _read_app_js()
    fn_start = js.index("function _removeRenderedRows(path)")
    fn_block = js[fn_start : fn_start + 800]
    assert "tree-folder" in fn_block
    assert "tree-children" in fn_block
    assert ".remove()" in fn_block


# ── Walker truncation banner ──────────────────────────────────


def test_load_tree_renders_truncation_banner_when_status_truncated() -> None:
    """When ``/api/tree`` returns ``tally_cache_status="truncated"``
    the SPA paints a banner above the tree summary so the user
    knows the walker hit ``INVENTORY_MAX_FILES`` and the tree is
    partial."""

    js = _read_app_js()
    fn_start = js.index("async function loadTree()")
    fn_block = js[fn_start : fn_start + 5000]
    assert 'data.tally_cache_status === "truncated"' in fn_block
    assert "treeTruncationNoteHtml(data.tally_cache_max_files)" in fn_block
    assert "tree-truncation-note" in js
    assert "Bump <code>INVENTORY_MAX_FILES</code>" not in fn_block
    assert "function treeTruncationNoteHtml(maxFiles)" in js
    assert "File list incomplete." in js
    assert "some files and folders are not shown." in js


def test_index_progress_completion_inserts_truncation_banner() -> None:
    js = _read_app_js()
    fn_start = js.index("async function refreshIndexProgress(force)")
    fn_block = js[fn_start : fn_start + 2500]
    assert "meta?.truncated" in fn_block
    assert "ensureTreeTruncationNote(meta.max_files)" in fn_block


def test_styles_css_defines_tree_truncation_note() -> None:
    """The truncation banner ships its own CSS rule."""

    css = _read_styles_css()
    assert ".tree-truncation-note {" in css


def test_tree_pane_allows_selection_for_informational_text() -> None:
    """The nav pane contains warnings and status text that users may
    need to copy. Selection should be disabled on clickable controls,
    not inherited by every child of ``.tree-pane``."""

    css = _read_styles_css()
    tree_pane_start = css.index(".tree-pane {")
    tree_pane_block = css[tree_pane_start : css.index("}", tree_pane_start)]
    truncation_start = css.index(".tree-truncation-note {")
    truncation_block = css[truncation_start : css.index("}", truncation_start)]
    assert "user-select" not in tree_pane_block
    assert "user-select" not in truncation_block


def test_clickable_nav_controls_disable_selection() -> None:
    css = _read_styles_css()
    for selector in (".tree-item {", ".tree-page-more {", ".tab-btn {"):
        start = css.index(selector)
        block = css[start : css.index("}", start)]
        assert "user-select: var(--toggle-user-select);" in block


def test_text_selection_rule_is_documented_in_design_system() -> None:
    css = _read_styles_css()
    design_doc = _read_design_system_md()
    assert "Informational text" in css
    assert "Never put `user-select: none` on a container" in css
    assert "Text selection is content behavior" in design_doc
    assert "Do not set `user-select: none` on a broad container" in design_doc
