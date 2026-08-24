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
- mb.wrapWithCopy (new in 3b)
- mb.icons proxy (new in 3b — backed by window.MetabrowserIcons)
- mb.perf.measure (contributes to the shared performance recorder)
- mb.fetchKpressRender (KPress document fragment fetch + diagnostics)
- mb.renderTextTruncationWarning (visible partial-content warning)
"""

from __future__ import annotations

from pathlib import Path

SDK_JS = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "plugin-sdk.js"


def _sdk_source() -> str:
    return SDK_JS.read_text(encoding="utf-8")


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


def test_sdk_exports_wrap_with_copy() -> None:
    src = _sdk_source()
    assert "wrapWithCopy: wrapWithCopy" in src
    # wrapWithCopy emits a button with no inline handler; a delegated
    # click listener installed at SDK init handles .content-copy-btn clicks.
    assert "content-copy-btn" in src
    assert 'onclick="copyContent(this)"' not in src
    assert "_copyDelegationInstalled" in src


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
