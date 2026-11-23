"""A pull request's page: its route, its shell, and what its paint may parse.

The page's decisions run browserless in ``tests/dom/github-pull-page-session.js``. What is
left to the browser is the shell's route glue and the page's paint; this file pins what
of them can be pinned without one: the route grammar the server and ``--show`` share,
that ``/pull/`` serves the shell and loads the GitHub plugin for the ``pull-request``
kind, that the paint parses no HTML but KPress's sanitized Markdown, and that the
stylesheet reaches nothing outside the page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter
from metabrowser.inert_html import harden
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
        (b"/pull/7", (7, "", "")),
        (b"/pull/7/", (7, "", "")),
        (b"/pull/7/files", (7, "files", "")),
        (b"/pull/7/files/", (7, "files", "")),
        (b"/pull/7/checks", (7, "checks", "")),
        (b"/pull/7/checks/", (7, "checks", "")),
        (b"/pull/9999999999", (9999999999, "", "")),
        # One changed file: a path in the comparison, decoded one segment at a time.
        (b"/pull/7/files/x", (7, "files", "x")),
        (b"/pull/7/files/src/app.py", (7, "files", "src/app.py")),
        (b"/pull/7/files/docs/a%20b/%E9%9B%AA.md", (7, "files", "docs/a b/雪.md")),
        (b"/pull/7/files/a%25b", (7, "files", "a%b")),
        (b"/pull/7/files/.github/workflows/ci.yml", (7, "files", ".github/workflows/ci.yml")),
        (b"/pull/0", None),
        (b"/pull/07", None),
        (b"/pull/7/commits", None),
        (b"/pull/7/commits/x", None),
        (b"/pull/7/checks/x", None),
        (b"/pull/7/%63hecks", None),
        (b"/pull/7/x", None),
        (b"/pull/7//", None),
        (b"/pull/%37", None),
        (b"/pull/", None),
        (b"/pulls/7", None),
        # A file has no trailing slash, and its path is normalized: nothing that is not one.
        (b"/pull/7/files/src/", None),
        (b"/pull/7/files//x", None),
        (b"/pull/7/files/../x", None),
        (b"/pull/7/files/%2E%2E/x", None),
        (b"/pull/7/files/a/./b", None),
        (b"/pull/7/files/a%2Fb", None),
        (b"/pull/7/files/a%5Cb", None),
        (b"/pull/7/files/a%00b", None),
        (b"/pull/7/files/a%ZZ", None),
        (b"/pull/7/files/%FF", None),
        (b"/pull/7/%66iles/x", None),
    ],
)
def test_the_pull_route_grammar(raw: bytes, decoded: tuple[int, str, str] | None) -> None:
    assert decode_safe_pull_route(raw) == decoded
    if decoded is not None:
        assert decode_safe_pull_route(format_pull_href(*decoded).encode()) == decoded


def test_format_pull_href_refuses_what_the_route_does_not_parse() -> None:
    for number, tab, file in (
        (0, "", ""),
        (7, "commits", ""),
        (10**10, "", ""),
        (7, "", "src/app.py"),
        (7, "checks", "src/app.py"),
        (7, "files", "src/"),
        (7, "files", "../x"),
        (7, "files", "a\\b"),
        (7, "files", "a\0b"),
        (7, "files", "\ud800"),
    ):
        with pytest.raises(ValueError, match="pull route"):
            format_pull_href(number, tab, file)


def test_the_pull_route_serves_the_shell_and_the_plugin_for_its_kind() -> None:
    with TestClient(app) as client:
        shell = client.get("/pull/7/files")
        assert shell.status_code == 200
        assert 'id="preview-pane"' in shell.text
        preview = shell.text.split('id="preview-pane"', 1)[1].split("</main>", 1)[0]
        assert 'aria-label="Loading pull request"' in preview
        assert 'class="recent-loading"' in preview
        assert 'class="spinner"' not in preview
        ordinary = client.get("/view/").text.split('id="preview-pane"', 1)[1]
        assert 'class="spinner"' in ordinary.split("</main>", 1)[0]

        # The shell loads a plugin's assets by the kinds its views consume.
        config = re.search(r"configureAssets\((\{.*?\})\);", shell.text)
        assert config is not None and '"pull-request": ["github"]' in config.group(1)
        assert client.get("/pull/7/checks").status_code == 200
        # One changed file's address is the same page, and its path is never looked up.
        assert client.get("/pull/7/files/no/such/file.py").status_code == 200
        for refused in ("/pull/0", "/pull/7/commits", "/pull/7/files/src/", "/pull/7/files/%2E%2E"):
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
    assert "inert.sanitizeHtml(" in source
    assert 'shown?.pull?.htmlUrl ?? "https://github.com/"' in source
    assert 'ensureAsset("inert-html")' in source
    # The routes' one list of KPress's stylesheets, loaded in one place, and nothing a text
    # could name: a description's from the Markdown route, Guided PR's from the guide route.
    assert source.count("mb.loadKpressAssets(") == 1
    assert "documentStyles = mb.loadKpressAssets(assets)" in source
    assert "textStyles(rendered.assets)" in source
    # A failure to load them leaves the text readable under the shell's rules, and is said.
    assert 'console.warn("metabrowser github: the text styles did not load", error);' in source
    # Only shell-owned icon constants are parsed; every use takes an inert copy.
    assert source.count("new DOMParser()") == 1
    assert source.count("registryIcon(") == 2
    assert 'registryIcon("toggle")' in source and 'registryIcon("layers")' in source
    assert 'parseFromString(mb.icons[name] || "", "text/html")' in source
    assert "document.importNode(chevronSvg, true)" in source
    assert "document.importNode(stackSvg, true)" in source
    assert "insertAdjacentHTML" not in source and "outerHTML" not in source
    assert source.count('rel: "noopener noreferrer"') == 1
    # GitHub's own rendering of the text is never read.
    assert ".body_html" not in source and '["body_html"]' not in source


def _style_rules(path: Path = STYLES_CSS) -> dict[str, str]:
    """Each selector and its declarations, comments stripped."""

    return _rules_of(path.read_text(encoding="utf-8"))


def _rules_of(text: str) -> dict[str, str]:
    """Each selector in the stylesheet *text* and its declarations, comments stripped."""

    css = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    rules: dict[str, str] = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        # A comma inside `:is(a, b)` is no separator.
        for selector in re.split(r",(?![^()]*\))", selectors):
            rules[selector.strip()] = rules.get(selector.strip(), "") + body
    return rules


def test_a_text_is_asked_for_one_pane_ahead_and_no_further() -> None:
    """A margin only widens the observer's root, so the root must be what scrolls.

    The window does not scroll here: ``body`` is ``overflow: hidden`` and the preview pane
    is the scroller. With no root, a text past the pane's edge is clipped by the pane
    before the window's margin applies, and the margin does nothing. Which texts that
    reaches is geometry and needs a browser; the session runs the concurrency bound.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    assert 'export const MARKDOWN_AHEAD = "100% 0px";' in source
    assert (
        'const pane = /** @type {HTMLElement | null} */ (container.closest("[data-kpress-viewport]"));'
        in source
    )
    assert "{ root: pane, rootMargin: MARKDOWN_AHEAD }" in source
    # Only the description is asked for at once, or a page with no observer at all: the one
    # rule every paint and every new record's asks go through.
    assert source.count('part === "body" || observer === null') == 1
    styles = (PAGE_JS.parent.parent.parent / "static" / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"\n\.preview-pane \{[^}]*overflow-y: auto;", styles)
    with TestClient(app) as client:
        assert 'id="preview-pane" data-kpress-viewport' in client.get("/pull/7").text


def test_a_readers_place_is_kept_in_the_entry_and_disposed_with_the_page() -> None:
    """What the keeper's decisions are wired to. The session runs the decisions; that a
    browser delivers these events and restores a place is checked in Chrome.

    A click writes in the capture phase, because a link's own handler moves history on from
    this entry. Only input ends a hold, because scroll anchoring also scrolls the pane.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    glue = source[source.index("function keepPlace(") :]
    assert 'document.addEventListener("click", keeper.flush, { capture: true, signal });' in glue
    assert 'for (const type of ["wheel", "touchstart", "pointerdown"]) {' in glue
    # Only a key that can move the pane, which the session lists.
    listener = glue[glue.index('window.addEventListener(\n    "keydown",') :]
    assert "if (keyMovesPane(event.key, target)) {" in listener[: listener.index("capture")]
    assert "{ capture: true, signal }" in listener
    assert "window.history.replaceState({ ...window.history.state, [PLACE_KEY]: place }" in glue
    disposal = glue[glue.index("dispose() {") :]
    for released in ("listening.abort();", "heights.disconnect();", "keeper.dispose();"):
        assert released in disposal
    # Only the page's own tab change is a landing: asking for the tab it shows moves nothing.
    assert "const changed = controller.snapshot().tab !== next;" in source
    assert "place?.dispose();" in source


def test_a_hunks_tints_are_the_diff_views() -> None:
    """A conversation hunk reads the diff view's row tints, which the shell holds on `:root`
    so they exist without the diff plugin's stylesheet, which loads only with Files changed."""

    rules = _style_rules()
    shell_css = (PAGE_JS.parent.parent.parent / "static" / "styles.css").read_text(encoding="utf-8")
    for kind, token in (("add", "--diff-add-row-bg"), ("del", "--diff-del-row-bg")):
        assert re.search(rf"{token}:", shell_css) is not None, token
        assert f"background: var({token});" in rules[f'.github-pull-hunk-line[data-kind="{kind}"]']


def test_a_hunk_is_painted_as_text_in_a_native_disclosure() -> None:
    """The lines' classes and split are the session's; what paint does with them is here."""

    source = PAGE_JS.read_text(encoding="utf-8")
    assert '"data-kind": line.kind }, [line.text])' in source
    # The browser opens it. The page listens to that event in one place, the function the
    # session drives, and remembers nothing: a repaint replaces the disclosure.
    assert 'h("details", { class: "github-pull-hunk-earlier" }' in source
    assert (
        source.split("export function tintOnFirstOpen(", 1)[1].split("\n}", 1)[0].count('"toggle"')
        == 1
    )
    assert "tintOnFirstOpen(disclosure, plain, earlier, hunkLines);" in source


def test_one_box_scrolls_all_of_a_hunk() -> None:
    """The lines above the cut and below it move together, under a label that stays put.

    With a scroller each, a wide hunk had a scrollbar in its middle. Measured again with the
    label at ``100cqi``, 2026-11-02 in headed Chrome 152, on pallets/click#3030 with every
    fold open: the first wide box has a ``scrollWidth`` of 1,859 px in 685; at ``scrollLeft``
    200 its 15 lines move 200 px and the label none; every line is 1,859 px wide, the label
    is the box's 685 px, and its row's far end is still the label, so a click there opens it.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    assert 'const box = h("div", { class: "github-pull-hunk-box" });' in source
    assert "box.append(disclosure);" in source and "box.append(hunkLines(tail));" in source
    rules = _style_rules()
    assert "overflow-x: auto" in rules[".github-pull-hunk-box"]
    assert "overflow" not in rules[".github-pull-hunk"]
    assert "overflow" not in rules.get(".github-pull-hunk-earlier", "")
    # As wide as the widest line of either part, so a tint reaches the end of a scrolled line.
    for selector in (".github-pull-hunk-box", ".github-pull-hunk"):
        assert "grid-template-columns: minmax(max-content, 1fr)" in rules[selector]
    # The fold stays the full-width row it is, as wide as the box shows, and stays put.
    label = rules[".github-pull-hunk-earlier > summary"]
    assert "position: sticky" in label and "left: 0" in label and "width: 100cqi" in label
    assert "container-type: inline-size" in rules[".github-pull-hunk-box"]


def _vertical_margins(declarations: str) -> tuple[str, str]:
    """The top and bottom of a rule's ``margin`` shorthand: its last, which is what wins."""

    found = re.findall(r"(?:^|;|\s)margin:\s*([^;]+);", declarations)
    assert found, declarations
    sides = found[-1].split()
    return sides[0], sides[2] if len(sides) > 2 else sides[0]


def test_a_later_margin_is_the_one_read() -> None:
    """``_style_rules`` joins a selector's rules in source order, and the cascade takes the last."""

    assert _vertical_margins("margin: 0.75em 0;\n  margin: 0;\n") == ("0", "0")
    assert _vertical_margins("margin: 1.25em 0 0.5em;\n  line-height: 1.25;") == ("1.25em", "0.5em")


def test_nothing_in_the_pages_stylesheet_can_reach_another_page() -> None:
    text = STYLES_CSS.read_text(encoding="utf-8")
    # An animation's keyframes are named in one space for every stylesheet, so the page's are
    # its own by name; their `from` and `to` are steps, not selectors.
    keyframes = r"@keyframes\s+([\w-]+)\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}"
    names = re.findall(keyframes, text)
    assert all(name.startswith("github-pull-") for name in names), names
    rules = _rules_of(re.sub(keyframes, "", text))
    # A state's color tokens, in the two blocks a theme's tokens are declared in. Each names
    # only those, so it styles nothing itself.
    themes = (":root", '[data-theme="dark"]')
    for theme in themes:
        for declaration in rules[theme].split(";"):
            assert declaration.strip() == "" or declaration.strip().startswith("--github-pull-")
    assert [
        selector
        for selector in rules
        if not selector.startswith(".github-pull") and selector not in themes
    ] == []


def test_a_text_is_set_in_a_kpress_article_the_page_makes() -> None:
    """A text reads as the same Markdown a file reads as, because it is the same rules.

    KPress's stylesheets set its type, spacing, lists, tables, and code. The article and
    every class in it are the page's own, chosen by element (``kpressProse``); the session
    in ``tests/dom/inert-html-session.js`` pins what that builds.
    """

    source = PAGE_JS.read_text(encoding="utf-8")
    assert re.search(
        r'h\("article", \{ class: "kpress kpress-inert" \}, \[\s*'
        r"inert\.kpressProse\(nodes, document\),?\s*\]\)",
        source,
    )
    assert '{ class: "metabrowser-kpress-host" }' in source
    # Nothing but the card's own edges is left to this stylesheet.
    rules = _style_rules()
    assert "margin-block-start: 0" in rules[".github-pull-text .kpress-prose > :first-child"]
    assert "margin-block-end: 0" in rules[".github-pull-text .kpress-prose > :last-child"]
    for selector in rules:
        assert ".kpress" not in selector.replace(".github-pull-text .kpress-prose > ", "")


def _rem(length: str) -> float:
    assert length == "0" or length.endswith("rem"), length
    return 0.0 if length == "0" else float(length.removesuffix("rem"))


def test_a_heading_is_nearer_its_section_than_what_precedes_it() -> None:
    """A heading belongs to the section it opens, so it has more space above it than below.

    Inside a text the space is KPress's, as in a file: a heading's top margin collapses with
    the block before it, so after any block each level has at least its own top margin
    above it, and KPress sets that above what is below it, the larger of its bottom margin
    and a paragraph's top. At the top of a text the page trims the heading's margin, so the
    card's padding is the space above it and must be at least any level's space below.
    It was a header row's 8 px under an h2 keeping 16 px below. KPress's lengths are rem,
    and the app leaves the root at the browser's 16 px. Measured in Chrome by
    ``tests/test_github_pull_text_chrome.py``.
    """

    root_px = 16
    kpress = _rules_of(kpress_adapter.get_kpress_static_asset("css/document.css").content.decode())
    found = re.findall(r"margin-block:\s*([^;]+);", kpress[".kpress-prose p"])
    paragraph_top = _rem(found[-1].split()[0])
    below: dict[int, float] = {}
    for level in range(1, 7):
        top, bottom = (_rem(side) for side in _vertical_margins(kpress[f".kpress-prose h{level}"]))
        # KPress takes a paragraph's top margin away under h4 to h6: read what that rule
        # declares, so a changed value is checked rather than assumed to be zero.
        after = paragraph_top
        adjacent = kpress.get(f".kpress-prose h{level} + p")
        if adjacent is not None:
            declared = re.findall(r"margin-(?:top|block-start):\s*([^;]+);", adjacent)
            assert declared, adjacent
            after = _rem(declared[-1].strip())
        below[level] = max(bottom, after) * root_px
        assert top * root_px > 0
        assert top * root_px >= below[level], f"h{level}"
    padding = _style_rules()[".github-pull-text"]
    inset = re.search(r"padding:\s*var\((--[\w-]+)\)", padding)
    assert inset is not None, padding
    shell = (PAGE_JS.parents[2] / "static" / "styles.css").read_text(encoding="utf-8")
    # The pad steps up in wider windows (styles.css, after its root rule), so the narrowest
    # of its values is the one that must hold.
    token = re.findall(rf"{inset.group(1)}:\s*(\d+)px;", shell)
    assert token
    assert min(int(value) for value in token) >= max(below.values())


def test_a_wide_table_and_a_long_word_stay_reachable_in_a_card() -> None:
    """The card clips what overflows it, so what is too wide must scroll or break itself.

    KPress does both, on the classes ``kpressProse`` gives a table's wrapper and a code
    block. Measured in Chrome 152 on 2026-11-02 in a 661 px text: an 8-column table of
    400-character cells has a 769 px ``scrollWidth`` in its 661 px wrapper, a 400-character
    line of code 2,855 px in its 659 px block, and a 400-character word and a long URL
    break at the text's edge. The card's own ``scrollWidth`` stays its 685 px width.
    """

    rules = _style_rules(PAGE_JS.parents[2] / "static" / "styles.css")
    assert "overflow: hidden" in rules[".page-card"]
    inert_js = (PAGE_JS.parents[2] / "static" / "inert-html.js").read_text(encoding="utf-8")
    assert 'pre.className = "kpress-code"' in inert_js
    assert 'table.className = "kpress-table"' in inert_js
    assert 'parent.className = "kpress-table-wrap"' in inert_js
    document_css = kpress_adapter.get_kpress_static_asset("css/document.css").content.decode()
    components_css = kpress_adapter.get_kpress_static_asset("css/components.css").content.decode()
    assert "overflow-wrap: break-word" in document_css
    assert (
        "overflow-x: auto" in components_css[components_css.index(".kpress-table-wrap {") :][:400]
    )
    assert "overflow-x: auto" in document_css[document_css.rindex(".kpress-code {") :][:300]


def test_a_text_arrives_in_the_two_wrappers_kpress_prose_drops() -> None:
    """A trim on the prose's children reaches a text's first block only if they are its own."""

    html = read_recording("github-pull-page-responses.json")["markdown body"]["body"]["html"]
    wrappers = re.match(r"\s*((?:<div>)*)", html)
    assert wrappers is not None and wrappers.group(1) == "<div>" * 2
    source = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    table = harden(
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
    # A table's own wrapper is the third, the one kpressProse names.
    assert re.match(r"\s*<div><div><div><table>", table), table
