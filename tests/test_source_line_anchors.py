"""Line anchors in source views: the wiring and paint a browserless session cannot see.

`tests/dom/source-line-anchors-session.js` runs the anchor state machine through the
production SDK and navigation controller. What stays here is what it cannot observe:
that the shell loads the module before the SDK that calls it, that the browser and the
GitHub reducer accept the same `#L` grammar, and that the stylesheet paints the gutter
and the highlight on the code's own line box.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
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


# Fragments the two parsers must agree on, including the edges a regular expression
# gets wrong: a trailing newline, a leading zero, a tenth digit, and letter case.
ANCHOR_CORPUS = (
    "L10",
    "L10-L20",
    "L20-L10",
    "L10C5-L20C8",
    "L10C5",
    "L7-L7",
    "L123456789",
    "L1234567890",
    "L0",
    "L01",
    "L1-",
    "l10",
    "L10\n",
    "L10-L20\n",
    " L10",
    "heading",
    "",
)

_JS_PARSE = """
const fs = require("node:fs");
const vm = require("node:vm");
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
const corpus = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(corpus.map((f) => sandbox.MetabrowserSourceLineAnchors.parse(f))));
"""


def test_browser_and_reducer_accept_the_same_line_anchors() -> None:
    result = subprocess.run(
        [
            "node",
            "-e",
            _JS_PARSE,
            str(STATIC / "source-line-anchors.js"),
            json.dumps(ANCHOR_CORPUS),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    browser = json.loads(result.stdout)
    for fragment, parsed in zip(ANCHOR_CORPUS, browser, strict=True):
        selection = github_urls._lines(fragment)  # pyright: ignore[reportPrivateUsage]
        reducer = None if selection is None else {"start": selection.start, "end": selection.end}
        assert parsed == reducer, fragment


# Queries the two `plain=1` tests must agree on: the reducer keeps it for the served
# address, and the browser opens the Source view for it.
PLAIN_CORPUS = (
    "plain=1",
    "utm_source=chat&plain=1",
    "plain=1&utm_source=chat",
    "plain=10",
    "plain=0",
    "Plain=1",
    "plain%3D1",
    "xplain=1",
    "",
)

_JS_PLAIN = """
const fs = require("node:fs");
const vm = require("node:vm");
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
const corpus = JSON.parse(process.argv[2]);
const view = (query) => sandbox.MetabrowserSourceLineAnchors.preferredView({ path: "a.md", query });
process.stdout.write(JSON.stringify(corpus.map((query) => view(query) === "source")));
"""


def test_browser_and_reducer_read_plain_the_same_way() -> None:
    result = subprocess.run(
        ["node", "-e", _JS_PLAIN, str(STATIC / "source-line-anchors.js"), json.dumps(PLAIN_CORPUS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    browser = json.loads(result.stdout)
    for query, source in zip(PLAIN_CORPUS, browser, strict=True):
        assert source == github_urls._plain(query), query  # pyright: ignore[reportPrivateUsage]


def test_an_anchored_address_opens_the_source_view() -> None:
    # The shell asks for the view the address names when it opens a file; an explicit
    # view from plugin navigation still wins. tests/dom/preview-pane-state-session.js
    # runs this; Load more's full render, which no session runs, keeps the active tab.
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert (
        "context.viewId || window.MetabrowserSourceLineAnchors.preferredView(target) || undefined"
        in app
    )
    load_more = app[app.index("async function loadMoreCurrentText(") :]
    load_more = load_more[: load_more.index("\n}\n")]
    assert 'var activeView = document.getElementById("preview-pane")?.dataset.activeView;' in (
        load_more
    )
    assert "await renderFile(nextCached, activeView || undefined, previewClaim, {" in load_more


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
    # Rendered line boxes are rounded, so a position in `lh` units drifts off its line
    # far down a file; the band and the scroll target use the measured pitch, and `1lh`
    # only until the first measurement.
    # A code block below another, such as a Markdown body below its front matter,
    # offsets its band by the lines above it.
    offset = "var(--mb-line-offset, 0)"
    pitch = "var(--mb-line-pitch, 1lh)"
    assert f"calc((var(--mb-line-first) - 1 - {offset}) * {pitch})" in highlight
    assert f"calc((var(--mb-line-last) - {offset}) * {pitch})" in highlight
    assert "var(--highlight-bg)" in highlight
    # One gutter runs beside every code block, and a key's scroll target is its line.
    assert "grid-row: 1 / span var(--mb-source-parts, 1);" in gutter
    assert "outline: 2px solid var(--link);" in _rule(css, ".source-line-numbers:focus-visible")
    target = _rule(css, ".source-line-anchor-target")
    assert f"top: calc((var(--mb-line-focus, var(--mb-line-first)) - 1) * {pitch});" in target
    assert "height: var(--mb-line-pitch, 1lh);" in target
    assert "pointer-events: none;" in target
    assert not re.search(r"--mb-line-(first|last)\)[^;]*\* 1lh\)", css)
    print_block = css[css.index("@media print") :]
    assert re.search(r"\.source-line-numbers\s*\{\s*display: none;", print_block)
    assert re.search(
        r"pre\.code-block\.has-line-anchor > code\s*\{\s*background-image: none;", print_block
    )
