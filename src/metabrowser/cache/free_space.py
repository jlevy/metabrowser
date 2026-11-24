"""The free space a first clone may use on the cache's volume.

A clone that fills the disk stops partway with an error that reads like a network
failure, and leaves the volume full for everything else on it. So a first clone is
refused before it starts when it could not leave :data:`FREE_SPACE_RESERVE_MB` free on
the volume that holds the cache: any first clone, whatever its source, when the volume
already has less than that free (:func:`refuse_below_reserve`, which core runs before it
asks a provider), and one whose host reports its size when the pack it would write does
not fit with the reserve left over (:func:`refuse_unless_it_fits`, which a provider runs).
Size alone is no reason to refuse.

How long a clone takes is not bounded here. The low-speed bound in ``cache/origin.py``
ends a transfer that stalls, and ``GIT_ACQUISITION_TIMEOUT_S`` (``git/process.py``) stops
every acquisition Git process at its deadline, a first clone still making progress too.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
from pathlib import Path
from typing import Final, Literal, NoReturn

log = logging.getLogger(__name__)

type Rounding = Literal["nearest", "down", "up"]
_ROUNDINGS: Final = {"nearest": round, "down": math.floor, "up": math.ceil}
# The invalid reserve values already warned about, so that the core check and a
# provider's, which both read the reserve for one clone, warn once (review C3 on #768).
_WARNED: set[str] = set()

# A pack is 1.0 to 1.1 times GitHub's reported size: 1.1 times for django (313 MB stored
# for 283 MB reported, measured 2026-09-23), and 1.0 times for a 1,222,854 KB private
# repository whose pack was 1.16 GiB (measured 2026-11-02). The larger ratio is used.
PACK_PER_REPORTED: Final = 1.1
# What a first clone leaves free on the cache's volume, in megabytes (10^6 bytes). One
# gigabyte is room for the system and other programs on the volume to keep writing; it is
# a choice, not a measurement, and METABROWSER_CACHE_RESERVE_MB changes it.
FREE_SPACE_RESERVE_MB: Final[int] = 1000
FREE_SPACE_RESERVE_ENV: Final = "METABROWSER_CACHE_RESERVE_MB"
_REMEDY: Final = (
    "free space on the volume, set METABROWSER_CACHE_DIR to one with more, or lower "
    f"{FREE_SPACE_RESERVE_ENV}"
)


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
        if raw not in _WARNED:
            _WARNED.add(raw)
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


def size_text(count: int, rounding: Rounding = "nearest") -> str:
    """*count* bytes in decimal units: gigabytes to one place from one gigabyte, whole
    megabytes below it, and "under 1 MB" for a size that rounds to none.

    A refusal rounds what the volume has ``"down"`` and what a clone needs or leaves
    ``"up"``, so that the figures it prints never read as fitting when the bytes do not:
    nearest rounding printed "has 1000 MB free, less than the 1.0 GB" one byte below the
    reserve (review C1 on #768).

    Decimal, as :data:`FREE_SPACE_RESERVE_ENV` is; a progress line's sizes
    (``format_size`` in ``cli/clone_report.py``) are binary.
    """

    rounded = _ROUNDINGS[rounding]
    if count >= 1_000_000_000:
        tenths = rounded(count / 1e8)
        if tenths >= 10:
            return f"{tenths / 10:.1f} GB"
        # Down from just above a gigabyte, it falls back to megabytes below.
    megabytes = rounded(count / 1e6)
    if megabytes >= 1000:
        return f"{megabytes / 1000:.1f} GB"
    if count == 0 or megabytes >= 1:
        return f"{megabytes} MB"
    return "under 1 MB"


def refuse_below_reserve(source_url: str, free_bytes: int | None) -> None:
    """Refuse a first clone of *source_url*, whatever its size, when the cache's volume has
    *free_bytes* free, less than the reserve, so that no clone could leave the reserve.

    Raise :class:`~metabrowser.cache.acquire.RepositoryTooLargeError`. A volume whose free
    space could not be read, ``None``, refuses nothing.
    """

    if free_bytes is not None:
        _refuse_below(source_url, free_bytes, free_space_reserve_bytes())


def refuse_unless_it_fits(source_url: str, free_bytes: int, *, host: str, reported_kb: int) -> None:
    """Refuse a first clone of *source_url*, which *host* reports at *reported_kb*, when
    its pack would leave less than the reserve of the *free_bytes* on the cache's volume.

    A provider that can size a first clone calls this. It raises as
    :func:`refuse_below_reserve` does, and names the size, the volume's free space, and
    the reserve.
    """

    reserve = free_space_reserve_bytes()
    _refuse_below(source_url, free_bytes, reserve)
    needed = packed_bytes(reported_kb)
    if needed + reserve > free_bytes:
        _refuse(
            source_url,
            f"{host} reports {reported_kb:,} KB, which can take {size_text(needed, 'up')}, and "
            f"the cache's volume has {size_text(free_bytes, 'down')} free, of which metab "
            f"leaves {size_text(reserve, 'up')}",
        )


def _refuse_below(source_url: str, free_bytes: int, reserve: int) -> None:
    if free_bytes < reserve:
        _refuse(
            source_url,
            f"the cache's volume has {size_text(free_bytes, 'down')} free, less than the "
            f"{size_text(reserve, 'up')} metab leaves free",
        )


def _refuse(source_url: str, why: str) -> NoReturn:
    # Imported here so that the doctor, which reads this module's sizes, does not load
    # the acquisition machinery.
    from metabrowser.cache.acquire import RepositoryTooLargeError

    raise RepositoryTooLargeError(source_url, detail=f"{why}; {_REMEDY}")


__all__ = [
    "FREE_SPACE_RESERVE_ENV",
    "FREE_SPACE_RESERVE_MB",
    "PACK_PER_REPORTED",
    "Rounding",
    "free_space_reserve_bytes",
    "packed_bytes",
    "refuse_below_reserve",
    "refuse_unless_it_fits",
    "size_text",
    "volume_free_bytes",
]
