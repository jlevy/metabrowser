"""The Markdown built-in plugin owns its renderers.

The markdown plugin's `index.js` used to be a stub IIFE; the actual
`renderMarkdownTab` / `renderSourceTab` lived in `app.js` behind a
`VIEW_RENDERERS` fallback. They now live in the plugin so every
kind-and-view pair goes through the plugin registry.

These tests assert on source text (no JS runtime in the metabrowser
suite); the JSDOM end-to-end test covers actual render behavior.
"""

from __future__ import annotations

from pathlib import Path

PLUGIN_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "builtin_plugins" / "markdown"
)


def _index_js() -> str:
    return (PLUGIN_DIR / "index.js").read_text(encoding="utf-8")


def _all_js() -> str:
    return "\n".join(
        (PLUGIN_DIR / name).read_text(encoding="utf-8")
        for name in ("index.js", "rendered.js", "source.js")
    )


def _manifest_toml() -> str:
    return (PLUGIN_DIR / "manifest.toml").read_text(encoding="utf-8")


def test_index_js_registers_rendered_view() -> None:
    src = _all_js()
    assert 'mb.registerView("markdown", "rendered"' in src


def test_index_js_registers_source_view() -> None:
    src = _index_js()
    assert 'mb.registerView("markdown", "source"' in src


def test_index_js_uses_sdk_helpers_not_local_copies() -> None:
    """The plugin must call SDK methods (mb.escapeHtml etc.) so the cut
    is actually real — not just call back into app.js helpers."""
    src = _all_js()
    assert "mb.escapeHtml" in src
    assert "mb.isLargeTextPreview" in src
    assert "mb.wrapWithCopy" in src
    assert "mb.renderTextTruncationWarning" in src
    assert "mb.fetchKpressRender" in src
    assert "mb.perf.measure" in src


def test_index_js_no_legacy_stub_comments() -> None:
    """Stub-era ownership comments must not creep back in."""
    src = _index_js()
    forbidden = [
        "renderers stay in app.js",
        "for now",
        "renderers (renderMarkdownTab",
        "Reserve namespace",
    ]
    for needle in forbidden:
        assert needle not in src, f"stub-era language reappeared: {needle!r}"


def test_index_js_exposes_builtins_namespace_for_other_plugins() -> None:
    """Specialized document plugins reuse the markdown renderers via
    mb.builtins.markdown.{mountRendered,renderSource}."""
    src = _index_js()
    assert "mb.builtins.markdown" in src
    assert "mountRendered" in src
    assert "renderSource" in src


def test_index_js_has_no_client_side_markdown_renderer() -> None:
    """KPress is the only rendered-Markdown implementation."""
    src = _index_js()
    forbidden = [
        "renderMarkdownHtml",
        "window.marked",
        "window.DOMPurify",
        "client-side Markdown fallback",
    ]
    for needle in forbidden:
        assert needle not in src


def test_manifest_views_match_index_registrations() -> None:
    """The manifest declares the views; index.js must register
    renderers for the same (kind, view) pairs."""
    manifest = _manifest_toml()
    js = _index_js()
    # Manifest declares both views.
    assert 'id = "rendered"' in manifest
    assert 'id = "source"' in manifest
    # JS registers both.
    assert 'registerView("markdown", "rendered"' in js
    assert 'registerView("markdown", "source"' in js
    assert 'print_profile = "document"' in manifest
    assert 'print_profile = "source"' in manifest
    assert 'render_runtime = "kpress"' in manifest


def test_rendered_view_uses_kpress_with_visible_error() -> None:
    src = _all_js()
    assert "mb.fetchKpressRender" in src
    assert 'profile: "document"' in src
    assert "renderKpressError" in src
    assert "Could not render this document." in src
    assert "renderMarkdownHtml(ctx.raw)" not in src


def test_source_views_include_visible_truncation_warning() -> None:
    src = _all_js()
    assert "mb.renderTextTruncationWarning(data)" in src
    assert "warning" in src


def test_embedded_readme_suppresses_its_own_table_of_contents() -> None:
    """The folder Overview's README asks KPress for no TOC.

    The panel stack around it is already the reader's way through the folder,
    so a second navigation inside the embed competes with it. Opening the same
    README as a file passes nothing and keeps KPress' ordinary thresholds, so
    the suppression has to travel with this one call rather than being a
    property of the renderer.
    """

    folder_dir = PLUGIN_DIR.parent / "folder"
    readme_panel = (folder_dir / "readme-panel.js").read_text(encoding="utf-8")
    assert 'includeToc: "off"' in readme_panel

    # The option has to survive the whole path or the panel's request is inert:
    # renderer -> SDK -> query string.
    rendered = (PLUGIN_DIR / "rendered.js").read_text(encoding="utf-8")
    assert "includeToc: options.includeToc" in rendered

    sdk = (PLUGIN_DIR.parent.parent / "static" / "plugin-sdk.js").read_text(encoding="utf-8")
    assert 'url.searchParams.set("toc", includeToc)' in sdk


def test_a_readme_opened_as_a_file_keeps_its_table_of_contents() -> None:
    """Only the embedded mount opts out; the view registration must not."""

    index = _index_js()
    assert "includeToc" not in index
