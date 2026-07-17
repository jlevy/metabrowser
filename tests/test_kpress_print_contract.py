"""Metabrowser KPress print/theme shell contract tests."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


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
    # Host bridge token: metabrowser sets --kpress-host-* on :root; KPress
    # consumes them as var(--kpress-host-*, default) (see kpress-visual-polish
    # §5.1). The old name was --kpress-doc-bg.
    assert "--kpress-host-bg" in css
    assert ".metabrowser-source-truncation-warning" in css


def test_embedded_markdown_does_not_double_top_spacing() -> None:
    css = _read_styles_css()
    assert ".metabrowser-kpress-host .kpress-doc" in css
    assert "padding-block-start: var(--content-padding-y)" in css
    assert ".metabrowser-kpress-host .kpress-prose > h1:first-child" in css
    assert "margin-block-start: 0" in css
