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
# A `%` that does not start an escape, where decodeURIComponent throws.
_BAD_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
# links.js MAX_AUTHORED_TARGET_LENGTH.
_MAX_AUTHORED_TARGET_LENGTH = 4096


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
    """The identity links.js resolves *authored* to from *source_path*, or None.

    None for an outside address, an address of the document itself or of a folder, and
    every address links.js refuses: a backslash, a NUL, a malformed escape, an encoded
    separator, or a path above the served root.
    """

    if len(authored) > _MAX_AUTHORED_TARGET_LENGTH or "\\" in authored or "\0" in authored:
        return None
    probe = "".join(character for character in authored if ord(character) > 32)
    if probe.startswith("//") or _SCHEME.match(probe):
        return None
    path = authored.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return None
    rooted = path.startswith("/")
    relative = path[1:] if rooted else path
    if not relative or relative.endswith("/"):
        return None
    segments: list[str] = []
    parent_pops = 0
    for raw in relative.split("/"):
        if not raw or _BAD_ESCAPE.search(raw):
            return None
        try:
            segment = unquote(raw, errors="strict")
        except UnicodeDecodeError:
            return None
        if "/" in segment or "\0" in segment:
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
    if not segments:
        return None
    # links.js inventoryName: the inventory spells `%` as `%25` and a backslash as `%5C`.
    authored_path = "/".join(
        segment.replace("%", "%25").replace("\\", "%5C") for segment in segments
    )
    if rooted:
        return authored_path
    parents = source_path.split("/")[:-1]
    if parent_pops > len(parents):
        return None
    base = "/".join(parents[: len(parents) - parent_pops])
    return f"{base}/{authored_path}" if base else authored_path


__all__ = ["embedded_raw_paths", "resolve_embedded_path"]
