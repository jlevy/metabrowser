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
- Heading anchors, in a document inside the served tree only: every ``h1`` to ``h6``
  gets an ``id`` the hardener makes, never one the document wrote, as github.com does:
  :data:`ANCHOR_PREFIX` and the GitHub slug of the heading's inert text
  (:func:`heading_slug`), with ``-1``, ``-2``, ... for repeats. A fragment-only link,
  ``#name``, becomes ``#user-content-name`` to reach it. The prefix keeps every such
  ``id`` out of the application's names: an ``id`` is also a ``window`` property, and
  nothing the page or the SDK reads begins with ``user-content-``
  (``tests/test_inert_html.py`` checks the sources). The page keeps the anchors made
  here, so this Python's Unicode tables decide every slug; a character newer than
  github-slugger's tables (Unicode 13) can still slug differently than on github.com.

``static/inert-html.js`` applies the same rules in the browser (``sanitizeNodes``), and
``tests/test_inert_html.py`` proves the two allowlists are the same.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
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
# The attributes each tag may keep; every value is checked by allowed_attributes, except
# a heading's id, which is always the hardener's own anchor and never the document's. An
# image is not an allowed tag: it is kept, with these, only inside the served tree.
ALLOWED_ATTRIBUTES: Final = {
    "a": ("href", "target", "rel"),
    "img": ("src", "alt"),
    "ol": ("start",),
    "td": ("colspan", "rowspan", "align"),
    "th": ("colspan", "rowspan", "align"),
    "details": ("open",),
    **{f"h{level}": ("id",) for level in range(1, 7)},
}
# Every heading anchor begins with this, as on github.com: the document's names stay
# apart from the application's ids and from window properties.
ANCHOR_PREFIX: Final = "user-content-"
_HEADINGS: Final = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
# What a GitHub slug keeps besides hyphen and space: the Unicode word characters
# (Alphabetic, Mark, Decimal_Number, Connector_Punctuation) as github-slugger's
# expression lists them. By general category that is letters, marks, decimal digits
# (the characters with a decimal value), letter numbers, connector punctuation, and the
# alphabetic symbols below (circled and squared Latin letters), the only Alphabetic
# characters outside those categories.
_SLUG_CATEGORIES: Final = frozenset({"Nl", "Pc"})
_SLUG_SYMBOLS: Final = (
    (0x24B6, 0x24E9),
    (0x1F130, 0x1F149),
    (0x1F150, 0x1F169),
    (0x1F170, 0x1F189),
)


def _slug_keeps(character: str) -> bool:
    if character in "- " or unicodedata.decimal(character, None) is not None:
        return True
    category = unicodedata.category(character)
    if category[0] in "LM" or category in _SLUG_CATEGORIES:
        return True
    code = ord(character)
    return any(low <= code <= high for low, high in _SLUG_SYMBOLS)


def heading_slug(text: str) -> str:
    """GitHub's slug of a heading's text: lowercased, word characters, hyphens, and
    spaces kept, and each space a hyphen. Repeats are numbered by :class:`_Anchors`."""

    return "".join(character for character in text.lower() if _slug_keeps(character)).replace(
        " ", "-"
    )


class _Anchors:
    """GitHub's numbering of repeated slugs (github-slugger): ``a``, ``a-1``, ``a-2``."""

    def __init__(self) -> None:
        self.seen: dict[str, int] = {}

    def anchor(self, text: str) -> str:
        original = result = heading_slug(text)
        while result in self.seen:
            self.seen[original] += 1
            result = f"{original}-{self.seen[original]}"
        self.seen[result] = 0
        return ANCHOR_PREFIX + result


def fragment_link(href: str) -> str:
    """A fragment-only reference as it reaches a heading anchor: ``#name`` becomes
    ``#user-content-name``, and one already in the namespace stays, as on github.com."""

    name = href[1:]
    if not name or name.startswith(ANCHOR_PREFIX):
        return href
    return f"#{ANCHOR_PREFIX}{name}"


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
        cleaned = _clean(href or "")
        return (fragment_link(cleaned) if cleaned.startswith("#") else cleaned), False
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


class _Heading:
    def __init__(self, index: int, tag: str, original: str | None) -> None:
        self.index = index
        self.tag = tag
        self.original = original
        self.text: list[str] = []


class _Hardener(HTMLParser):
    def __init__(self, base: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.out: list[str] = []
        # Depth inside a dropped element; nothing is written while it is above zero.
        self.dropped = 0
        # Each heading of a document, in order: where its open tag is in `out`, its tag,
        # the id the document gave it, and its inert text. `open_headings` holds those
        # not yet closed, which the text written now belongs to.
        self.headings: list[_Heading] = []
        self.open_headings: list[_Heading] = []

    def _text(self, text: str) -> None:
        for heading in self.open_headings:
            heading.text.append(text)

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
            self._text(text)
            if href is None:
                self.out.append(f"<span>{escape(text, quote=False)}</span>")
            else:
                link = allowed_attributes("a", {"href": href}, self.base)
                self.out.append(f"{_open_tag('a', link)}{escape(text, quote=False)}</a>")
            return
        if tag in ALLOWED_TAGS:
            self.out.append(_open_tag(tag, allowed_attributes(tag, values, self.base)))
            if tag in _HEADINGS and self.base is None:
                heading = _Heading(len(self.out) - 1, tag, values.get("id"))
                self.headings.append(heading)
                self.open_headings.append(heading)

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
        # A heading's end closes it and any heading still open inside it.
        for position in range(len(self.open_headings) - 1, -1, -1):
            if self.open_headings[position].tag == tag:
                del self.open_headings[position:]
                break

    def handle_data(self, data: str) -> None:
        if not self.dropped:
            self.out.append(escape(data, quote=False))
            self._text(data)

    def anchor_headings(self) -> dict[str, str]:
        """Give each heading its anchor, in document order; the ids they replace.

        Only an id one heading alone had is mapped, the empty one included (KPress gives
        its first heading with an empty slug ``id=""``): a document that repeats an id
        -- a raw heading written with the id KPress gives a Markdown heading -- cannot
        say which heading it names, so neither is mapped.
        """

        anchors = _Anchors()
        written = Counter(h.original for h in self.headings if h.original is not None)
        replaced: dict[str, str] = {}
        for heading in self.headings:
            anchor = anchors.anchor("".join(heading.text))
            self.out[heading.index] = f'<{heading.tag} id="{escape(anchor)}">'
            if heading.original is not None and written[heading.original] == 1:
                replaced[heading.original] = anchor
        return replaced


def harden(html: str, link_base: str | None = None) -> str:
    """*html* reduced to :data:`ALLOWED_TAGS` and the attributes described above."""

    return _harden(html, link_base)[0]


def harden_document(html: str) -> tuple[str, dict[str, str]]:
    """:func:`harden` for a document inside the served tree, and its heading anchors:
    each ``id`` a heading had in *html*, mapped to the anchor that replaces it."""

    return _harden(html, None)


def _harden(html: str, link_base: str | None) -> tuple[str, dict[str, str]]:
    hardener = _Hardener(link_base)
    hardener.feed(html)
    hardener.close()
    replaced = hardener.anchor_headings()
    return "".join(hardener.out), replaced


__all__ = [
    "ALLOWED_ATTRIBUTES",
    "ANCHOR_PREFIX",
    "ALLOWED_TAGS",
    "DROPPED_WITH_CONTENT",
    "allowed_attributes",
    "fragment_link",
    "harden",
    "harden_document",
    "heading_slug",
    "image_link",
    "is_inside",
    "keeps_image",
    "link_href",
    "outside_link",
]
