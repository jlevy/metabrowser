"""The previews area of the cache: one PNG per key, bounded by size, least recently used out.

The area is ``plugins/pdf/previews/`` under the application cache root, inside the
directory :func:`metabrowser.plugin_api.plugin_cache_directory` keeps owner-only for this
plugin (``docs/project/architecture/arch-repository-cache.md``, Layout). Each entry is
``<key>.png``, where the key is a SHA-256 of what the preview was computed from
(:func:`metabrowser.builtin_plugins.pdf.preview.preview_key`), so an entry is never
stale, only unused, and the same bytes are rendered once whichever source holds them.

- **Reads** go through :func:`metabrowser.home.open_private_file`, which verifies the
  cache root, every directory down to the area, and the entry before it opens it, and
  refuses rather than repairs a shared one. A read is bounded by :data:`ENTRY_MAX_BYTES`
  and moves the entry's modification time to now, which is what marks it recently used.
- **Writes** go through :func:`metabrowser.home.write_private_file_atomic`: a reader sees
  the whole PNG or none.
- **Eviction** follows each write: when the area holds more than :data:`AREA_MAX_BYTES`
  or :data:`AREA_MAX_ENTRIES`, the entries used longest ago are removed until it holds
  no more than either. An evicted preview is rendered again on its next request.

Every method answers a filesystem failure as a miss or a skipped write, so a full disk or
a cache that cannot be kept private costs previews, never a request.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.builtin_plugins.pdf.render_child import PNG_SIGNATURE

LOG = logging.getLogger(__name__)

PLUGIN_NAME: Final = "pdf"
# The area, relative to the cache root.
AREA: Final = f"plugins/{PLUGIN_NAME}/previews"

# The largest entry read back: any PNG the render child can write for the preview box
# (480 by 640 pixels of RGB, filter bytes included, is 922,240 bytes before zlib, which
# grows incompressible input by under 0.1 percent), with room for its chunks. The
# largest measured is 500,358 bytes (the vector page beside `PREVIEW_BOX` in preview.py).
ENTRY_MAX_BYTES: Final = 1024 * 1024
# The area's size bound. Thirty-six real PDFs (papers, slides, scanned books, plots)
# measured a median preview of 71 KB and the largest 189 KB, so this keeps about 900
# previews at the median and at least 64 at the bound of one entry.
AREA_MAX_BYTES: Final = 64 * 1024 * 1024
# The area's entry bound, which keeps one eviction pass's listing and its `stat` calls
# short: listing and `lstat`-ing 4,096 entries took 17 ms (three runs, 2026-11-24, APFS,
# load average 36), beside a render's 115 to 410 ms; and the smallest measured preview,
# 18 KB, fills `AREA_MAX_BYTES` at about 3,600.
AREA_MAX_ENTRIES: Final = 4096
# The most names one eviction pass lists. Past it the area holds files this plugin did not
# write, and nothing is removed: eviction removes only entries it can name.
_LISTING_MAX_ENTRIES: Final = 2 * AREA_MAX_ENTRIES

_ENTRY_NAME: Final = re.compile(r"[0-9a-f]{64}\.png")
KEY_PATTERN: Final = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class EvictionReport:
    """What one eviction pass found and removed, for logs and tests."""

    entries: int
    total_bytes: int
    removed: int


class PreviewStore:
    """The previews area under one cache root. Blocking: call it off the event loop."""

    def __init__(self, home: Path) -> None:
        self.home = home

    @classmethod
    def open(cls) -> PreviewStore | None:
        """The store under the application cache, made owner-only, or None without one."""

        from metabrowser.home import (
            PrivateStorageError,
            StorageDirectoryError,
            application_cache,
            ensure_private_directory,
        )
        from metabrowser.plugin_api import PluginCacheUnavailableError, plugin_cache_directory

        try:
            plugin_cache_directory(PLUGIN_NAME)
            home = application_cache()
            ensure_private_directory(home, AREA)
        except (PluginCacheUnavailableError, PrivateStorageError, StorageDirectoryError, OSError):
            return None
        return cls(home)

    def _relative(self, key: str) -> str:
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError("a preview key is 64 lowercase hexadecimal digits")
        return f"{AREA}/{key}.png"

    def read(self, key: str) -> bytes | None:
        """The entry under *key*, marked as used now, or None for any kind of miss."""

        from metabrowser.home import PrivateStorageError, open_private_file

        try:
            fd = open_private_file(
                self.home, self._relative(key), os.O_RDONLY | os.O_NONBLOCK, shared="refuse"
            )
        except (FileNotFoundError, PrivateStorageError, OSError):
            return None
        try:
            if os.fstat(fd).st_size > ENTRY_MAX_BYTES:
                return None
            chunks: list[bytes] = []
            remaining = ENTRY_MAX_BYTES + 1
            while remaining > 0:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > ENTRY_MAX_BYTES or not data.startswith(PNG_SIGNATURE):
                return None
            # Its use is its modification time; failing to move it costs order, not data.
            with contextlib.suppress(OSError):
                os.utime(fd)
            return data
        except OSError:
            return None
        finally:
            os.close(fd)

    def write(self, key: str, png: bytes) -> bool:
        """Publish *png* under *key*, then evict past the bounds. False when it was not kept."""

        from metabrowser.home import PrivateStorageError, write_private_file_atomic

        if len(png) > ENTRY_MAX_BYTES:
            return False
        try:
            write_private_file_atomic(self.home, self._relative(key), png)
        except (PrivateStorageError, OSError) as exc:
            LOG.warning("pdf preview: could not keep a preview: %s", exc)
            return False
        self.evict()
        return True

    def evict(
        self, *, max_bytes: int = AREA_MAX_BYTES, max_entries: int = AREA_MAX_ENTRIES
    ) -> EvictionReport:
        """Remove the entries used longest ago until the area is within both bounds.

        Names are listed through the verified directory
        (:func:`metabrowser.cache.listing.list_private_directory`); only names of this
        store's form are considered, each is ``lstat``-ed without following a link, and only
        a regular file is removed. A name that vanished in between was removed by another
        process, which is what was wanted.
        """

        from metabrowser.cache.listing import ListingLimitError, list_private_directory
        from metabrowser.home import PrivateStorageError

        try:
            names = list_private_directory(
                self.home, AREA, max_entries=_LISTING_MAX_ENTRIES, shared="refuse"
            )
        except (ListingLimitError, PrivateStorageError, OSError) as exc:
            LOG.warning("pdf preview: the previews area was not evicted: %s", exc)
            return EvictionReport(entries=0, total_bytes=0, removed=0)
        directory = self.home / AREA
        entries: list[tuple[int, str, int]] = []
        for name in names:
            if not _ENTRY_NAME.fullmatch(name):
                continue
            try:
                status = os.lstat(directory / name)
            except OSError:
                continue
            if not stat.S_ISREG(status.st_mode):
                continue
            entries.append((status.st_mtime_ns, name, status.st_size))
        total = sum(size for _mtime, _name, size in entries)
        count = len(entries)
        removed = 0
        # Oldest use first; the name breaks a tie, so a pass is deterministic.
        for _mtime, name, size in sorted(entries):
            if total <= max_bytes and count <= max_entries:
                break
            try:
                os.unlink(directory / name)
            except FileNotFoundError:
                pass
            except OSError:
                continue
            total -= size
            count -= 1
            removed += 1
        return EvictionReport(entries=len(entries), total_bytes=total, removed=removed)


__all__ = [
    "AREA",
    "AREA_MAX_BYTES",
    "AREA_MAX_ENTRIES",
    "ENTRY_MAX_BYTES",
    "KEY_PATTERN",
    "EvictionReport",
    "PreviewStore",
]
