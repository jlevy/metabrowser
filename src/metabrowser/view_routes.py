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
_VIEW_ROUTE_PREFIX_BYTES = VIEW_ROUTE_PREFIX.encode()
_MALFORMED_ESCAPE = re.compile(rb"%(?![0-9A-Fa-f]{2})")


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
