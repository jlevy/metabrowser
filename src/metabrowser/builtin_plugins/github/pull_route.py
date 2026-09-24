"""The envelope the pull routes answer, built from the cache and memory alone.

It never runs gh or Git and never waits on the network, so a page opens as fast offline
as online. The served pull request is the :class:`ServedPull` the CLI handed the server
with the mirror, reached through the application's mirror session, so it is the same in
a one-shot command and a server. It reports one of:

- ``absent``: nothing to show, with a ``reason``: the served URL selects no pull
  request (``no_pull_request``), or no usable record is cached (``not_cached``,
  ``schema_mismatch``, ``unreadable``);
- ``pending``: no record yet, and a refresh is running;
- ``current``: a record fetched within the refresh coordinator's freshness window;
- ``stale``: an older record, still shown.

``refreshing`` says whether the pull request's refresh job is running, and
``last_refresh`` how this server's last one ended. ``pin`` is the commit the server
serves; the record's ``pull.head.sha`` and ``comparison_route`` name the head the record
was read at. They differ when the URL selected a commit inside the pull request, and
when a refresh found a newer head than the pin, which status reports as ``latest`` for
the page to offer rather than switching under a reader.
"""

from __future__ import annotations

import hashlib
import json
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
from metabrowser.builtin_plugins.github.served_pull import PullRefreshOutcome, ServedPull
from metabrowser.cache.paths import source_pull_record
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, MirrorSession
from metabrowser.source import RepositorySubject

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
    refreshing: bool
    last_refresh: PullRefreshOutcome | None
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
    return ("current" if age <= timedelta(seconds=FRESHNESS_WINDOW_S) else "stale"), None


def comparison_route(record: PullRecord) -> str | None:
    """The diff plugin's comparison of the record's pinned endpoints, or ``None``."""

    comparison = record.comparison
    if comparison is None:
        return None
    return (
        f"/api/plugin/diff/comparison?left={comparison.base}&right={comparison.head}"
        "&base_policy=merge_base"
    )


def _absent() -> PullEnvelope:
    return PullEnvelope(
        state="absent",
        reason="no_pull_request",
        source=None,
        number=None,
        pin=None,
        fetched_at=None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=False,
        last_refresh=None,
        comparison_route=None,
        record=None,
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


def served_pull_of(mirror: MirrorSession | None) -> ServedPull | None:
    """The pull request the mirror session serves beside the mirror, if any."""

    companion = None if mirror is None else mirror.companion
    return companion if isinstance(companion, ServedPull) else None


@dataclass(frozen=True, slots=True)
class ServedPullView:
    """What the envelope needs from memory, read on the event loop that owns it.

    The refresh job changes these on the loop, so a handler reads them there, before it
    reads the record in a thread, and the answer describes one moment.
    """

    served: ServedPull
    pin: str | None
    refreshing: bool
    last_refresh: PullRefreshOutcome | None


def served_pull_view(
    mirror: MirrorSession | None, subject: RepositorySubject
) -> ServedPullView | None:
    """The served pull request's in-memory state, or ``None`` when none is served."""

    served = served_pull_of(mirror)
    if mirror is None or served is None:
        return None
    return ServedPullView(
        served=served,
        pin=subject.commit_oid if isinstance(subject, GitRevisionSubject) else None,
        refreshing=mirror.companion_refreshing(),
        last_refresh=served.last,
    )


def served_pull_envelope(view: ServedPullView | None) -> PullEnvelope:
    """The envelope for the served pull request. Blocking and bounded; run it off the loop."""

    if view is None:
        return _absent()
    published = view.served.published
    record, dumped = cached_pull_record(published.home, published.slug, view.served.number)
    # Through the module, so records and their age share one clock seam.
    state, absence = pull_state(record, now=pulls.utc_now(), refreshing=view.refreshing)
    return PullEnvelope(
        state=state,
        reason=absence,
        source=published.source.normalized,
        number=view.served.number,
        pin=view.pin,
        fetched_at=record.fetched_at if isinstance(record, PullRecord) else None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=view.refreshing,
        last_refresh=view.last_refresh,
        comparison_route=comparison_route(record) if isinstance(record, PullRecord) else None,
        record=dumped if isinstance(record, PullRecord) else None,
    )


def envelope_etag(envelope: PullEnvelope) -> str:
    """An entity tag for *envelope* that never serializes the record.

    Every field but the record is in it, and a new record always brings a new
    ``fetched_at``, so the tag changes exactly when the answer does.
    """

    fields = {name: value for name, value in envelope.items() if name != "record"}
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return f'"{digest[:32]}"'


__all__ = [
    "PullEnvelope",
    "envelope_etag",
    "PullState",
    "ServedPullView",
    "cached_pull_record",
    "comparison_route",
    "pull_state",
    "served_pull_envelope",
    "served_pull_of",
    "served_pull_view",
]
