"""The inert-Markdown allowlist, the same on the server and in the browser.

``src/metabrowser/inert_html.py`` hardens untrusted Markdown on the server and
``static/inert-html.js`` rebuilds it in the page. These tests prove the two share one
allowlist, and that they make the same markup of the same input: KPress's own sanitized
render of a hostile document, in both link modes, parsed once by Python's HTML parser and
handed to each.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from metabrowser import inert_html, kpress_adapter
from metabrowser.git.message import COMMIT_MESSAGE_LINK_BASE
from metabrowser.inert_html import harden
from tests.github_pull_fixture import HOSTILE_COMMENT, allowlist_violations, html_tree
from tests.golden_harness import check_recording, run_session
from tests.required_tools import needs_node

REPO_ROOT = Path(__file__).resolve().parent.parent
INERT_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "inert-html.js"
PR_PAGE = "https://github.com/octo/demo/pull/7"

# A document with both kinds of reference inside the served tree, and a repository image.
HOSTILE_README = (
    HOSTILE_COMMENT + "\n![diagram](docs/diagram.png) ![tracker](https://example.com/t.gif)"
    ' <img src="//example.com/p.gif"> <img src="data:image/png;base64,AAAA">\n\n'
    # Badges: images in links, which keep their destinations, and images that are not in
    # one, from the web over https, and over http, which the page does not load.
    "[![Follow @ojoshe on X](https://img.shields.io/badge/follow-%40ojoshe-black)]"
    "(https://x.com/ojoshe)"
    " [![CI](https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg)]"
    "(https://github.com/octo/demo/actions/workflows/ci.yml)"
    " ![standalone](https://img.shields.io/badge/standalone-blue)"
    " ![insecure](http://example.com/insecure.png)\n\n"
    "[Guide](docs/guide.md) [Top](#readme) [Up](../x.md)"
    ' <a href="java\tscript:alert(1)">tab</a> <a href="\\\\example.com/x">slashes</a>\n\n'
    # References to the application rather than the tree, and a bare web scheme.
    "[api](/api/tree) [dots](/./api/tree) [escaped](/%61pi/tree) [debug](/_debug/tasks)"
    " [query](?q=1) [raw](/raw?path=evil.html) ![raw image](/raw?path=x.png)"
    " [bare](https:evil.test/no-slashes) [one slash](HTTPS:/one.test/x)\n\n"
    # The same routes behind escaped dots and separators.
    '<a href="/%2e%2e/raw?path=evil.js">dotdot</a> <a href="/.%2E/raw?x">dot2e</a>'
    ' <a href="/api%2ftree">slash</a> <a href="/%5capi/tree">back</a>'
    ' <img src="/%2e%2e/api/tree" alt="dotimg"> <img src="/.%2E/raw?path=x.png" alt="dot2eimg">\n'
    # A task list, and checkboxes written in raw HTML, which are kept in its box's shape
    # wherever they stand: in a paragraph with every attribute a form control can carry,
    # and in a table cell; any other input goes.
    "\n- [ ] Open\n- [x] Done\n- [X] Also done\n\n"
    '<INPUT TYPE="CheckBox" name="agree" form="f" value="yes" onclick="alert(1)" autofocus'
    ' checked> raw <input type="text" value="typed">\n\n'
    '| Done |\n|---|\n| <input type="checkbox" checked> |\n'
)
# The boxes KPress and both allowlists keep of HOSTILE_README, in document order.
HOSTILE_README_BOXES = [
    '<input type="checkbox" disabled>',
    *['<input type="checkbox" disabled checked>'] * 4,
]

# Runs the production sanitizer on a tree read from stdin and prints the rebuilt markup.
_NODE = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const [inertPath] = process.argv.slice(1);
const context = { window: {}, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
const inert = context.window.MetabrowserInertHtml;
const input = JSON.parse(fs.readFileSync(0, "utf8"));
// The settings the shell injects, which the sanitizer reads each time it runs.
if (input.settings) {
  context.window.METABROWSER_SETTINGS = input.settings;
}
if (input.lists) {
  process.stdout.write(JSON.stringify({
    tags: inert.ALLOWED_TAGS, dropped: inert.DROPPED_WITH_CONTENT,
    attributes: inert.ALLOWED_ATTRIBUTES, prefix: inert.ANCHOR_PREFIX,
    align: inert.ALIGN_VALUES, dimensions: inert.DIMENSIONS,
    fallback: inert.IMAGE_FALLBACK_CLASS, referrer: inert.IMAGE_REFERRER_POLICY,
    checkbox: inert.CHECKBOX_ATTRIBUTES,
  }));
  process.exit(0);
}
if (input.remoteImages) {
  process.stdout.write(JSON.stringify(
    input.remoteImages.map(([src, base]) => inert.remoteImage(src, base))));
  process.exit(0);
}
if (input.slugs) {
  process.stdout.write(JSON.stringify(input.slugs.map((text) => inert.headingSlug(text))));
  process.exit(0);
}
const nodes = (tree) => tree.map((node) => typeof node === "string"
  ? { nodeType: 3, nodeValue: node }
  : { nodeType: 1, tagName: node.tag.toUpperCase(), childNodes: nodes(node.children),
      getAttribute: (name) => node.attrs.find(([key]) => key === name)?.[1] ?? null });
const doc = {
  createTextNode: (text) => ({ text }),
  createElement: (tag) => ({ tag, attributes: [], children: [],
    setAttribute(name, value) { this.attributes.push([name, value]); },
    hasAttribute(name) { return this.attributes.some(([key]) => key === name); },
    append(...more) { this.children.push(...more); } }),
};
const escape = (value) => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const serialize = (list) => list.map((node) => "text" in node ? escape(node.text)
  : `<${node.tag}${node.attributes.map(([name, value]) => ` ${name}="${escape(value)}"`).join("")}>`
    + (["br", "hr", "img", "input"].includes(node.tag) ? ""
      : `${serialize(node.children)}</${node.tag}>`))
  .join("");
process.stdout.write(serialize(inert.sanitizeNodes(nodes(input.tree), doc, input.base, input.keepPathRelative)));
"""

pytestmark = needs_node


def _node(payload: dict[str, Any]) -> str:
    result = subprocess.run(
        ["node", "-e", _NODE, str(INERT_JS)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=50,
        check=True,
    )
    return result.stdout


def _tokens(html: str) -> list[tuple[str, ...]]:
    """*html* as a sequence of tags, sorted attributes, and text, to compare markup."""

    found: list[tuple[str, ...]] = []

    class _Read(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            flat = [f"{name}={'' if value is None else value}" for name, value in attrs]
            found.append(("start", tag, *sorted(flat)))

        def handle_endtag(self, tag: str) -> None:
            found.append(("end", tag))

        def handle_data(self, data: str) -> None:
            if found and found[-1][0] == "text":
                found[-1] = ("text", found[-1][1] + data)
            else:
                found.append(("text", data))

    reader = _Read(convert_charrefs=True)
    reader.feed(html)
    reader.close()
    return found


def _kpress(text: str) -> str:
    return str(
        kpress_adapter.render_kpress_view(
            source_text=text,
            source_path="README.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash="inert-html-test",
            size=len(text.encode()),
            include_toc="off",
        )["html"]
    )


def test_the_browser_and_the_server_share_one_allowlist() -> None:
    lists = json.loads(_node({"lists": True}))
    assert sorted(lists["tags"]) == sorted(inert_html.ALLOWED_TAGS)
    assert sorted(lists["dropped"]) == sorted(inert_html.DROPPED_WITH_CONTENT)
    assert {tag: tuple(names) for tag, names in lists["attributes"].items()} == (
        inert_html.ALLOWED_ATTRIBUTES
    )
    assert lists["prefix"] == inert_html.ANCHOR_PREFIX
    assert lists["fallback"] == inert_html.IMAGE_FALLBACK_CLASS
    assert lists["referrer"] == inert_html.IMAGE_REFERRER_POLICY
    assert tuple(tuple(pair) for pair in lists["checkbox"]) == inert_html.CHECKBOX_ATTRIBUTES
    assert {tag: tuple(values) for tag, values in lists["align"].items()} == (
        inert_html.ALIGN_VALUES
    )
    assert {tag: tuple(names) for tag, names in lists["dimensions"].items()} == (
        inert_html.DIMENSIONS
    )


# A commit message's base keeps only absolute http(s) addresses (git/message.py).
@pytest.mark.parametrize(
    ("base", "images"), [(None, True), (PR_PAGE, False), (COMMIT_MESSAGE_LINK_BASE, False)]
)
def test_both_sides_make_the_same_inert_markup_of_a_hostile_document(
    base: str | None, images: bool
) -> None:
    rendered = _kpress(HOSTILE_README)
    server = harden(rendered, base)
    browser = _node({"tree": html_tree(rendered), "base": base})
    assert allowlist_violations(server, images=images) == []
    assert allowlist_violations(browser, images=images) == []
    assert _tokens(browser) == _tokens(server)
    assert re.findall(r"<input[^>]*>", server) == HOSTILE_README_BOXES


@pytest.mark.parametrize(
    ("markup", "kept"),
    [
        # KPress's Mermaid figure: its block keeps GitHub's fallback language.
        (_kpress("```mermaid\nflowchart LR\n  A --> B\n```\n"), True),
        # GitHub's own fallback spelling, whatever its case.
        ('<pre lang="Mermaid"><code>graph TD</code></pre>', True),
        # Any other language, and the attribute on any other element, is dropped.
        ('<pre lang="python"><code>x = 1</code></pre>', False),
        ('<p lang="mermaid">graph TD</p>', False),
    ],
)
def test_a_mermaid_block_keeps_its_language_and_nothing_else_does(markup: str, kept: bool) -> None:
    server = harden(markup, None)
    browser = _node({"tree": html_tree(markup), "base": None})
    assert _tokens(browser) == _tokens(server)
    assert ('<pre lang="mermaid">' in server) is kept
    assert server.count("lang=") == int(kept)


HOSTILE_LINKS = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "inert-html-hostile-links.json").read_text(encoding="utf-8")
)


def _numeric(text: str) -> str:
    """*text* with every character written as a numeric character reference."""

    return "".join(f"&#{ord(character)};" for character in text)


@pytest.mark.parametrize("base", [None, PR_PAGE, COMMIT_MESSAGE_LINK_BASE])
@pytest.mark.parametrize("written", [lambda href: html.escape(href, quote=True), _numeric])
def test_neither_side_keeps_a_link_that_is_not_http(base: str | None, written: Any) -> None:
    """A link keeps its address only when it is ``http`` or ``https``, on both sides.

    KPress's own sanitizer removes a ``javascript:`` link before either side sees it, so
    a hostile document rendered through KPress never reaches this filter: a side that
    kept every scheme passed every other test here. This corpus is fed to each side as
    HTML, written plainly and as character references, which a parser reads the same.
    """

    refused, kept = HOSTILE_LINKS["refused"], HOSTILE_LINKS["kept"]
    document = "".join(
        f'<a href="{written(href)}">{name}</a>' for name, href in {**refused, **kept}.items()
    )
    # A kept link's scheme comes out in lower case on both sides, as a URL parser writes it,
    # with no CR, which comes out before the scheme is read, or the server's slice of the
    # address by the scheme's length would land in the wrong place.
    clean = {name: href.replace("\r", "") for name, href in kept.items()}
    expected = "".join(f"<a>{name}</a>" for name in refused) + "".join(
        f'<a href="{href[: href.index(":")].lower()}{href[href.index(":") :]}"'
        f' target="_blank" rel="noopener noreferrer">{name}</a>'
        for name, href in clean.items()
    )
    assert harden(document, base) == expected
    assert _node({"tree": html_tree(document), "base": base}) == expected


def test_a_document_keeps_its_own_references_and_images_and_those_from_the_web() -> None:
    inert = harden(_kpress(HOSTILE_README))
    assert '<img loading="lazy" src="docs/diagram.png" alt="diagram">' in inert
    assert '<a href="docs/guide.md">Guide</a>' in inert
    assert '<a href="#user-content-readme">Top</a>' in inert
    assert '<a href="../x.md">Up</a>' in inert
    # An image from the web is kept over https, with no referrer sent, however it is
    # written (`//host` is https here too); one with no http(s) address is not an image.
    for kept in (
        '<img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/t.gif"'
        ' alt="tracker">',
        '<img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/p.gif">',
    ):
        assert kept in inert, kept
    assert "data:image" not in inert and "javascript" not in inert
    assert "<a>tab</a>" in inert
    assert (
        '<a href="https://example.com/x" target="_blank" rel="noopener noreferrer">slashes</a>'
        in inert
    )


def test_a_document_never_names_the_application_or_a_bare_scheme_ambiguously() -> None:
    inert = harden(_kpress(HOSTILE_README))
    for text in (
        "api",
        "dots",
        "escaped",
        "debug",
        "query",
        "raw",
        "dotdot",
        "dot2e",
        "slash",
        "back",
    ):
        assert f"<a>{text}</a>" in inert, text
    for text in ("raw image", "dotimg", "dot2eimg"):
        assert f'<span class="mb-image-fallback">{text}</span>' in inert, text
    assert '<a href="https://evil.test/no-slashes" target="_blank"' in inert
    assert '<a href="https://one.test/x" target="_blank"' in inert
    # In a pull request's comment, a bare https: shares the page's scheme and is relative.
    comment = harden(_kpress("[bare](https:evil.test/no-slashes)"), PR_PAGE)
    assert 'href="https://github.com/octo/demo/pull/evil.test/no-slashes"' in comment


def test_pr_text_marks_only_authored_path_relative_links() -> None:
    absolute = "https://github.com/octo/demo/pull/7.patch"
    marker = 'data-metabrowser-path-relative=""'
    source = (
        '<a href="7.patch">relative</a>'
        f'<a href="{absolute}" {marker}>forged</a>'
        '<a href="../pull/7.patch">parent</a>'
        '<a href="#anchor">fragment</a>'
        f'<a href="javascript:alert(1)" {marker}>unsafe</a>'
    )
    hardened = harden(source, PR_PAGE, mark_path_relative=True)
    assert hardened.count(f'href="{absolute}"') == 3
    assert hardened.count(marker) == 1
    assert f"{marker}>relative</a>" in hardened
    assert "<a>unsafe</a>" in hardened
    payload = {"tree": html_tree(hardened), "base": PR_PAGE}
    assert _node({**payload, "keepPathRelative": True}) == hardened
    assert _node(payload) == hardened.replace(f" {marker}", "")


def test_harden_is_idempotent() -> None:
    for base in (None, PR_PAGE, COMMIT_MESSAGE_LINK_BASE):
        once = harden(_kpress(HOSTILE_README), base)
        assert harden(once, base) == once


@pytest.mark.parametrize(
    "written",
    [
        '<img src="docs/a.png" alt="a">',
        '<img src="docs/a.png" alt="a" loading="lazy">',
        '<img src="docs/a.png" alt="a" loading="eager">',
        '<img src="docs/a.png" alt="a" loading="LAZY">',
        '<img src="docs/a.png" alt="a" loading>',
        '<img src="docs/a.png" alt="a" loading="lazy&quot; onload=&quot;alert(1)">',
        # Everything else an image can carry, and sizes that are not numbers, none of which
        # may come along with it.
        '<img src="docs/a.png" alt="a" loading="eager" srcset="https://example.com/x.png 2x"'
        ' sizes="1px" fetchpriority="high" decoding="sync" crossorigin="use-credentials"'
        ' referrerpolicy="unsafe-url" ismap usemap="#m" width="1;x" height="auto" longdesc="x"'
        ' lowsrc="https://example.com/y.png" attributionsrc="https://example.com/z"'
        ' style="position:fixed" class="c" id="i" name="n" data-x="1" onerror="alert(1)"'
        ' onload="alert(2)">',
    ],
)
def test_a_kept_image_is_lazy_whatever_the_document_wrote(written: str) -> None:
    """A kept image loads as it nears the reader, as KPress's own render has it do.

    ``loading`` is a constant both sides write, so nothing of the document's reaches it:
    not an ``eager`` that fetches at once, and not a value that carries anything else.
    """

    expected = '<img loading="lazy" src="docs/a.png" alt="a">'
    assert harden(written) == expected
    assert _node({"tree": html_tree(written), "base": None}) == expected
    # The page hardens the server's answer again, and it comes out the same.
    assert harden(expected) == expected
    assert _node({"tree": html_tree(expected), "base": None}) == expected
    assert allowlist_violations(expected, images=True) == []


def test_the_allowlist_check_refuses_any_other_loading_value() -> None:
    for value in ("eager", "LAZY", "", 'lazy" onload="alert(1)'):
        written = f"<img loading='{value}' src='docs/a.png'>"
        assert any("loading" in found for found in allowlist_violations(written, images=True))
    # A kept image with no `loading` is as eager as one that says so.
    assert allowlist_violations('<img src="docs/a.png">', images=True) == ["img[loading missing]"]
    assert allowlist_violations('<img loading="lazy" src="docs/a.png">', images=True) == []


_FALLBACK = '<span class="mb-image-fallback"'
_NEW_TAB = ' target="_blank" rel="noopener noreferrer"'
_FROM_THE_WEB = (
    '<img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/a.png" alt="a">'
)


@pytest.mark.parametrize(
    ("base", "written", "expected"),
    [
        # A pull-request comment keeps no image of its own, which has no tree to name one in:
        # a path is a link to where it would be, whatever `loading` it asks for.
        (
            PR_PAGE,
            '<img src="docs/a.png" alt="a" loading="lazy">',
            f'<a href="https://github.com/octo/demo/pull/docs/a.png"{_NEW_TAB}>'
            f'{_FALLBACK} data-tip-text="https://github.com/octo/demo/pull/docs/a.png">a</span></a>',
        ),
        # An image the comment writes in full, over https, is kept, as a document's is; the
        # `loading` it asks for is not read.
        (PR_PAGE, '<img src="https://example.com/a.png" alt="a" loading="eager">', _FROM_THE_WEB),
        (None, '<img src="https://example.com/a.png" alt="a" loading="lazy">', _FROM_THE_WEB),
        # Over http it is not loaded: a link to it.
        (
            None,
            '<img src="http://example.com/a.png" alt="a" loading="lazy">',
            f'<a href="http://example.com/a.png"{_NEW_TAB}>'
            f'{_FALLBACK} data-tip-text="http://example.com/a.png">a</span></a>',
        ),
        # A reference to the application is not an image, nor a link: the alt text alone.
        (None, '<img src="/raw?path=a.png" alt="a" loading="lazy">', f"{_FALLBACK}>a</span>"),
    ],
)
def test_an_image_gains_nothing_from_loading_and_one_not_loaded_is_a_fallback(
    base: str | None, written: str, expected: str
) -> None:
    assert harden(written, base) == expected
    assert _node({"tree": html_tree(written), "base": base}) == expected


REMOTE_IMAGES = [
    # Over https, written in any spelling a browser reads as one.
    ("https://example.com/a.png", None, "https://example.com/a.png"),
    (" HTTPS://example.com/a.png\t", None, "https://example.com/a.png"),
    ("//example.com/a.png", None, "https://example.com/a.png"),
    ("\\\\example.com/a.png", None, "https://example.com/a.png"),
    ("https:example.com/a.png", None, "https://example.com/a.png"),
    ("https://example.com/a.png", PR_PAGE, "https://example.com/a.png"),
    ("//example.com/a.png", PR_PAGE, "https://example.com/a.png"),
    # Not over https, and not written in full, or carrying a credential: not loaded.
    ("http://example.com/a.png", None, None),
    ("data:image/png;base64,AAAA", None, None),
    ("javascript:alert(1)", None, None),
    ("ftp://example.com/a.png", None, None),
    ("https://user:secret@example.com/a.png", None, None),
    ("https://user@example.com/a.png", None, None),
    # No host of its own, or one a browser's URL parser refuses: an address that resolves
    # against the page, or none, and no image of the web.
    ("//", None, None),
    ("//", PR_PAGE, None),
    ("\\\\", PR_PAGE, None),
    ("https:///", None, None),
    ("https://:443/a.png", None, None),
    ("//?a.png", None, None),
    ("https://x.com:99999/a.png", None, None),
    ("https://[::1/a.png", None, None),
    ("https://[zz]/a.png", None, None),
    ("https://evil.test127.0.0.1/a.png", None, None),
    ("https://1.2.3.4.5/a.png", None, None),
    ("https://256.1.1.1/a.png", None, None),
    ("https://x.com%2f@evil/a.png", None, None),
    ("https://x .com/a.png", None, None),
    # Written outside ASCII, which a document can hide another host in (IDNA drops some
    # characters and maps others).
    ("https://m\u00fcnchen.de/a.png", None, None),
    ("//\u200b..", None, None),
    # And what is a host: an IPv4 address in any form a browser reads, and an IPv6 one.
    ("https://127.0.0.1/a.png", None, "https://127.0.0.1/a.png"),
    ("https://[::1]/a.png", None, "https://[::1]/a.png"),
    ("https://x.com:8443/a.png", None, "https://x.com:8443/a.png"),
    ("docs/a.png", None, None),
    ("/raw?path=a.png", None, None),
    ("docs/a.png", PR_PAGE, None),
    ("/a.png", PR_PAGE, None),
    ("https:docs/a.png", "https://github.com/octo/demo/pull/7", None),
    ("", None, None),
    (None, None, None),
]


@pytest.mark.parametrize(("src", "base", "expected"), REMOTE_IMAGES)
def test_only_an_address_written_in_full_over_https_is_loaded(
    src: str | None, base: str | None, expected: str | None
) -> None:
    """Both sides read what an image from the web is the same way."""

    assert inert_html.remote_image(src, base) == expected
    assert json.loads(_node({"remoteImages": [[src, base]]})) == [expected]


REMOTE_IMAGE_CORPUS = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "inert-html-remote-image-corpus.json").read_text(
        encoding="utf-8"
    )
)


def test_both_sides_agree_which_addresses_are_images_of_the_web_on_a_corpus() -> None:
    """The server's choice and the page's are one, on addresses written to tell them apart.

    ``tests/fixtures/inert-html-remote-image-corpus.json`` is every degenerate shape of an
    address written in full (no host, an empty port, a credential, IPv6 and IPv4 forms, a
    host outside ASCII, backslashes, tabs, a bare scheme), each with no base and with a
    pull request's, beside what a seeded fuzz of such fragments (seed 644) made of them: the
    first sixty it accepted, and sixty it refused. Each side reads the address
    its own way, Python's split and the browser's URL parser, so agreeing on which are
    images is the check; what they write for one differs only as a URL parser writes it
    (a trailing slash, lower case, an IPv4 address in dots).
    """

    py = [inert_html.remote_image(src, base) for src, base in REMOTE_IMAGE_CORPUS]
    js = json.loads(_node({"remoteImages": REMOTE_IMAGE_CORPUS}))
    disagree = [
        (case, one, other)
        for case, one, other in zip(REMOTE_IMAGE_CORPUS, py, js, strict=True)
        if (one is None) != (other is None)
    ]
    assert disagree == []
    kept = [one for one in py if one is not None]
    assert 100 < len(kept) < len(py) - 100, "the corpus has both kinds"
    assert all(one.startswith("https://") for one in kept)
    # A pull request's page is no host an address with none resolves to.
    assert not any(
        one is not None and one.startswith("https://github.com/octo/demo/pull")
        for (_src, base), one in zip(REMOTE_IMAGE_CORPUS, py, strict=True)
        if base is not None
    )


def _parsed(html: str) -> list[tuple[str, tuple[str, ...]]]:
    """Each element of *html* with the elements it is inside, innermost last."""

    found: list[tuple[str, tuple[str, ...]]] = []
    stack: list[str] = []

    class _Read(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            found.append((tag, tuple(stack)))
            if tag not in {"img", "br"}:
                stack.append(tag)

        def handle_endtag(self, tag: str) -> None:
            if tag in stack:
                del stack[stack.index(tag) :]

    reader = _Read()
    reader.feed(html)
    reader.close()
    return found


BADGES = (
    '<p><a href="https://x.com/ojoshe"><img src="https://img.shields.io/badge/f-x-black"'
    ' alt="Follow @ojoshe on X"></a> <a href="https://github.com/o/r/actions/ci.yml">'
    '<img src="https://github.com/o/r/actions/ci.yml/badge.svg" alt="CI"></a>'
    ' <a href="https://example.com/dest"><img src="http://example.com/insecure.png" alt="Old">'
    '</a> <img src="https://img.shields.io/badge/s-blue" alt="Standalone">'
    ' <img src="http://example.com/plain.png" alt="Plain http"></p>'
)


@pytest.mark.parametrize("base", [None, PR_PAGE, COMMIT_MESSAGE_LINK_BASE])
def test_a_badge_keeps_its_link_and_no_link_holds_another_or_nothing(base: str | None) -> None:
    """A linked image is never an empty link followed by a link to the image.

    The first bug: ``<a href=destination><a href=image>alt</a></a>`` is not valid
    HTML, so a browser reads it as ``<a href=destination></a><a href=image>alt</a>``, an
    empty link and a visible one that goes to the image, not where the author sent it.
    """

    server = harden(BADGES, base)
    browser = _node({"tree": html_tree(BADGES), "base": base})
    assert _tokens(browser) == _tokens(server)
    assert allowlist_violations(server) == []
    elements = _parsed(server)
    # No link is inside another, and none is empty: each holds an image or a fallback.
    assert not any(tag == "a" and "a" in inside for tag, inside in elements)
    assert server.count("</a>") == server.count("<a ")
    assert re.search(r"<a[^>]*></a>", server) is None, server
    # The author's destinations are kept, each link holds one image, and the images
    # over http are the link's own content, with the address they stand for.
    for destination in (
        "https://x.com/ojoshe",
        "https://github.com/o/r/actions/ci.yml",
        "https://example.com/dest",
    ):
        assert f'<a href="{destination}"' in server, destination
    assert 'src="https://img.shields.io/badge/f-x-black" alt="Follow @ojoshe on X"></a>' in server
    assert (
        '<a href="https://example.com/dest" target="_blank" rel="noopener noreferrer">'
        '<span class="mb-image-fallback" data-tip-text="http://example.com/insecure.png">Old</span>'
        "</a>"
    ) in server
    # An image in no link that is not loaded links to the image, in the same chip.
    assert (
        '<a href="http://example.com/plain.png" target="_blank" rel="noopener noreferrer">'
        '<span class="mb-image-fallback" data-tip-text="http://example.com/plain.png">Plain http'
        "</span></a>"
    ) in server
    # And one that is loaded stays an image, with no referrer sent.
    assert (
        '<img loading="lazy" referrerpolicy="no-referrer" '
        'src="https://img.shields.io/badge/s-blue" alt="Standalone">'
    ) in server


@pytest.mark.parametrize("base", [None, PR_PAGE])
def test_the_reader_who_blocks_remote_images_sees_their_alt_text_in_the_same_links(
    base: str | None,
) -> None:
    """The setting is the page's: the server's answer is the same, the page rebuilds it.

    ``BLOCK_REMOTE_IMAGES`` is what ``/view/`` carries when the reader's cookie says so, and
    ``static/inert-html.js`` makes every image from the web the fallback, a linked one
    inside its own link and an unlinked one inside a link to the image. Images inside the
    served tree are not from the web and still load.
    """

    server = harden(BADGES + '<p><img src="docs/a.png" alt="local"></p>', base)
    blocked = _node(
        {
            "tree": html_tree(server),
            "base": base,
            "settings": {"BLOCK_REMOTE_IMAGES": True},
        }
    )
    # No image from the web is left; a document's own image is, a comment's is a link.
    assert "referrerpolicy" not in blocked
    assert ('<img loading="lazy" src="docs/a.png" alt="local">' in blocked) is (base is None)
    assert not any(tag == "a" and "a" in inside for tag, inside in _parsed(blocked))
    assert (
        '<a href="https://x.com/ojoshe" target="_blank" rel="noopener noreferrer">'
        '<span class="mb-image-fallback"'
        ' data-tip-text="https://img.shields.io/badge/f-x-black">Follow @ojoshe on X</span></a>'
    ) in blocked
    assert (
        '<a href="https://img.shields.io/badge/s-blue" target="_blank" rel="noopener noreferrer">'
        '<span class="mb-image-fallback"'
        ' data-tip-text="https://img.shields.io/badge/s-blue">Standalone</span></a>'
    ) in blocked
    assert allowlist_violations(blocked, images=True) == []
    # The same input with the setting off, or absent, is what the server wrote.
    for settings in ({"BLOCK_REMOTE_IMAGES": False}, {}, {"BLOCK_REMOTE_IMAGES": "true"}):
        open_ = _node({"tree": html_tree(server), "base": base, "settings": settings})
        assert _tokens(open_) == _tokens(server)


def test_a_task_lists_box_keeps_its_state_and_no_other_input_survives() -> None:
    """KPress's box stays a disabled checkbox, ticked as the document has it, on both sides.

    The allowlist dropped every ``input``, so ``- [x] Done`` read as an item with no box,
    and a tick was a change neither the Document view nor a rendered diff showed.
    """

    rendered = _kpress("- [ ] Open\n- [x] Done\n- [X] Also done\n")
    server = harden(rendered)
    assert re.findall(r"<input[^>]*>", server) == [
        '<input type="checkbox" disabled>',
        '<input type="checkbox" disabled checked>',
        '<input type="checkbox" disabled checked>',
    ]
    assert _tokens(_node({"tree": html_tree(rendered), "base": None})) == _tokens(server)
    written = (
        # KPress's own box, ticked.
        '<input class="task-list-item-checkbox" checked="checked" disabled="disabled"'
        ' type="checkbox">'
        # Every other attribute of a checkbox goes, and so does every other input.
        '<input type="CheckBox" name="agree" form="f" value="yes" onclick="alert(1)" autofocus>'
        '<input type=" checkbox" checked><input type="text" value="typed"><input type="submit">'
        # A type a browser reads as a text field, which only Unicode lowercasing (U+212A
        # KELVIN SIGN to k) would read as a checkbox.
        '<input type="checKbox" checked>'
        "<input><input/>"
    )
    expected = '<input type="checkbox" disabled checked><input type="checkbox" disabled>'
    for base in (None, PR_PAGE):
        assert harden(written, base) == expected
        assert _node({"tree": html_tree(written), "base": base}) == expected.replace(
            "disabled", 'disabled=""'
        ).replace("checked>", 'checked="">')
    assert harden(expected) == expected
    assert allowlist_violations(expected) == []
    # The allowlist check refuses any other shape of one.
    assert allowlist_violations('<input type="checkbox">') == ["input[('type', 'checkbox')]"]
    assert allowlist_violations('<input type="text" disabled>') == [
        "input[('type', 'text'), ('disabled', None)]"
    ]


def test_both_sides_read_a_repeated_attribute_as_its_first() -> None:
    """A browser keeps an attribute's first copy and drops the rest, and so do KPress's
    sanitizer and the page's sanitizer (`getAttribute`); the server's hardener reads raw
    HTML the same way, so what it keeps never rests on KPress having dropped the copies."""

    written = (
        '<input type="text" type="checkbox"><input type="checkbox" type="text" checked>'
        '<p align="center" align="right">a</p><p align="middle" align="center">b</p>'
        '<a href="https://example.org/a" href="javascript:alert(1)">c</a>'
        '<a href="javascript:alert(1)" href="https://example.org/b">d</a>'
        '<ol start="2" start="9"><li>e</li></ol>'
        '<table><tr><td colspan="2" colspan="x">f</td><td colspan="x" colspan="3">g</td></tr>'
        "</table>"
        '<img src="https://example.com/a.png" src="javascript:alert(1)" alt="first"'
        ' alt="second">'
    )
    server = harden(written)
    assert server == (
        '<input type="checkbox" disabled checked><p align="center">a</p><p>b</p>'
        '<a href="https://example.org/a" target="_blank" rel="noopener noreferrer">c</a>'
        '<a>d</a><ol start="2"><li>e</li></ol>'
        '<table><tr><td colspan="2">f</td><td>g</td></tr></table>'
        '<img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/a.png"'
        ' alt="first">'
    )
    for base in (None, PR_PAGE):
        assert _tokens(_node({"tree": html_tree(written), "base": base})) == _tokens(
            harden(written, base)
        )


def test_a_document_keeps_the_fallbacks_shape_and_nothing_else_on_a_span() -> None:
    """The hardener's own span hardens to itself; no other attribute of a span survives."""

    chip = '<span class="mb-image-fallback" data-tip-text="https://example.com/a.png">a</span>'
    written = (
        f"{chip}"
        '<span class="mb-image-fallback" data-tip-text="javascript:alert(1)" style="x:y"'
        ' onclick="alert(1)" id="i" data-x="1" title="t">b</span>'
        '<span class="modal-overlay mb-image-fallback" data-tip-text="https://example.com/c">c</span>'
        '<span class="x" data-tip-text="https://example.com/d" style="position:fixed">d</span>'
    )
    expected = f'{chip}<span class="mb-image-fallback">b</span><span>c</span><span>d</span>'
    assert harden(written) == expected
    assert _node({"tree": html_tree(written), "base": None}) == expected
    assert harden(expected) == expected
    assert allowlist_violations(expected) == []
    # The allowlist check refuses what the hardener would drop.
    assert allowlist_violations('<span class="c" data-tip-text="x">y</span>') == [
        "span[class=c]",
        "span[data-tip-text=x]",
    ]


# The opening of Metabrowser's own README, which github.com draws as a 192-pixel logo
# centered over a centered title, and the other layouts a README writes with the
# attributes github.com keeps (html-pipeline's SanitizationFilter): an aligned block, a
# floated image, an image sized by its height alone, and an aligned, sized table.
GITHUB_LAYOUT = (
    '<p align="center"><img src="images/metabrowser-icon.png" alt="Metabrowser app icon"'
    ' width="192"></p>\n\n<h1 align="center">Metabrowser</h1>\n\n'
    '<div align="right">Right</div>\n\n'
    '<img src="docs/logo.png" alt="logo" align="right" width="25%">'
    '<img src="docs/badge.svg" alt="badge" height="20px">\n\n'
    '<table align="center" width="80%"><tr align="right"><td align="center" width="50%"'
    ' height="40">A</td><td>B</td></tr></table>\n'
)


def test_github_layout_attributes_survive_the_allowlist() -> None:
    """An untrusted README keeps the layout github.com draws it with, on both sides.

    The allowlist dropped every ``align`` but a cell's and every ``width`` and ``height``,
    so Metabrowser's README drew its logo at the file's 512 pixels, against the left edge.
    """

    rendered = _kpress(GITHUB_LAYOUT)
    server = harden(rendered)
    assert (
        '<p align="center"><img loading="lazy" src="images/metabrowser-icon.png"'
        ' alt="Metabrowser app icon" width="192"></p>'
    ) in server
    assert '<h1 id="user-content-metabrowser" align="center">Metabrowser</h1>' in server
    assert '<div align="right">Right</div>' in server
    assert (
        '<img loading="lazy" src="docs/logo.png" alt="logo" align="right" width="25%">'
        '<img loading="lazy" src="docs/badge.svg" alt="badge" height="20px">'
    ) in server
    assert (
        '<table align="center" width="80%"><tbody><tr align="right">'
        '<td align="center" width="50%" height="40">A</td><td>B</td></tr></tbody></table>'
    ) in server
    assert allowlist_violations(server, images=True) == []
    assert _tokens(_node({"tree": html_tree(rendered), "base": None})) == _tokens(server)
    # The page hardens the server's answer again, and it comes out the same.
    assert harden(server) == server
    assert _tokens(_node({"tree": html_tree(server), "base": None})) == _tokens(server)
    # A pull request's text keeps its blocks' layout; its images are links, as ever.
    comment = harden(rendered, PR_PAGE)
    assert (
        '<p align="center"><a href="https://github.com/octo/demo/pull/images/metabrowser-icon.png"'
    ) in comment
    assert '<h1 align="center">Metabrowser</h1>' in comment
    assert allowlist_violations(comment) == []
    assert _tokens(_node({"tree": html_tree(rendered), "base": PR_PAGE})) == _tokens(comment)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        # A keyword in any case is kept, lowercased, as a browser matches it.
        ('<p align="CENTER">x</p>', '<p align="center">x</p>'),
        (
            '<img src="docs/a.png" align="Center">',
            '<img loading="lazy" src="docs/a.png" align="center">',
        ),
        # Anything else in it, or around it, is not a keyword a browser reads.
        ('<p align="center;color:red">x</p>', "<p>x</p>"),
        ('<p align=" center">x</p>', "<p>x</p>"),
        ('<h2 align="middle">x</h2>', '<h2 id="user-content-x">x</h2>'),
        ('<img src="docs/a.png" align="justify">', '<img loading="lazy" src="docs/a.png">'),
        (
            '<table align="justify"><tr><td align="char">x</td></tr></table>',
            "<table><tr><td>x</td></tr></table>",
        ),
        # An element GitHub's attribute lays out nothing on keeps none.
        ('<span align="center" width="9">x</span>', "<span>x</span>"),
        ('<ul><li align="center">x</li></ul>', "<ul><li>x</li></ul>"),
        ('<a href="docs/a.md" align="right">x</a>', '<a href="docs/a.md">x</a>'),
        ('<p width="50%" height="9">x</p>', "<p>x</p>"),
        # A size is a number of pixels or a percentage, and nothing else.
        (
            '<img src="docs/a.png" width="expression(alert(1))" height="1e9">',
            '<img loading="lazy" src="docs/a.png">',
        ),
        (
            '<img src="docs/a.png" width="100vh" height="-5">',
            '<img loading="lazy" src="docs/a.png">',
        ),
        (
            '<img src="docs/a.png" width="123456" height="1.2345">',
            '<img loading="lazy" src="docs/a.png">',
        ),
        ('<img src="docs/a.png" width=" 9" height="9\n">', '<img loading="lazy" src="docs/a.png">'),
        (
            '<img src="docs/a.png" width="12.5%" height="80PX">',
            '<img loading="lazy" src="docs/a.png" width="12.5%" height="80PX">',
        ),
        (
            '<table width="100;position:fixed"><tr><td height="1 0">x</td></tr></table>',
            "<table><tr><td>x</td></tr></table>",
        ),
        # Nothing else comes with a kept one.
        (
            '<p align="center" style="position:fixed" onclick="alert(1)" class="c" id="i">x</p>',
            '<p align="center">x</p>',
        ),
    ],
)
def test_a_layout_attribute_is_a_keyword_or_a_number(written: str, expected: str) -> None:
    assert harden(written) == expected
    assert _node({"tree": html_tree(written), "base": None}) == expected
    assert allowlist_violations(expected, images=True) == []


def test_the_allowlist_check_refuses_a_layout_value_the_hardener_drops() -> None:
    assert allowlist_violations('<p align="center;x">x</p><td width="9vh">y</td>') == [
        "p[align=center;x]",
        "td[width=9vh]",
    ]
    assert allowlist_violations('<p align="CENTER">x</p>') == ["p[align=CENTER]"]
    assert allowlist_violations('<p align="center">x</p><td width="9%">y</td>') == []


FIXTURE_README = REPO_ROOT / "tests" / "fixtures" / "untrusted-markdown" / "README.md"


def test_the_session_plays_what_kpress_renders_of_the_hostile_readme() -> None:
    """``tests/dom/inert-html-session.js`` runs on KPress's render of the fixture README.

    The tree is Python's HTML parse of that render, recorded so the session never runs on
    markup a test wrote by hand; this fails when KPress renders it differently.
    ``make golden-update`` rewrites the recording and then
    ``tests/golden/cli-ui-inert-markdown.tryscript.md``.
    """

    check_recording(
        "inert-html-kpress-tree.json",
        html_tree(_kpress(FIXTURE_README.read_text(encoding="utf-8"))),
        transcript="cli-ui-inert-markdown.tryscript.md",
        indent=1,
    )
    transcript = run_session("inert-html-session.js")
    assert allowlist_violations(transcript["document"], images=True) == []
    assert allowlist_violations(transcript["comment"]) == []
    for mode in ("document", "comment"):
        assert allowlist_violations(transcript["links"][mode]) == []
    # With the reader's setting on, no image of the web is left, and what is left is allowed.
    assert allowlist_violations(transcript["blocked"]["document"], images=True) == []
    assert allowlist_violations(transcript["blocked"]["comment"]) == []
    for mode in ("document", "comment"):
        assert "referrerpolicy" not in transcript["blocked"][mode]
    assert allowlist_violations(transcript["fallbacks"]) == []
    assert allowlist_violations(transcript["badges"]["document"], images=True) == []
    for mode in ("comment", "blocked"):
        assert allowlist_violations(transcript["badges"][mode], images=True) == []
    assert transcript["inertRender"] == {"inert": True, "trusted": False}
    assert allowlist_violations(transcript["boxes"]) == []
    assert re.findall(r"<input[^>]*>", transcript["boxes"]) == [
        '<input type="checkbox" disabled>',
        *['<input type="checkbox" disabled checked>'] * 3,
    ]


# Headings written to attack the anchors: names of Object.prototype and window, ids and
# names of the document's own, repeats that collide with a numbered repeat, text that is
# all punctuation or emoji, a very long one, scripts and marks, and markup inside.
HOSTILE_HEADINGS = "\n\n".join(
    [
        "# Hostile headings",
        "## `__proto__`",
        "## constructor",
        "## constructor",
        "## hasOwnProperty",
        "## metabrowser",
        '<h2 id="metabrowser" name="MetabrowserInertHtml">Clobber</h2>',
        '<h3 id="user-content-clobber">Clobber</h3>',
        "## a-1",
        "## A",
        "## a",
        "## !!!",
        "## !!!",
        "## \U0001f680 Getting started",
        "## C++ & Rust: *fast* `code`",
        "## Über Straße ΣΊΣΥΦΟΣ",
        "## 日本語の見出し",
        "## Ⓐ x² Ⅻ café \u200d",
        "## العربية مَرحبا",
        "## ![logo](https://example.com/logo.png) Project",
        "## ![local](docs/local.png) Local",
        "<h2>Inside <svg><text>hidden</text></svg><script>x</script>shown</h2>",
        "## " + "Long " * 2000,
        "[a](#__proto__) [b](#constructor-1) [c](#user-content-a-2) [d](#) [e](#Über-straße)",
    ]
)


def test_headings_get_github_anchors_and_links_reach_them() -> None:
    inert = harden(_kpress(HOSTILE_HEADINGS))
    ids = [value for _tag, value in _heading_ids(inert)]
    assert ids[:19] == [
        "user-content-hostile-headings",
        "user-content-__proto__",
        "user-content-constructor",
        "user-content-constructor-1",
        "user-content-hasownproperty",
        "user-content-metabrowser",
        "user-content-clobber",
        "user-content-clobber-1",
        "user-content-a-1",
        "user-content-a",
        "user-content-a-2",
        "user-content-",
        "user-content--1",
        "user-content--getting-started",
        "user-content-c--rust-fast-code",
        "user-content-über-straße-σίσυφος",
        "user-content-日本語の見出し",
        "user-content-ⓐ-x-ⅻ-café-",
        "user-content-العربية-مَرحبا",
    ]
    # Text the page shows counts; hidden text not, and neither does an image the page
    # draws, from the web or the tree, as on github.com (an image the page does not load
    # is its alt text, which would).
    assert ids[19:22] == [
        "user-content--project",
        "user-content--local",
        "user-content-inside-shown",
    ]
    assert ids[22] == "user-content-" + "long-" * 1999 + "long"
    assert len(ids) == len(set(ids)) == 23
    # No id or name the document wrote survives; every link reaches the namespace.
    assert 'id="metabrowser"' not in inert and "name=" not in inert
    for fragment in ("__proto__", "constructor-1", "a-2", "%C3%9Cber-stra%C3%9Fe"):
        assert f'href="#user-content-{fragment}"' in inert, fragment
    assert '<a href="#">d</a>' in inert
    assert allowlist_violations(inert, images=True) == []
    # A pull request's comment has no anchors: its fragments are the pull request's.
    comment = harden(_kpress(HOSTILE_HEADINGS), PR_PAGE)
    assert " id=" not in comment
    assert 'href="https://github.com/octo/demo/pull/7#__proto__"' in comment


def test_both_sides_make_the_same_anchors() -> None:
    rendered = _kpress(HOSTILE_HEADINGS)
    browser = _node({"tree": html_tree(rendered), "base": None})
    assert _tokens(browser) == _tokens(harden(rendered))
    # The page hardens the server's answer again; the anchors come out the same.
    assert _tokens(_node({"tree": html_tree(harden(rendered)), "base": None})) == _tokens(
        harden(rendered)
    )


def test_both_sides_slug_the_same() -> None:
    samples = [
        "Hello World",
        "  spaced  out  ",
        "tab\tand\nnewline",
        "snake_case and kebab-case",
        "en–dash — em",
        "ÀÉÎÕÜ İstanbul ΣΊΣΥΦΟΣ",
        "Ⓐⓩ \U0001f130 \U0001f170 x²³ ½ Ⅻ ٣",
        "\u0301 combining \u200c\u200d joiners",
        "emoji \U0001f680\U0001f3fd flags \U0001f1fa\U0001f1f8",
        "\u00a0nbsp\u2003em space",
        "<>&\"'`",
    ]
    assert json.loads(_node({"slugs": samples})) == [
        inert_html.heading_slug(text) for text in samples
    ]


def test_harden_document_maps_the_ids_it_replaces() -> None:
    html, replaced = inert_html.harden_document(
        '<h1 id="title">T</h1><h2 id="">\U0001f680</h2><h2 id="part">Part</h2>'
        '<h2 id="part">Part</h2><h3>No id</h3>'
    )
    # The empty id KPress gives a heading with an empty slug is mapped; a repeated id
    # names no one heading, so neither is.
    assert replaced == {"title": "user-content-t", "": "user-content-"}
    assert '<h2 id="user-content-part-1">' in html


def test_the_page_keeps_the_servers_anchors() -> None:
    """The server's Unicode tables decide a slug: the page keeps each anchor it arrives
    with, once, so a character one side knows and the other does not cannot split them.
    A heading arriving with no anchor, or one already used, gets its own."""

    import unicodedata

    # A Sidetic letter (Unicode 17), unassigned in this Python's tables if they are older
    # than node's: the server drops it from the slug, and a newer browser would keep it.
    unknown = next(
        (chr(c) for c in range(0x10940, 0x10960) if unicodedata.category(chr(c)) == "Cn"),
        "x",
    )
    server = harden(_kpress(f"# Guide\n\n## Sidetic {unknown}\n\n## Sidetic\n"))
    assert _tokens(_node({"tree": html_tree(server), "base": None})) == _tokens(server)
    arrived = (
        '<h2 id="user-content-kept">Kept</h2><h2 id="user-content-kept">Again</h2>'
        '<h2 id="elsewhere">Made</h2>'
    )
    page = _node({"tree": html_tree(arrived), "base": None})
    assert [value for _tag, value in _heading_ids(page)] == [
        "user-content-kept",
        "user-content-again",
        "user-content-made",
    ]


def _heading_ids(html: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    class _Read(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                found.append((tag, dict(attrs).get("id") or ""))

    reader = _Read()
    reader.feed(html)
    reader.close()
    return found


# The only sources that may name the anchor namespace: the two allowlists that make the
# anchors, the inert render that points KPress's entries at them, the page's table of
# contents that links to them, and the link enhancer that scrolls a GitHub fragment to one.
ANCHOR_NAMESPACE_OWNERS = {
    "src/metabrowser/inert_html.py",
    "src/metabrowser/kpress_adapter.py",
    "src/metabrowser/static/inert-html.js",
    "src/metabrowser/builtin_plugins/markdown/inert-toc.js",
    "src/metabrowser/builtin_plugins/markdown/link-enhancer.js",
}


def test_no_application_name_is_in_the_anchor_namespace() -> None:
    """An ``id`` is a ``window`` property and a ``getElementById`` answer. A document's
    anchors all begin with ``user-content-``, so they can shadow only a name that begins
    with it; nothing the application or its plugins read, write, or look up does."""

    namers = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "src" / "metabrowser").rglob("*")
        if path.suffix in {".py", ".js", ".ts", ".html", ".css", ".toml"}
        and "vendor" not in path.parts
        and "user-content" in path.read_text(encoding="utf-8", errors="replace")
    )
    assert set(namers) <= ANCHOR_NAMESPACE_OWNERS, namers


def test_the_browser_names_prose_elements_by_element() -> None:
    """``kpressProse`` unwraps KPress's two wrappers and names a code block and a table.

    The session builds KPress's two wrappers around a heading, a code block, and a table,
    and prints what ``kpressProse`` makes of them: the classes KPress's stylesheets set the
    two by come from the module, by element, and never from the document.
    """

    transcript = run_session("inert-html-session.js")
    assert transcript["prose"]["div.kpress-prose"] == [
        {"h1": []},
        {"pre.kpress-code": [{"code": []}]},
        {"div.kpress-table-wrap": [{"table.kpress-table": []}]},
    ]
