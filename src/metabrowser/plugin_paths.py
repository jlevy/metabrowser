"""Normalization and validation for operator-configured plugin directories."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def normalize_plugin_dirs(paths: Iterable[Path]) -> list[Path]:
    """Return canonical existing directories in input order without duplicates."""
    seen: set[str] = set()
    normalized: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError(f"plugin directory not a directory: {path}")
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(resolved)
    return normalized
