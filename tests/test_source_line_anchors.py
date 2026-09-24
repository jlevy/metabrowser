"""Line anchors in source views: the wiring and paint a browserless session cannot see.

`tests/dom/source-line-anchors-session.js` runs the anchor state machine through the
production SDK and navigation controller. What stays here is what it cannot observe:
that the shell loads the module before the SDK that calls it, that the browser and the
GitHub reducer accept the same `#L` grammar, and that the stylesheet paints the gutter
and the highlight on the code's own line box.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, cast

from metabrowser import server
from metabrowser.builtin_plugins.github import urls as github_urls

STATIC = Path(server.__file__).resolve().parent / "static"


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_shell_loads_line_anchors_eagerly_before_the_sdk() -> None:
    response = asyncio.run(server.index(cast(Any, None)))
    html = bytes(response.body).decode()
    assert '<script src="/static/source-line-anchors.js?v=' in html
    assert html.index("/static/source-line-anchors.js") < html.index("/static/plugin-sdk.js")


def test_browser_and_reducer_accept_the_same_line_anchor_grammar() -> None:
    source = (STATIC / "source-line-anchors.js").read_text(encoding="utf-8")
    match = re.search(r"const ANCHOR =\s*/(.+)/;", source)
    assert match
    assert match.group(1) == github_urls._LINE_ANCHOR.pattern  # pyright: ignore[reportPrivateUsage]


def test_gutter_and_highlight_use_the_code_line_box() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    code = _rule(css, ".code-block code")
    gutter = _rule(css, ".source-line-numbers")
    for declaration in (
        "font-family: var(--font-mono);",
        "font-size: var(--mono-block-font-size);",
        "line-height: 1.5;",
    ):
        assert declaration in code
        assert declaration in gutter
    assert "user-select: none;" in gutter
    highlight = _rule(
        css,
        ".content-copy-wrap > pre.code-block.has-line-anchor > code,\n"
        ".content-copy-wrap > pre.code-block.has-line-anchor > .source-line-numbers",
    )
    assert "calc((var(--mb-line-first) - 1) * 1lh)" in highlight
    assert "calc(var(--mb-line-last) * 1lh)" in highlight
    assert "var(--highlight-bg)" in highlight
    target = _rule(css, ".source-line-anchor-target")
    assert "top: calc((var(--mb-line-first) - 1) * 1lh);" in target
    assert "pointer-events: none;" in target
    print_block = css[css.index("@media print") :]
    assert re.search(r"\.source-line-numbers\s*\{\s*display: none;", print_block)
