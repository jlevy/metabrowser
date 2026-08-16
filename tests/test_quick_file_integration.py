"""Structural integration checks for the client-side quick-file finder.

The search modules have focused JavaScript behavior tests. These checks protect the
application-shell seams that feed those modules and route an accepted result through
the existing preview navigation path.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _render_index_html() -> str:
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


def test_quick_file_assets_load_in_dependency_order_before_app() -> None:
    html = _render_index_html()
    asset_paths = (
        "/static/known_file_catalog.js",
        "/static/catalog_feed.js",
        "/static/file_fuzzy_match.js",
        "/static/search_controller.js",
        "/static/search_palette.js",
        "/static/app.js",
    )
    positions = []
    for asset_path in asset_paths:
        assert f'src="{asset_path}?v=' in html
        positions.append(html.index(asset_path))
    assert positions == sorted(positions)


def test_preview_is_a_programmatic_focus_destination() -> None:
    html = _render_index_html()
    assert 'id="preview-pane" data-kpress-viewport tabindex="-1"' in html


def test_application_initializes_one_injected_quick_file_finder() -> None:
    js = _read_app_js()
    init_start = js.index("function initQuickFileFinder()")
    init_block = js[init_start : init_start + 2600]
    assert "MetabrowserKnownFileCatalog.create()" in init_block
    assert "MetabrowserSearch.createController" in init_block
    assert "MetabrowserSearch.createLocalFileProvider" in init_block
    assert "registerProvider(localProvider)" in init_block
    assert "MetabrowserSearchPalette.create" in init_block
    assert "getCatalogSnapshot" in init_block
    assert "getFileIcon" in init_block
    assert "openFile" in init_block
    assert "onNotFound" in init_block

    loaded_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    loaded_block = js[loaded_start:]
    assert loaded_block.index("initQuickFileFinder();") < loaded_block.index("selectFile(")
    assert loaded_block.count("initQuickFileFinder();") == 1


def test_every_browser_observation_seam_feeds_the_known_file_catalog() -> None:
    js = _read_app_js()

    load_tree = js[
        js.index("async function loadTree()") : js.index("function treeTruncationNoteHtml")
    ]
    assert "knownFileCatalog?.observeInitialTree(data.tree)" in load_tree
    assert load_tree.index("observeInitialTree") < load_tree.index('"renderTreeNodes:root"')

    # Lazily fetched rows are observed in fetchSubtree, so a subtree pulled in
    # by the idle prefetch reaches the catalog the same as an expanded one.
    fetch_subtree = js[
        js.index("function fetchSubtree(path)") : js.index("async function loadSubtree(")
    ]
    assert "knownFileCatalog?.observeLazyTree(data.tree)" in fetch_subtree
    assert fetch_subtree.index("observeLazyTree") < fetch_subtree.index(
        "subtreeCache.set(path, data.tree)"
    )

    recent = js[
        js.index("function fetchRecent(windowKey)") : js.index("function renderRecentFromBase()")
    ]
    assert "knownFileCatalog?.observeRecent(flat)" in recent
    assert recent.index("observeRecent") < recent.index("renderRecentFromBase();")

    snapshot = js[
        js.index("function fileStoreApplySnapshot(scope, entries)") : js.index(
            "function fileStoreApplyChange(ops)"
        )
    ]
    assert "knownFileCatalog?.observeEventSnapshot(entries)" in snapshot

    changes = js[
        js.index("function fileStoreApplyChange(ops)") : js.index("// Mirror entry.active")
    ]
    assert "knownFileCatalog?.applyEventChange(ops)" in changes

    resync_start = js.index('addEventListener("fs.resync_required"')
    resync_block = js[resync_start : resync_start + 700]
    assert "knownFileCatalog?.clear()" in resync_block

    outcome_start = js.index("function openedFileOutcome(path, data, preview)")
    outcome_block = js[outcome_start : outcome_start + 700]
    assert "knownFileCatalog?.observeNavigation" in outcome_block
    assert 'data.kind !== "folder"' in outcome_block


def test_catalog_feed_is_wired_into_every_stream_signal() -> None:
    """The complete-coverage feed rides the existing stream: deltas
    via ``catalog.change``, refetch on the sentinel snapshot and on
    resync, terminal coverage via ``capability.update``, and the bulk
    fetch starting only once the stream is subscribed (first open;
    the no-EventSource degradation path starts it directly)."""

    js = _read_app_js()

    snapshot_start = js.index('addEventListener("fs.snapshot"')
    snapshot_block = js[snapshot_start : js.index('addEventListener("fs.change"')]
    assert "quickFileCatalogFeed?.onSentinelSnapshot()" in snapshot_block

    change_start = js.index('addEventListener("catalog.change"')
    change_block = js[change_start : change_start + 400]
    assert "quickFileCatalogFeed?.onCatalogChange(data)" in change_block

    capability_start = js.index('addEventListener("capability.update"')
    capability_block = js[capability_start : capability_start + 900]
    assert "quickFileCatalogFeed?.onIndexComplete(data.index.truncated === true)" in (
        capability_block
    )
    assert "data.index.complete === true" in capability_block
    # A capped walk is terminal and must repair membership, but the callback
    # receives its truncated state so it cannot promote root coverage.
    assert "data.index.truncated !== true" not in capability_block

    resync_start = js.index('addEventListener("fs.resync_required"')
    resync_block = js[resync_start : resync_start + 700]
    assert "quickFileCatalogFeed?.onResync()" in resync_block
    # The catalog clears before the feed refetches, not after.
    assert resync_block.index("knownFileCatalog?.clear()") < resync_block.index("onResync")

    onopen_start = js.index("inventoryEventSource.onopen")
    onopen_block = js[onopen_start : onopen_start + 700]
    assert "quickFileCatalogFeed?.start()" in onopen_block

    degraded_start = js.index("function startInventoryEventStream()")
    degraded_block = js[degraded_start : degraded_start + 600]
    assert "quickFileCatalogFeed?.start()" in degraded_block

    init_start = js.index("function initQuickFileFinder()")
    init_block = js[init_start : init_start + 1200]
    assert "window.MetabrowserCatalogFeed.create" in init_block


def test_navigation_returns_explicit_palette_outcomes_and_revalidates_hits() -> None:
    js = _read_app_js()
    select_file = js[
        js.index("async function selectFile(path, skipHistory, preferredViewId)") : js.index(
            "// ── File rendering"
        )
    ]
    for status in ("opened", "not-found", "error", "cancelled"):
        assert f'status: "{status}"' in select_file
    assert "resp.status === 404" in select_file

    navigate = js[
        js.index("async function navigateToPath(path, skipHistory, preferredViewId)") : js.index(
            "function initQuickFileFinder()"
        )
    ]
    assert "return selectFile(" in navigate

    init_start = js.index("function initQuickFileFinder()")
    init_block = js[init_start : init_start + 2600]
    assert "fileNeedsRevalidate.add(path)" in init_block
    assert "return navigateToPath(path)" in init_block
    assert "knownFileCatalog.removePath(path)" in init_block


def test_plugin_navigation_can_prefer_a_destination_view() -> None:
    """Folder visualizations can carry their view intent across navigation."""
    js = _read_app_js()
    sdk = (proc_browser.STATIC_DIR / "plugin_sdk.js").read_text()
    types = (proc_browser.STATIC_DIR / "types.d.ts").read_text()
    treemap = (
        proc_browser.STATIC_DIR.parent / "builtin_plugins" / "folder" / "treemap.js"
    ).read_text()

    assert "function openPath(path, options)" in sdk
    assert "viewId: viewId" in sdk
    assert "type MetabrowserOpenPathOptions" in types
    assert "openPath(path: string, options?: MetabrowserOpenPathOptions): void;" in types

    assert "async function selectFile(path, skipHistory, preferredViewId)" in js
    assert "function renderFile(data, preferredViewId)" in js
    assert "async function navigateToPath(path, skipHistory, preferredViewId)" in js
    listener_start = js.index('window.addEventListener("metabrowser:open-path"')
    listener = js[listener_start : listener_start + 500]
    assert "event.detail?.viewId" in listener
    assert "navigateToPath(path, undefined, viewId)" in listener

    render_start = js.index("function renderFile(data, preferredViewId)")
    render = js[render_start : render_start + 5000]
    assert "view.id === preferredViewId" in render
    assert "views.find((view) => view.default)" in render

    assert 'const TREEMAP_VIEW_ID = "treemap";' in treemap
    assert "mb.openPath(cell.path, { viewId: TREEMAP_VIEW_ID })" in treemap


def test_local_quick_file_modules_define_no_search_endpoint() -> None:
    for filename in (
        "known_file_catalog.js",
        "file_fuzzy_match.js",
        "search_controller.js",
        "search_palette.js",
    ):
        source = proc_browser.STATIC_DIR.joinpath(filename).read_text()
        assert "/api/search" not in source
