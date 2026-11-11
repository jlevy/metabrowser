"""Whether a cached pull-request record still describes the pull request on GitHub.

The repository catalog's delta scan reads pull requests by ``UPDATED_AT`` until its
watermark, so its row of a number says when GitHub last changed that pull request and
which commit its head is. A record is checked against that row, read with the checkpoint
in one transaction, and only when the catalog's ``source`` and ``reader`` are the record's:

- **changed**: the row's ``updated_at`` is newer than the record's ``pull.updated_at``,
  whatever the scan's age. ``head_moved`` says the row names another head commit.
- **current**: the row is not newer, the scan that published it ran within the window,
  and the record has no pending checks. ``verified_at`` is then the newer of that scan's
  ``fetched_at`` and the record's, and ``verified_by`` is ``catalog``.
- **unverified**: anything else, which the refresh coordinator's clock decides as before.

GraphQL's ``updatedAt`` and ``headRefOid`` equalled REST's ``updated_at`` and ``head.sha``
character for character on five open cli/cli pull requests (2026-11-11), which is what the
comparison relies on.

``updated_at`` does not move for a check run, a commit status, or ``mergeable``. An open
pull request with a check run not completed, a combined status pending with contexts, or
``mergeable`` unknown has pending checks, and the catalog does not vouch for it: it ages
by its own fetch, so a visible page refreshes it once a window until they settle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_list import PullListRow
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

type Verdict = Literal["current", "changed", "unverified"]
type VerifiedBy = Literal["catalog", "fetch"]


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RecordFreshness:
    """What the catalog says of one record.

    ``changed_seen_at`` is, for a changed record, the checkpoint's ``count_at``: when the
    catalog last published, which is no earlier than when it published the newer row. A
    refresh attempted after it has seen the change.
    """

    verdict: Verdict
    verified_at: str
    verified_by: VerifiedBy
    head_moved: bool
    checks_pending: bool
    changed_seen_at: str | None = None


def checks_pending(record: PullRecord) -> bool:
    """Whether an open pull request's checks, statuses, or mergeability are still settling."""

    if record.pull.state != "open":
        return False
    if record.pull.mergeable == "unknown":
        return True
    if any(run.status != "completed" for run in record.check_runs):
        return True
    status = record.status
    return status is not None and bool(status.statuses) and status.state == "pending"


def record_freshness(
    record: PullRecord,
    catalog: CatalogState | None,
    row: PullListRow | None,
    *,
    now: datetime,
    window_s: float = FRESHNESS_WINDOW_S,
) -> RecordFreshness:
    """The verdict on *record* from *catalog* and its *row* of the same number."""

    pending = checks_pending(record)
    usable = (
        catalog is not None
        and row is not None
        and row.number == record.number
        and catalog.source == record.source
        and catalog.reader == record.reader
    )
    if usable and row is not None and catalog is not None:
        if row.updated_at > record.pull.updated_at:
            moved = row.head_oid is not None and row.head_oid != record.pull.head.sha
            return RecordFreshness(
                "changed", record.fetched_at, "fetch", moved, pending, catalog.count_at
            )
        recent = now - _parse(catalog.fetched_at) <= timedelta(seconds=window_s)
        if recent and not pending:
            verified = max(record.fetched_at, catalog.fetched_at)
            return RecordFreshness("current", verified, "catalog", False, False)
    return RecordFreshness("unverified", record.fetched_at, "fetch", False, pending)


__all__ = ["RecordFreshness", "VerifiedBy", "Verdict", "checks_pending", "record_freshness"]
