"""Provider-neutral serialization for the Recent-files surface.

The inventory provider owns filtering, ignored-ancestor resolution, ordering and the
tracked-first cap policy. This module translates that typed projection into the stable
browser envelope; client-side clustering remains a rendering concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from metabrowser.inventory_engine.contract import InventoryEntry, RecentProjection
from metabrowser.settings import (
    RECENT_DEFAULT_LIMIT,
    RECENT_MAX_LIMIT,
)

WindowKey = Literal["live", "1h", "24h", "7d", "30d", "all"]
DEFAULT_LIMIT = RECENT_DEFAULT_LIMIT
MAX_LIMIT = RECENT_MAX_LIMIT


@dataclass(slots=True, frozen=True)
class RecentResult:
    """Flat recent leaves and ignored ancestors consumed by the browser."""

    entries_flat: list[dict[str, Any]]
    gitignored_dirs: list[str]
    total_matching: int
    truncated: bool
    window: WindowKey
    limit: int


def recent_result_from_projection(
    projection: RecentProjection,
    *,
    window: WindowKey,
    limit: int,
) -> RecentResult:
    """Serialize one coherent recent projection for the browser."""

    return RecentResult(
        entries_flat=[_entry_to_wire(entry) for entry in projection.entries],
        gitignored_dirs=list(projection.gitignored_directories),
        total_matching=projection.total_matches,
        truncated=projection.truncated,
        window=window,
        limit=limit,
    )


def _entry_to_wire(entry: InventoryEntry) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "name": entry.name,
        "path": entry.path,
        "type": "file",
        "size": entry.size,
        "mtime": entry.mtime_ns / 1_000_000_000.0 if entry.mtime_ns else 0.0,
        "ext": entry.ext,
    }
    if entry.gitignored:
        wire["gitignored"] = True
    return wire


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "RecentResult",
    "WindowKey",
    "recent_result_from_projection",
]
