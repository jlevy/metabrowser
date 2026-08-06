"""Metabrowser KPress print/theme shell contract tests."""

from __future__ import annotations

import asyncio
import re
from typing import Any, cast

from kpress.runtime import get_static_asset

from metabrowser import server as proc_browser

KPRESS_DOC_MIN_WIDTH_QUERY_RE = re.compile(r"@container kpress-doc \(min-width: [\d.]+rem\) \{")


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _read_styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text()


def _read_icons_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("icons.js").read_text()


def _render_index_html() -> str:
    class _FakeReq:
        def __init__(self) -> None:
            self.query_params: dict[str, str] = {}
            self.headers: dict[str, str] = {}

    resp = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    return resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else str(resp.body)


def test_app_shell_tracks_active_printable_view() -> None:
    src = _read_app_js()
    assert "function setActivePreviewView" in src
    assert "data-printable" in src
    assert "data-print-profile" in src
    assert "data-render-runtime" in src
    assert 'data-active-view="false"' in src
    assert 'id="print-view-btn"' in src
    assert "function printActiveView()" in src
    assert "window.print()" in src
    assert "setActivePreviewView(tabId, container)" in src


def test_icons_include_print_and_theme_controls() -> None:
    src = _read_icons_js()
    for icon in ("print", "monitor", "sun", "moon"):
        assert f"{icon}:" in src


def test_index_bootstraps_theme_before_app_paint() -> None:
    html = _render_index_html()
    assert '<meta name="color-scheme" content="light dark">' in html
    assert "metabrowser.themeMode" in html
    assert "data-theme-mode" in html
    assert "data-theme" in html
    assert "data-kpress-resolved-theme" in html
    assert html.index("/static/theme_state.js") < html.index("/static/plugin_sdk.js")
    assert html.index("/static/theme_state.js") < html.index("/static/app.js")
    # Settings menu (gear) + the reading-font boot.
    assert 'id="settings-btn"' in html
    assert "metabrowser.proseFont" in html
    assert "data-prose-font" in html


def test_app_theme_control_contract() -> None:
    src = _read_app_js()
    assert "function initSettingsControl" in src
    assert 'var THEME_MODE_KEY = "metabrowser.themeMode"' in src
    assert 'var THEME_MODES = ["system", "light", "dark"]' in src
    assert 'setAttribute("data-theme-mode", normalized)' in src
    assert 'setAttribute("data-theme", resolved)' in src
    assert 'setAttribute("data-kpress-resolved-theme", resolved)' in src
    assert "previousResolved !== resolved" in src
    assert "MetabrowserTheme.notifyChanged" in src
    assert 'setAttribute("data-kpress-theme", normalized)' not in src
    assert 'querySelectorAll(".metabrowser-kpress-host .kpress")' not in src
    assert 'matchMedia("(prefers-color-scheme: dark)")' in src
    # Reading-font chooser.
    assert 'var PROSE_FONT_KEY = "metabrowser.proseFont"' in src
    assert "function applyProseFont" in src
    assert 'setAttribute("data-prose-font", normalized)' in src


def test_print_css_hides_chrome_and_preserves_active_printable_surface() -> None:
    css = _read_styles_css()
    assert "@media print" in css
    for selector in (
        ".tree-pane",
        ".resize-handle",
        ".file-header",
        ".tab-bar",
        ".content-copy-btn",
        ".settings-toggle",
        ".custom-tooltip",
    ):
        assert selector in css
    assert ".preview-pane [data-tab-content]" in css
    assert '[data-active-view="true"][data-printable="true"]' in css
    assert '.preview-pane[data-printable="false"]::before' in css
    assert "--kpress-print-page-margin" in css
    # KPress 0.3 exposes document color tokens directly; the retired
    # --kpress-host-* color aliases must not survive the host migration.
    assert "--kpress-doc-bg: var(--bg);" in css
    assert "--kpress-host-bg" not in css
    normalized_css = " ".join(css.split())
    assert ".metabrowser-kpress-host .kpress, :root .kpress-tooltip {" in normalized_css
    assert ".metabrowser-source-truncation-warning" in css


def test_embedded_markdown_does_not_double_top_spacing() -> None:
    css = _read_styles_css()
    assert "--embedded-document-padding-top: 8px;" in css
    assert ".metabrowser-kpress-host .kpress-doc" in css
    assert "padding-block-start: var(--embedded-document-padding-top)" in css
    assert ".metabrowser-kpress-host .kpress-prose > h1:first-child" in css
    assert "margin-block-start: 0" in css


def test_embedded_markdown_toggle_labels_match_tabs() -> None:
    css = _read_styles_css()
    rule_start = css.index(".metabrowser-kpress-host .kpress details > summary {")
    rule_block = css[rule_start : rule_start + 500]
    for token in (
        "--label-color",
        "--label-font-size",
        "--label-font-weight",
        "--label-letter-spacing",
        "--label-text-transform",
    ):
        assert f"var({token})" in rule_block


def test_embedded_markdown_body_uses_host_reading_size() -> None:
    css = _read_styles_css()
    assert "--body-font-size: 14px;" in css
    assert "--document-body-font-size: 15px;" in css
    root_start = css.index(":root {")
    root_block = css[root_start : root_start + 9_000]
    assert "--kpress-host-font-size-base: var(--document-body-font-size);" in root_block
    rule_start = css.index(".metabrowser-kpress-host .kpress {")
    rule_block = css[rule_start : rule_start + 1_000]
    assert "--kpress-font-size-normal" not in rule_block
    assert "--kpress-font-size-mono: var(--document-mono-font-size);" in rule_block
    assert "--kpress-font-size-small: var(--document-small-font-size);" in rule_block
    assert "--kpress-caps-label-size: var(--label-font-size);" in rule_block
    assert "--kpress-bullet-size" not in rule_block
    assert ".metabrowser-kpress-host .kpress-prose h1" not in css
    assert "TEMPORARY SHAPE" not in css


def test_embedded_kpress_toc_resets_legacy_list_spacing() -> None:
    css = _read_styles_css()
    rule_start = css.index(".metabrowser-kpress-host .kpress-toc li {")
    rule_block = css[rule_start : rule_start + 140]
    assert "margin-block: 0;" in rule_block


def test_embedded_kpress_wide_toc_uses_borderless_rail() -> None:
    css = _read_styles_css()
    band_match = KPRESS_DOC_MIN_WIDTH_QUERY_RE.search(css)
    assert band_match is not None
    kpress_css = get_static_asset("css/components.css").content.decode("utf-8")
    assert band_match.group(0) in kpress_css

    band_start = band_match.start()
    band_block = css[band_start : band_start + 500]
    assert ".metabrowser-kpress-host .kpress-toc {" in band_block
    assert "border: none;" in band_block
    assert "scrollbar-width: none;" in band_block
    assert ".metabrowser-kpress-host .kpress-toc::-webkit-scrollbar {" in band_block
    assert "display: none;" in band_block
