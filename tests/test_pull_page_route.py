"""The served pull request's page: its route, its shell, and what its paint may parse.

The page's decisions run browserless in ``tests/dom/github-pull-page-session.js``. What is
left to the browser is the shell's route glue and the page's paint; this file pins what
of them can be pinned without one: the route grammar the server and ``--show`` share,
that ``/pull/`` serves the shell and loads the GitHub plugin for the ``pull-request``
kind, that the paint parses no HTML but KPress's sanitized Markdown, and that the
stylesheet spaces a text's markup and reaches nothing outside the page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter
from metabrowser.inert_html import ALLOWED_TAGS, harden
from metabrowser.server import app
from metabrowser.view_routes import decode_safe_pull_route, format_pull_href
from tests.golden_harness import read_recording

PAGE_JS = (
    Path(__file__).resolve().parent.parent / "src/metabrowser/builtin_plugins/github/pull-page.js"
)
STYLES_CSS = PAGE_JS.parent / "styles.css"


@pytest.mark.parametrize(
    ("raw", "decoded"),
    [
        (b"/pull/7", (7, "")),
        (b"/pull/7/", (7, "")),
        (b"/pull/7/files", (7, "files")),
        (b"/pull/7/files/", (7, "files")),
        (b"/pull/9999999999", (9999999999, "")),
        (b"/pull/0", None),
        (b"/pull/07", None),
        (b"/pull/7/commits", None),
        (b"/pull/7/files/x", None),
        (b"/pull/7//", None),
        (b"/pull/%37", None),
        (b"/pull/", None),
        (b"/pulls/7", None),
    ],
)
def test_the_pull_route_grammar(raw: bytes, decoded: tuple[int, str] | None) -> None:
    assert decode_safe_pull_route(raw) == decoded
    if decoded is not None:
        assert decode_safe_pull_route(format_pull_href(*decoded).encode()) == decoded


def test_format_pull_href_refuses_what_the_route_does_not_parse() -> None:
    for number, tab in ((0, ""), (7, "commits"), (10**10, "")):
        with pytest.raises(ValueError, match="pull route"):
            format_pull_href(number, tab)


def test_the_pull_route_serves_the_shell_and_the_plugin_for_its_kind() -> None:
    with TestClient(app) as client:
        shell = client.get("/pull/7/files")
        assert shell.status_code == 200
        assert 'id="preview-pane"' in shell.text
        # The shell loads a plugin's assets by the kinds its views consume.
        config = re.search(r"configureAssets\((\{.*?\})\);", shell.text)
        assert config is not None and '"pull-request": [{"name": "github"' in config.group(1)
        for refused in ("/pull/0", "/pull/7/commits"):
            answer = client.get(refused)
            assert (answer.status_code, answer.text) == (400, "Invalid pull-request route.")


def test_the_page_parses_no_html_but_through_the_inert_allowlist() -> None:
    """Every text of the pull request is painted with textContent.

    Its Markdown is parsed and rebuilt only by ``static/inert-html.js``'s ``sanitizeHtml``,
    with links made absolute against the pull request; every outside link opens with no
    opener or referrer, and no KPress script or stylesheet is loaded for it.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    assert "innerHTML" not in source
    assert "inert.sanitizeHtml(String(rendered.html), shown?.pull?.htmlUrl" in source
    assert 'ensureAsset("inert-html")' in source
    assert "loadKpressAssets" not in source
    assert "insertAdjacentHTML" not in source and "outerHTML" not in source
    assert source.count('rel: "noopener noreferrer"') == 1
    # GitHub's own rendering of the text is never read.
    assert ".body_html" not in source and '["body_html"]' not in source


def _style_rules() -> dict[str, str]:
    """Each selector of the page's stylesheet and its declarations, comments stripped."""

    css = re.sub(r"/\*.*?\*/", "", STYLES_CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    rules: dict[str, str] = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        # A comma inside `:is(a, b)` is no separator.
        for selector in re.split(r",(?![^()]*\))", selectors):
            rules[selector.strip()] = rules.get(selector.strip(), "") + body
    return rules


def test_a_comment_with_no_line_links_to_its_file_with_no_fragment() -> None:
    """Whether a comment has a line is the session's; what paint does without one is here."""

    source = PAGE_JS.read_text(encoding="utf-8")
    assert "...(line === null ? {} : { fragment: `L${line}` })" in source
    assert "line === null ? path : `${path}:${line}`" in source


def test_a_hunks_tints_are_the_diff_views() -> None:
    """The diff plugin's stylesheet loads only with Files changed, so its tints are restated
    for the conversation's hunks; a change to one that misses the other fails here."""

    rules = _style_rules()
    diff_css = (PAGE_JS.parent.parent / "diff" / "styles.css").read_text(encoding="utf-8")
    for kind, token in (("add", "--diff-add-row-bg"), ("del", "--diff-del-row-bg")):
        tint = re.search(rf"{token}:\s*([^;]+);", diff_css)
        assert tint is not None, token
        assert (
            f"background: {tint.group(1)};" in rules[f'.github-pull-hunk-line[data-kind="{kind}"]']
        )


def test_a_hunk_is_painted_as_text_in_a_native_disclosure() -> None:
    """The lines' classes and split are the session's; what paint does with them is here."""

    source = PAGE_JS.read_text(encoding="utf-8")
    assert '"data-kind": line.kind }, [line.text])' in source
    # Stateless: the browser opens it, and nothing of the page listens or remembers.
    assert 'h("details", { class: "github-pull-hunk-earlier" }' in source
    assert "toggle" not in source


def _vertical_margins(declarations: str) -> tuple[str, str]:
    """The top and bottom of a rule's ``margin`` shorthand."""

    found = re.search(r"(?:^|;|\s)margin:\s*([^;]+);", declarations)
    assert found is not None, declarations
    sides = found.group(1).split()
    return sides[0], sides[2] if len(sides) > 2 else sides[0]


def test_nothing_in_the_pages_stylesheet_can_reach_another_page() -> None:
    assert [
        selector for selector in _style_rules() if not selector.startswith(".github-pull")
    ] == []


# The block markup of the allowlist a text can arrive with. The shell's reset takes every
# block's margin away, so a block with no rule of its own runs into the next one. Which
# margin looks right is judged in a browser; that each block has one is a contract.
_TEXT_BLOCKS = (
    "p",
    "ul",
    "ol",
    "dl",
    "pre",
    "blockquote",
    "table",
    "details",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
)


@pytest.mark.parametrize("tag", _TEXT_BLOCKS)
def test_a_block_of_a_text_is_spaced_under_the_shells_reset(tag: str) -> None:
    assert tag in ALLOWED_TAGS
    top, bottom = _vertical_margins(_style_rules()[f".github-pull-markdown {tag}"])
    assert float(top.removesuffix("em")) > 0
    assert float(bottom.removesuffix("em")) > 0


def test_a_lists_markers_have_room_inside_the_card() -> None:
    rules = _style_rules()
    for tag in ("ul", "ol", "dd"):
        assert "padding-left: 1.8em" in rules[f".github-pull-markdown {tag}"]
    # A nested list is part of its item, so it does not take a block's margin.
    assert _vertical_margins(rules[".github-pull-markdown li > ul"]) == ("0.25em", "0")
    assert _vertical_margins(rules[".github-pull-markdown li > ol"]) == ("0.25em", "0")


def test_a_wide_table_scrolls_inside_its_text() -> None:
    """The card clips what overflows it, so a table wider than its text must scroll itself.

    Measured 2026-11-01 with an 8-column table in a text on pallets/click#3866: 3,349 px in
    a 673 px card, with 2,689 px out of reach and nothing between them that scrolled.
    """

    rules = _style_rules()
    assert "overflow: hidden" in rules[".github-pull-card"]
    for declaration in ("display: block", "max-width: 100%", "overflow-x: auto"):
        assert declaration in rules[".github-pull-markdown table"], declaration
    # A block keeps the table's own layout inside it, and its collapsed borders by
    # inheritance; a width of its own would stretch a table that fits.
    assert "border-collapse: collapse" in rules[".github-pull-markdown table"]
    assert "width: 100%" not in rules[".github-pull-markdown table"].replace("max-width", "")


def test_a_table_at_either_end_of_a_text_is_what_the_deepest_trim_reaches() -> None:
    """KPress wraps a table in a ``<div>`` of its own, beneath the two every text has."""

    source = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    html = harden(
        str(
            kpress_adapter.render_kpress_view(
                source_text=source,
                source_path="comment.md",
                kind="markdown",
                view="document",
                ext=".md",
                mtime_hash="pull-page-table",
                size=len(source.encode()),
                include_toc="off",
            )["html"]
        ),
        "https://github.com/octo/demo/pull/7",
    )
    assert re.match(r"\s*<div><div><div><table>", html), html
    assert re.search(r"</table></div></div></div>\s*$", html), html
    rules = _style_rules()
    first = ".github-pull-markdown > " + "div:first-child > " * 3 + ":first-child"
    last = ".github-pull-markdown > " + "div:last-child > " * 3 + ":last-child"
    assert "margin-top: 0" in rules[first] and "margin-bottom: 0" in rules[last]
    # No trim names a cell's ancestors, so a cell keeps its padding and borders. What a
    # cell holds, as raw HTML can give it, is trimmed by the rule for its container.
    cell = ".github-pull-markdown :is(blockquote, details, dd, th, td) > "
    assert "margin-top: 0" in rules[f"{cell}:first-child"]
    assert "margin-bottom: 0" in rules[f"{cell}:last-child"]


def test_a_texts_first_and_last_block_are_trimmed_through_its_wrappers() -> None:
    """The trims reach as deep as what the Markdown route answers actually nests.

    The route's text arrives as ``<div><div><p>``, and a table has its own ``<div>``
    beneath those. A trim that stops at the outer wrapper leaves the margin it means to
    remove, with the card's padding on top of it.
    """

    html = read_recording("github-pull-page-responses.json")["markdown body"]["body"]["html"]
    wrappers = re.match(r"\s*((?:<div>)*)", html)
    assert wrappers is not None and wrappers.group(1) == "<div>" * 2
    rules = _style_rules()
    for depth in range(4):
        first = ".github-pull-markdown > " + "div:first-child > " * depth + ":first-child"
        last = ".github-pull-markdown > " + "div:last-child > " * depth + ":last-child"
        assert "margin-top: 0" in rules[first], first
        assert "margin-bottom: 0" in rules[last], last
