"""The envelope ``GET /api/plugin/github/pull`` answers, built from the cache alone.

It never runs gh or Git and never waits on the network, so a page opens as fast offline
as online. It reads the record of the pull request the served URL selected, bounded,
and reports one of:

- ``absent``: nothing to show, with a ``reason``: the served URL selects no pull
  request (``no_pull_request``), or no usable record is cached (``not_cached``,
  ``schema_mismatch``, ``unreadable``);
- ``pending``: no record yet, and a refresh is running;
- ``current``: a record fetched within :data:`PULL_FRESH_S`;
- ``stale``: an older record, still shown.

Only a refresh fetches. Its integration point is the background refresh coordinator,
which runs :func:`~metabrowser.builtin_plugins.github.pulls.refresh_pull_request`
keyed by the store and the pull-request number, answers ``pending`` through
``refreshing`` below, and adds the ``POST`` route that starts or joins it. Until then
the CLI fetches: see :mod:`metabrowser.builtin_plugins.github.pulls`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    RecordAbsence,
    read_pull_record,
)
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.source import SourceSession

# How long a record reads as current. The plan's freshness default is about a minute;
# the refresh coordinator owns the tuned window and replaces this when it lands.
PULL_FRESH_S: Final[float] = 60.0

type PullState = Literal["absent", "pending", "current", "stale"]
type PullAbsence = Literal["no_pull_request"] | RecordAbsence


class PullEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull`` returns."""

    state: PullState
    reason: PullAbsence | None
    source: str | None
    number: int | None
    pin: str | None
    fetched_at: str | None
    fresh_for_s: float
    comparison_route: str | None
    record: dict[str, Any] | None


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def pull_state(
    record: PullRecord | RecordAbsence, *, now: datetime, refreshing: bool = False
) -> tuple[PullState, RecordAbsence | None]:
    """The state a cached record (or its absence) is in at *now*."""

    if not isinstance(record, PullRecord):
        return ("pending", None) if refreshing else ("absent", record)
    age = now - _parse_stamp(record.fetched_at)
    return ("current" if age <= timedelta(seconds=PULL_FRESH_S) else "stale"), None


def comparison_route(record: PullRecord) -> str | None:
    """The diff plugin's comparison of the record's pinned endpoints, or ``None``."""

    comparison = record.comparison
    if comparison is None:
        return None
    return (
        f"/api/plugin/diff/comparison?left={comparison.base}&right={comparison.head}"
        "&base_policy=merge_base"
    )


def _envelope(
    state: PullState,
    reason: PullAbsence | None,
    *,
    source: str | None = None,
    number: int | None = None,
    pin: str | None = None,
    record: PullRecord | None = None,
) -> PullEnvelope:
    return PullEnvelope(
        state=state,
        reason=reason,
        source=source,
        number=number,
        pin=pin,
        fetched_at=None if record is None else record.fetched_at,
        fresh_for_s=PULL_FRESH_S,
        comparison_route=None if record is None else comparison_route(record),
        record=None if record is None else record.model_dump(mode="json"),
    )


def served_pull_envelope(session: SourceSession) -> PullEnvelope:
    """The envelope for *session*'s pull request. Blocking and bounded; run it off the loop."""

    published = session.published
    selection = None if published is None else published.source.selection
    number = None if selection is None else selection.pull_request
    if published is None or number is None:
        return _envelope("absent", "no_pull_request")
    subject = session.subject
    pin = subject.commit_oid if isinstance(subject, GitRevisionSubject) else None
    record = read_pull_record(published.home, published.slug, number)
    # Through the module, so records and their age share one clock seam.
    state, absence = pull_state(record, now=pulls.utc_now())
    return _envelope(
        state,
        absence,
        source=published.source.normalized,
        number=number,
        pin=pin,
        record=record if isinstance(record, PullRecord) else None,
    )


__all__ = [
    "PULL_FRESH_S",
    "PullEnvelope",
    "PullState",
    "comparison_route",
    "pull_state",
    "served_pull_envelope",
]
