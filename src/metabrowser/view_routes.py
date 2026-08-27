"""Canonical browser-route validation and formatting.

The server validates the raw ASGI path exactly once before returning the application
shell. The CLI uses the matching formatter for startup URLs. Filesystem lookup remains
in the existing API routes; this module only protects and serializes route identity.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote_to_bytes

from metabrowser.paths_safe import _safe_path

VIEW_ROUTE_PREFIX = "/view/"
COMMIT_ROUTE_PREFIX = "/commit/"
_VIEW_ROUTE_PREFIX_BYTES = VIEW_ROUTE_PREFIX.encode()
_MALFORMED_ESCAPE = re.compile(rb"%(?![0-9A-Fa-f]{2})")
# A revision as it may appear in a route: an oid, or a ref name git
# itself would accept. Deliberately narrow — the shell only needs to
# recognize the route; the API resolves the revision for real.
_ROUTE_REVISION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/@^~-]{0,255}$")


def format_view_href(logical_path: str) -> str:
    """Return the canonical segment-encoded route for a normalized logical path."""

    _validate_logical_segments(logical_path.split("/"))
    return VIEW_ROUTE_PREFIX + "/".join(
        quote(segment, safe="") for segment in logical_path.split("/")
    )


def decode_safe_view_path(raw_path: bytes) -> str | None:
    """Decode one raw ``/view/`` path and require served-root containment.

    ``None`` covers malformed encodings, non-canonical segments, invalid UTF-8, and
    paths whose resolution (including symlinks) escapes the configured served root.
    Missing paths beneath the root are safe and remain valid shell destinations.
    """

    if not raw_path.startswith(_VIEW_ROUTE_PREFIX_BYTES):
        return None
    raw_segments = raw_path[len(_VIEW_ROUTE_PREFIX_BYTES) :].split(b"/")
    decoded_segments: list[str] = []
    try:
        for raw_segment in raw_segments:
            if _MALFORMED_ESCAPE.search(raw_segment):
                return None
            decoded = unquote_to_bytes(raw_segment)
            if any(forbidden in decoded for forbidden in (b"/", b"\\", b"\0")):
                return None
            decoded_segments.append(decoded.decode("utf-8", errors="strict"))
        _validate_logical_segments(decoded_segments)
    except (UnicodeDecodeError, ValueError):
        return None

    logical_path = "/".join(decoded_segments)
    return logical_path if _safe_path(logical_path) is not None else None


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
        for raw_segment in raw_segments:
            if _MALFORMED_ESCAPE.search(raw_segment):
                return None
            decoded = unquote_to_bytes(raw_segment)
            if any(forbidden in decoded for forbidden in (b"/", b"\\", b"\0")):
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


def _validate_logical_segments(segments: list[str]) -> None:
    """Require the root, a normalized path, or a single trailing folder slash."""

    final_index = len(segments) - 1
    for index, segment in enumerate(segments):
        trailing_folder_slash = index == final_index and not segment
        if (
            (not segment and not trailing_folder_slash)
            or segment in {".", ".."}
            or "\\" in segment
            or "\0" in segment
        ):
            raise ValueError("view path must be normalized and served-root-relative")
