"""Shared rendering helpers must stay on ``window.metabrowser``.

Helpers moved from app.js into plugin-sdk.js so the built-in plugins
(and any external plugin) can call them via ``mb.<helper>(...)``
instead of duplicating the body. Unit-style assertions here check the
SDK source for the public surface; runtime behaviour is covered by
the JSDOM shim end-to-end test (see tests/dom/).

Surface checked:
- mb.escapeHtml, mb.formatSize, mb.formatTimestamp (already shipped)
- mb.countClass, mb.sizeClass, mb.sizeHtml, mb.isLargeTextPreview
- mb.highlightSyntax (bounded DOM-free Highlight.js token data)
- mb.renderSourceView (shared generic Source surface)
- mb.wrapWithCopy (new in 3b)
- mb.icons proxy (new in 3b — backed by window.MetabrowserIcons)
- mb.perf.measure (contributes to the shared performance recorder)
- mb.fetchKpressRender (KPress document fragment fetch + diagnostics)
- mb.renderTextTruncationWarning (visible partial-content warning)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from devtools import check_startup_scripts
from tests.required_tools import require_node

TESTS = Path(__file__).resolve().parent
STATIC = TESTS.parent / "src" / "metabrowser" / "static"
# The SDK is two scripts: the startup one, and the helpers a view's renderer calls,
# which load with the view compositor and before any plugin's code.
SDK_JS = (STATIC / "plugin-sdk.js", STATIC / "plugin-sdk-views.js")
VIEW_HELPERS_SESSION = TESTS / "dom" / "plugin-view-helpers-session.js"
STYLESHEET = "link rel=stylesheet /plugin-static/fixture-kind/styles.css"
MODULE_PRELOAD = "link rel=modulepreload <the plugin's module>"
VIEW_HELPERS = "script /static/plugin-sdk-views.js"


def _sdk_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SDK_JS)


@pytest.fixture(scope="module")
def view_helpers() -> dict[str, Any]:
    result = subprocess.run(
        [require_node(), str(VIEW_HELPERS_SESSION)],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return cast("dict[str, Any]", json.loads(result.stdout))


def test_view_helpers_are_no_startup_script() -> None:
    # A view's renderer calls these and the first tree does not, so the shell must not
    # fetch them before it paints: they are an on-demand bundle of one file.
    html = check_startup_scripts.render_folder_shell()
    startup = check_startup_scripts.startup_script_paths(html)
    assert "/static/plugin-sdk.js" in startup
    assert "/static/plugin-sdk-views.js" not in startup
    bundles = json.loads(
        html.split("window.METABROWSER_ASSET_BUNDLES=", 1)[1].split(";</script>", 1)[0]
    )
    assert [entry["src"].partition("?")[0] for entry in bundles["sdk-views"]] == [
        "/static/plugin-sdk-views.js"
    ]


def test_a_plugin_finds_every_view_helper_wherever_its_code_runs(
    view_helpers: dict[str, Any],
) -> None:
    # tests/dom/plugin-view-helpers-session.js loads a third-party plugin through
    # ensureKindAssets with no compositor, as the commit page and the pull-request page
    # load theirs. Its whole output is pinned by cli-ui-plugin-view-helpers.tryscript.md.
    loaded = view_helpers["withoutACompositor"]
    # The startup script keeps none of the helpers, or the move saved nothing.
    assert loaded["helpersBefore"] == "0 of 9"
    assert loaded["helpersAfter"] == "9 of 9"
    # The plugin's stylesheet and module are on the wire beside the helpers, not a
    # round trip after them, and none of its code has run while they are.
    assert loaded["requestedTogether"] == [STYLESHEET, MODULE_PRELOAD, VIEW_HELPERS]
    assert loaded["whileWaiting"] == {"loading": "pending", "pluginCode": []}
    # A documented helper works while the module evaluates, in a view's render, and in
    # a handler: the three places a plugin's code runs.
    assert loaded["pluginCode"][:3] == [
        "module evaluation: a Source view with a gutter of 1 lines",
        "render: a Source view with a gutter of 2 lines",
        "click handler: a Source view with a gutter of 3 lines",
    ]
    # Once they are there, another plugin's load asks only for its own assets.
    assert loaded["aSecondPlugin"]["loading"] == "resolved"
    assert VIEW_HELPERS not in loaded["aSecondPlugin"]["requested"]
    assert len(loaded["aSecondPlugin"]["requested"]) == 2


def test_no_plugin_code_runs_without_the_view_helpers(view_helpers: dict[str, Any]) -> None:
    refused = view_helpers["whenTheHelpersCannotBeFetched"]
    # The caller is told, so it can say what failed; the plugin did not run half-armed.
    assert refused["afterFailure"] == {
        "loading": "rejected: Failed to load asset: /static/plugin-sdk-views.js",
        "pluginCode": [],
        "viewRegistered": False,
    }
    # Asking again fetches what failed and nothing twice, and then the plugin runs once.
    assert refused["retry"] == {
        "requested": [VIEW_HELPERS],
        "loading": "resolved",
        "pluginCode": ["module evaluation: a Source view with a gutter of 1 lines"],
    }


# The shell's prefetch chain, as the server wrote it into the page, run to its end with
# every script answering at once. It reports whether the flag was already set when the
# terminal event was dispatched.
_RUN_PREFETCH_CHAIN = """
const vm = require("node:vm");
const seen = [];
const sandbox = {
  console,
  document: {
    readyState: "complete",
    createElement: () => ({}),
    head: { appendChild(script) { queueMicrotask(() => script.onload()); } },
  },
  CustomEvent: class { constructor(type) { this.type = type; } },
  Event: class { constructor(type) { this.type = type; } },
  dispatchEvent(event) {
    if (event.type === "metabrowser:optional-assets-loaded") {
      seen.push(sandbox.METABROWSER_OPTIONAL_ASSETS_SETTLED === true);
    }
    return true;
  },
  setTimeout: (run) => queueMicrotask(run),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(process.argv[1], sandbox);
setImmediate(() => process.stdout.write(JSON.stringify({ flagWhenAnnounced: seen })));
"""


def test_the_prefetch_chain_records_its_end_before_announcing_it() -> None:
    # The syntax service waits on the optional assets' terminal event. It loads with
    # the first view, which can be after that event fired, so the chain leaves a flag
    # behind it and sets the flag first: a listener that runs on the event and one that
    # arrives later read the same answer. tests/dom/syntax-token-sdk-behavior.js runs
    # the service's half.
    html = check_startup_scripts.render_folder_shell()
    blocks = [block for block in html.split("<script>")[1:] if "optional-assets-loaded" in block]
    assert len(blocks) == 1
    chain = blocks[0].split("</script>", 1)[0]
    result = subprocess.run(
        [require_node(), "-e", _RUN_PREFETCH_CHAIN, chain],
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == {"flagWhenAnnounced": [True]}


def test_sdk_exports_size_html() -> None:
    src = _sdk_source()
    assert "sizeHtml: sizeHtml" in src, "sizeHtml should be exposed on window.metabrowser"
    assert "function sizeHtml" in src


def test_sdk_exports_is_large_text_preview() -> None:
    src = _sdk_source()
    assert "isLargeTextPreview: isLargeTextPreview" in src
    assert "SYNTAX_HIGHLIGHT_MAX_BYTES" in src


def test_sdk_exports_highlight_syntax() -> None:
    src = _sdk_source()
    assert "highlightSyntax: highlightSyntax" in src
    assert "async function highlightSyntax" in src


def test_sdk_exports_shared_source_renderer() -> None:
    src = _sdk_source()
    assert "renderSourceView: renderSourceView" in src
    assert "function renderSourceView" in src


def test_sdk_exports_wrap_with_copy() -> None:
    src = _sdk_source()
    assert "wrapWithCopy: wrapWithCopy" in src
    # wrapWithCopy emits a button with no inline handler; a delegated
    # click listener installed at SDK init handles .content-copy-btn clicks.
    assert "content-copy-btn" in src
    assert 'onclick="copyContent(this)"' not in src
    assert "_copyDelegationInstalled" in src


def test_sdk_exports_source_kind() -> None:
    src = _sdk_source()
    assert "sourceKind: sourceKind" in src
    assert "function sourceKind" in src
    assert 'global.METABROWSER_SOURCE_KIND === "git_revision"' in src


def test_sdk_exports_icons_proxy() -> None:
    src = _sdk_source()
    assert "icons: icons" in src
    # The proxy must read from window.MetabrowserIcons so plugins get the
    # canonical SVGs, not their own copies.
    assert "MetabrowserIcons" in src


def test_sdk_exports_file_type_icon_proxy() -> None:
    src = _sdk_source()
    assert "fileTypeIcon: fileTypeIcon" in src
    assert "function fileTypeIcon" in src
    assert "MetabrowserFileTypes.iconFor" in src
    assert 'typeof icon.cls === "string"' in src


def test_sdk_exports_perf_measure() -> None:
    src = _sdk_source()
    assert "perf: perf" in src
    assert "measure(_label, fn)" in src


def test_sdk_fetch_plugin_data_throws_on_degraded_plugin_error() -> None:
    src = _sdk_source()
    assert 'data.type === "plugin_error"' in src
    assert "Plugin data hook failed" in src


def test_sdk_exports_kpress_render_helper() -> None:
    src = _sdk_source()
    assert "fetchKpressRender: fetchKpressRender" in src
    assert "function formatKpressError" in src
    assert 'new URL("/api/kpress/render"' in src
    assert 'url.searchParams.set("path", path)' in src
    assert 'url.searchParams.set("view", viewId || "document")' in src
    assert 'url.searchParams.set("profile", profile)' in src
    assert "data-kpress-asset" in src
    assert '"kpress-asset-manifest-v2"' in src
    assert 'loading === "classic"' in src
    assert 'script.type = "importmap"' in src
    assert "_loadedKpressAssets" in src


def test_sdk_exports_clear_truncation_warning() -> None:
    src = _sdk_source()
    assert "renderTextTruncationWarning: renderTextTruncationWarning" in src
    assert "function renderTextTruncationWarning" in src
    # The notice names the condition plainly and reports how much of the file
    # is showing. It was "Content truncated."; "Partial file." says the same
    # thing about the file rather than about the rendering.
    assert "Partial file." in src
    assert "Showing " in src
    assert "Printed output" not in src
    assert "complete source PDF" not in src
    assert "metabrowser-source-truncation-warning" in src


def test_truncation_banner_carries_its_own_load_more() -> None:
    """The notice that content is missing offers the remedy in place.

    It used to end "Select Load more to continue." and point at a control in
    the pane header, which is a different place from the explanation and is
    scrolled away by the time a reader wants it.
    """
    src = _sdk_source()
    assert "Select Load more to continue." not in src
    assert "function loadMoreButtonHtml" in src
    assert 'data-position="${position}"' in src


def test_sdk_exports_a_trailing_load_more_control() -> None:
    """Partial content is bracketed by the control that continues it.

    See docs/design-system.md, "Continuing partial content".
    """
    src = _sdk_source()
    assert "renderTextLoadMoreFooter: renderTextLoadMoreFooter" in src
    assert "function renderTextLoadMoreFooter" in src
    assert "metabrowser-source-more-footer" in src
    # Both ends read the same payload, so they cannot disagree about whether
    # more remains.
    assert "function textPreviewProgress" in src


def test_sdk_size_html_handles_null_skeleton() -> None:
    """Walker emits null aggregates while finalizing; sizeHtml should
    paint a skeleton cell (matches the shell's existing convention)."""
    src = _sdk_source()
    # The null-handling branch must produce a 'tally-pending' span for
    # in-flight aggregates (matches app.js behaviour pre-promotion).
    assert "tally-pending" in src


def test_sdk_exports_shared_metric_emphasis_classes() -> None:
    """Plugins use the same count and byte emphasis contract as the shell."""
    src = _sdk_source()
    assert "countClass: countClass" in src
    assert "sizeClass: sizeClass" in src
    assert "MetabrowserFormatters.countClass" in src
    assert "MetabrowserFormatters.sizeClass" in src
