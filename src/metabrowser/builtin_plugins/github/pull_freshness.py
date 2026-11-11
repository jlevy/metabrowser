"""Whether a cached pull-request record still describes the pull request on GitHub.

The repository catalog's delta scan reads pull requests by ``UPDATED_AT`` until its
watermark, so its row of a number says when GitHub last changed that pull request and
which commit its head is. A record is checked against that row, read with the checkpoint
in one transaction, and only when the catalog's ``source`` and ``reader`` are the record's:

- **changed**: the row's ``updated_at`` is newer than the record's ``pull.updated_at``,
  whatever the scan's age, or equal with another head. ``head_moved`` says the row names
  another head commit.
- **current**: the row is not changed, the scan that published it ran within the window,
  or the next one is running and the last ran within :data:`SCAN_GRACE_S` past it, and the
  record is closed or was read within the window. ``verified_at`` is then the newer of that
  scan's ``fetched_at`` and the record's, and ``verified_by`` is ``catalog``.
- **checks**: the same, for an open pull request read longer ago than the window. The
  catalog vouches for its conversation and head, and the record is stale for what
  ``updated_at`` does not track: check runs, commit statuses, and ``mergeable``, which a
  refresh then reads on their own (``checks_only`` in :mod:`.pulls`).
- **unverified**: anything else, which the refresh coordinator's clock decides as before.

GraphQL's ``updatedAt`` and ``headRefOid`` equalled REST's ``updated_at`` and ``head.sha``
character for character on five open cli/cli pull requests (2026-11-11), which is what the
comparison relies on. ``checks_pending`` reports checks still settling, for the page to
say; it changes no verdict, since an open record past the window is read again anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_list import PullListRow
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

type Verdict = Literal["current", "changed", "checks", "unverified"]
type VerifiedBy = Literal["catalog", "fetch"]

# How long past the window a running scan keeps the last one vouching. A delta scan with
# nothing new to page is one account check and one GraphQL page, 0.46-0.58 s and 0.48 s
# with gh 2.98.0 (2026-11-11), and it can wait for a network slot behind a record refresh
# that holds one, 4.7 to 7.0 s (``MAX_PULL_JOBS``'s note): 15 s is twice the slowest. An
# older catalog is unverified whatever is running, so a reopened page is judged by the
# clock and refreshes a changed record at once, as it did before the catalog vouched.
SCAN_GRACE_S: Final = 15.0
# How long after a pull request's last update an open record with no check run and no
# commit status counts as pending, since CI may not have registered yet. On three cli/cli
# heads the first check run started 1 to 2 s after its check suite was created (2026-11-11);
# five minutes leaves room for a queued workflow, and a visible open pull request's checks
# are read again once a window in any case (``checks``).
NO_CHECKS_GRACE_S: Final = 300.0


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecordFreshness:
    """What the catalog says of one record.

    ``changed_row`` is, for a changed record, the identity of the row that reported the
    change, its ``updated_at`` and head: a refresh attempted for that row has seen it, and
    the next is due at once only when another row reports another change.
    """

    verdict: Verdict
    verified_at: str
    verified_by: VerifiedBy
    head_moved: bool
    checks_pending: bool
    changed_row: str | None = None


def checks_pending(record: PullRecord) -> bool:
    """Whether an open pull request's checks, statuses, or mergeability are still settling.

    A record read within :data:`NO_CHECKS_GRACE_S` of the pull request's last update with
    no check run and no status context counts too: its CI may not have registered yet.
    """

    if record.pull.state != "open":
        return False
    if record.pull.mergeable == "unknown":
        return True
    if any(run.status != "completed" for run in record.check_runs):
        return True
    status = record.status
    if status is not None and bool(status.statuses) and status.state == "pending":
        return True
    unregistered = not record.check_runs and (status is None or not status.statuses)
    since_update = _parse(record.fetched_at) - _parse(record.pull.updated_at)
    return unregistered and since_update <= timedelta(seconds=NO_CHECKS_GRACE_S)


def record_freshness(
    record: PullRecord,
    catalog: CatalogState | None,
    row: PullListRow | None,
    *,
    now: datetime,
    window_s: float = FRESHNESS_WINDOW_S,
    scanning: bool = False,
) -> RecordFreshness:
    """The verdict on *record* from *catalog* and its *row* of the same number.

    *scanning* says the catalog's next scan is running, which decides in a moment what a
    scan just past the window would: until it ends, and for at most :data:`SCAN_GRACE_S`
    past the window, the last scan still vouches.
    """

    pending = checks_pending(record)
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
                "changed", record.fetched_at, "fetch", other_head, pending, identity
            )
        age = now - _parse(catalog.fetched_at)
        window = timedelta(seconds=window_s)
        recent = age <= window or (scanning and age <= window + timedelta(seconds=SCAN_GRACE_S))
        if recent:
            verified = max(record.fetched_at, catalog.fetched_at)
            if record.pull.state == "open" and now - _parse(record.fetched_at) > window:
                # The conversation and head are as GitHub has them; checks, statuses, and
                # mergeability are not in `updated_at`, so an open pull request's are read
                # again once a window, on their own.
                return RecordFreshness("checks", verified, "catalog", False, pending)
            return RecordFreshness("current", verified, "catalog", False, pending)
    return RecordFreshness("unverified", record.fetched_at, "fetch", False, pending)


__all__ = [
    "NO_CHECKS_GRACE_S",
    "SCAN_GRACE_S",
    "RecordFreshness",
    "VerifiedBy",
    "Verdict",
    "checks_pending",
    "record_freshness",
]
