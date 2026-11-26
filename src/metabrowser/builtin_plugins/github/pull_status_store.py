"""Where a pull request's operational status is kept, and how its last read ended.

A status (:class:`~.pull_status.PullStatus`) is a row of the repository's catalog
database, in a table of its own (:func:`~.pull_catalog.write_pull_status`), so a status
that changes with every check moves no catalog row, fingerprint, core, or window
generation. The checks of the same head (:class:`~.pull_status.PullChecks`) are
``pulls/<n>.checks.json`` beside the record, which only the pull request page needs.
How the last read of them ended is ``pulls/<n>.status.refresh.json``. All three are under
the source's ``pulls`` directory, so clearing the cache clears them
(:func:`~.pull_record.clear_pulls`), and a checkout without a store has them as it has a
catalog.

A write keeps the newer observation: a status or a list of checks observed before the
one kept is dropped, so two reads that end out of order leave the later one. Every file
is written atomically by the home's private writer under the source-alias lock, and read
lock-free with a size bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.builtin_plugins.github.pull_catalog import read_pull_status
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_PULL_REFRESH_BYTES,
    PullRefreshStamp,
    ensure_pulls_directory,
)
from metabrowser.builtin_plugins.github.pull_status import PullChecks, PullStatus
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import source_pull_checks, source_pull_status_refresh
from metabrowser.home import PrivateStorageError, write_private_file_atomic

# The most a checks file may be, written or read. Measured 2026-11-26 on this repository's
# pull requests #380, #498, #508, and #872, 15 to 35 checks each as GitHub Actions names
# them: a written check took 261 to 270 bytes, so the most a file lists,
# ``MAX_CHECK_ITEMS`` (400) checks, is about 110 KB. A mebibyte is nine times that, for
# checks with longer names, links, and descriptions; a list that would pass it is cut
# from the end until it fits, and marked ``truncated``, so every file written reads back.
MAX_PULL_CHECKS_BYTES: Final = 1024 * 1024


def _fitted(checks: PullChecks) -> bytes:
    """*checks* serialized within :data:`MAX_PULL_CHECKS_BYTES`, cut from the end to fit."""

    data = checks.model_dump_json().encode("utf-8")
    if len(data) <= MAX_PULL_CHECKS_BYTES:
        return data
    # The longest prefix of the items that fits, by bisection: at most nine serializations.
    low, high = 0, len(checks.items)
    while low < high:
        middle = (low + high + 1) // 2
        trial = checks.model_copy(update={"items": checks.items[:middle], "truncated": True})
        if len(trial.model_dump_json().encode("utf-8")) <= MAX_PULL_CHECKS_BYTES:
            low = middle
        else:
            high = middle - 1
    cut = checks.model_copy(update={"items": checks.items[:low], "truncated": True})
    return cut.model_dump_json().encode("utf-8")


def read_pull_checks(home: Path, slug: str, number: int) -> PullChecks | None:
    """The kept checks of pull request *number*, or ``None``. Blocking and bounded.

    A file that is missing, too large, malformed, outside the model, or of another number
    is no checks; the next read of the status replaces it.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_checks(slug, number), max_bytes=MAX_PULL_CHECKS_BYTES
        )
        checks = PullChecks.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        return None
    return checks if checks.number == number else None


def write_pull_checks(home: Path, slug: str, checks: PullChecks) -> bool:
    """Keep *checks* unless newer ones are kept; whether it did. Blocking.

    Under the source's alias lock, as every writer of the ``pulls`` directory; call it
    through ``run_lock_section``. Raises the home's ``PrivateStorageError`` or an
    ``OSError`` when the cache cannot take it, a slug no source holds among them.
    """

    data = _fitted(checks)
    with source_alias_lock(home, slug):
        ensure_pulls_directory(home, slug)
        kept = read_pull_checks(home, slug, checks.number)
        if kept is not None and kept.observed_at > checks.observed_at:
            return False
        write_private_file_atomic(home, source_pull_checks(slug, checks.number), data)
        return True


def write_status_outcome(home: Path, slug: str, number: int, stamp: PullRefreshStamp) -> None:
    """Keep how the last read of pull request *number*'s status ended. Blocking.

    A failed read is the status's own part, as a refused part of a record is the record's:
    the refresh that ran it still succeeded, so it is not noted in the event log as the
    refresh's failure is (:func:`~.pull_record.note_refresh_outcome`).
    """

    with source_alias_lock(home, slug):
        ensure_pulls_directory(home, slug)
        write_private_file_atomic(
            home,
            source_pull_status_refresh(slug, number),
            stamp.model_dump_json().encode("utf-8"),
        )


def read_status_outcome(home: Path, slug: str, number: int) -> PullRefreshStamp | None:
    """How the last read of the status ended, or ``None`` when no usable stamp is kept."""

    try:
        data = read_bytes_bounded(
            home, source_pull_status_refresh(slug, number), max_bytes=MAX_PULL_REFRESH_BYTES
        )
        return PullRefreshStamp.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        # ValueError covers pydantic's ValidationError: anything unusable is no stamp.
        return None


@dataclass(frozen=True, slots=True)
class KeptStatus:
    """What is kept of a pull request's operational status.

    ``unavailable`` is why the last read failed, when it did: the status and checks are
    then the ones an earlier read kept, or ``None``.
    """

    status: PullStatus | None
    checks: PullChecks | None
    unavailable: str | None


def kept_status(home: Path, slug: str, number: int) -> KeptStatus:
    """The kept status, checks, and last outcome of pull request *number*. Blocking, bounded.

    Reads one catalog row and two small files, and asks nothing of GitHub.
    """

    outcome = read_status_outcome(home, slug, number)
    return KeptStatus(
        status=read_pull_status(home, slug, number),
        checks=read_pull_checks(home, slug, number),
        unavailable=None if outcome is None or outcome.outcome == "succeeded" else outcome.outcome,
    )


__all__ = [
    "MAX_PULL_CHECKS_BYTES",
    "KeptStatus",
    "kept_status",
    "read_pull_checks",
    "read_status_outcome",
    "write_pull_checks",
    "write_status_outcome",
]
