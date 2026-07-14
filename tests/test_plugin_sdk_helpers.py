"""Phase 3b — promoted shared rendering helpers must be on window.metabrowser.

Helpers moved from app.js into plugin_sdk.js so the built-in plugins
(and any external plugin) can call them via ``mb.<helper>(...)``
instead of duplicating the body. Unit-style assertions here check the
SDK source for the public surface; runtime behaviour is covered by
the JSDOM shim end-to-end test (see tests/dom/).

Surface checked:
- mb.escapeHtml, mb.formatSize, mb.formatTimestamp (already shipped)
- mb.sizeHtml, mb.isLargeTextPreview (new in 3b)
- mb.wrapWithCopy (new in 3b)
- mb.icons proxy (new in 3b — backed by window.MetabrowserIcons)
- mb.perf.measure (new in 3b — wraps app.js's _mbPerf)
- mb.fetchKpressRender (KPress document fragment fetch + diagnostics)
- mb.renderTextTruncationWarning (print-visible partial source warning)
"""

from __future__ import annotations

from pathlib import Path

SDK_JS = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "plugin_sdk.js"


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


def test_sdk_exports_wrap_with_copy() -> None:
    src = _sdk_source()
    assert "wrapWithCopy: wrapWithCopy" in src
    # Plugins emit onclick="copyContent(this)" — verify the helper still
    # produces that handler (copyContent lives in app.js for now; plugins
    # fire it at click time).
    assert 'onclick="copyContent(this)"' in src


def test_sdk_exports_icons_proxy() -> None:
    src = _sdk_source()
    assert "icons: icons" in src
    # The proxy must read from window.MetabrowserIcons so plugins get the
    # canonical SVGs, not their own copies.
    assert "MetabrowserIcons" in src


def test_sdk_exports_perf_measure() -> None:
    src = _sdk_source()
    assert "perf: perf" in src
    assert "measure(label, fn)" in src


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
    assert 'script.type = "module"' in src
    assert "_loadedKpressAssets" in src


def test_sdk_exports_print_visible_truncation_warning() -> None:
    src = _sdk_source()
    assert "renderTextTruncationWarning: renderTextTruncationWarning" in src
    assert "function renderTextTruncationWarning" in src
    assert "Source preview truncated." in src
    assert "metabrowser-source-truncation-warning" in src


def test_sdk_size_html_handles_null_skeleton() -> None:
    """Walker emits null aggregates while finalizing; sizeHtml should
    paint a skeleton cell (matches the shell's existing convention)."""
    src = _sdk_source()
    # The null-handling branch must produce a 'tally-pending' span for
    # in-flight aggregates (matches app.js behaviour pre-promotion).
    assert "tally-pending" in src


def test_sdk_size_html_uses_size_class_threshold() -> None:
    """1 MiB threshold defines size-large vs normal class — same as app.js."""
    src = _sdk_source()
    assert "size-large" in src
    assert "1024 * 1024" in src
