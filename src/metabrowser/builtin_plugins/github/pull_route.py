"""The envelope the pull routes answer, built from the cache and memory alone.

It never runs gh or Git and never waits on the network, so a page opens as fast offline
as online. Every request names its pull request by number, and a server answers for any
number of its repository, so it is the same in a one-shot command and a server. It
reports one of:

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
the window. A visible cold page can request the selected fetch with a separate POST.

Which pull requests a server has is :func:`pull_host`'s to say, and nothing else here
knows whether it is a mirror or a checkout. A checkout with no attached store answers a
record with no comparison, ``no_store``, whoever wrote it. A server with a store answers
a record written that way as ``stale``. Only an explicit comparison Fetch may attach a
store to a checkout's pull records.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.checkout import (
    checkout_job_key,
    checkout_pulls,
    served_checkout,
    start_pull_refresh,
)
from metabrowser.builtin_plugins.github.pull_core_cache import read_cached_core
from metabrowser.builtin_plugins.github.pull_cores import CoreAdmission, CoreWindow, preparation_key
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    RecordAbsence,
    read_pull_record,
)
from metabrowser.builtin_plugins.github.served_pull import (
    PullCorePreview,
    PullRefreshOutcome,
    ServedPull,
    ServedPulls,
    written_without_store,
)
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_record
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.git.wire import is_full_revision
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    PullJobStart,
    RefreshCoordinator,
    mirror_session,
    refresh_coordinator,
)
from metabrowser.source import RepositorySubject
from metabrowser.view_routes import parse_pull_number

PULL_ROUTE: Final = "/api/plugin/github/pull"
_REFRESH_FIELDS: Final = frozenset({"number", "retry", "comparison", "recovery", "wait_core"})
NUMBER_REQUIRED: Final = '"number" is a pull-request number'

type PullState = Literal["absent", "pending", "current", "stale"]
type PullAbsence = Literal["not_github"] | RecordAbsence
type PullRefreshStart = PullJobStart | Literal["not_due", "not_cached"]


class PullRequestError(Exception):
    """A request the pull routes refuse. ``str()`` says why, and names only the request."""


class PullEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull`` returns."""

    state: PullState
    reason: PullAbsence | None
    source: str | None
    number: int
    pin: str | None
    pin_ref: str | None
    fetched_at: str | None
    record_revision: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: PullRefreshOutcome | None
    comparison_route: str | None
    record: dict[str, Any] | None
    core_preview: PullCorePreview | None


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def pull_state(
    record: PullRecord | RecordAbsence,
    *,
    now: datetime,
    refreshing: bool = False,
    has_store: bool = True,
) -> tuple[PullState, RecordAbsence | None]:
    """The state a cached record (or its absence) is in at *now*.

    A record written with no store, by a checkout's server, is stale whatever its age on a
    server that *has_store*, which can give it its Files changed.
    """

    if not isinstance(record, PullRecord):
        return ("pending", None) if refreshing else ("absent", record)
    if has_store and written_without_store(record):
        return "stale", None
    age = now - _parse_stamp(record.fetched_at)
    return ("current" if age <= timedelta(seconds=FRESHNESS_WINDOW_S) else "stale"), None


def _without_store(dumped: dict[str, Any]) -> dict[str, Any]:
    """A record as a server with no store has it: no comparison, ``no_store``.

    A checkout's server may read a record a mirror wrote, with a comparison of commits in
    that mirror's store. It has no store of its own, and it never reads the checkout's, so
    it offers no Files changed for it. A new dictionary: *dumped* is the parsed cache's.
    """

    unavailable = {**dumped.get("unavailable", {}), "comparison": "no_store"}
    return {**dumped, "comparison": None, "unavailable": unavailable}


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
    revision: str


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


def _record_revision(dumped: dict[str, Any]) -> str:
    """Reader-owned content identity, unaffected by refresh time and provider ETags."""

    content = {key: value for key, value in dumped.items() if key not in {"fetched_at", "etags"}}
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cached_pull_record(
    home: Path, slug: str, number: int
) -> tuple[PullRecord | RecordAbsence, dict[str, Any] | None, str | None]:
    """One parsed record, its JSON and content revision, reused while the file is unchanged."""

    key = (str(home), slug, number)
    stamp = _file_stamp(home, slug, number)
    with _PARSED_LOCK:
        hit = _PARSED.get(key)
    if hit is not None and stamp is not None and hit.stamp == stamp:
        return hit.record, hit.dumped, hit.revision
    record = read_pull_record(home, slug, number)
    if not isinstance(record, PullRecord):
        return record, None, None
    dumped = record.model_dump(mode="json")
    revision = _record_revision(dumped)
    # JSON numbers above JavaScript's safe integer range still need exact part IDs.
    for kind in ("issue_comments", "reviews"):
        for item in dumped[kind]:
            if abs(item["id"]) > (1 << 53) - 1:
                item["timeline_id"] = str(item["id"])
    if stamp is not None:
        with _PARSED_LOCK:
            if key not in _PARSED and len(_PARSED) >= _MAX_PARSED:
                _PARSED.pop(next(iter(_PARSED)))
            _PARSED[key] = _Parsed(stamp, record, dumped, revision)
    return record, dumped, revision


@dataclass(frozen=True, slots=True)
class PullHost:
    """What the pull routes need of a server that has pull requests, and no more.

    ``pulls`` is the repository's set, ``running`` says whether a number's refresh is
    running, and ``start`` starts or joins it.
    """

    pulls: ServedPulls
    running: Callable[[int], bool]
    start: Callable[[int], PullJobStart]
    start_comparison: Callable[[int], PullJobStart] | None = None
    coordinator: RefreshCoordinator | None = None


def pull_host(app: Any) -> PullHost | None:
    """This server's pull requests, or ``None``.

    On a mirror, those the provider keeps. On a folder, those of a served checkout's
    repository (:mod:`.checkout`), whose jobs run on the server's refresh coordinator.
    """

    session = mirror_session(app)
    if session is None:
        checkout = served_checkout(app)
        coordinator = refresh_coordinator(app)
        if checkout is None or coordinator is None:
            return None
        pulls = checkout_pulls(checkout)
        return PullHost(
            pulls,
            lambda number: coordinator.running(checkout_job_key(checkout, number)),
            partial(start_pull_refresh, coordinator, checkout),
            partial(start_pull_refresh, coordinator, checkout, comparison=True),
            coordinator,
        )
    served = session.pull_requests
    if not isinstance(served, ServedPulls):
        return None
    return PullHost(
        served,
        session.pull_refreshing,
        session.request_pull_refresh,
        coordinator=refresh_coordinator(app),
    )


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
    core_preview: PullCorePreview | None = None
    core_window: CoreWindow | None = None
    core_admission: CoreAdmission | None = None


def pull_view(host: PullHost | None, subject: RepositorySubject, number: int) -> PullView:
    """Pull request *number*'s in-memory state. Reads nothing, so a read adds nothing."""

    revision = subject if isinstance(subject, GitRevisionSubject) else None
    kept = None if host is None else host.pulls.held(number)
    refreshing = host is not None and host.running(number)
    live = kept.core_preview if kept is not None and refreshing else None
    adopted = kept.display_core if kept is not None and refreshing and live is None else None
    window = host.pulls.core_window if host is not None and not refreshing else None
    prepared = window.preview(number) if window is not None else None
    admission = window.admission if prepared is not None and window is not None else None
    if adopted is not None:
        live, admission = adopted
    return PullView(
        number=number,
        host=host,
        pin=None if revision is None else revision.commit_oid,
        pin_ref=None if revision is None else revision.ref,
        refreshing=refreshing,
        kept=kept,
        core_preview=live or prepared,
        core_window=window if prepared is not None else None,
        core_admission=admission,
    )


def pull_envelope(view: PullView) -> PullEnvelope:
    """The envelope for one pull request. Blocking and bounded; run it off the loop."""

    host = view.host
    if host is None:
        return PullEnvelope(
            state="absent",
            reason="not_github",
            source=None,
            number=view.number,
            pin=view.pin,
            pin_ref=view.pin_ref,
            fetched_at=None,
            record_revision=None,
            fresh_for_s=FRESHNESS_WINDOW_S,
            refreshing=False,
            last_refresh=None,
            comparison_route=None,
            record=None,
            core_preview=None,
        )
    served = host.pulls
    record, dumped, revision = cached_pull_record(served.home, served.slug, view.number)
    has_store = served.git_dir is not None
    # Through the module, so records and their age share one clock seam.
    state, absence = pull_state(
        record, now=pulls.utc_now(), refreshing=view.refreshing, has_store=has_store
    )
    if not has_store and isinstance(record, PullRecord) and dumped is not None:
        dumped = _without_store(dumped)
        record = record.model_copy(update={"comparison": None})
    route = (
        comparison_route(record, store=store_tag(served.git_dir))
        if isinstance(record, PullRecord) and served.git_dir is not None
        else None
    )
    preview = view.core_preview
    if view.core_admission is not None and not view.core_admission.catalog_matches(view.number):
        preview = None
    if preview is None and record == "not_cached":
        preview = read_cached_core(
            served.home,
            served.slug,
            view.number,
            reader=served.observed_reader,
            reader_identity=served.core_catalog_identity,
        )
    return PullEnvelope(
        state=state,
        reason=absence,
        source=served.source,
        number=view.number,
        pin=view.pin,
        pin_ref=view.pin_ref,
        fetched_at=record.fetched_at if isinstance(record, PullRecord) else None,
        record_revision=revision,
        fresh_for_s=FRESHNESS_WINDOW_S,
        refreshing=view.refreshing,
        last_refresh=view.kept.last if view.kept is not None else served.last_refresh(view.number),
        comparison_route=route,
        record=dumped if isinstance(record, PullRecord) else None,
        core_preview=preview if record == "not_cached" else None,
    )


def note_full_record(view: PullView) -> None:
    window = view.core_window
    if (
        view.host is not None
        and window is not None
        and view.host.pulls.core_window is window
        and window.previews is not None
    ):
        window.previews.pop(view.number, None)


def core_preview_current(view: PullView, preview: PullCorePreview | None) -> bool:
    """Reject an observation revoked while the envelope was built off the loop."""
    if preview is None:
        return True
    if view.host is None:
        return False
    if preview is not view.core_preview:
        cached = read_cached_core(
            view.host.pulls.home,
            view.host.pulls.slug,
            view.number,
            reader=view.host.pulls.observed_reader,
            reader_identity=view.host.pulls.core_catalog_identity,
        )
        return cached is not None and cached == preview
    if view.core_window is not None:
        return (
            view.host.pulls.core_window is view.core_window
            and not view.host.running(view.number)
            and view.core_window.preview(view.number) is preview
        )
    kept = view.kept
    if kept is None or not view.host.running(view.number):
        return False
    if kept.core_preview is not None:
        return kept.core_preview is preview
    adopted = kept.display_core
    return adopted is not None and adopted[0] is preview and adopted[1] is view.core_admission


def record_stamp(view: PullView) -> tuple[int, int, int] | None:
    """The record file's inode, modification time in nanoseconds, and size."""

    if view.host is None:
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

    fields: dict[str, Any] = {
        name: value for name, value in envelope.items() if name not in {"record", "core_preview"}
    }
    preview = envelope["core_preview"]
    fields["core_preview"] = (
        None if preview is None else (preview["revision"], preview["observed_at"])
    )
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
    comparison: bool = False
    recovery: tuple[str, str] | None = None
    wait_core: bool = False


def refresh_request(body: Mapping[str, object]) -> RefreshRequest:
    """What a ``POST`` body names, or :class:`PullRequestError`."""

    if set(body) - _REFRESH_FIELDS:
        raise PullRequestError(
            'a refresh request names only "number", "retry", "comparison", "recovery", and "wait_core"'
        )
    number = body.get("number")
    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or not 1 <= number <= MAX_PULL_REQUEST_NUMBER
    ):
        raise PullRequestError(NUMBER_REQUIRED)
    retry = body.get("retry", False)
    if not isinstance(retry, bool):
        raise PullRequestError('"retry" is true or false')
    comparison = body.get("comparison", False)
    if not isinstance(comparison, bool) or (comparison and not retry):
        raise PullRequestError('"comparison" is true or false and requires "retry": true')
    recovery = body.get("recovery")
    pair: tuple[str, str] | None = None
    if recovery is not None:
        if (
            comparison
            or not retry
            or not isinstance(recovery, dict)
            or set(recovery) != {"base", "head"}
        ):
            raise PullRequestError(
                '"recovery" names a displayed base and head and requires "retry": true'
            )
        base, head = recovery.get("base"), recovery.get("head")
        if (
            not isinstance(base, str)
            or not isinstance(head, str)
            or not is_full_revision(base)
            or not is_full_revision(head)
        ):
            raise PullRequestError('"recovery" requires two full commit IDs')
        pair = (base, head)
    wait_core = body.get("wait_core", False)
    if not isinstance(wait_core, bool) or (
        wait_core and (not retry or comparison or pair is not None)
    ):
        raise PullRequestError('"wait_core" is true or false and requires only "retry": true')
    return RefreshRequest(number, retry, comparison, pair, wait_core)


async def start_refresh(host: PullHost, ask: RefreshRequest) -> PullRefreshStart:
    if not ask.retry and not ask.comparison:
        return await _start_refresh(host, ask)
    served = host.pulls
    served.foreground_intents += 1
    try:
        window = served.core_window
        prepared = None
        if window is None or window.previews is None:
            served.core_window = None
            coordinator = host.coordinator
            if coordinator is not None:
                job = coordinator.cancel(preparation_key(served.source))
                if job is not None:
                    await asyncio.shield(asyncio.gather(job, return_exceptions=True))
        elif ask.wait_core:
            preview = window.preview(ask.number)
            if preview is not None:
                prepared = (window, preview)
        started = await _start_refresh(host, ask, prepared)
        if started in {"started", "joined"} and window is not None and window.previews is not None:
            window.previews.pop(ask.number, None)
        return started
    finally:
        served.foreground_intents -= 1


async def _start_refresh(
    host: PullHost, ask: RefreshRequest, prepared: tuple[CoreWindow, PullCorePreview] | None = None
) -> PullRefreshStart:
    """Start the refresh *ask* names, join the one running, or say why it starts nothing.

    A reader's own action always may start one. An automatic request may only for a
    pull request with a record (``not_cached`` otherwise), and only when that record is
    stale and no attempt is due to wait (``not_due`` otherwise).
    """

    queued: ServedPull | None = None
    adopt = None
    if ask.retry and not ask.comparison:
        served = await host.pulls.companion(ask.number)
        queued = served
        if ask.recovery is not None and not served.issued_comparison(ask.recovery):
            raise PullRequestError("this pull request did not issue the requested comparison")
        if not served.request_recovery(ask.recovery):
            return "too_many"
        if ask.wait_core:
            cached, _dumped, _revision = await asyncio.to_thread(
                cached_pull_record, host.pulls.home, host.pulls.slug, ask.number
            )
            if isinstance(cached, PullRecord):
                served.saw_record(cached.fetched_at, without_store=written_without_store(cached))
            else:
                served.request_core_preview()
                if (
                    cached == "not_cached"
                    and prepared is not None
                    and prepared[0].publication is served.published
                ):
                    adopt = prepared
    if ask.comparison and host.start_comparison is not None:
        return host.start_comparison(ask.number)
    if host.running(ask.number):
        return "joined"
    if not ask.retry:
        served = await host.pulls.companion(ask.number)
        if served.fetched_at is None:
            return "not_cached"
        if not served.is_stale(pulls.utc_now(), window_s=FRESHNESS_WINDOW_S):
            return "not_due"
    if adopt is not None:
        window, preview = adopt
        # This is the last worker read. Start and adoption below are synchronous.
        catalog_matches = await asyncio.to_thread(window.catalog_matches, ask.number)
        if (
            not catalog_matches
            or host.pulls.published is not window.publication
            or host.pulls.core_window is not window
            or window.preview(ask.number) is not preview
        ):
            adopt = None
    if host.running(ask.number):
        return "joined"
    started = host.start(ask.number)
    if queued is not None:
        if started == "too_many":
            queued.discard_recovery(ask.recovery)
        elif started == "started" and adopt is not None:
            window, preview = adopt
            admission = window.admission
            if admission is not None:
                queued.display_core = (preview, admission)
    return started


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
