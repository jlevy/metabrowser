"""Reduce KPress's HTML of a pull request's text to a small allowlist of plain markup.

KPress's sanitized mode is a document renderer's policy: it keeps what a document of its
own may use, such as stylesheets, images, SVG, classes the application styles, and data
attributes KPress's own scripts act on. Inside the pull-request page, one untrusted comment
shares the page with the application, and each of those is an attack: an SVG paint
server or a stylesheet loads from anywhere on render, a class borrows the application's
dialog styling, and a data attribute reaches a document-wide handler. A denylist of them
does not hold, so :func:`harden` keeps only what is listed here and drops the rest.

- Tags: :data:`ALLOWED_TAGS`. :data:`DROPPED_WITH_CONTENT` are removed with everything in
  them; an image becomes a link to it (``http`` and ``https`` only, its text the alt
  text or ``image``); any other tag is unwrapped, keeping its text.
- Attributes: none, except ``a[href]`` made absolute against the pull request's
  github.com page and kept only for ``http`` and ``https``, with a fixed
  ``target="_blank" rel="noopener noreferrer"``; ``ol[start]`` as digits;
  ``td``/``th`` ``colspan`` and ``rowspan`` as small numbers and ``align`` as left,
  center, or right; and ``details[open]``.

``builtin_plugins/github/pull-page.js`` applies the same rules again (``sanitizeNodes``)
to what it inserts. Repository Markdown files are not rewritten here.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from typing import Final
from urllib.parse import urljoin, urlsplit

ALLOWED_TAGS: Final = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "dd",
        "del",
        "details",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "ins",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
DROPPED_WITH_CONTENT: Final = frozenset(
    {
        "audio",
        "base",
        "canvas",
        "embed",
        "form",
        "iframe",
        "link",
        "math",
        "meta",
        "noscript",
        "object",
        "option",
        "picture",
        "script",
        "select",
        "source",
        "style",
        "svg",
        "template",
        "textarea",
        "title",
        "track",
        "video",
    }
)
# Elements with no end tag, so entering one never opens a level.
_VOID: Final = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_DIGITS: Final = re.compile(r"^[0-9]{1,6}$")
_SPAN: Final = re.compile(r"^[1-9][0-9]?$")
_ALIGN: Final = frozenset({"left", "center", "right"})
LINK_ATTRIBUTES: Final = ' target="_blank" rel="noopener noreferrer"'


def safe_link(href: str | None, base: str) -> str | None:
    """*href* made absolute against *base*, or ``None`` unless it is http or https."""

    if not href:
        return None
    try:
        absolute = urljoin(base, href.strip())
        scheme = urlsplit(absolute).scheme
    except ValueError:
        return None
    return absolute if scheme in {"http", "https"} else None


def allowed_attributes(tag: str, attrs: dict[str, str | None], base: str) -> list[tuple[str, str]]:
    """The attributes *tag* keeps, in a fixed order, each value checked."""

    kept: list[tuple[str, str]] = []
    if tag == "a":
        href = safe_link(attrs.get("href"), base)
        if href is not None:
            kept += [("href", href), ("target", "_blank"), ("rel", "noopener noreferrer")]
    elif tag == "ol":
        start = attrs.get("start") or ""
        if _DIGITS.match(start):
            kept.append(("start", start))
    elif tag in {"td", "th"}:
        for name in ("colspan", "rowspan"):
            value = attrs.get(name) or ""
            if _SPAN.match(value):
                kept.append((name, value))
        align = (attrs.get("align") or "").lower()
        if align in _ALIGN:
            kept.append(("align", align))
    elif tag == "details" and "open" in attrs:
        kept.append(("open", ""))
    return kept


def image_link(src: str | None, alt: str | None, base: str) -> tuple[str | None, str]:
    """What an image becomes: the href of a link to it, if any, and the link's text."""

    return safe_link(src, base), (alt or "").strip() or "image"


class _Hardener(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.out: list[str] = []
        # Depth inside a dropped element; nothing is written while it is above zero.
        self.dropped = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.dropped or tag in DROPPED_WITH_CONTENT:
            if tag not in _VOID:
                self.dropped += 1
            return
        values = dict(attrs)
        if tag == "img":
            href, text = image_link(values.get("src"), values.get("alt"), self.base)
            if href is None:
                self.out.append(f"<span>{escape(text, quote=False)}</span>")
            else:
                self.out.append(
                    f'<a href="{escape(href)}"{LINK_ATTRIBUTES}>{escape(text, quote=False)}</a>'
                )
            return
        if tag not in ALLOWED_TAGS:
            return
        kept = allowed_attributes(tag, values, self.base)
        rendered = "".join(
            f" {name}" if name == "open" else f' {name}="{escape(value)}"' for name, value in kept
        )
        self.out.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and tag != "img":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.dropped:
            if tag not in _VOID:
                self.dropped -= 1
            return
        if tag in ALLOWED_TAGS and tag not in _VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.dropped:
            self.out.append(escape(data, quote=False))


def harden(html: str, base: str) -> str:
    """*html* reduced to :data:`ALLOWED_TAGS` and the attributes listed above."""

    hardener = _Hardener(base)
    hardener.feed(html)
    hardener.close()
    return "".join(hardener.out)


__all__ = [
    "ALLOWED_TAGS",
    "DROPPED_WITH_CONTENT",
    "LINK_ATTRIBUTES",
    "allowed_attributes",
    "harden",
    "image_link",
    "safe_link",
]
