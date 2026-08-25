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
from types import MappingProxyType

from metabrowser.inventory_engine.contract import require_canonical_inventory_path


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
class InventoryDecorationPatch:
    """Sparse ownership-safe update to one application decoration.

    ``None`` leaves the scalar or tuple field unchanged. Label values of ``None``
    remove only that named label, which lets independent host features share one
    decoration without reading and replacing each other's state.
    """

    active: bool | None = None
    views: tuple[str, ...] | None = None
    labels: tuple[tuple[str, str | None], ...] = ()

    def __post_init__(self) -> None:
        if self.views is not None:
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
            raise ValueError("overlay label updates must be sorted by name")

    def apply(self, current: InventoryDecoration) -> InventoryDecoration:
        """Merge this patch onto *current* without touching unowned fields."""

        labels = dict(current.labels)
        for name, value in self.labels:
            if value is None:
                labels.pop(name, None)
            else:
                labels[name] = value
        return InventoryDecoration(
            active=current.active if self.active is None else self.active,
            views=current.views if self.views is None else self.views,
            labels=tuple(sorted(labels.items())),
        )


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
            require_canonical_inventory_path(path, "overlay path", allow_root=True)
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
            require_canonical_inventory_path(path, "overlay path", allow_root=True)
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
    "InventoryDecorationPatch",
    "InventoryOverlay",
    "OverlaySnapshot",
]
