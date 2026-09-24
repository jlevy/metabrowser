"""Reduce rendered Markdown from an untrusted source to a small allowlist of plain markup.

KPress's sanitized mode is a document renderer's policy: it keeps what a document of its
own may use, such as stylesheets, images, SVG, classes the application styles, and data
attributes KPress's own scripts act on. Inside Metabrowser's page, untrusted Markdown --
a pull-request comment, or a mirrored repository's README a fork's author controls --
shares the page with the application, and each of those is an attack: an SVG paint
server or a stylesheet loads from anywhere on render, a class borrows the application's
dialog styling, a data attribute reaches a document-wide handler, and an ``id`` or
``name`` clobbers a global. A denylist of them does not hold, so :func:`harden` keeps
only what is listed here and drops the rest.

- Tags: :data:`ALLOWED_TAGS`. :data:`DROPPED_WITH_CONTENT` are removed with everything in
  them; any other tag is unwrapped, keeping its text.
- Attributes: none, except ``a[href]``, ``img[src, alt]`` where images are kept,
  ``ol[start]`` as digits, ``td``/``th`` ``colspan`` and ``rowspan`` as small numbers and
  ``align`` as left, center, or right, and ``details[open]``. A kept link opens in a new
  tab with no opener or referrer when it leaves the page.
- Links and images depend on *link_base*. With one -- a pull request's github.com page
  -- every reference is made absolute against it and kept only for ``http`` and
  ``https``, and every image becomes a link to it. Without one -- a document inside the
  served tree -- a reference inside the tree (a relative path or a fragment) is kept as
  written, for the page to resolve within the served root or pin; an outside ``http`` or
  ``https`` link is kept; and an image is kept only when it is inside the tree, and
  otherwise becomes a link. Anything else, such as ``javascript:`` or ``data:``, goes.

``static/inert-html.js`` applies the same rules in the browser (``sanitizeNodes``), and
``tests/test_inert_html.py`` proves the two allowlists are the same.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from typing import Final
from urllib.parse import unquote, urljoin, urlsplit

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
# The attributes each tag may keep; every value is checked by allowed_attributes. An
# image is not an allowed tag: it is kept, with these, only inside the served tree.
ALLOWED_ATTRIBUTES: Final = {
    "a": ("href", "target", "rel"),
    "img": ("src", "alt"),
    "ol": ("start",),
    "td": ("colspan", "rowspan", "align"),
    "th": ("colspan", "rowspan", "align"),
    "details": ("open",),
}
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
# What a browser strips from a URL before reading it: ASCII tab and newline anywhere,
# and C0 controls and spaces at either end. Read the same way here, so "java\tscript:"
# is the scheme a browser would see.
_URL_NOISE: Final = re.compile(r"[\t\n\r]")
_SCHEME: Final = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# Two slashes or backslashes in any mix begin another origin's address.
_OTHER_ORIGIN: Final = re.compile(r"^[/\\]{2}")


# C0 controls and space, which a browser trims from either end of a URL.
_EDGE: Final = "".join(chr(code) for code in range(0x21))


def _clean(href: str) -> str:
    return _URL_NOISE.sub("", href).strip(_EDGE)


# The application's own routes, which a document inside the served tree never names:
# fetching or following one from untrusted markup reaches the application, not the tree.
_RESERVED: Final = re.compile(r"^/(?:api|_debug|raw)(?:[/?#]|$)", re.IGNORECASE)
# An escaped dot, which a browser's URL parser reads as a dot in a dot segment, and an
# escaped slash or backslash, which the server's router reads as a separator. A document
# inside the served tree has no reason to write either.
_ENCODED_DOT: Final = re.compile(r"%2e", re.IGNORECASE)
_DOT_SEGMENT: Final = re.compile(r"^(?:\.|%2e){1,2}$", re.IGNORECASE)
_ENCODED_SEPARATOR: Final = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
# An http(s) address written without its two slashes, which a browser reads as absolute
# unless the page it sits in shares the scheme.
_BARE_WEB_SCHEME: Final = re.compile(r"^(https?):(?![/\\]{2})", re.IGNORECASE)


def is_inside(href: str | None) -> bool:
    """Whether *href* is a reference inside the served tree: a relative path or fragment.

    A query alone, and a root-relative path to the application's own routes (``/api``,
    ``/_debug``, ``/raw``, however spelled), are not: they address the application.
    """

    if not href:
        return False
    cleaned = _clean(href)
    if not cleaned or _SCHEME.match(cleaned) or _OTHER_ORIGIN.match(cleaned):
        return False
    if cleaned.startswith("?") or _ENCODED_SEPARATOR.search(cleaned):
        return False
    if cleaned.startswith(("/", "\\")):
        # As a browser would: an escaped dot is a dot in a dot segment, backslashes are
        # slashes, dot segments are resolved, and the server reads the other escapes.
        dotted = _ENCODED_DOT.sub(".", cleaned).replace("\\", "/")
        path = urlsplit(urljoin("http://page.invalid/", dotted)).path
        if _RESERVED.match(unquote(path)):
            return False
    return True


def _dot_segments(href: str) -> str:
    """*href* with each escaped dot segment (``%2e``, ``.%2e``, ...) read as a dot segment.

    A browser's URL parser does this before it resolves dot segments; ``urljoin`` does
    not, so without it the two would resolve ``/%2e%2e/x`` differently.
    """

    path, *rest = re.split(r"([?#])", href, maxsplit=1)
    segments = [
        ("." if len(_ENCODED_DOT.sub(".", segment)) == 1 else "..")
        if _DOT_SEGMENT.match(segment)
        else segment
        for segment in path.split("/")
    ]
    return "/".join(segments) + "".join(rest)


def _spelled_out(href: str, base: str | None) -> str:
    """*href* with a bare ``https:`` or ``http:`` given its two slashes, as a browser reads it.

    A browser reads ``https:host/path`` as absolute unless the page shares the scheme,
    where it is relative; spelling it out makes the address mean the same on both sides.
    """

    bare = _BARE_WEB_SCHEME.match(href)
    if bare is None:
        return href
    scheme = bare.group(1).lower()
    if base is not None and urlsplit(base).scheme.lower() == scheme:
        return href
    return f"{scheme}://" + href[bare.end() :].lstrip("/\\")


def outside_link(href: str | None, base: str | None) -> str | None:
    """*href* as an absolute ``http`` or ``https`` address, or ``None``.

    Against *base* when there is one; without one only an absolute reference qualifies.
    """

    if not href:
        return None
    cleaned = _spelled_out(_clean(href), base)
    if base is None and not (_SCHEME.match(cleaned) or _OTHER_ORIGIN.match(cleaned)):
        return None
    try:
        # A browser reads a backslash as a slash in an http(s) address; so does this.
        absolute = urljoin(base or "https:", _dot_segments(cleaned.replace("\\", "/")))
        scheme = urlsplit(absolute).scheme
    except ValueError:
        return None
    return absolute if scheme in {"http", "https"} else None


def link_href(href: str | None, base: str | None) -> tuple[str, bool] | None:
    """What a link keeps: its address and whether it leaves the page, or ``None``."""

    if base is None and is_inside(href):
        return _clean(href or ""), False
    outside = outside_link(href, base)
    return None if outside is None else (outside, True)


def allowed_attributes(
    tag: str, attrs: dict[str, str | None], base: str | None
) -> list[tuple[str, str]]:
    """The attributes *tag* keeps, in a fixed order, each value checked."""

    kept: list[tuple[str, str]] = []
    if tag == "a":
        link = link_href(attrs.get("href"), base)
        if link is not None:
            href, leaves = link
            kept.append(("href", href))
            if leaves:
                kept += [("target", "_blank"), ("rel", "noopener noreferrer")]
    elif tag == "img":
        kept.append(("src", _clean(attrs.get("src") or "")))
        alt = attrs.get("alt")
        if alt:
            kept.append(("alt", alt))
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


def keeps_image(src: str | None, base: str | None) -> bool:
    """Whether an image stays an image: only one inside the served tree, and only then."""

    return base is None and is_inside(src)


def image_link(src: str | None, alt: str | None, base: str | None) -> tuple[str | None, str]:
    """What an image becomes when it is not kept: a link's href, if any, and its text."""

    return outside_link(src, base), (alt or "").strip() or "image"


def _open_tag(tag: str, kept: list[tuple[str, str]]) -> str:
    rendered = "".join(
        f" {name}" if name == "open" else f' {name}="{escape(value)}"' for name, value in kept
    )
    return f"<{tag}{rendered}>"


class _Hardener(HTMLParser):
    def __init__(self, base: str | None) -> None:
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
            if keeps_image(values.get("src"), self.base):
                self.out.append(_open_tag("img", allowed_attributes("img", values, self.base)))
                return
            href, text = image_link(values.get("src"), values.get("alt"), self.base)
            if href is None:
                self.out.append(f"<span>{escape(text, quote=False)}</span>")
            else:
                link = allowed_attributes("a", {"href": href}, self.base)
                self.out.append(f"{_open_tag('a', link)}{escape(text, quote=False)}</a>")
            return
        if tag in ALLOWED_TAGS:
            self.out.append(_open_tag(tag, allowed_attributes(tag, values, self.base)))

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


def harden(html: str, link_base: str | None = None) -> str:
    """*html* reduced to :data:`ALLOWED_TAGS` and the attributes described above."""

    hardener = _Hardener(link_base)
    hardener.feed(html)
    hardener.close()
    return "".join(hardener.out)


__all__ = [
    "ALLOWED_ATTRIBUTES",
    "ALLOWED_TAGS",
    "DROPPED_WITH_CONTENT",
    "allowed_attributes",
    "harden",
    "image_link",
    "is_inside",
    "keeps_image",
    "link_href",
    "outside_link",
]
