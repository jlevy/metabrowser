"""Line anchors in source views: the wiring and paint a browserless session cannot see.

`tests/dom/source-line-anchors-session.js` runs the anchor state machine through the
production SDK and navigation controller, and `tests/dom/preview-pane-state-session.js`
runs the shell fetching the module on demand and waiting for it where an address names
a view. What stays here is what they cannot observe: what the server's shell publishes,
that the browser and the GitHub reducer accept the same `#L` grammar, and that the
stylesheet paints the gutter and the highlight on the code's own line box.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from devtools import check_startup_scripts
from metabrowser import server
from metabrowser.builtin_plugins.github import urls as github_urls
from tests.required_tools import needs_node, require_node

STATIC = Path(server.__file__).resolve().parent / "static"
SDK_SANDBOX = Path(__file__).resolve().parent / "dom" / "sdk-sandbox.js"


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_the_shell_publishes_the_gutter_as_an_on_demand_bundle() -> None:
    # The gutter belongs to a Source view's first paint, not the folder shell's: it is
    # no startup script. It is in the one bundle that holds what a view's renderer
    # calls, which names the global it must leave behind, so a file that arrived and
    # did not define the anchors is a failed load and not a Source view without them.
    html = check_startup_scripts.render_folder_shell()
    startup = check_startup_scripts.startup_script_paths(html)
    assert "/static/plugin-sdk-views.js" not in startup
    # Nor does a folder's shell carry the GitPath codec, which only a pin's page reads.
    assert "/static/git-path.js" not in startup
    bundles = json.loads(
        html.split("window.METABROWSER_ASSET_BUNDLES=", 1)[1].split(";</script>", 1)[0]
    )
    assert [
        (entry["src"].partition("?")[0], entry.get("provides")) for entry in bundles["sdk-views"]
    ] == [("/static/plugin-sdk-views.js", "MetabrowserSourceLineAnchors")]
    # One request beside the compositor's, not two: no bundle of the gutter's own.
    assert "source-line-anchors" not in bundles
    assert len(bundles["view-composition"]) == 1


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
const sandbox = require(process.argv[1]).createSdkSandbox();
const corpus = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(corpus.map((f) => sandbox.MetabrowserSourceLineAnchors.parse(f))));
"""


@needs_node
def test_browser_and_reducer_accept_the_same_line_anchors() -> None:
    result = subprocess.run(
        [require_node(), "-e", _JS_PARSE, str(SDK_SANDBOX), json.dumps(ANCHOR_CORPUS)],
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
const sandbox = require(process.argv[1]).createSdkSandbox();
const corpus = JSON.parse(process.argv[2]);
const view = (query) => sandbox.MetabrowserSourceLineAnchors.preferredView({ path: "a.md", query });
process.stdout.write(JSON.stringify(corpus.map((query) => view(query) === "source")));
"""


@needs_node
def test_browser_and_reducer_read_plain_the_same_way() -> None:
    result = subprocess.run(
        [require_node(), "-e", _JS_PLAIN, str(SDK_SANDBOX), json.dumps(PLAIN_CORPUS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    browser = json.loads(result.stdout)
    for query, source in zip(PLAIN_CORPUS, browser, strict=True):
        assert source == github_urls._plain(query), query  # pyright: ignore[reportPrivateUsage]


def test_load_more_keeps_the_tab_the_reader_is_on() -> None:
    # Which view an address opens, and that a view plugin navigation names wins, is run
    # by tests/dom/preview-pane-state-session.js. Load more's full render, which no
    # session runs, keeps the active tab.
    app = (STATIC / "app.js").read_text(encoding="utf-8")
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
