"""Parse navigation-filter selections before provider query construction.

The HTTP and CLI surfaces share this small input model. Inventory providers own the
actual filtering and aggregate semantics through ``FilteredTreeQuery``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from metabrowser.settings import RECENT_WINDOW_SECONDS


@dataclass(frozen=True, slots=True)
class TreeFilter:
    """One filter selection in the navigation filter bar's vocabulary."""

    recency_seconds: int = 0
    types: tuple[str, ...] = ()
    min_size: int = 0
    include_ignored: bool = True

    @property
    def active(self) -> bool:
        """Whether this selection removes anything."""

        return bool(self.recency_seconds or self.types or self.min_size or not self.include_ignored)


def parse_size_floor(raw: str) -> int:
    """Read the ``min_size`` query value as a positive byte count."""

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def parse_recency(raw: str) -> int:
    """Read a known recency-window key as seconds, or return unbounded."""

    seconds = RECENT_WINDOW_SECONDS.get(raw)
    return int(seconds) if seconds else 0


def parse_types(values: Sequence[str]) -> tuple[str, ...]:
    """Normalize repeated and comma-separated extension or filename tokens."""

    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.split(","):
            token = part.strip().lower()
            if token and token != "." and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tuple(tokens)
