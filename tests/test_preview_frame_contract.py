"""The preview pane scrolls inside a frame that pins KPress's floating UI.

KPress's TOC drawer, its toggle, and its backdrop are ``position: fixed``. They pin to
their containing block, which the shell must make a non-scrolling box the size of the
pane: KPress's ``.kpress-frame``. When the scrolling pane itself carried the transform
that makes a containing block, the floating UI was laid out in the pane's scrolled
content, so in a narrow pane the drawer toggle scrolled away with the document
(mb-ddbe). Where that UI lands is browser layout, measured in the QA runbook's section
5.9; this module pins the two decisions that place it: the shell's wrapper and the CSS
that makes the frame, and never the scroller, the containing block.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, cast

from metabrowser import server

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}")

# Properties that make an element the containing block for fixed-position descendants
# (CSS Transforms, Filter Effects, Containment, and will-change).
FIXED_CONTAINING_BLOCK_PROPERTIES = frozenset(
    {"transform", "perspective", "filter", "backdrop-filter", "contain", "will-change"}
)


def _shell_html() -> str:
    class _Request:
        def __init__(self) -> None:
            self.query_params: dict[str, str] = {}
            self.headers: dict[str, str] = {}

    response = asyncio.run(server.index(cast(Any, _Request())))
    return bytes(response.body).decode()


def _declarations(selector: str) -> list[tuple[str, str]]:
    """Every ``property: value`` of each rule whose selector list names *selector*."""

    css = CSS_COMMENT_RE.sub("", (server.STATIC_DIR / "styles.css").read_text(encoding="utf-8"))
    found: list[tuple[str, str]] = []
    for rule in CSS_RULE_RE.finditer(css):
        selectors = {part.strip() for part in rule.group("selectors").split(",")}
        if selector not in selectors:
            continue
        for declaration in rule.group("body").split(";"):
            name, separator, value = declaration.partition(":")
            if separator:
                found.append((name.strip(), value.strip()))
    return found


def test_the_scrolling_pane_sits_directly_inside_the_kpress_frame() -> None:
    html = _shell_html()
    assert re.search(
        r'<div class="preview-frame kpress-frame">\s*'
        r'<div class="preview-pane" id="preview-pane" data-kpress-viewport tabindex="-1">',
        html,
    ), "the preview pane must be the only child a non-scrolling .kpress-frame wraps"


def test_the_scroller_is_never_the_containing_block_for_fixed_ui() -> None:
    pane = _declarations(".preview-pane")
    assert ("overflow-y", "auto") in pane
    assert ("container", "kpress-doc / inline-size") in pane
    for selector in (".preview-pane", "#preview-pane"):
        pinned = [
            (name, value)
            for name, value in _declarations(selector)
            if name in FIXED_CONTAINING_BLOCK_PROPERTIES and value != "none"
        ]
        assert pinned == [], f"{selector} would carry the floating UI with its scroll: {pinned}"


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
