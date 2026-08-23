"""Sparse Metabrowser-owned decorations for provider inventory entries.

Providers own filesystem facts. The host owns transient UI state such as activity,
preview choices, and plugin labels. Keeping those decorations in this path-keyed
overlay prevents either provider from carrying browser-specific state or forcing the
coordinator to duplicate the retained inventory.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType


def _require_canonical_path(path: str) -> None:
    """Require the lossless POSIX-relative identity used by inventory providers."""

    if path == "":
        return
    pure = PurePosixPath(path)
    if (
        "\\" in path
        or "\x00" in path
        or pure.is_absolute()
        or pure.as_posix() != path
        or ".." in pure.parts
    ):
        raise ValueError("overlay paths must be canonical POSIX-relative paths")


@dataclass(frozen=True, slots=True)
class InventoryDecoration:
    """Application state joined onto one returned filesystem entry."""

    active: bool = False
    views: tuple[str, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if any(not view for view in self.views):
            raise ValueError("overlay view ids must not be empty")
        if len(self.views) != len(set(self.views)):
            raise ValueError("overlay view ids must be unique")
        label_names = [name for name, _value in self.labels]
        if any(not name for name in label_names):
            raise ValueError("overlay label names must not be empty")
        if len(label_names) != len(set(label_names)):
            raise ValueError("overlay label names must be unique")
        if self.labels != tuple(sorted(self.labels)):
            raise ValueError("overlay labels must be sorted by name")

    @property
    def is_empty(self) -> bool:
        """Whether this record is the implicit default and need not be retained."""

        return not self.active and not self.views and not self.labels


EMPTY_DECORATION = InventoryDecoration()


@dataclass(frozen=True, slots=True)
class OverlaySnapshot:
    """One coherent sparse overlay image for a requested path set."""

    revision: int
    decorations: Mapping[str, InventoryDecoration]


class InventoryOverlay:
    """Thread-safe sparse decorations with one semantic revision sequence."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._revision = 0
        self._decorations: dict[str, InventoryDecoration] = {}

    def snapshot(self, paths: Iterable[str] = ()) -> OverlaySnapshot:
        """Return decorations for only *paths* at one overlay revision."""

        requested = tuple(dict.fromkeys(paths))
        for path in requested:
            _require_canonical_path(path)
        with self._lock:
            selected = {
                path: decoration
                for path in requested
                if (decoration := self._decorations.get(path)) is not None
            }
            return OverlaySnapshot(
                revision=self._revision,
                decorations=MappingProxyType(selected),
            )

    def replace(self, path: str, decoration: InventoryDecoration | None) -> int:
        """Replace one decoration and return the resulting revision."""

        return self.replace_many({path: decoration})

    def replace_many(
        self,
        replacements: Mapping[str, InventoryDecoration | None],
    ) -> int:
        """Atomically apply sparse replacements, incrementing once on a real change."""

        for path in replacements:
            _require_canonical_path(path)
        with self._lock:
            changed = False
            for path, requested in replacements.items():
                decoration = requested if requested is not None else EMPTY_DECORATION
                current = self._decorations.get(path, EMPTY_DECORATION)
                if current == decoration:
                    continue
                changed = True
                if decoration.is_empty:
                    self._decorations.pop(path, None)
                else:
                    self._decorations[path] = decoration
            if changed:
                self._revision += 1
            return self._revision

    def clear(self) -> int:
        """Drop every retained decoration, incrementing iff the image changed."""

        with self._lock:
            if self._decorations:
                self._decorations.clear()
                self._revision += 1
            return self._revision

    @property
    def retained_count(self) -> int:
        """Number of non-default records retained by the sparse overlay."""

        with self._lock:
            return len(self._decorations)


__all__ = [
    "EMPTY_DECORATION",
    "InventoryDecoration",
    "InventoryOverlay",
    "OverlaySnapshot",
]
