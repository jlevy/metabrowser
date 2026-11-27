"""Where a pull request's operational status is kept, and how its last read ended.

A status (:class:`~.pull_status.PullStatus`) is a row of the repository's catalog
database, in a table of its own (:func:`~.pull_catalog.write_pull_status`), so a status
that changes with every check moves no catalog row, fingerprint, core, or window
generation. The checks of the same head (:class:`~.pull_status.PullChecks`) are
``pulls/<n>.checks.json`` beside the record, which only the pull request page needs.
How the latest read of them ended is ``pulls/<n>.status.refresh.json``
(:class:`StatusOutcome`), and what the probes of the head's checks last saw is
``pulls/<n>.checks.probe.json`` (:class:`CheckProbes`).
All four are under the source's ``pulls`` directory, so clearing the cache clears them
(:func:`~.pull_record.clear_pulls`), and a checkout without a store has them as it has a
catalog.

A write keeps the newer observation: a status observed before the one kept is dropped, so
two reads that end out of order leave the later one (:func:`~.pull_status.kept_observation`),
and a list of checks is kept exactly when the status kept then names it, so the checks
file is always the list a status's ``listed_at`` names, whatever order reads end in. How
a read ended is kept likewise for the attempt that began last (:func:`write_status_outcome`),
so an older read that fails after a newer one succeeded leaves the newer's outcome. Every
file is written atomically by the home's private writer under the source-alias lock, and
read lock-free with a size bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from metabrowser.builtin_plugins.github.pull_catalog import read_pull_status
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_PULL_REFRESH_BYTES,
    PullRefreshStamp,
    Reader,
    Sha,
    Timestamp,
    ensure_pulls_directory,
)
from metabrowser.builtin_plugins.github.pull_status import PullChecks, PullStatus, counted_list
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import (
    source_pull_check_probes,
    source_pull_checks,
    source_pull_status_refresh,
)
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
    """Keep *checks* when the status kept names them; whether it did. Blocking.

    Write the status first (:func:`~.pull_catalog.write_pull_status`). The status names
    the list its summary counts (``listed_at`` of its head), which is never an older list
    than one it named before, so keeping only that list keeps the file and the status
    agreeing whatever order reads end in, and a read whose list the status does not count,
    one that ended after a newer list or after its checks moved, leaves the file as it is.

    Under the source's alias lock, as every writer of the ``pulls`` directory; call it
    through ``run_lock_section``. Raises the home's ``PrivateStorageError`` or an
    ``OSError`` when the cache cannot take it, a slug no source holds among them.
    """

    data = _fitted(checks)
    with source_alias_lock(home, slug):
        status = read_pull_status(home, slug, checks.number)
        if status is None or (status.head, status.checks.listed_at) != (
            checks.head,
            checks.observed_at,
        ):
            return False
        ensure_pulls_directory(home, slug)
        write_private_file_atomic(home, source_pull_checks(slug, checks.number), data)
        return True


class StatusOutcome(PullRefreshStamp):
    """How one read of a pull request's status ended, and ``started_at``, when it began.

    ``at`` is when GitHub answered a read that succeeded, its status's ``observed_at``, and
    when one that failed gave up.
    """

    started_at: Timestamp

    @field_validator("started_at")
    @classmethod
    def _a_real_start(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return value


def write_status_outcome(home: Path, slug: str, number: int, outcome: StatusOutcome) -> bool:
    """Keep how a read of pull request *number*'s status ended, unless a later attempt's
    is kept; whether it is now the one kept. Blocking.

    Reads run in several processes, a server's and the one-shot CLI's among them, and end
    in any order, so an attempt that began earlier and failed later never replaces the
    outcome of one that began after it: the outcome kept is the newest attempt's, by
    ``started_at``, as the status kept is the newest observation. Of two that began in one
    second, the one written last is kept, as one process's reads follow each other.

    A failed read is the status's own part, as a refused part of a record is the record's:
    the refresh that ran it still succeeded, so it is not noted in the event log as the
    refresh's failure is (:func:`~.pull_record.note_refresh_outcome`). Under the source's
    alias lock; call it through ``run_lock_section``.
    """

    data = outcome.model_dump_json().encode("utf-8")
    with source_alias_lock(home, slug):
        kept = read_status_outcome(home, slug, number)
        if kept is not None and kept.started_at > outcome.started_at:
            return False
        ensure_pulls_directory(home, slug)
        write_private_file_atomic(home, source_pull_status_refresh(slug, number), data)
        return True


def read_status_outcome(home: Path, slug: str, number: int) -> StatusOutcome | None:
    """How the latest read of the status ended, or ``None`` when no usable stamp is kept."""

    try:
        data = read_bytes_bounded(
            home, source_pull_status_refresh(slug, number), max_bytes=MAX_PULL_REFRESH_BYTES
        )
        return StatusOutcome.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        # ValueError covers pydantic's ValidationError: anything unusable is no stamp.
        return None


class ProbedPage(BaseModel):
    """What the last conditional read of one checks page found.

    ``etag`` is GitHub's for that answer, sent with the next read, or ``None`` when it sent
    none; ``digest`` is a SHA-256 of what a status keeps of the page, each check's name,
    state, and links (:func:`.pulls.probe_pull_request`), so a ``200`` that changed none of
    it is no change.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    etag: Annotated[str, StringConstraints(max_length=300)] | None
    digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CheckProbes(BaseModel):
    """What the probes of one head's checks last saw, as *reader*, at ``seen_at``.

    The status is read with GraphQL, which has no ETag, so the conditional reads that find
    a change for free, the first pages of the head's check runs and of its combined status,
    keep their own: the first probe of a head asks each page once unconditionally, a
    ``200`` that seeds the baseline and is counted as a change, and every later probe is
    conditional on it. ``refused`` says GitHub would not answer one of the pages for this
    head and reader, as a token without checks access is refused, so its checks are not
    probed and the status is read on the window's clock instead.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int = Field(ge=1)
    head: Sha
    reader: Reader
    seen_at: Timestamp
    pages: dict[Annotated[str, StringConstraints(max_length=512)], ProbedPage] = Field(max_length=2)
    refused: bool = False


# The most a probes file may be: two pages, each a path of at most 512 characters, an ETag
# of at most 300, and a 64-digit digest, with a head, a reader, and their keys, comes to
# under 2.5 KB; 4 KiB is the bound, written and read.
MAX_CHECK_PROBES_BYTES: Final = 4096


def read_check_probes(home: Path, slug: str, number: int) -> CheckProbes | None:
    """What the probes of pull request *number*'s checks last saw, or ``None``. Blocking.

    A file that is missing, too large, malformed, or of another number is none, and the
    next probe seeds a baseline again.
    """

    try:
        data = read_bytes_bounded(
            home, source_pull_check_probes(slug, number), max_bytes=MAX_CHECK_PROBES_BYTES
        )
        probes = CheckProbes.model_validate_json(data)
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        return None
    return probes if probes.number == number else None


def write_check_probes(home: Path, slug: str, probes: CheckProbes) -> bool:
    """Keep *probes* unless what a later probe saw is kept; whether it did. Blocking.

    Under the source's alias lock; call it through ``run_lock_section``. Raises the home's
    ``PrivateStorageError`` or an ``OSError`` when the cache cannot take it, a slug no
    source holds among them.
    """

    data = probes.model_dump_json().encode("utf-8")
    if len(data) > MAX_CHECK_PROBES_BYTES:
        raise ValueError("what a probe saw is larger than its file may be")
    with source_alias_lock(home, slug):
        ensure_pulls_directory(home, slug)
        kept = read_check_probes(home, slug, probes.number)
        if kept is not None and kept.seen_at > probes.seen_at:
            return False
        write_private_file_atomic(home, source_pull_check_probes(slug, probes.number), data)
        return True


@dataclass(frozen=True, slots=True)
class KeptStatus:
    """What is kept of a pull request's operational status.

    ``unavailable`` is why the latest read failed, when it did: the status and checks are
    then the ones an earlier read kept, or ``None``.
    """

    status: PullStatus | None
    checks: PullChecks | None
    unavailable: str | None

    @property
    def listed_checks(self) -> PullChecks | None:
        """The kept checks when they are the list the kept status counts, else ``None``.

        That is a list of the status's head kept by the read the status's summary names
        (:func:`~.pull_status.counted_list`). A status the Pulls tab's scan read for a new
        head, or with checks that moved since the page's read, names none, so the page's
        list of another head or of other counts is never shown beside it, and the page
        reads its own (:func:`.pull_freshness.record_freshness`).
        """

        return counted_list(self.status, self.checks)


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
    "MAX_CHECK_PROBES_BYTES",
    "MAX_PULL_CHECKS_BYTES",
    "CheckProbes",
    "KeptStatus",
    "ProbedPage",
    "StatusOutcome",
    "kept_status",
    "read_check_probes",
    "read_pull_checks",
    "read_status_outcome",
    "write_check_probes",
    "write_pull_checks",
    "write_status_outcome",
]
