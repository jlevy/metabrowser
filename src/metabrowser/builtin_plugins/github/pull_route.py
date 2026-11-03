"""The envelope the pull routes answer, built from the cache and memory alone.

It never runs gh or Git and never waits on the network, so a page opens as fast offline
as online. Canonical requests name their pull request by number, and a server answers
for any number of its repository. Published one-shot calls that omit the number address
the already attended pull request, without creating one. It reports one of:

- ``absent``: nothing to show, with a ``reason``: this server serves no GitHub repository
  (``not_github``), or no usable record is cached (``not_cached``, ``schema_mismatch``,
  ``unreadable``);
- ``pending``: no record yet, and a refresh is running;
- ``current``: a record fetched within the refresh coordinator's freshness window;
- ``stale``: an older record, still shown.

``refreshing`` says whether the pull request's refresh job is running, and
``last_refresh`` how its last one ended. ``pin`` is the commit the server serves and
``pin_ref`` the ref it was resolved from; the record's ``pull.head.sha`` and
``comparison_route`` name the head the record was read at. They differ when the pin is
another pull request or a branch, when the URL selected a commit inside the pull request,
and when a refresh found a newer head than the pin, which status reports as ``latest``
for the page to offer rather than switching under a reader.

A read never starts a fetch. Only ``POST pull-refresh`` does, and :func:`start_refresh`
holds what it starts to the rule: a request that is not a reader's own action refreshes
only a pull request with a record, and only when that record is stale and not tried within
the window. So nothing a link can do adds to the cache.

Which pull requests a server has is :func:`pull_host`'s to say, and nothing else here
knows whether it is a mirror.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
from collections.abc import Callable, Mapping
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
from metabrowser.builtin_plugins.github.served_pull import (
    PullRefreshOutcome,
    ServedPull,
    ServedPulls,
)
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_record
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    PullJobStart,
    mirror_session,
)
from metabrowser.source import RepositorySubject
from metabrowser.view_routes import parse_pull_number

PULL_ROUTE: Final = "/api/plugin/github/pull"
_REFRESH_FIELDS: Final = frozenset({"number", "retry"})
NUMBER_REQUIRED: Final = '"number" is a pull-request number'

type PullState = Literal["absent", "pending", "current", "stale"]
type PullAbsence = Literal["not_github", "no_pull_request"] | RecordAbsence
type PullRefreshStart = PullJobStart | Literal["not_due", "not_cached"]


class PullRequestError(Exception):
    """A request the pull routes refuse. ``str()`` says why, and names only the request."""


class PullEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull`` returns."""

    state: PullState
    reason: PullAbsence | None
    source: str | None
    number: int | None
    pin: str | None
    pin_ref: str | None
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


def comparison_route(record: PullRecord, *, store: str) -> str | None:
    """The diff plugin's comparison of the record's pinned endpoints, or ``None``."""

    comparison = record.comparison
    if comparison is None:
        return None
    return (
        f"/api/plugin/github/pull-comparison?number={record.number}"
        f"&left={comparison.base}&right={comparison.head}&base_policy=merge_base"
        f"&build={BUILD_TAG}&store={store}"
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


@dataclass(frozen=True, slots=True)
class PullHost:
    """What the pull routes need of a server that has pull requests, and no more.

    ``pulls`` is the repository's set, ``running`` says whether a number's refresh is
    running, and ``start`` starts or joins it.
    """

    pulls: ServedPulls
    running: Callable[[int], bool]
    start: Callable[[int], PullJobStart]


def pull_host(app: Any) -> PullHost | None:
    """This server's pull requests, or ``None``: on a mirror, those the provider keeps."""

    session = mirror_session(app)
    served = None if session is None else session.pull_requests
    if session is None or not isinstance(served, ServedPulls):
        return None
    return PullHost(served, session.pull_refreshing, session.request_pull_refresh)


def attended_number(app: Any) -> int | None:
    """The existing attended GitHub companion's number, with no read or creation."""

    session = mirror_session(app)
    companion = None if session is None else session.companion
    return companion.number if isinstance(companion, ServedPull) else None


@dataclass(frozen=True, slots=True)
class PullView:
    """What the envelope needs from memory, read on the event loop that owns it.

    The refresh job changes these on the loop, so a handler reads them there, before it
    reads the record in a thread, and the answer describes one moment. ``kept`` is the
    number's state when the set holds it; otherwise its last refresh is read from disk.
    """

    number: int
    host: PullHost | None
    pin: str | None
    pin_ref: str | None
    refreshing: bool
    kept: ServedPull | None


def pull_view(host: PullHost | None, subject: RepositorySubject, number: int) -> PullView:
    """Pull request *number*'s in-memory state. Reads nothing, so a read adds nothing."""

    revision = subject if isinstance(subject, GitRevisionSubject) else None
    return PullView(
        number=number,
        host=host,
        pin=None if revision is None else revision.commit_oid,
        pin_ref=None if revision is None else revision.ref,
        refreshing=host is not None and host.running(number),
        kept=None if host is None else host.pulls.held(number),
    )


def pull_envelope(view: PullView | None) -> PullEnvelope:
    """The envelope for one pull request. Blocking and bounded; run it off the loop."""

    host = None if view is None else view.host
    if host is None:
        return PullEnvelope(
            state="absent",
            reason="no_pull_request" if view is None else "not_github",
            source=None,
            number=None if view is None else view.number,
            pin=None if view is None else view.pin,
            pin_ref=None if view is None else view.pin_ref,
            fetched_at=None,
            fresh_for_s=FRESHNESS_WINDOW_S,
            refreshing=False,
            last_refresh=None,
            comparison_route=None,
            record=None,
        )
    assert view is not None
    served = host.pulls
    record, dumped = cached_pull_record(served.home, served.slug, view.number)
    # Through the module, so records and their age share one clock seam.
    state, absence = pull_state(record, now=pulls.utc_now(), refreshing=view.refreshing)
    return PullEnvelope(
        state=state,
        reason=absence,
        source=served.source,
        number=view.number,
        pin=view.pin,
        pin_ref=view.pin_ref,
        fetched_at=record.fetched_at if isinstance(record, PullRecord) else None,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=view.refreshing,
        last_refresh=view.kept.last if view.kept is not None else served.last_refresh(view.number),
        comparison_route=(
            comparison_route(record, store=store_tag(served.published.git_dir))
            if isinstance(record, PullRecord)
            else None
        ),
        record=dumped if isinstance(record, PullRecord) else None,
    )


def record_stamp(view: PullView | None) -> tuple[int, int, int] | None:
    """The record file's inode, modification time in nanoseconds, and size."""

    if view is None or view.host is None:
        return None
    return _file_stamp(view.host.pulls.home, view.host.pulls.slug, view.number)


def envelope_etag(envelope: PullEnvelope, stamp: tuple[int, int, int] | None) -> str:
    """An entity tag for *envelope* that never serializes the record.

    Every field but the record is in it, and so is *stamp*, the record file's
    :func:`record_stamp`: a record is replaced atomically, which changes its inode, so
    two records written within the same second of ``fetched_at`` still differ. Read the
    stamp before the envelope; a record replaced in between then gets a tag the next
    request no longer matches, and is sent again rather than taken as unchanged.
    """

    fields: dict[str, Any] = {name: value for name, value in envelope.items() if name != "record"}
    fields["record_stamp"] = list(stamp) if stamp is not None else None
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pull-{digest[:32]}")


def requested_number(params: Mapping[str, str]) -> int:
    """The number a ``GET`` names, or :class:`PullRequestError`. It is required."""

    number = parse_pull_number(params.get("number", ""))
    if number is None:
        raise PullRequestError(NUMBER_REQUIRED)
    return number


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    """What a ``POST`` asks for. *retry* is a reader's own action."""

    number: int
    retry: bool


def refresh_request(
    body: Mapping[str, object], *, attended: int | None = None
) -> RefreshRequest | None:
    """The explicit selection or existing attended alias; ``None`` if neither exists.

    Only omission uses *attended*. The published empty body requests a manual refresh;
    an explicit number defaults to automatic, and an explicit retry always wins.
    """

    if set(body) - _REFRESH_FIELDS:
        raise PullRequestError('a refresh request names only "number" and "retry"')
    number = body.get("number", attended)
    if number is None and "number" not in body:
        if not isinstance(body.get("retry", True), bool):
            raise PullRequestError('"retry" is true or false')
        return None
    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or not 1 <= number <= MAX_PULL_REQUEST_NUMBER
    ):
        raise PullRequestError(NUMBER_REQUIRED)
    retry = body.get("retry", "number" not in body)
    if not isinstance(retry, bool):
        raise PullRequestError('"retry" is true or false')
    return RefreshRequest(number, retry)


async def start_refresh(host: PullHost, ask: RefreshRequest) -> PullRefreshStart:
    """Start the refresh *ask* names, join the one running, or say why it starts nothing.

    A reader's own action always may start one. An automatic request may only for a
    pull request with a record (``not_cached`` otherwise), and only when that record is
    stale and no attempt is due to wait (``not_due`` otherwise).
    """

    if host.running(ask.number):
        return "joined"
    if not ask.retry:
        served = await host.pulls.companion(ask.number)
        if served.fetched_at is None:
            return "not_cached"
        if not served.is_stale(pulls.utc_now(), window_s=FRESHNESS_WINDOW_S):
            return "not_due"
    return host.start(ask.number)


def status_route(number: int) -> str:
    """Where a one-shot ``--api`` reads how a refresh ended."""

    return f"{PULL_ROUTE}?number={number}"


__all__ = [
    "NUMBER_REQUIRED",
    "PULL_ROUTE",
    "PullEnvelope",
    "PullHost",
    "PullRefreshStart",
    "PullRequestError",
    "PullState",
    "PullView",
    "RefreshRequest",
    "attended_number",
    "cached_pull_record",
    "comparison_route",
    "envelope_etag",
    "pull_envelope",
    "pull_host",
    "pull_state",
    "pull_view",
    "record_stamp",
    "refresh_request",
    "requested_number",
    "start_refresh",
    "status_route",
]
