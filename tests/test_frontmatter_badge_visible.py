"""Malformed frontmatter must be visible in the browser UI.

An earlier implementation added ``frontmatter_error``
to the ``/api/file`` JSON response but the shell didn't surface it
anywhere visible — a user clicking a malformed process spec saw a
normal-looking Markdown view unless they opened DevTools.

These tests assert that the shell's ``renderBadges`` emits a
``badge-frontmatter-error`` chip when ``data.frontmatter_error`` is
present, and that the CSS rule scoping that class lives in styles.css.

We assert against the JS source text rather than driving the renderer
in a JSDOM shim; the e2e shim under ``tests/dom/`` covers full
registration but doesn't render the file header. Source-text checks
are sufficient for the badge contract (tooltip + class + label).
"""

from __future__ import annotations

from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "app.js"
STYLES_CSS = (
    Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "styles.css"
)


def test_render_badges_emits_frontmatter_error_badge() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    assert "data.frontmatter_error" in src, (
        "renderBadges must read data.frontmatter_error from the api/file response"
    )
    assert "badge-frontmatter-error" in src, "renderBadges must emit a badge-frontmatter-error chip"
    # Tooltip carries the parser message so the operator sees what's wrong.
    badges_block_start = src.index("data.frontmatter_error")
    badges_block_end = badges_block_start + 400
    block = src[badges_block_start:badges_block_end]
    assert "data-tip-text=" in block, (
        "frontmatter-error badge must announce through the app's tooltip"
    )
    assert "esc(data.frontmatter_error)" in block, "tooltip must HTML-escape the parser message"


def test_styles_css_defines_frontmatter_error_class() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert ".badge-frontmatter-error" in css, "styles.css must scope the frontmatter-error badge"
