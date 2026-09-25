"""The inert-Markdown allowlist, the same on the server and in the browser.

``src/metabrowser/inert_html.py`` hardens untrusted Markdown on the server and
``static/inert-html.js`` rebuilds it in the page. These tests prove the two share one
allowlist, and that they make the same markup of the same input: KPress's own sanitized
render of a hostile document, in both link modes, parsed once by Python's HTML parser and
handed to each.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from metabrowser import inert_html, kpress_adapter
from metabrowser.inert_html import harden
from tests.github_pull_fixture import HOSTILE_COMMENT, allowlist_violations, html_tree

REPO_ROOT = Path(__file__).resolve().parent.parent
INERT_JS = REPO_ROOT / "src" / "metabrowser" / "static" / "inert-html.js"
PR_PAGE = "https://github.com/octo/demo/pull/7"

# A document with both kinds of reference inside the served tree, and a repository image.
HOSTILE_README = (
    HOSTILE_COMMENT + "\n![diagram](docs/diagram.png) ![tracker](https://example.com/t.gif)"
    ' <img src="//example.com/p.gif"> <img src="data:image/png;base64,AAAA">\n\n'
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
)

# Runs the production sanitizer on a tree read from stdin and prints the rebuilt markup.
_NODE = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const [inertPath] = process.argv.slice(1);
const context = { window: {}, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
const inert = context.window.MetabrowserInertHtml;
const input = JSON.parse(fs.readFileSync(0, "utf8"));
if (input.lists) {
  process.stdout.write(JSON.stringify({
    tags: inert.ALLOWED_TAGS, dropped: inert.DROPPED_WITH_CONTENT,
    attributes: inert.ALLOWED_ATTRIBUTES, prefix: inert.ANCHOR_PREFIX,
  }));
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
    append(...more) { this.children.push(...more); } }),
};
const escape = (value) => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const serialize = (list) => list.map((node) => "text" in node ? escape(node.text)
  : `<${node.tag}${node.attributes.map(([name, value]) => ` ${name}="${escape(value)}"`).join("")}>`
    + (["br", "hr", "img"].includes(node.tag) ? "" : `${serialize(node.children)}</${node.tag}>`))
  .join("");
process.stdout.write(serialize(inert.sanitizeNodes(nodes(input.tree), doc, input.base)));
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


def _node(payload: dict[str, Any]) -> str:
    result = subprocess.run(
        ["node", "-e", _NODE, str(INERT_JS)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
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


@pytest.mark.parametrize(("base", "images"), [(None, True), (PR_PAGE, False)])
def test_both_sides_make_the_same_inert_markup_of_a_hostile_document(
    base: str | None, images: bool
) -> None:
    rendered = _kpress(HOSTILE_README)
    server = harden(rendered, base)
    browser = _node({"tree": html_tree(rendered), "base": base})
    assert allowlist_violations(server, images=images) == []
    assert allowlist_violations(browser, images=images) == []
    assert _tokens(browser) == _tokens(server)


def test_a_document_keeps_its_own_references_and_turns_outside_images_into_links() -> None:
    inert = harden(_kpress(HOSTILE_README))
    assert '<img src="docs/diagram.png" alt="diagram">' in inert
    assert '<a href="docs/guide.md">Guide</a>' in inert
    assert '<a href="#user-content-readme">Top</a>' in inert
    assert '<a href="../x.md">Up</a>' in inert
    # An outside image is a link to it, in a new tab; one with no http(s) address is text.
    assert (
        '<a href="https://example.com/t.gif" target="_blank" rel="noopener noreferrer">tracker</a>'
    ) in inert
    assert '<a href="https://example.com/p.gif" target="_blank"' in inert
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
        assert f"<span>{text}</span>" in inert, text
    assert '<a href="https://evil.test/no-slashes" target="_blank"' in inert
    assert '<a href="https://one.test/x" target="_blank"' in inert
    # In a pull request's comment, a bare https: shares the page's scheme and is relative.
    comment = harden(_kpress("[bare](https:evil.test/no-slashes)"), PR_PAGE)
    assert 'href="https://github.com/octo/demo/pull/evil.test/no-slashes"' in comment


def test_harden_is_idempotent() -> None:
    for base in (None, PR_PAGE):
        once = harden(_kpress(HOSTILE_README), base)
        assert harden(once, base) == once


FIXTURE_README = REPO_ROOT / "tests" / "fixtures" / "untrusted-markdown" / "README.md"
SESSION_TREE = REPO_ROOT / "tests" / "fixtures" / "inert-html-kpress-tree.json"
SESSION_JS = REPO_ROOT / "tests" / "dom" / "inert-html-session.js"


def test_the_session_plays_what_kpress_renders_of_the_hostile_readme() -> None:
    """``tests/dom/inert-html-session.js`` runs on KPress's render of the fixture README.

    The tree is Python's HTML parse of that render, recorded so the session never runs on
    markup a test wrote by hand; this fails when KPress renders it differently. Regenerate
    with GOLDEN_UPDATE=1, then update tests/golden/cli-ui-inert-markdown.tryscript.md.
    """

    import os

    tree = html_tree(_kpress(FIXTURE_README.read_text(encoding="utf-8")))
    recorded = json.dumps(tree, indent=1, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        SESSION_TREE.write_text(recorded, encoding="utf-8")
    assert SESSION_TREE.read_text(encoding="utf-8") == recorded
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=True
    )
    transcript = json.loads(result.stdout)
    assert allowlist_violations(transcript["document"], images=True) == []
    assert allowlist_violations(transcript["comment"]) == []
    assert transcript["inertRender"] == {"inert": True, "trusted": False}


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
    # Text the page shows counts, as an outside image's link text does; hidden text not.
    assert ids[19:22] == [
        "user-content-logo-project",
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
