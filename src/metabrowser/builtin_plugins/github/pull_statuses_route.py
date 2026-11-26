"""Each named pull request's operational status and its verdict, for the rows the Pulls tab draws.

``GET /api/plugin/github/pull-statuses?numbers=<n>,<n>,...`` answers, for each pull request
it names, in its order, the status kept for it (:class:`~.pull_status.PullStatus`) and the
verdict on it (:func:`~.pull_readiness.readiness`), from the cache alone: it never runs gh
or Git and never waits on the network. The statuses are the Pulls tab's scan's
(:mod:`.pull_status_scan`), which ``POST pulls-refresh`` starts when it is due, or the pull
request page's own read, whichever observed last.

The verdict judges the lifecycle the catalog's row names, open, draft, closed, or merged,
and the row's head: a status is ``status`` only when it describes that head, and its
``readiness`` is ``None`` for a closed or merged pull request, whose lifecycle is its
answer. Anything else is ``absent``, with a ``reason``:

- ``not_cached``: the catalog has no row of that number, so no lifecycle to judge;
- ``no_status``: no status is kept for it yet;
- ``not_scanned``: the status kept is a scan's from before the last whole walk, which did
  not read it: a pull request that has fallen past the newest the scan reads
  (:data:`~.pull_status_scan.MAX_SCAN_PAGES`), or one GitHub no longer lists open, whose
  last verdict nothing keeps current. A status the page's own read kept is answered as it
  is;
- ``other_head``: the status kept describes another head than the row's, a push the scan
  or the page has not read since, or a row that names no head.

``scanning`` says a scan runs now, so a status may arrive, and ``scan`` is how the last
one ended (:class:`ScanWire`), a failure included: what it kept before is still answered.

Bounded: at most :data:`~.pull_catalog.MAX_STATUS_NUMBERS` numbers, read by primary key in
one catalog transaction, and one small stamp file.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github.pull_catalog import MAX_STATUS_NUMBERS, catalog_statuses
from metabrowser.builtin_plugins.github.pull_files_summary import named_numbers
from metabrowser.builtin_plugins.github.pull_readiness import DisplayState, lifecycle, readiness
from metabrowser.builtin_plugins.github.pull_status_scan import (
    ScanStamp,
    ScanTrigger,
    read_scan_stamp,
)
from metabrowser.http_caching import build_scoped_etag

if TYPE_CHECKING:
    from collections.abc import Mapping

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow
    from metabrowser.builtin_plugins.github.pull_status import PullStatus

PULL_STATUSES_ROUTE: Final = "/api/plugin/github/pull-statuses"

type StatusesState = Literal["status", "absent"]
type StatusAbsence = Literal["not_cached", "no_status", "not_scanned", "other_head"]


class PullStatusWire(TypedDict):
    """One pull request's status and verdict, or why there is none."""

    number: int
    state: StatusesState
    reason: StatusAbsence | None
    # The catalog's row's lifecycle and head, which the verdict judges; ``None`` with no row.
    lifecycle: DisplayState | None
    head: str | None
    status: dict[str, Any] | None
    readiness: dict[str, Any] | None


class ScanWire(TypedDict):
    """How the last scan of every open pull request's status ended (:class:`~.pull_status_scan.ScanStamp`).

    ``settle_at`` is when the pages that held answers GitHub had not finished computing are
    read once more, when they are.
    """

    outcome: str
    message: str | None
    reset_at: str | None
    at: str
    reader: str | None
    trigger: ScanTrigger
    pages: int
    rows: int
    cost: int
    unknown: int
    settle_at: str | None


class PullStatusesEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull-statuses`` answers."""

    source: str | None
    scanning: bool
    scan: ScanWire | None
    rows: list[PullStatusWire]


def status_numbers(params: Mapping[str, str]) -> tuple[int, ...]:
    """The pull requests a request names, in its order; ``SummaryRequestError`` otherwise."""

    return named_numbers(params, request="a status request", limit=MAX_STATUS_NUMBERS)


def _row_lifecycle(row: PullListRow) -> DisplayState:
    return lifecycle(closed=row.state == "closed", draft=row.draft, merged=row.merged)


def unscanned(status: PullStatus, stamp: ScanStamp | None) -> bool:
    """Whether *status* is a scan's that the last whole walk neither read nor came after.

    That walk read the newest open pull requests and kept which (``walked_numbers``); a
    status a scan kept before it started, of any other, is one nothing has read since. A
    page's read, and a scan's status from after the walk started, a settle re-read's or
    the next walk's, are current as kept.
    """

    return (
        status.observed_by == "scan"
        and stamp is not None
        and stamp.walked_at is not None
        and status.observed_at < stamp.walked_at
        and status.number not in stamp.walked_numbers
    )


def _wire(
    number: int,
    row: PullListRow | None,
    status: PullStatus | None,
    source: str,
    stamp: ScanStamp | None,
) -> PullStatusWire:
    def absent(reason: StatusAbsence) -> PullStatusWire:
        return PullStatusWire(
            number=number,
            state="absent",
            reason=reason,
            lifecycle=None if row is None else _row_lifecycle(row),
            head=None if row is None else row.head_oid,
            status=None,
            readiness=None,
        )

    if row is None:
        return absent("not_cached")
    if status is None:
        return absent("no_status")
    if unscanned(status, stamp):
        return absent("not_scanned")
    if row.head_oid is None or status.head != row.head_oid:
        return absent("other_head")
    shown = _row_lifecycle(row)
    verdict = readiness(
        state=shown, head=row.head_oid, status=status, html_url=f"{source}/pull/{number}"
    )
    return PullStatusWire(
        number=number,
        state="status",
        reason=None,
        lifecycle=shown,
        head=row.head_oid,
        status=status.model_dump(mode="json"),
        readiness=None if verdict is None else verdict.model_dump(mode="json"),
    )


def _scan(stamp: ScanStamp | None) -> ScanWire | None:
    if stamp is None:
        return None
    return ScanWire(
        outcome=stamp.outcome,
        message=stamp.message,
        reset_at=stamp.reset_at,
        at=stamp.at,
        reader=stamp.reader,
        trigger=stamp.trigger,
        pages=stamp.pages,
        rows=stamp.rows,
        cost=stamp.cost,
        unknown=stamp.unknown,
        settle_at=stamp.settle_at,
    )


def pull_statuses(
    repository: ListedRepository | None, numbers: tuple[int, ...], *, scanning: bool
) -> PullStatusesEnvelope:
    """Each of *numbers*' status and verdict, in their order. Blocking and bounded; run it
    off the loop. *scanning* is read on the loop, from the coordinator."""

    if repository is None:
        return PullStatusesEnvelope(source=None, scanning=False, scan=None, rows=[])
    found = catalog_statuses(repository.home, repository.slug, numbers)
    usable = found.state is not None and found.state.source == repository.source
    rows = found.rows if usable else {}
    stamp = read_scan_stamp(repository.home, repository.slug)
    return PullStatusesEnvelope(
        source=repository.source,
        scanning=scanning,
        scan=_scan(stamp),
        rows=[
            _wire(number, rows.get(number), found.statuses.get(number), repository.source, stamp)
            for number in numbers
        ],
    )


def envelope_etag(envelope: PullStatusesEnvelope) -> str:
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pull-statuses-{digest[:32]}")


__all__ = [
    "PULL_STATUSES_ROUTE",
    "PullStatusWire",
    "PullStatusesEnvelope",
    "ScanWire",
    "StatusAbsence",
    "envelope_etag",
    "pull_statuses",
    "status_numbers",
    "unscanned",
]
