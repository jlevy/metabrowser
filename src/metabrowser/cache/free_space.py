"""The free space a first clone may use on the cache's volume.

A first clone is refused before it starts when the pack it would write, with
:data:`FREE_SPACE_RESERVE_MB` left over, does not fit on the volume that holds the cache:
a clone that fills the disk stops partway with an error that reads like a network
failure, and leaves the volume full for everything else on it. Size alone is no reason to
refuse; how long a clone takes is bounded by ``GIT_ACQUISITION_TIMEOUT_S`` and the
low-speed stall bound (``cache/origin.py``), not here.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Final

log = logging.getLogger(__name__)

# A pack is 1.0 to 1.1 times GitHub's reported size: 1.1 times for django (313 MB stored
# for 283 MB reported, measured 2026-09-23), and 1.0 times for a 1,222,854 KB private
# repository whose pack was 1.16 GiB (measured 2026-11-02). The larger ratio is used.
PACK_PER_REPORTED: Final = 1.1
# What a first clone leaves free on the cache's volume, in megabytes (10^6 bytes). One
# gigabyte is room for the system and other programs on the volume to keep writing; it is
# a choice, not a measurement, and METABROWSER_CACHE_RESERVE_MB changes it.
FREE_SPACE_RESERVE_MB: Final[int] = 1000
FREE_SPACE_RESERVE_ENV: Final = "METABROWSER_CACHE_RESERVE_MB"


def free_space_reserve_bytes() -> int:
    """The environment's whole number of megabytes, zero or more, or else the default."""

    raw = os.environ.get(FREE_SPACE_RESERVE_ENV, "").strip()
    if raw:
        try:
            reserve_mb = int(raw)
        except ValueError:
            reserve_mb = -1
        if reserve_mb >= 0:
            return reserve_mb * 1_000_000
        log.warning("ignored %s: it is not a whole number of megabytes", FREE_SPACE_RESERVE_ENV)
    return FREE_SPACE_RESERVE_MB * 1_000_000


def volume_free_bytes(directory: Path) -> int | None:
    """The free space on the volume that holds *directory*, or its nearest existing parent,
    or ``None`` when it cannot be read."""

    probe = directory
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def packed_bytes(reported_kb: int) -> int:
    """The bytes a clone of a repository its host reports at *reported_kb* can write."""

    return int(reported_kb * 1024 * PACK_PER_REPORTED)


def gigabytes(count: int) -> str:
    """*count* bytes as decimal gigabytes, to one place."""

    return f"{count / 1e9:.1f} GB"


__all__ = [
    "FREE_SPACE_RESERVE_ENV",
    "FREE_SPACE_RESERVE_MB",
    "PACK_PER_REPORTED",
    "free_space_reserve_bytes",
    "gigabytes",
    "packed_bytes",
    "volume_free_bytes",
]
