"""Bounded direct-child discovery for folder envelopes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PREFERRED_README_NAMES = ("README.md", "readme.md", "Readme.md")


@dataclass(frozen=True, slots=True)
class FolderDiscovery:
    """Facts discovered without recursively walking a folder."""

    readme_name: str = ""
    readme_search_truncated: bool = False


def _choose_readme(candidates: list[str]) -> str:
    """Choose a real child name with stable casing precedence."""

    for preferred in _PREFERRED_README_NAMES:
        if preferred in candidates:
            return preferred
    return min(candidates, default="")


def discover_folder(target: Path, *, max_entries: int) -> FolderDiscovery:
    """Find a direct-child README within a bounded directory scan.

    The caller has already resolved ``target`` through the safe-path helper.
    Symlinks are excluded and no child content is read.
    """

    if max_entries < 0:
        raise ValueError("max_entries must be nonnegative")

    candidates: list[str] = []
    visited = 0
    truncated = False
    try:
        with os.scandir(target) as entries:
            for entry in entries:
                if visited >= max_entries:
                    truncated = True
                    break
                visited += 1
                if entry.name.casefold() != "readme.md":
                    continue
                try:
                    if entry.is_file(follow_symlinks=False):
                        candidates.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return FolderDiscovery()
    return FolderDiscovery(
        readme_name=_choose_readme(candidates),
        readme_search_truncated=truncated,
    )


__all__ = ["FolderDiscovery", "discover_folder"]
