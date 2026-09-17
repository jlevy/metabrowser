"""Bounded, verified, lock-free listing of one directory in the application home.

The read routes enumerate sources, stores, and reclamation areas without a lock and
without creating anything, so they cannot use :func:`metabrowser.home.ensure_private_directory`,
which creates a missing directory. This walks the same descriptor-relative, no-follow path
that a record read does: the home's ancestors and the home are verified, each directory
below it is opened without following a link and held to the owner-only rules, and the
names are read from the verified descriptor itself, so a directory swapped for a link
after verification is never listed. As with a record read, an existing shared directory
loses its group and other access, and a missing one raises :class:`FileNotFoundError`.
"""

from __future__ import annotations

import os
from pathlib import Path

from metabrowser.home import (
    _open_directory_entry,
    _open_home,
    _require_home_argument,
    _verify_home_ancestors,
    _without_file_names,
)
from metabrowser.inventory_engine.contract import require_canonical_inventory_path


class ListingLimitError(Exception):
    """A directory holds more entries than one listing reads."""

    def __init__(self, max_entries: int) -> None:
        super().__init__(f"the directory holds more than {max_entries} entries")
        self.max_entries: int = max_entries


@_without_file_names
def list_private_directory(home: Path, relative_path: str, *, max_entries: int) -> tuple[str, ...]:
    """Return the sorted entry names of an owner-only directory below *home*.

    *relative_path* is a POSIX-relative path such as ``"cache/sources"``. Raises
    :class:`FileNotFoundError` when the home or the directory is missing,
    :class:`~metabrowser.home.PrivateStorageError` when any part of the path is not
    private, and :class:`ListingLimitError` rather than reading past *max_entries*.
    """

    _require_home_argument(home)
    require_canonical_inventory_path(relative_path, "application-home path", allow_root=False)
    _verify_home_ancestors(home)
    path = home
    fd = _open_home(home)
    try:
        for name in relative_path.split("/"):
            path = path / name
            child = _open_directory_entry(fd, name, path, create=False)
            os.close(fd)
            fd = child
        names: list[str] = []
        # scandir reads a duplicate of the verified descriptor and closes only that.
        with os.scandir(fd) as entries:
            for entry in entries:
                if len(names) == max_entries:
                    raise ListingLimitError(max_entries)
                names.append(entry.name)
    finally:
        os.close(fd)
    return tuple(sorted(names))


__all__ = ["ListingLimitError", "list_private_directory"]
