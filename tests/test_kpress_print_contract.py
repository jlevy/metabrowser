"""Metabrowser KPress print/theme shell contract tests."""

from __future__ import annotations

import asyncio
import re

from kpress.runtime import get_static_asset

from metabrowser import server as proc_browser
from metabrowser.settings import DOC_MAX_CHARS_DEFAULT, client_settings_dict
from tests.shell_request import shell_request

KPRESS_DOC_MIN_WIDTH_QUERY_RE = re.compile(r"@container kpress-doc \(min-width: [\d.]+rem\) \{")


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _read_styles_css() -> str:
    return proc_browser.STATIC_DIR.joinpath("styles.css").read_text()


def _read_icons_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("icons.js").read_text()


def _render_index_html() -> str:
    resp = asyncio.run(proc_browser.index(shell_request()))
    return resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else str(resp.body)


def test_app_shell_tracks_active_printable_view() -> None:
    src = _read_app_js()
    # Which view is in front, and its print state, is the compositor's to say.
    composition = proc_browser.STATIC_DIR.joinpath("view-composition.js").read_text()
    assert "function setActiveView(host, viewId)" in composition
    assert "host.dataset.printable = " in composition
    assert "setActiveView(host, tabId)" in composition
    assert "data-printable" in composition
    assert "data-print-profile" in composition
    assert "data-render-runtime" in composition
    assert 'data-active-view="false"' in composition
    # Printing is the browser's, for Command-P and for the rendered document's print
    # button alike: the shell draws no print control and holds no print command (mb-07a1).
    assert "file-header-print" not in src
    assert "printActiveView" not in src
    assert "window.print()" not in src
    printer = (
        proc_browser.STATIC_DIR.parent / "builtin_plugins" / "markdown" / "print-indicator.js"
    ).read_text()
    assert "window.print()" in printer
    # No id, so a document's `<label for=…>` has nothing to click through.
    assert 'setAttribute("id"' not in printer


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
    assert html.index("/static/theme-state.js") < html.index("/static/plugin-sdk.js")
    assert html.index("/static/theme-state.js") < html.index('<script src="/static/app.js')
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


def test_document_width_default_reaches_the_shell_from_client_settings() -> None:
    """One Python default seeds first paint and the exact browser state machine."""

    html = _render_index_html()
    src = _read_app_js()
    css = _read_styles_css()

    assert DOC_MAX_CHARS_DEFAULT == 102
    assert client_settings_dict()["DOC_MAX_CHARS_DEFAULT"] == DOC_MAX_CHARS_DEFAULT
    assert f'<html lang="en" style="--doc-max-chars: {DOC_MAX_CHARS_DEFAULT}">' in html
    assert f'"DOC_MAX_CHARS_DEFAULT": {DOC_MAX_CHARS_DEFAULT}' in html
    document_width = (proc_browser.STATIC_DIR / "document-width.js").read_text()
    assert f"<script>{document_width}</script>" in html
    assert '<script src="/static/document-width.js' not in html
    assert html.index("window.METABROWSER_SETTINGS=") < html.index(
        "// Persisted document reading-width state."
    )
    assert html.index("// Persisted document reading-width state.") < html.index(
        "/static/app.js?v="
    )
    assert "String(width.readStored(cookie))" in html
    assert "window.MetabrowserDocumentWidth" in src
    assert "var DOC_MAX_CHARS_DEFAULT = documentWidth.DEFAULT;" in src
    assert "return documentWidth.readStored(readPrefCookie);" in src
    assert "return documentWidth.apply(chars, persist" in src
    assert "--doc-max-chars: 105;" not in css


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
    assert ":root .kpress, :root .kpress-tooltip {" in normalized_css
    # Notices print through the `.notice` primitive rather than each use site,
    # so a new one prints correctly without being named here.
    # See tests/test_notice_style.py.
    assert "\n  .notice {" in css


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
    root_block = css[root_start : css.index('[data-theme="dark"] {')]
    assert "--kpress-host-font-size-base: var(--document-body-font-size);" in root_block
    rule_start = css.index(".metabrowser-kpress-host .kpress {")
    rule_block = css[rule_start : rule_start + 1_000]
    # The size ramp is KPress's to own; anchoring the base above is the whole
    # bridge. KPress grades secondary text (small / smaller / tiny) and code
    # (mono / mono-small / mono-tiny) by context, because the smaller tiers land
    # where the surrounding text is already reduced — table cells, captions,
    # footnotes. A host token collapses the family onto one size: a flat mono
    # token once rendered inline code in a table LARGER than its own cell, and a
    # flat secondary token shrank table text well under what KPress intends.
    for family in (
        "--kpress-font-size-normal",
        "--kpress-font-size-mono",
        "--kpress-font-size-small",
    ):
        assert family not in rule_block
    # The one surviving size override is a real design difference, not a ratio.
    assert "--kpress-caps-label-size: var(--label-font-size);" in rule_block
    assert "--kpress-bullet-size" not in rule_block
    assert ".metabrowser-kpress-host .kpress-prose h1" not in css
    assert "TEMPORARY SHAPE" not in css


def test_legacy_md_body_chrome_never_reaches_into_an_embedded_document() -> None:
    """`.md-body` is chrome CSS; an embedded KPress document is not chrome.

    The markdown view's container carries BOTH classes (``md-body`` is kept as a
    convention for third-party plugins), so an unscoped ``.md-body`` rule also
    matches inside the document. Ties go to KPress — its stylesheet loads after
    ``styles.css`` — so a leak only bites where KPress has no competing
    declaration, which is why the symptoms were scattered and easy to miss:
    paragraphs capped 16px under the reading measure KPress had just computed,
    list rhythm overridden, and a ``.kpress-toc li`` counter-rule existing only
    to undo ``.md-body li``.

    Scope every one of them. A divergence the embed genuinely wants is stated
    directly against ``.metabrowser-kpress-host`` instead (see the blockquote
    rule), so it is deliberate rather than inherited by class collision.
    """

    css = _read_styles_css()
    unscoped = [
        line
        for line in css.splitlines()
        if line.startswith(".md-body") and ":not(.metabrowser-kpress-host)" not in line
    ]

    assert unscoped == [], (
        "these .md-body rules also match inside embedded KPress documents; "
        f"scope them with :not(.metabrowser-kpress-host): {unscoped}"
    )


def test_embedded_kpress_blockquote_takes_kpress_rule_and_muted_text() -> None:
    """KPress draws the accent rule and muted text the app uses for quoted material.

    It colors both from the document tokens the host maps to `--border` and `--muted`,
    so the embed adds no blockquote rule of its own.
    """

    css = _read_styles_css()
    document = get_static_asset("css/document.css").content.decode("utf-8")
    rule_start = document.index("\n.kpress blockquote {")
    rule_block = document[rule_start : document.index("}\n", rule_start)]

    assert "border-inline-start: 3px solid var(--kpress-doc-border);" in rule_block
    assert "color: var(--kpress-doc-muted);" in rule_block
    assert "--kpress-doc-border: var(--border);" in css
    assert "--kpress-doc-muted: var(--muted);" in css
    assert ".metabrowser-kpress-host .kpress blockquote" not in css


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


def test_print_page_margin_is_kpress_token_as_a_length() -> None:
    """WebKit resolves no custom property in ``@page``, so the adapter writes KPress's margin out.

    The copy in ``static/styles.css`` must stay KPress's ``--kpress-print-page-margin``,
    and must outrank print.css's own ``@page`` rule, which loads after it.
    """

    tokens = get_static_asset("css/style-tokens.css").content.decode()
    token = re.search(r"--kpress-print-page-margin:\s*([^;]+);", tokens)
    assert token is not None
    css = _read_styles_css()
    adapter = css[css.index("/* ── Print adapter") :]
    page = re.search(r"@page \{\s*(?:/\*.*?\*/\s*)?margin: ([^;]+);", adapter, re.DOTALL)
    assert page is not None
    assert page.group(1) == f"{token.group(1).strip()} !important"
    assert "var(" not in page.group(1)
