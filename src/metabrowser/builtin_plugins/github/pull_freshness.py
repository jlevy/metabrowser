"""Whether a cached pull-request record still describes the pull request on GitHub.

The repository catalog's delta scan reads pull requests by ``UPDATED_AT`` until its
watermark, so its row of a number says when GitHub last changed that pull request and
which commit its head is. A record is checked against that row, read with the checkpoint
in one transaction, and only when the catalog's ``source`` and ``reader`` are the record's:

- **changed**: the row's ``updated_at`` is newer than the record's ``pull.updated_at``,
  whatever the scan's age, or equal with another head. ``head_moved`` says the row names
  another head commit.
- **current**: the row is not changed, the scan that published it ran within the window,
  or the next one is running and the last ran within :data:`SCAN_GRACE_S` past it, the
  record is of this build's ``PULL_RECORD_PROJECTION``, and it is closed or was read
  within the window. ``verified_at`` is then the newer of that scan's ``fetched_at`` and
  the record's, and ``verified_by`` is ``catalog``. A list probe that found the catalog
  unchanged (:mod:`.pull_list_probe`) counts as a scan run when it asked: GitHub had no
  pull request newer than the catalog's newest, so every row was as the scan left it.
- **checks**: the same, for an open pull request whose operational status
  (:class:`~.pull_status.PullStatus`) is missing, describes another head, or was observed
  longer ago than the window. The record is current: the catalog vouches for its
  conversation and head, and it holds nothing ``updated_at`` does not track. Its status
  does, conflicts and checks, which a status read then reads on its own
  (:func:`.pulls.refresh_pull_status`).
- **unverified**: anything else, which the refresh coordinator's clock decides as before.

GraphQL's ``updatedAt`` and ``headRefOid`` equalled REST's ``updated_at`` and ``head.sha``
character for character on five open cli/cli pull requests (2026-11-11), which is what the
comparison relies on.

Whatever the verdict, ``status_missing`` says no kept status of the record's head counts a
list of its checks (:func:`listing_missing`), so a visible page reads its own
(:meth:`.served_pull.ServedPull.is_stale`): none is kept, or the one kept is the Pulls tab's
scan's, of a new head or of checks that moved since the page last listed them.
``unlisted_at`` is then that status's ``observed_at``, when it has one, and a status newer
than the page's last read is a change the page reads at once. ``checks_pending`` says the
status's checks or mergeability are still settling, which the probes watch
(:func:`checks_settling`, :func:`mergeability_pending`) and the page may say. None of them
changes the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

from metabrowser.builtin_plugins.github.pull_record import PULL_RECORD_PROJECTION
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_list import PullListRow
    from metabrowser.builtin_plugins.github.pull_record import PullRecord
    from metabrowser.builtin_plugins.github.pull_status import PullStatus

type Verdict = Literal["current", "changed", "checks", "unverified"]
# ``probe`` is never a verdict of this module's: the pull route reports it when a probe
# found the record unchanged more recently than either (:func:`.pull_route.probed_at`).
type VerifiedBy = Literal["catalog", "fetch", "probe"]

# How long past the window a running scan keeps the last one vouching. A delta scan with
# nothing new to page is one account check and one GraphQL page, 0.46-0.58 s and 0.48 s
# with gh 2.98.0 (2026-11-11), and it can wait for a network slot behind a record refresh
# that holds one, 4.7 to 7.0 s (``MAX_PULL_JOBS``'s note): 15 s is twice the slowest. An
# older catalog is unverified whatever is running, so a reopened page is judged by the
# clock and refreshes a changed record at once, as it did before the catalog vouched.
SCAN_GRACE_S: Final = 15.0
# How long after a pull request's last update an open pull request whose status has no
# checks counts as settling, since CI may not have registered yet: a status observed that
# soon after the update. On three cli/cli heads the first check run started 1 to 2 s after
# its check suite was created (2026-11-11); five minutes leaves room for a queued workflow,
# and a visible open pull request's status is read again once a window in any case
# (``checks``).
NO_CHECKS_GRACE_S: Final = 300.0


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecordFreshness:
    """What the catalog says of one record, and whether its status describes it.

    ``changed_row`` is, for a changed record, the identity of the row that reported the
    change, its ``updated_at`` and head: a refresh attempted for that row has seen it, and
    the next is due at once only when another row reports another change.
    ``status_missing`` says no kept status of the record's head counts a list of its checks,
    and ``unlisted_at`` is the ``observed_at`` of the one kept that counts none, if any
    (:func:`listing_missing`).
    """

    verdict: Verdict
    verified_at: str
    verified_by: VerifiedBy
    head_moved: bool
    checks_pending: bool
    changed_row: str | None = None
    status_missing: bool = False
    unlisted_at: str | None = None


def described(record: PullRecord, status: PullStatus | None) -> PullStatus | None:
    """*status* when it describes *record*'s head, and ``None`` when it describes another."""

    return status if status is not None and status.head == record.pull.head.sha else None


def listing_missing(record: PullRecord, status: PullStatus | None) -> tuple[bool, str | None]:
    """Whether the page lacks a list of its head's checks, and since which status, if one.

    The page's read lists its head's checks with the status; the Pulls tab's scan reads the
    status alone. A scan's status of the record's head that finds the checks as the page's
    read left them keeps that read's list (:func:`~.pull_status.kept_observation`); one of a
    new head, or of checks that moved, counts none, and the page then reads its own while
    the readiness is the scan's. ``(True, None)`` with no status of the record's head;
    ``(True, observed_at)`` with one that counts no list.
    """

    kept = described(record, status)
    if kept is None:
        return True, None
    if kept.checks.listed_at is None:
        return True, kept.observed_at
    return False, None


def mergeability_pending(record: PullRecord, status: PullStatus | None) -> bool:
    """Whether GitHub has not yet said whether an open pull request can merge.

    That is a kept status of the record's head whose ``conflicts`` (GitHub's
    ``mergeable``) or ``merge_state`` (its ``mergeStateStatus``) is ``unknown``. GitHub
    computes both in the background: the read that asks first is answered ``UNKNOWN``,
    and a later one the answer. Nothing else about the pull request moves when it does,
    its ``updated_at`` included. With no status of that head there is nothing pending to
    watch; a status read comes first.
    """

    kept = described(record, status)
    return (
        record.pull.state == "open"
        and kept is not None
        and (kept.conflicts == "unknown" or kept.merge_state == "unknown")
    )


def checks_settling(record: PullRecord, status: PullStatus | None) -> bool:
    """Whether an open pull request's checks are still settling, by its kept status.

    They are while GitHub's rollup for the record's head is ``pending`` or ``expected``,
    or any check is in the bucket ``gh pr checks`` calls pending, as a run in progress
    beside one that failed is. A status observed within :data:`NO_CHECKS_GRACE_S` of the
    pull request's last update with no checks counts too: its CI may not have registered
    yet. With no status of that head there is nothing settling to watch; a status read
    comes first.
    """

    kept = described(record, status)
    if record.pull.state != "open" or kept is None:
        return False
    checks = kept.checks
    if checks.state in ("pending", "expected") or checks.counts["pending"]:
        return True
    since_update = _parse(kept.observed_at) - _parse(record.pull.updated_at)
    return not checks.total and since_update <= timedelta(seconds=NO_CHECKS_GRACE_S)


def checks_pending(record: PullRecord, status: PullStatus | None) -> bool:
    """Whether an open pull request's checks or mergeability are still settling.

    Either :func:`mergeability_pending` or :func:`checks_settling`, which a probe asks
    of different pages.
    """

    return mergeability_pending(record, status) or checks_settling(record, status)


def status_stale(
    record: PullRecord, status: PullStatus | None, *, now: datetime, window_s: float
) -> bool:
    """Whether *record* has no status of its head observed within *window_s* of *now*."""

    kept = described(record, status)
    return kept is None or now - _parse(kept.observed_at) > timedelta(seconds=window_s)


def record_freshness(
    record: PullRecord,
    catalog: CatalogState | None,
    row: PullListRow | None,
    *,
    status: PullStatus | None,
    now: datetime,
    window_s: float = FRESHNESS_WINDOW_S,
    scanning: bool = False,
    checked_at: str | None = None,
) -> RecordFreshness:
    """The verdict on *record* from *catalog* and its *row* of the same number.

    *status* is the kept operational status of that number, which decides ``checks``,
    ``checks_pending``, and ``status_missing``. *scanning* says the catalog's next scan is
    running, which decides in a moment what a scan just past the window would: until it
    ends, and for at most :data:`SCAN_GRACE_S` past the window, the last scan still
    vouches. *checked_at* is when a list probe last found the catalog unchanged, if one
    did after the scan: the catalog is then as old as that probe, not as its scan.
    """

    pending = checks_pending(record, status)
    missing, unlisted = listing_missing(record, status)
    usable = (
        catalog is not None
        and row is not None
        and row.number == record.number
        and catalog.source == record.source
        and catalog.reader == record.reader
    )
    if usable and row is not None and catalog is not None:
        head = record.pull.head.sha
        other_head = row.head_oid is not None and row.head_oid != head
        # A push in the second the record was read leaves the times equal and the head not.
        if row.updated_at > record.pull.updated_at or (
            row.updated_at == record.pull.updated_at and other_head
        ):
            identity = f"{row.updated_at} {row.head_oid or '-'}"
            return RecordFreshness(
                "changed",
                record.fetched_at,
                "fetch",
                other_head,
                pending,
                identity,
                missing,
                unlisted,
            )
        checked = max(catalog.fetched_at, checked_at or catalog.fetched_at)
        age = now - _parse(checked)
        window = timedelta(seconds=window_s)
        recent = age <= window or (scanning and age <= window + timedelta(seconds=SCAN_GRACE_S))
        # A record an earlier projection wrote lacks what this one reads, its labels'
        # colors among them, and the row cannot say so. The catalog still reports a change,
        # but vouches for no such record: the clock decides, and a refresh past the window
        # rewrites it at this projection, once.
        if recent and record.projection_version >= PULL_RECORD_PROJECTION:
            verified = max(record.fetched_at, checked)
            if record.pull.state == "open" and status_stale(
                record, status, now=now, window_s=window_s
            ):
                # The conversation and head are as GitHub has them; conflicts and checks
                # are not in `updated_at`, so an open pull request's status is read again
                # once a window, on its own.
                return RecordFreshness(
                    "checks",
                    verified,
                    "catalog",
                    False,
                    pending,
                    status_missing=missing,
                    unlisted_at=unlisted,
                )
            return RecordFreshness(
                "current",
                verified,
                "catalog",
                False,
                pending,
                status_missing=missing,
                unlisted_at=unlisted,
            )
    return RecordFreshness(
        "unverified",
        record.fetched_at,
        "fetch",
        False,
        pending,
        status_missing=missing,
        unlisted_at=unlisted,
    )


__all__ = [
    "NO_CHECKS_GRACE_S",
    "SCAN_GRACE_S",
    "RecordFreshness",
    "VerifiedBy",
    "Verdict",
    "checks_pending",
    "checks_settling",
    "described",
    "listing_missing",
    "mergeability_pending",
    "record_freshness",
    "status_stale",
]
