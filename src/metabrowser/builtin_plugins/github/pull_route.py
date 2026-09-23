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

``pin`` is the commit the server serves; the record's ``pull.head.sha`` and
``comparison_route`` name the head the record was read at. They differ when the URL
selected a commit inside the pull request, and when a refresh found a newer head than
the pin, which a page offers to switch to rather than switching under a reader.

Only a refresh fetches. Its integration point is the background refresh coordinator,
which runs :func:`~metabrowser.builtin_plugins.github.pulls.refresh_pull_request`
keyed by the store and the pull-request number, answers ``pending`` through
``refreshing`` below, and adds the ``POST`` route that starts or joins it. Until then
the CLI fetches: see :mod:`metabrowser.builtin_plugins.github.pulls`.
"""

from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    RecordAbsence,
    read_pull_record,
)
from metabrowser.cache.paths import source_pull_record
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
    dumped: dict[str, Any] | None = None,
) -> PullEnvelope:
    if record is not None and dumped is None:
        dumped = record.model_dump(mode="json")
    return PullEnvelope(
        state=state,
        reason=reason,
        source=source,
        number=number,
        pin=pin,
        fetched_at=None if record is None else record.fetched_at,
        fresh_for_s=PULL_FRESH_S,
        comparison_route=None if record is None else comparison_route(record),
        record=None if record is None else dumped,
    )


@dataclass(frozen=True, slots=True)
class _Parsed:
    stamp: tuple[int, int, int]
    record: PullRecord
    dumped: dict[str, Any]


# Records parsed for this route, keyed by home, slug, and number, each kept with the
# inode, modification time, and size it was read at. A browser polls the route, and a
# record is rewritten only by atomic replacement, which changes the inode, so an
# unchanged file is answered without reading or parsing it again.
_PARSED: dict[tuple[str, str, int], _Parsed] = {}
_PARSED_LOCK: Final = threading.Lock()
_MAX_PARSED: Final = 16


def _file_stamp(home: Path, slug: str, number: int) -> tuple[int, int, int] | None:
    try:
        status = os.lstat(home / source_pull_record(slug, number))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def cached_pull_record(
    home: Path, slug: str, number: int
) -> tuple[PullRecord | RecordAbsence, dict[str, Any] | None]:
    """The record and its JSON form, parsed again only when its file changed."""

    key = (str(home), slug, number)
    stamp = _file_stamp(home, slug, number)
    with _PARSED_LOCK:
        hit = _PARSED.get(key)
    if hit is not None and stamp is not None and hit.stamp == stamp:
        return hit.record, hit.dumped
    record = read_pull_record(home, slug, number)
    if not isinstance(record, PullRecord) or stamp is None:
        return record, None
    dumped = record.model_dump(mode="json")
    with _PARSED_LOCK:
        if key not in _PARSED and len(_PARSED) >= _MAX_PARSED:
            _PARSED.pop(next(iter(_PARSED)))
        _PARSED[key] = _Parsed(stamp, record, dumped)
    return record, dumped


def served_pull_envelope(session: SourceSession) -> PullEnvelope:
    """The envelope for *session*'s pull request. Blocking and bounded; run it off the loop."""

    published = session.published
    selection = None if published is None else published.source.selection
    number = None if selection is None else selection.pull_request
    if published is None or number is None:
        return _envelope("absent", "no_pull_request")
    subject = session.subject
    pin = subject.commit_oid if isinstance(subject, GitRevisionSubject) else None
    record, dumped = cached_pull_record(published.home, published.slug, number)
    # Through the module, so records and their age share one clock seam.
    state, absence = pull_state(record, now=pulls.utc_now())
    return _envelope(
        state,
        absence,
        source=published.source.normalized,
        number=number,
        pin=pin,
        record=record if isinstance(record, PullRecord) else None,
        dumped=dumped,
    )


__all__ = [
    "PULL_FRESH_S",
    "PullEnvelope",
    "PullState",
    "cached_pull_record",
    "comparison_route",
    "pull_state",
    "served_pull_envelope",
]
