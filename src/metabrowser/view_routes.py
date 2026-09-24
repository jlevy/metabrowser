"""Canonical browser-route validation and formatting.

The server validates the raw ASGI path exactly once before returning the application
shell. The CLI uses the matching formatter for startup URLs. Filesystem lookup remains
in the existing API routes; this module only protects and serializes route identity.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote_from_bytes, unquote_to_bytes

from metabrowser.inventory_engine.contract import native_inventory_path
from metabrowser.paths_safe import _safe_path

VIEW_ROUTE_PREFIX = "/view/"
COMMIT_ROUTE_PREFIX = "/commit/"
PULL_ROUTE_PREFIX = "/pull/"
# The tabs of a pull-request page after its number: the conversation is the page
# itself, and `files` is its Files changed, spelled as github.com spells it.
PULL_ROUTE_TABS = ("", "files")
# A pull-request number as the GitHub URL reducer admits one.
_PULL_NUMBER = re.compile(r"^[1-9][0-9]{0,9}$")
_VIEW_ROUTE_PREFIX_BYTES = VIEW_ROUTE_PREFIX.encode()
_MALFORMED_ESCAPE = re.compile(rb"%(?![0-9A-Fa-f]{2})")
# A revision as it may appear in a route: an oid, or a ref name git
# itself would accept. Deliberately narrow — the shell only needs to
# recognize the route; the API resolves the revision for real.
_ROUTE_REVISION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/@^~-]{0,255}$")


def format_view_href(logical_path: str) -> str:
    """Return the canonical route for a normalized native filesystem path.

    POSIX filenames are byte strings at the kernel boundary. Python preserves an
    undecodable byte with ``surrogateescape``; encoding that native spelling with
    :func:`os.fsencode` restores the byte so every filename has a URL. Windows names
    are UTF-16 and may contain an unpaired code unit, for which WTF-8 is the route
    spelling already used by the browser codec.
    """

    _validate_logical_segments(logical_path.split("/"), native=True)
    return VIEW_ROUTE_PREFIX + "/".join(
        quote_from_bytes(_route_segment_bytes(segment), safe="")
        for segment in logical_path.split("/")
    )


def format_inventory_view_href(identity_path: str) -> str:
    """Format one canonical inventory identity as its human-facing view route.

    The inverse is also the validity check: strings outside the image of the
    platform escaper are not inventory identities and must not be guessed into a
    different path.
    """

    native = native_inventory_path(identity_path)
    if native is None:
        raise ValueError("view identity is not canonical for this platform")
    return format_view_href(native)


def format_commit_href(revision: str, inner_path: str = "") -> str:
    """Return the canonical commit route with the ref in one encoded segment."""

    if _ROUTE_REVISION.fullmatch(revision) is None:
        raise ValueError("commit route requires a valid revision")
    head = COMMIT_ROUTE_PREFIX + quote_from_bytes(revision.encode("utf-8"), safe="")
    if not inner_path:
        return head
    segments = inner_path.split("/")
    _validate_logical_segments(segments)
    return (
        head
        + "/"
        + "/".join(quote_from_bytes(segment.encode("utf-8"), safe="") for segment in segments)
    )


def decode_view_logical_path(raw_path: bytes) -> str | None:
    """Decode one raw ``/view/`` path without filesystem containment.

    The result is the slash-joined logical identity. A filesystem session still
    has to pass :func:`decode_safe_view_path`. A Git revision session uses
    that identity as a ``GitPath`` wire, optionally plus a container inner.
    """

    if not raw_path.startswith(_VIEW_ROUTE_PREFIX_BYTES):
        return None
    raw_segments = raw_path[len(_VIEW_ROUTE_PREFIX_BYTES) :].split(b"/")
    decoded_segments: list[str] = []
    try:
        for raw_segment in raw_segments:
            # A literal backslash is never the canonical spelling (the formatter
            # writes `%5C`), and a browser would have read it as a separator.
            if _MALFORMED_ESCAPE.search(raw_segment) or b"\\" in raw_segment:
                return None
            decoded = unquote_to_bytes(raw_segment)
            if b"/" in decoded or b"\0" in decoded or (b"\\" in decoded and os.name == "nt"):
                return None
            decoded_segments.append(_native_route_segment(decoded))
        _validate_logical_segments(decoded_segments, native=True)
    except (UnicodeDecodeError, ValueError):
        return None
    return "/".join(decoded_segments)


def decode_safe_view_path(raw_path: bytes) -> str | None:
    """Decode one raw ``/view/`` path and require served-root containment.

    ``None`` covers malformed encodings, non-canonical segments, bytes the platform
    cannot name, and paths whose resolution (including symlinks) escapes the configured
    served root. POSIX undecodable bytes and Windows unpaired UTF-16 units retain their
    native spelling so the route codec is total over the inventory contract. Missing
    paths beneath the root are safe and remain valid shell destinations.
    """

    logical_path = decode_view_logical_path(raw_path)
    if logical_path is None:
        return None
    return logical_path if _safe_path(logical_path) is not None else None


def _route_segment_bytes(segment: str) -> bytes:
    """Encode one native segment exactly as the browser route codec does."""

    if os.name == "nt":
        return segment.encode("utf-8", errors="surrogatepass")
    return os.fsencode(segment)


def _native_route_segment(encoded: bytes) -> str:
    """Recover one platform spelling from its route bytes."""

    if os.name == "nt":
        return encoded.decode("utf-8", errors="surrogatepass")
    return os.fsdecode(encoded)


def decode_safe_commit_route(raw_path: bytes) -> tuple[str, str] | None:
    """Decode ``/commit/<rev>[/<inner path>]`` into (revision, inner path).

    The revision is matched, not resolved: this gate only decides whether
    the shell should be served, and the comparison API owns resolution.
    The inner path is a path *within a comparison*, so it is validated for
    shape and never touched by the served-root check — the files a commit
    changed need not exist in the working tree at all.
    """

    if not raw_path.startswith(COMMIT_ROUTE_PREFIX.encode()):
        return None
    remainder = raw_path[len(COMMIT_ROUTE_PREFIX) :]
    raw_segments = remainder.split(b"/")
    decoded_segments: list[str] = []
    try:
        for index, raw_segment in enumerate(raw_segments):
            if _MALFORMED_ESCAPE.search(raw_segment):
                return None
            decoded = unquote_to_bytes(raw_segment)
            forbidden_bytes = (b"\\", b"\0") if index == 0 else (b"/", b"\\", b"\0")
            if any(forbidden in decoded for forbidden in forbidden_bytes):
                return None
            decoded_segments.append(decoded.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError):
        return None
    if decoded_segments and decoded_segments[-1] == "":
        # A trailing slash names the comparison itself.
        decoded_segments.pop()
    if not decoded_segments:
        return None
    revision, *inner_segments = decoded_segments
    if not _ROUTE_REVISION.match(revision):
        return None
    if any(segment in ("", ".", "..") for segment in inner_segments):
        return None
    return revision, "/".join(inner_segments)


def format_pull_href(number: int, tab: str = "") -> str:
    """Return the served pull request's page, ``/pull/<n>`` or ``/pull/<n>/files``."""

    if _PULL_NUMBER.fullmatch(str(number)) is None or tab not in PULL_ROUTE_TABS:
        raise ValueError("pull route requires a pull-request number and a known tab")
    return f"{PULL_ROUTE_PREFIX}{number}" + (f"/{tab}" if tab else "")


def decode_safe_pull_route(raw_path: bytes) -> tuple[int, str] | None:
    """Decode ``/pull/<n>[/files]`` into (number, tab), or ``None``.

    The page belongs to the pull request the server serves; which one that is, and
    whether it is cached, is the pull route's answer, not this gate's. A trailing slash
    names the same page.
    """

    if not raw_path.startswith(PULL_ROUTE_PREFIX.encode()):
        return None
    segments = raw_path[len(PULL_ROUTE_PREFIX) :].split(b"/")
    if len(segments) > 1 and segments[-1] == b"":
        segments.pop()
    if len(segments) > 2:
        return None
    try:
        number, tab = (
            segments[0].decode("ascii"),
            (segments[1].decode("ascii") if len(segments) == 2 else ""),
        )
    except UnicodeDecodeError:
        return None
    if (
        _PULL_NUMBER.fullmatch(number) is None
        or tab not in PULL_ROUTE_TABS
        or (len(segments) == 2 and not tab)
    ):
        return None
    return int(number), tab


def _validate_logical_segments(segments: list[str], *, native: bool = False) -> None:
    """Require the root, a normalized path, or a single trailing folder slash.

    ``native`` segments are served-tree filenames. POSIX allows a backslash in one and
    the inventory escapes it as ``%5C``, so the route codec carries it (as ``%5C``) to
    stay total over the inventory; Windows reads it as a separator, so there it stays
    refused, as it does in a commit route's Git path.
    """

    final_index = len(segments) - 1
    for index, segment in enumerate(segments):
        trailing_folder_slash = index == final_index and not segment
        if (
            (not segment and not trailing_folder_slash)
            or segment in {".", ".."}
            or ("\\" in segment and (not native or os.name == "nt"))
            or "\0" in segment
        ):
            raise ValueError("view path must be normalized and served-root-relative")
