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
- Attributes: none, except ``a[href]``, ``img[src, alt]`` where images are kept, with
  ``loading="lazy"`` written here on every one and never read from the document, and
  ``referrerpolicy="no-referrer"`` on one from the web, ``ol[start]`` as digits,
  ``td``/``th`` ``colspan`` and ``rowspan`` as small numbers, ``details[open]``, and the
  layout attributes github.com keeps (:data:`ALIGN_VALUES`,
  :data:`DIMENSIONS`): ``align`` as a keyword on a block, a heading, an image, or a table
  part, ``width`` and ``height`` as a number of pixels or a percentage on an image or a
  table cell, and ``width`` on a table. A kept link opens in a new tab with no opener or
  referrer when it leaves the page. A ``span`` keeps only the image fallback's own
  attributes, described below.
- Layout: github.com's sanitizer (html-pipeline's ``SanitizationFilter``) keeps
  ``align``, ``width``, and ``height`` on every element, and a README lays itself out
  with them: ``<p align="center"><img width="192">`` is a small centered logo there. Each
  is a keyword or a number, with no address, script, or style in it, so the allowlist
  keeps those that KPress's sanitized mode keeps too, and the page shows a document from
  an untrusted source laid out as a trusted one is. A table's ``align`` and ``width``
  are kept with the rest, so the two renders write the same HTML, but they change
  nothing on the page today: KPress's stylesheet sets every table at least as wide as
  its column. KPress's sanitized mode drops others that github.com keeps before this
  sees them: ``valign``, ``hspace``, ``vspace``, ``clear``, ``nowrap``, and ``open`` on
  ``details``, which this would keep.
- Links and images depend on *link_base*. With one -- a pull request's github.com page
  -- every reference is made absolute against it and kept only for ``http`` and
  ``https``. Without one -- a document inside the served tree -- a reference inside the
  tree (a relative path or a fragment) is kept as written, for the page to resolve within
  the served root or pin, and an outside ``http`` or ``https`` link is kept. Anything
  else, such as ``javascript:`` or ``data:``, goes.
- Images: one inside the served tree is kept, and so is one the document writes as an
  ``https`` address (:func:`remote_image`), which the page shows as github.com does with
  no referrer sent; the page's policy (``capabilities.untrusted_shell_csp``) admits
  ``https`` images and nothing else, and the reader's own setting turns even those into
  the fallback below (``static/inert-html.js``). Any other image -- ``http``, a reference
  into the application, a pull-request comment's relative path -- is not loaded, and
  becomes the fallback: its alt text as a small span of the class
  :data:`IMAGE_FALLBACK_CLASS`, whose ``data-tip-text`` is the address the image would
  have loaded (the page's tooltip shows it). Inside a link, which a badge is, the span is
  the link's content and the link keeps its own destination; outside one, the span is
  inside a link to the image. A ``span`` keeps no other attribute, and these two only in
  that shape, the class exactly and the tooltip as an absolute ``http`` or ``https``
  address, so the hardener's own answer hardens to itself, as the page needs it to. A
  document that writes the shape gets a chip and a tooltip of that address, which do
  nothing else.
- Checkboxes: an ``input`` is kept only in the shape of a task list's box, as KPress
  and github.com write one for ``- [ ]`` and ``- [x]``: ``type="checkbox"``, always
  ``disabled``, and ``checked`` when the document's was, so a ticked item reads as
  ticked (:data:`CHECKBOX_ATTRIBUTES`). The allowlist reads HTML, not where it came
  from, so a checkbox the document writes in raw HTML, in a paragraph or a table cell,
  is kept in that shape too. Like an image, it is not an allowed tag: any other
  ``input``, and any other attribute of one, goes. A disabled checkbox with no name,
  value, or form cannot be focused, changed, or submitted, and reaches no handler.
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

import ipaddress
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
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
# The align keywords each tag keeps, lowercased: those a browser lays out (the HTML
# standard's rendering section), so a kept value always means what it does on github.com.
# A block, a heading, and a table's cells, rows, and row groups align their text; a table
# sits left, center, or right; an image floats left or right, or sits on the line at its
# top, middle (written `middle` or `center`), bottom, or baseline.
_TEXT_ALIGN: Final = ("left", "center", "right", "justify")
ALIGN_VALUES: Final = {
    "p": _TEXT_ALIGN,
    "div": _TEXT_ALIGN,
    **{f"h{level}": _TEXT_ALIGN for level in range(1, 7)},
    "img": ("left", "right", "top", "middle", "center", "bottom", "baseline"),
    "table": ("left", "center", "right"),
    **dict.fromkeys(("thead", "tbody", "tfoot", "tr", "td", "th"), _TEXT_ALIGN),
}
# The sizes each tag keeps, each a number of pixels or a percentage (_DIMENSION).
DIMENSIONS: Final = {
    "img": ("width", "height"),
    "table": ("width",),
    "td": ("width", "height"),
    "th": ("width", "height"),
}
# The attributes each tag may keep; every value is checked by allowed_attributes, except
# a heading's id, which is always the hardener's own anchor and never the document's, an
# image's loading, which is always lazy, its referrerpolicy, which is always no-referrer,
# and a span's, which only the image fallback's own shape (IMAGE_FALLBACK_CLASS) keeps. An
# image is not an allowed tag: it is kept, with these, only inside the served tree and
# from an https address. Nor is an input: it is kept only in the shape of a task list's
# box, which CHECKBOX_ATTRIBUTES writes, wherever the document writes a checkbox.
ALLOWED_ATTRIBUTES: Final = {
    "a": ("href", "target", "rel"),
    "img": ("loading", "referrerpolicy", "src", "alt", "align", "width", "height"),
    "input": ("type", "disabled", "checked"),
    "span": ("class", "data-tip-text"),
    "ol": ("start",),
    "p": ("align",),
    "div": ("align",),
    "table": ("align", "width"),
    "thead": ("align",),
    "tbody": ("align",),
    "tfoot": ("align",),
    "tr": ("align",),
    "td": ("colspan", "rowspan", "align", "width", "height"),
    "th": ("colspan", "rowspan", "align", "width", "height"),
    "details": ("open",),
    "pre": ("lang",),
    **{f"h{level}": ("id", "align") for level in range(1, 7)},
}
# The one shape an input keeps, a task list's box, ahead of `checked` when the document's
# was ticked: the hardener writes each of these, and reads only `type` and `checked` from
# the document.
CHECKBOX_ATTRIBUTES: Final = (("type", "checkbox"), ("disabled", ""))
# The attributes written without a value, whose presence is their meaning. The allowlist
# reads none of their values: HTML spells one as nothing or as the attribute's own name.
BARE_ATTRIBUTES: Final = frozenset({"open", "disabled", "checked"})
# The one language a block keeps: a Mermaid diagram's, spelled as GitHub's own fallback
# markup spells it, `<pre lang="mermaid">`, so the page can draw it as an image
# (builtin_plugins/markdown/diagrams.js). KPress marks the block with this class inside
# its diagram figure, and the figure and its class do not survive the allowlist.
DIAGRAM_LANGUAGE: Final = "mermaid"
_DIAGRAM_SOURCE_CLASS: Final = "kpress-diagram-source"
# What an image the page does not load becomes: its alt text in a span of this class,
# which static/styles.css draws as a compact chip, with the address the image would have
# loaded in its `data-tip-text`, the page's tooltip (a `title` is a second tooltip, which
# docs/design-system.md, "One Tooltip, and It Is Ours", forbids). Only the hardener writes
# the class, and a document's own span keeps it only in that shape.
IMAGE_FALLBACK_CLASS: Final = "mb-image-fallback"
# The policy an image from the web is fetched under: no `Referer`, so the page's address
# (which names the repository the reader opened) does not reach the image's host.
IMAGE_REFERRER_POLICY: Final = "no-referrer"
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
# A size as a browser reads one from an attribute: a number, with an optional fraction,
# then `%` for a share of the container, or the `px` a README often writes, which a
# browser reads as the number before it. Five digits reach 99999 pixels, past any screen
# or image a README sizes (an 8K display is 7680 wide), and bound how long a value a
# document can write; a longer one is dropped. Whatever a width says, the page caps an
# image at its container (`max-width: 100%`). static/inert-html.js has the same pattern.
_DIMENSION: Final = re.compile(r"[0-9]{1,5}(?:\.[0-9]{1,3})?(?:%|px)?", re.IGNORECASE)
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
    if scheme not in {"http", "https"}:
        return None
    # As a browser's URL parser writes it, which is what the page's layer keeps. urlsplit
    # reads a scheme in lower case, but urljoin hands back as written an address whose
    # scheme is not its base's.
    return scheme + absolute[len(scheme) :]


# Emitted only by the PR text hardener from the authored href. The browser otherwise
# cannot tell that two identical absolute URLs had different origins.
PATH_RELATIVE_LINK: Final = "data-metabrowser-path-relative"


def _is_path_relative(href: str | None) -> bool:
    if not href:
        return False
    cleaned = _clean(href)
    if not cleaned or cleaned.startswith(("/", "\\", "#", "?")) or _SCHEME.match(cleaned):
        return False
    # A reference up from the PR page can name another explicit GitHub route.
    # Mark paths that remain below this page's directory.
    path = _dot_segments(cleaned.replace("\\", "/")).split("?", 1)[0].split("#", 1)[0]
    depth = 0
    for segment in path.split("/"):
        if segment == "..":
            if depth == 0:
                return False
            depth -= 1
        elif segment not in {"", "."}:
            depth += 1
    return depth > 0


def link_href(href: str | None, base: str | None) -> tuple[str, bool] | None:
    """What a link keeps: its address and whether it leaves the page, or ``None``."""

    if base is None and is_inside(href):
        cleaned = _clean(href or "")
        return (fragment_link(cleaned) if cleaned.startswith("#") else cleaned), False
    outside = outside_link(href, base)
    return None if outside is None else (outside, True)


def _checkbox_type(kind: str | None) -> bool:
    """Whether an input's `type` makes it a checkbox, as a browser reads one: ASCII
    letters in any case, and nothing around them. Python's `lower` also folds U+212A
    KELVIN SIGN to `k`, which neither a browser's match nor KPress's sanitizer does."""

    written = kind or ""
    return written.isascii() and written.lower() == "checkbox"


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
        # A constant, so the document has no say in when its images load: a trusted
        # render's images wait until they near the reader, and these wait the same way.
        # Ahead of src, for a browser that reads the two in order.
        kept.append(("loading", "lazy"))
        remote = remote_image(attrs.get("src"), base)
        if remote is None:
            kept.append(("src", _clean(attrs.get("src") or "")))
        else:
            # The address as a browser's URL parser writes it, as a kept link's is.
            kept += [("referrerpolicy", IMAGE_REFERRER_POLICY), ("src", remote)]
        alt = attrs.get("alt")
        if alt:
            kept.append(("alt", alt))
    elif tag == "span":
        # The fallback the hardener writes for an image the page does not load, so its own
        # answer hardens to itself: the class exactly, and an address a browser reads as
        # http(s) for the tooltip.
        if attrs.get("class") == IMAGE_FALLBACK_CLASS:
            kept.append(("class", IMAGE_FALLBACK_CLASS))
            address = outside_link(attrs.get("data-tip-text"), None)
            if address is not None:
                kept.append(("data-tip-text", address))
    elif tag == "ol":
        start = attrs.get("start") or ""
        if _DIGITS.match(start):
            kept.append(("start", start))
    elif tag in {"td", "th"}:
        for name in ("colspan", "rowspan"):
            value = attrs.get(name) or ""
            if _SPAN.match(value):
                kept.append((name, value))
    elif tag == "details" and "open" in attrs:
        kept.append(("open", ""))
    elif tag == "input" and _checkbox_type(attrs.get("type")):
        kept += CHECKBOX_ATTRIBUTES
        if "checked" in attrs:
            kept.append(("checked", ""))
    elif tag == "pre" and (
        (attrs.get("lang") or "").lower() == DIAGRAM_LANGUAGE
        or _DIAGRAM_SOURCE_CLASS in (attrs.get("class") or "").split()
    ):
        kept.append(("lang", DIAGRAM_LANGUAGE))
    # A browser matches an align keyword in any case and with nothing around it.
    align = (attrs.get("align") or "").lower()
    if align in ALIGN_VALUES.get(tag, ()):
        kept.append(("align", align))
    for name in DIMENSIONS.get(tag, ()):
        size = attrs.get(name) or ""
        if _DIMENSION.fullmatch(size):
            kept.append((name, size))
    return kept


# An address written in full: its scheme (or none, for `//host`), two slashes in any mix, and
# then a character of the host, so `//`, `https:///`, and `//?x` name none. Without a host
# of its own, an address resolves against the page it sits in, which is no image of the web.
_WRITTEN_AUTHORITY: Final = re.compile(r"^(?:https:)?[/\\]{2}[^/\\?#]", re.IGNORECASE)
# The authority a written address names: what follows its two slashes up to the path, query,
# or fragment. A host in letters outside ASCII is read through IDNA, which Python does not
# have and which drops or maps characters a document can hide a different host in, so an
# address with one is not an image the page fetches: its alt text and a link are shown.
_AUTHORITY: Final = re.compile(r"^(?:https:)?[/\\]{2}([^/\\?#]*)", re.IGNORECASE)
# What a browser's URL parser refuses in a host: controls, space, and these (the WHATWG
# URL standard's forbidden host code points, with the percent sign it adds for a domain).
_HOST_FORBIDDEN: Final = re.compile(r"[\x00-\x20#%/:<>?@\[\\\]^|\x7f]")


# A number in one part of an IPv4 address, as the URL standard reads one: hex after `0x`,
# octal after a leading `0`, decimal otherwise.
_IPV4_DECIMAL: Final = re.compile(r"[0-9]+")
_IPV4_HEX: Final = re.compile(r"[0-9a-fA-F]*")
_IPV4_OCTAL: Final = re.compile(r"[0-7]*")


def _ipv4_number(part: str) -> int | None:
    if part == "":
        return None
    if part[:2].lower() == "0x":
        digits, pattern, base = part[2:], _IPV4_HEX, 16
    elif len(part) > 1 and part[0] == "0":
        digits, pattern, base = part[1:], _IPV4_OCTAL, 8
    else:
        digits, pattern, base = part, _IPV4_DECIMAL, 10
    if pattern.fullmatch(digits) is None:
        return None
    return int(digits, base) if digits else 0


def _ends_in_number(host: str) -> bool:
    """The URL standard's test for a host that is an IPv4 address, or fails to be one."""

    parts = host.split(".")
    if parts[-1] == "":
        if len(parts) == 1:
            return False
        parts.pop()
    return _ipv4_number(parts[-1]) is not None


def _ipv4_parses(host: str) -> bool:
    parts = host.split(".")
    if parts[-1] == "" and len(parts) > 1:
        parts.pop()
    numbers = [_ipv4_number(part) for part in parts]
    if len(parts) > 4 or None in numbers:
        return False
    values = [number for number in numbers if number is not None]
    return all(number < 256 for number in values[:-1]) and values[-1] < 256 ** (5 - len(parts))


def _host_parses(address: str) -> bool:
    """Whether *address* has a host a browser reads and a port it accepts.

    The host is named, holds none of :data:`_HOST_FORBIDDEN`, and, in brackets, is an IPv6
    address; the port, if there is one, is a number a browser takes. Python's own split
    reads neither, so an address with an empty or malformed one passes it.
    """

    try:
        parts = urlsplit(address)
        host = parts.hostname
        parts.port  # noqa: B018 -- reading it is the check: it raises for one out of range
    except ValueError:
        return False
    if not host:
        return False
    if parts.netloc.rpartition("@")[2].startswith("["):
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            return False
        return True
    if _HOST_FORBIDDEN.search(host) is not None:
        return False
    # A host that ends in a number is an IPv4 address or none: `evil.test127.0.0.1` is neither.
    return _ipv4_parses(host) if _ends_in_number(host) else True


def remote_image(src: str | None, base: str | None) -> str | None:
    """The ``https`` address of an image the page may fetch from the web, or ``None``.

    Only an address the document writes in full qualifies, as ``https://host/...``, in
    any case or spelling a browser reads the same way (``//host/...``, ``https:host/...``,
    a backslash for a slash), so a relative path in a pull request's comment, which
    :func:`outside_link` would make absolute against *base*, is not one. ``http`` is not
    one, nor is an address with no host, or one a browser's URL parser refuses
    (:func:`_host_parses`), nor one with a user name or password in it, which a browser
    refuses an image under, nor one whose host is written outside ASCII. What qualifies is
    returned as :func:`outside_link` writes it.
    ``static/inert-html.js`` makes the same choice; ``tests/test_inert_html.py`` holds the two
    to one answer on a corpus.
    """

    if not src:
        return None
    cleaned = _spelled_out(_clean(src), base)
    if not _WRITTEN_AUTHORITY.match(cleaned):
        return None
    authority = _AUTHORITY.match(cleaned)
    if authority is None or not authority[1].isascii():
        return None
    outside = outside_link(src, base)
    if outside is None or not outside.startswith("https://"):
        return None
    parts = urlsplit(outside)
    if parts.username or parts.password:
        return None
    return outside if _host_parses(outside) else None


def keeps_image(src: str | None, base: str | None) -> bool:
    """Whether an image stays an image: one inside the served tree, or one from the web."""

    return (base is None and is_inside(src)) or remote_image(src, base) is not None


def image_link(src: str | None, alt: str | None, base: str | None) -> tuple[str | None, str]:
    """What an image becomes when it is not kept: a link's href, if any, and its text."""

    return outside_link(src, base), (alt or "").strip() or "image"


def image_fallback(text: str, address: str | None) -> str:
    """The span an image the page does not load becomes: its alt *text*, and the
    *address* it would have loaded, if it has one, for the page's tooltip."""

    kept = [("class", IMAGE_FALLBACK_CLASS)]
    if address is not None:
        kept.append(("data-tip-text", address))
    return f"{_open_tag('span', kept)}{escape(text, quote=False)}</span>"


def _open_tag(tag: str, kept: list[tuple[str, str]]) -> str:
    rendered = "".join(
        f" {name}" if name in BARE_ATTRIBUTES else f' {name}="{escape(value)}"'
        for name, value in kept
    )
    return f"<{tag}{rendered}>"


class _Heading:
    def __init__(
        self, index: int, tag: str, original: str | None, kept: list[tuple[str, str]]
    ) -> None:
        self.index = index
        self.tag = tag
        self.original = original
        # The attributes it keeps besides the anchor, such as its `align`.
        self.kept = kept
        self.text: list[str] = []


type RewriteLocal = Callable[[str, bool], str | None]


class _Hardener(HTMLParser):
    def __init__(
        self,
        base: str | None,
        rewrite_local: RewriteLocal | None,
        mark_path_relative: bool,
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.rewrite_local = rewrite_local
        self.mark_path_relative = mark_path_relative
        self.out: list[str] = []
        # Depth inside a dropped element; nothing is written while it is above zero.
        self.dropped = 0
        # Depth inside a link, which an image's fallback is the content of, not a link of
        # its own.
        self.links = 0
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
        # An attribute written twice is its first, as a browser, KPress's sanitizer, and
        # static/inert-html.js read it: `<input type="text" type="checkbox">` is no box.
        values = dict(reversed(attrs))
        if tag == "img":
            self._image(values)
            return
        if tag == "input":
            # Kept only in the shape of a task list's box, wherever a checkbox is written;
            # any other input is void, so nothing of it is left.
            if kept := allowed_attributes("input", values, self.base):
                self.out.append(_open_tag("input", kept))
            return
        if tag in ALLOWED_TAGS:
            kept = allowed_attributes(tag, values, self.base)
            if tag == "a" and self.rewrite_local is not None:
                href = dict(kept).get("href")
                if href is not None and is_inside(href):
                    scoped = self.rewrite_local(href, False)
                    kept = [] if scoped is None else [("href", scoped)]
            if tag == "a":
                if self.mark_path_relative and kept and _is_path_relative(values.get("href")):
                    kept.append((PATH_RELATIVE_LINK, ""))
                self.links += 1
            self.out.append(_open_tag(tag, kept))
            if tag in _HEADINGS and self.base is None:
                heading = _Heading(len(self.out) - 1, tag, values.get("id"), kept)
                self.headings.append(heading)
                self.open_headings.append(heading)

    def _image(self, values: dict[str, str | None]) -> None:
        """Write an image: kept, or the fallback for one the page does not load."""

        src = values.get("src")
        if keeps_image(src, self.base):
            kept = allowed_attributes("img", values, self.base)
            if remote_image(src, self.base) is not None or self.rewrite_local is None:
                # An address on the web is not a reference into the tree, so the rewrite
                # a page makes of those is not asked about it.
                self.out.append(_open_tag("img", kept))
                return
            original = dict(kept)["src"]
            rewritten = self.rewrite_local(original, True)
            if rewritten is not None:
                kept = [(name, rewritten if name == "src" else value) for name, value in kept]
                self.out.append(_open_tag("img", kept))
                return
            # An image the rewrite does not keep is a link to where it leads as one,
            # an address the rewrite wrote and so kept as it is.
            href = self.rewrite_local(original, False)
            text = image_link(None, values.get("alt"), self.base)[1]
            link = None if href is None else [("href", href)]
            address = href
        else:
            href, text = image_link(src, values.get("alt"), self.base)
            link = None if href is None else allowed_attributes("a", {"href": href}, self.base)
            address = href
        self._text(text)
        fallback = image_fallback(text, address)
        if link is None or self.links:
            # Inside a link, which a badge is, the link is the image's own: a second one
            # inside it is not valid, and a browser reads it as the first's end.
            self.out.append(fallback)
        else:
            self.out.append(f"{_open_tag('a', link)}{fallback}</a>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and tag != "img":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.dropped:
            if tag not in _VOID:
                self.dropped -= 1
            return
        if tag == "a" and self.links:
            self.links -= 1
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
            self.out[heading.index] = _open_tag(heading.tag, [("id", anchor), *heading.kept])
            if heading.original is not None and written[heading.original] == 1:
                replaced[heading.original] = anchor
        return replaced


def harden(html: str, link_base: str | None = None, *, mark_path_relative: bool = False) -> str:
    """Reduce *html* to the inert allowlist and optionally identify authored PR file links."""

    return _harden(html, link_base, mark_path_relative=mark_path_relative)[0]


def harden_document(
    html: str, *, rewrite_local: RewriteLocal | None = None
) -> tuple[str, dict[str, str]]:
    """:func:`harden` for a document inside the served tree, and its heading anchors:
    each ``id`` a heading had in *html*, mapped to the anchor that replaces it.

    *rewrite_local*, when given, is asked for every reference inside the tree that
    survives the allowlist, with whether it is an image's: it answers the address to
    write instead, which is kept as written, or ``None``. A link it drops keeps its text
    and loses its ``href``; an image it drops becomes a link to the address it answers for
    the same reference as a link, or, without one, its alt text. A page that serves a
    document from somewhere other than the served tree, such as a pull request's rendered
    Markdown, uses it to keep every reference in that tree.
    """

    return _harden(html, None, rewrite_local)


def _harden(
    html: str,
    link_base: str | None,
    rewrite_local: RewriteLocal | None = None,
    *,
    mark_path_relative: bool = False,
) -> tuple[str, dict[str, str]]:
    hardener = _Hardener(link_base, rewrite_local, mark_path_relative and link_base is not None)
    hardener.feed(html)
    hardener.close()
    replaced = hardener.anchor_headings()
    return "".join(hardener.out), replaced


__all__ = [
    "ALIGN_VALUES",
    "ALLOWED_ATTRIBUTES",
    "ANCHOR_PREFIX",
    "ALLOWED_TAGS",
    "BARE_ATTRIBUTES",
    "CHECKBOX_ATTRIBUTES",
    "DIMENSIONS",
    "DROPPED_WITH_CONTENT",
    "IMAGE_FALLBACK_CLASS",
    "IMAGE_REFERRER_POLICY",
    "allowed_attributes",
    "fragment_link",
    "harden",
    "harden_document",
    "heading_slug",
    "image_fallback",
    "image_link",
    "is_inside",
    "keeps_image",
    "link_href",
    "outside_link",
    "remote_image",
]
