"""The preview pane scrolls inside a frame that pins KPress's floating UI.

KPress's TOC drawer, its toggle, and its backdrop are ``position: fixed``. They pin to
their containing block, which the shell must make a non-scrolling box the size of the
pane: KPress's ``.kpress-frame``. When the scrolling pane itself carried the transform
that makes a containing block, the floating UI was laid out in the pane's scrolled
content, so in a narrow pane the drawer toggle scrolled away with the document
(mb-ddbe).

Where that UI lands is browser layout, which this repository has no browser harness
to measure; the QA runbook's section 5.9 step 5 checks it by hand. This module pins
what places it, statically: the shell's wrapper, the frame's transform, and that no
stylesheet rule gives the pane or an element between the pane and the TOC a property
that makes a containing block for fixed descendants. It reads the shell's stylesheet,
every built-in plugin's, and KPress's, by selector text: a rule it cannot attribute to
one of those elements, such as one added by a script, is not seen.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, cast

import pytest
from kpress.runtime import get_static_asset

from metabrowser import server

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")
COMBINATOR_RE = re.compile(r"\s*[>+~]\s*|\s+")

PLUGIN_CSS = sorted((server.STATIC_DIR.parent / "builtin_plugins").glob("*/*.css"))
KPRESS_CSS = ("css/components.css", "css/document.css", "css/page-reset.css", "css/print.css")

# The elements between the scrolling pane and the TOC, its toggle, and its backdrop, as
# a trusted and a mirrored Markdown document render them (read in the browser,
# 2026-09-24):
#   div#preview-pane.preview-pane[data-kpress-viewport]
#   > div.content-body.metabrowser-kpress-host.md-body[data-tab-content][data-plugin-view]
#   > article.kpress.kpress-doc (.kpress-print-surface trusted, .kpress-inert mirrored)
#   > div.kpress-doc-layout.kpress-content-with-toc
#   > nav.kpress-toc, button.kpress-toc-toggle, div.kpress-toc-backdrop
# A selector whose subject names one of these can style one of them.
ANCESTOR_TOKENS = (
    "#preview-pane",
    ".preview-pane",
    "[data-kpress-viewport",
    ".content-body",
    ".metabrowser-kpress-host",
    ".md-body",
    "[data-tab-content",
    "[data-plugin-view",
    ".kpress",
    ".kpress-doc",
    ".kpress-print-surface",
    ".kpress-inert",
    ".kpress-doc-layout",
    ".kpress-content-with-toc",
    "article",
)

# What makes an element the containing block for fixed-position descendants: CSS
# Transforms 1 and 2 (transform, translate, rotate, scale, perspective,
# transform-style: preserve-3d), Filter Effects 1 and 2 (filter, backdrop-filter), CSS
# Containment 2 (contain: layout, paint, strict, or content; content-visibility: auto or
# hidden), and will-change naming any of them.
_SAFE_VALUES = frozenset({"none", "initial", "unset", "revert", "revert-layer", "normal"})
_ANY_VALUE = frozenset(
    {"transform", "translate", "rotate", "scale", "perspective", "filter", "backdrop-filter"}
)


def _makes_containing_block(name: str, value: str) -> bool:
    value = value.removesuffix("!important").strip().lower()
    if value in _SAFE_VALUES:
        return False
    words = set(re.split(r"[\s,]+", value))
    if name in _ANY_VALUE:
        return True
    if name == "transform-style":
        return value == "preserve-3d"
    if name == "contain":
        return bool(words & {"layout", "paint", "strict", "content"})
    if name == "content-visibility":
        return value in {"auto", "hidden"}
    if name == "will-change":
        return bool(words & (_ANY_VALUE | {"transform-style", "contain", "content-visibility"}))
    return False


def _stylesheets() -> list[tuple[str, str]]:
    sheets = [("static/styles.css", (server.STATIC_DIR / "styles.css").read_text("utf-8"))]
    sheets += [
        (str(path.relative_to(server.STATIC_DIR.parent)), path.read_text("utf-8"))
        for path in PLUGIN_CSS
    ]
    sheets += [
        (f"kpress/{name}", get_static_asset(name).content.decode("utf-8")) for name in KPRESS_CSS
    ]
    return sheets


def _rules(css: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    rules: list[tuple[list[str], list[tuple[str, str]]]] = []
    for rule in CSS_RULE_RE.finditer(CSS_COMMENT_RE.sub("", css)):
        selectors = [part.strip() for part in rule.group("selectors").split(",") if part.strip()]
        declarations: list[tuple[str, str]] = []
        for declaration in rule.group("body").split(";"):
            name, separator, value = declaration.partition(":")
            if separator:
                declarations.append((name.strip().lower(), value.strip()))
        rules.append((selectors, declarations))
    return rules


def _subject(selector: str) -> str:
    """The last compound selector, the element a rule styles; ``""`` for a pseudo-element."""

    compound = COMBINATOR_RE.split(selector.strip())[-1]
    return "" if "::" in compound else compound


def _names_ancestor(compound: str) -> bool:
    for token in ANCESTOR_TOKENS:
        # A tag leads its compound; a class, id, or attribute may sit anywhere in it.
        pattern = rf"^{token}(?![\w-])" if token.isalpha() else rf"{re.escape(token)}(?![\w-])"
        if re.search(pattern, compound):
            return True
    return False


def _declarations(selector: str) -> list[tuple[str, str]]:
    """Every declaration of each shell rule whose selector list names *selector* exactly."""

    found: list[tuple[str, str]] = []
    for selectors, declarations in _rules((server.STATIC_DIR / "styles.css").read_text("utf-8")):
        if selector in selectors:
            found += declarations
    return found


def _shell_html() -> str:
    class _Request:
        def __init__(self) -> None:
            self.query_params: dict[str, str] = {}
            self.headers: dict[str, str] = {}

    response = asyncio.run(server.index(cast(Any, _Request())))
    return bytes(response.body).decode()


def test_the_scrolling_pane_sits_directly_inside_the_kpress_frame() -> None:
    html = _shell_html()
    assert re.search(
        r'<div class="preview-frame kpress-frame">\s*'
        r'<div class="preview-pane" id="preview-pane" data-kpress-viewport tabindex="-1">',
        html,
    ), "the preview pane must be the only child a non-scrolling .kpress-frame wraps"


def test_no_rule_makes_the_pane_or_an_element_above_the_toc_a_containing_block() -> None:
    found: list[str] = []
    for sheet, css in _stylesheets():
        for selectors, declarations in _rules(css):
            subjects = [selector for selector in selectors if _names_ancestor(_subject(selector))]
            for name, value in declarations:
                if subjects and _makes_containing_block(name, value):
                    found.append(f"{sheet}: {', '.join(subjects)} {{ {name}: {value} }}")
    assert found == [], "the floating UI would pin to one of these and scroll away:\n" + "\n".join(
        found
    )


def test_the_scroller_keeps_the_scroll_and_the_query_container() -> None:
    pane = _declarations(".preview-pane")
    assert ("overflow-y", "auto") in pane
    assert ("container", "kpress-doc / inline-size") in pane


def test_the_frame_is_the_containing_block_and_does_not_scroll() -> None:
    frame = _declarations(".preview-frame")
    assert ("transform", "translateZ(0)") in frame
    scrolls = [
        (name, value)
        for name, value in frame
        if name.startswith("overflow") and value in {"auto", "scroll"}
    ]
    assert scrolls == []
    # Print drops the frame's layer, since a transformed ancestor breaks fragmentation.
    assert ("transform", "none") in frame


@pytest.mark.parametrize(
    ("css", "flagged"),
    [
        (".preview-pane { transform: translateZ(0); }", True),
        ("#preview-pane:focus { translate: 0 1px; }", True),
        (".content-body.md-body { will-change: transform; }", True),
        ("main .metabrowser-kpress-host { contain: layout paint; }", True),
        (".kpress-doc-layout { content-visibility: auto; }", True),
        (".md-body > .kpress { transform-style: preserve-3d; }", True),
        ("article.kpress-doc { filter: blur(1px) !important; }", True),
        (".preview-pane { contain: inline-size; transform: none; }", False),
        (".md-body::before { transform: rotate(1deg); }", False),
        (".md-body .kpress-table-wrap { transform: none; }", False),
        (".md-body .kpress-callout { transform: scale(1.1); }", False),
        (".kpress-document { transform: scale(1.1); }", False),
    ],
)
def test_the_scan_sees_each_property_and_only_the_elements_above_the_toc(
    css: str, flagged: bool
) -> None:
    hits = [
        name
        for selectors, declarations in _rules(css)
        for name, value in declarations
        if any(_names_ancestor(_subject(selector)) for selector in selectors)
        and _makes_containing_block(name, value)
    ]
    assert bool(hits) is flagged, (css, hits)


def test_every_stylesheet_the_scan_names_exists() -> None:
    assert PLUGIN_CSS and all(Path(path).is_file() for path in PLUGIN_CSS)
    assert {sheet for sheet, _css in _stylesheets()} >= {
        "static/styles.css",
        "kpress/css/components.css",
    }
