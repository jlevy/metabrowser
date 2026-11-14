"""Which served files a rendered document embeds, as the page will ask ``/raw`` for them.

The Markdown plugin's link enhancer resolves each image, audio, video, source, and object
address of a render in the page (``builtin_plugins/markdown/links.js``) and points it at
``/raw?path=<identity>``. The render route answers, beside the HTML, a version for each of
those identities (``raw_versions``), and the enhancer puts it in the address, so a
replaced file is a new address and a browser cannot show the copy it holds of the old one
(``SECURITY.md``, ``docs/design-system.md``, "A Repaint Keeps Its Images").

This predicts the identities the enhancer will compute, with its rule for a source-relative
or root-relative path on a served folder. The prediction need not be complete: a version
is looked up by the identity the page computed, so an address this misses is only left
unversioned, and one it adds that the page never asks for costs a ``stat``. It can never
name the wrong file, because the route resolves each identity it returns with the same
resolver ``/raw`` uses for that identity, and versions what that resolver finds.
"""

from __future__ import annotations

import html
import re
from urllib.parse import unquote

# An element the enhancer resolves, with the attribute that holds its address
# (link-enhancer.js RESOURCE_ATTRIBUTES). Attribute values may hold `>` inside quotes.
_RESOURCE_TAG = re.compile(
    r"<(img|audio|video|source|object)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
    re.IGNORECASE,
)
_ATTRIBUTE = re.compile(
    r"""\s([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))"""
)
# links.js resolveExternal: a scheme, or `//`, after leading controls and spaces.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# What JavaScript's `trimStart` removes: its white space and line terminators.
_JS_LEADING_SPACE = re.compile(
    "^[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+"
)
# A `%` that does not start an escape, where decodeURIComponent throws.
_BAD_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
# links.js MAX_AUTHORED_TARGET_LENGTH.
_MAX_AUTHORED_TARGET_LENGTH = 16384


def embedded_raw_paths(rendered_html: str, source_path: str, *, limit: int) -> list[str]:
    """The distinct identities, at most *limit*, that *rendered_html*'s resources resolve to.

    *source_path* is the document's own identity, which a relative address resolves
    against. Order is document order, so the bound keeps a document's first resources.
    """

    found: dict[str, None] = {}
    for tag in _RESOURCE_TAG.finditer(rendered_html):
        wanted = "data" if tag.group(1).lower() == "object" else "src"
        for attribute in _ATTRIBUTE.finditer(tag.group(2)):
            if attribute.group(1).lower() != wanted:
                continue
            value = next(group for group in attribute.groups()[1:] if group is not None)
            identity = resolve_embedded_path(html.unescape(value), source_path)
            if identity is not None:
                found[identity] = None
                if len(found) >= limit:
                    return list(found)
            break
    return list(found)


def resolve_embedded_path(authored: str, source_path: str) -> str | None:
    """The identity the link enhancer asks ``/raw`` for when *authored* is embedded, or None.

    It is links.js ``resolveStandardTarget`` for an embed on a served folder, followed by
    the enhancer's ``normalizedFilePath``: the document itself for an address with no path,
    a folder for one that names a folder, which no version is given for, and None for an
    outside address and every address links.js refuses -- a backslash, a NUL, a malformed
    escape, an encoded separator, or a path above the served root.
    ``tests/test_raw_versions.py`` compares it with links.js itself.
    """

    # The bound counts UTF-16 code units, as a JavaScript string's length does.
    units = len(authored.encode("utf-16-le", errors="surrogatepass")) // 2
    if units > _MAX_AUTHORED_TARGET_LENGTH or "\\" in authored or "\0" in authored:
        return None
    trimmed = _JS_LEADING_SPACE.sub("", authored)
    probe = "".join(character for character in trimmed if ord(character) > 32)
    if probe.startswith("//") or _SCHEME.match(probe):
        return None
    before_fragment, _, fragment = authored.partition("#")
    path, _, query = before_fragment.partition("?")
    resolved = _resolve_logical_path(source_path, path)
    if resolved is None or not _valid_part(query) or not _valid_part(fragment):
        return None
    return resolved.removesuffix("/")


def _resolve_logical_path(source_path: str, path: str) -> str | None:
    """links.js ``resolveLogicalPath`` for a served folder."""

    if not path:
        return source_path
    rooted = path.startswith("/")
    relative = path[1:] if rooted else path
    if not relative:
        return ""
    trailing_slash = relative.endswith("/")
    raw_segments = relative.split("/")
    segments: list[str] = []
    parent_pops = 0
    for index, raw in enumerate(raw_segments):
        if not raw:
            if trailing_slash and index == len(raw_segments) - 1:
                continue
            return None
        segment = _decode(raw)
        if segment is None or "/" in segment or "\0" in segment:
            return None
        if segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            elif rooted:
                return None
            else:
                parent_pops += 1
            continue
        segments.append(segment)
    # links.js inventoryName: the inventory spells `%` as `%25` and a backslash as `%5C`.
    authored_path = "/".join(
        segment.replace("%", "%25").replace("\\", "%5C") for segment in segments
    )
    base = ""
    if not rooted:
        parents = source_path.split("/")[:-1]
        if parent_pops > len(parents):
            return None
        base = "/".join(parents[: len(parents) - parent_pops])
    resolved = f"{base}/{authored_path}" if base and authored_path else base or authored_path
    return f"{resolved}/" if trailing_slash and resolved else resolved


def _decode(raw: str) -> str | None:
    """decodeURIComponent, or None where it throws."""

    if _BAD_ESCAPE.search(raw):
        return None
    try:
        return unquote(raw, errors="strict")
    except UnicodeDecodeError:
        return None


def _valid_part(serialized: str) -> bool:
    """links.js ``validateSerializedPart``: a query or fragment that decodes, with no NUL."""

    if not serialized:
        return True
    decoded = _decode(serialized)
    return decoded is not None and "\0" not in decoded


__all__ = ["embedded_raw_paths", "resolve_embedded_path"]
