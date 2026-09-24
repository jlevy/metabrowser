"""Make KPress's sanitized HTML of a pull request's text inert inside the page.

KPress's sanitized mode removes scripts and event handlers, but it is a document
renderer: it keeps ``<link href>``, ``<img src>``, ``id`` attributes, and SVG ``<use>``,
which a document of its own may use. Inside the pull-request page, where one untrusted
comment shares the page with the application, each of them is an attack: a ``<link
rel=stylesheet>`` restyles the whole page, an image or media element reports that the
page was read, and an ``id`` or ``name`` clobbers a global the page's scripts read.

:func:`harden` rewrites the rendered HTML so nothing in it loads and nothing names
itself: the elements that load or embed are removed with their content, an image
becomes a link to it (for ``http`` and ``https`` only), every URL-bearing attribute but a
link's ``href`` is dropped, and a link's ``href`` is made absolute against the pull
request's github.com page, kept only for ``http`` and ``https``, and opened in a new tab
without an opener or referrer. ``builtin_plugins/github/pull-page.js`` applies the same
rules again to what it inserts. Repository Markdown files are not rewritten here.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from typing import Final
from urllib.parse import urljoin, urlsplit

# Elements removed with everything inside them: they load, embed, style, or submit.
DROPPED: Final = frozenset(
    {
        "audio",
        "base",
        "embed",
        "form",
        "iframe",
        "image",
        "link",
        "meta",
        "noscript",
        "object",
        "script",
        "source",
        "style",
        "symbol",
        "template",
        "title",
        "track",
        "use",
        "video",
    }
)
# Attributes that load, restyle, or name an element for scripts to find, and a link's
# own target and rel, which a kept link is given anew.
DROPPED_ATTRIBUTES: Final = frozenset(
    {
        "action",
        "background",
        "data",
        "formaction",
        "href",
        "id",
        "lowsrc",
        "name",
        "poster",
        "rel",
        "src",
        "srcset",
        "style",
        "target",
        "xlink:href",
    }
)
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


class _Hardener(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.out: list[str] = []
        # Depth inside a dropped element; nothing is written while it is above zero.
        self.dropped = 0

    def _attributes(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        kept: list[str] = []
        for name, value in attrs:
            if name in DROPPED_ATTRIBUTES or name.startswith("on"):
                continue
            kept.append(f' {name}="{escape(value or "", quote=True)}"')
        if tag == "a":
            href = safe_link(dict(attrs).get("href"), self.base)
            if href is not None:
                kept.append(
                    f' href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer"'
                )
        return "".join(kept)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # KPress's icon sprite is a hidden SVG of symbols; without its style and symbols
        # it would be an empty box, so it goes whole.
        hidden_sprite = tag == "svg" and "display: none" in (dict(attrs).get("style") or "")
        if self.dropped or tag in DROPPED or hidden_sprite:
            if tag not in _VOID:
                self.dropped += 1
            return
        if tag == "img":
            values = dict(attrs)
            text = escape((values.get("alt") or "").strip() or "image", quote=False)
            href = safe_link(values.get("src"), self.base)
            if href is None:
                self.out.append(f'<span class="github-pull-image">{text}</span>')
            else:
                self.out.append(
                    f'<a class="github-pull-image" href="{escape(href, quote=True)}"'
                    f' target="_blank" rel="noopener noreferrer">{text}</a>'
                )
            return
        self.out.append(f"<{tag}{self._attributes(tag, attrs)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID or tag == "img":
            self.handle_starttag(tag, attrs)
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.dropped:
            if tag not in _VOID:
                self.dropped -= 1
            return
        if tag in DROPPED or tag in _VOID or tag == "img":
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.dropped:
            self.out.append(escape(data, quote=False))


def harden(html: str, base: str) -> str:
    """*html* with nothing in it that loads, embeds, restyles, or names an element."""

    hardener = _Hardener(base)
    hardener.feed(html)
    hardener.close()
    return "".join(hardener.out)


__all__ = ["DROPPED", "DROPPED_ATTRIBUTES", "harden", "safe_link"]
