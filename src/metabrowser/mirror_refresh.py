"""Keep the served mirror fresh in the background, and switch its pin.

A server serving a repository mirror answers every page from the mirror and never makes
a request wait on the network. Network work runs as background jobs that a request
starts or joins and then returns: the :class:`RefreshCoordinator` on the application
state keeps one job per key (a store key, or for a pull request's record the store key
and its number) so concurrent requests join the running one, and a semaphore bounds how
many run at once. A :class:`CompanionRefresh` is data a provider serves beside the
mirror, refreshed with it under its own key.
A job outlives the request that started it, and its failures become typed outcomes
rather than exceptions. A graceful shutdown cancels whatever is still running through the
application lifespan, which kills each job's Git; a Ctrl-C exits at once instead, after
:func:`metabrowser.git.process.kill_live_process_groups` has killed them. A server that
is killed outright cannot do either, and its Git keeps the store's fetch lock until it
exits, so nothing else writes or cleans the store under it.

:class:`MirrorSession` ties the served mirror to that coordinator and to the source
session. It answers what ``GET /api/source/status`` reports about freshness from
memory -- the tip of the pinned ref as last observed, the last fetch time and outcome,
whether a refresh is running -- so the status route runs no Git and reads no store. The
observations are taken again when a job finishes and when the pin changes, one at a
time, so a pin switch during a refresh cannot leave the other ref's tip behind. When a
refresh finds another process refreshing the store, a served mirror follows that one
and observes the store again once it ends. Switching the pin resolves a selection in
the mirror, opens the new subject, and replaces the served one under a new generation.

This module holds no cache or Git code of its own. The CLI hands the server a
:class:`ServedMirror` implementation (``cache/served_mirror.py``) through
:func:`serve_mirror`, so a server that serves a folder never imports the cache.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any, ClassVar, Final, Literal, Protocol, TypedDict

from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.paths_safe import register_root_callback
from metabrowser.repository_context import RepositoryContext
from metabrowser.source import SourceSession, get_source_session, replace_owned_subject

log = logging.getLogger(__name__)

# How old the last fetch may be before a served mirror counts as stale: the server
# starts one refresh when it opens a stale mirror, and the browser asks for one when
# a stale page becomes visible. A refresh with nothing new is one ls-remote and one
# fetch that transfers no objects: 135-170 ms over file:// for a three-commit origin
# and for this repository (210 refs), measured on macOS with Git 2.50.1 on 2026-09-23.
# HTTPS adds its round trips and is measured with the transport in step 5 of the
# thin-mirror plan. A minute keeps a reader who moves between pages of one session
# from paying that on every open, while one who comes back later still sees a push
# from minutes ago without asking.
FRESHNESS_WINDOW_S: Final = 60.0
# Background network jobs running at once in one server, across every key. Two lets a
# pull request's refresh proceed beside its repository's without letting a burst of
# requests open unbounded connections to one host.
MAX_CONCURRENT_REFRESHES: Final = 2
# How often a served mirror checks whether another process's refresh has ended, and for
# how long at most: that process's own fetch deadline. A check tries a lock file, so it
# is cheap; a second keeps the page's label a second behind the other process at worst.
ELSEWHERE_POLL_S: Final = 1.0
ELSEWHERE_WAIT_S: Final = GIT_ACQUISITION_TIMEOUT_S

type StartedOrJoined = Literal["started", "joined"]


class SelectionError(Exception):
    """A pin selection could not be served. ``str()`` names no path."""

    code: ClassVar[str] = "invalid_selection"
    http_status: ClassVar[int] = 400


class InvalidSelectionError(SelectionError):
    """The selection is not a ref name or commit ID Metabrowser will look up."""


class SelectionNotFoundError(SelectionError):
    """No branch, tag, or commit in the mirror matches the selection."""

    code = "selection_not_found"
    http_status = 404


class SelectionNotACommitError(SelectionError):
    """The selection names a tag or object in the mirror that is not a commit, such as a tag of a tree.

    No fetch can change what an existing name points at, so this is answered at once.
    """

    code = "not_a_commit"
    http_status = 409


class AmbiguousSelectionError(SelectionError):
    """An abbreviated commit ID matches more than one commit in the mirror."""

    code = "ambiguous_selection"
    http_status = 409


class SelectionFetchFailedError(SelectionError):
    """The fetch a missing selection waited for did not run to the end.

    ``outcome`` is that refresh's typed outcome. Asking again starts another fetch.
    """

    code = "selection_fetch_failed"
    http_status = 502

    def __init__(self, outcome: str) -> None:
        super().__init__(
            f"the mirror could not fetch from its origin ({outcome}); ask again to try again"
        )
        self.outcome = outcome


class SelectionPendingError(SelectionError):
    """The mirror does not have the selection yet; one background fetch will say.

    ``refresh`` is ``"started"`` or ``"joined"``. Asking again after that fetch ends
    answers the switch, or :class:`SelectionNotFoundError`.
    """

    code = "selection_pending"
    http_status = 202

    def __init__(self, refresh: StartedOrJoined) -> None:
        super().__init__("the mirror is fetching from its origin; ask again when it finishes")
        self.refresh: StartedOrJoined = refresh


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """How one refresh ended: a typed outcome code and when."""

    outcome: str
    at: str


@dataclass(frozen=True, slots=True)
class RecordedFreshness:
    """What the mirror's own record says about its last fetch and operation."""

    last_fetch_at: str | None
    last_operation: str | None
    last_outcome: str | None
    last_outcome_at: str | None


class ServedMirror(Protocol):
    """The repository mirror a server serves, as this module needs it."""

    @property
    def key(self) -> str:
        """The single-flight key of this mirror's refresh: its store key."""
        ...

    async def open_selection(self, *, ref: str | None, oid: str | None) -> GitRevisionSubject:
        """Resolve a selection in the mirror and open it, or raise :class:`SelectionError`."""
        ...

    async def refresh(self) -> RefreshResult:
        """Fetch from the origin. Returns a typed outcome for every failure it can name."""
        ...

    async def recorded_freshness(self) -> RecordedFreshness:
        """Read the mirror's record of its last fetch, off the event loop."""
        ...

    async def ref_tip(self, ref: str) -> str | None:
        """The commit *ref* names in the mirror now, or ``None`` when it is gone."""
        ...

    async def refresh_running_elsewhere(self) -> bool:
        """Whether a refresh of this mirror is running now, in any process."""
        ...

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        """What lets rendered links into this mirror's hosted repository open locally.

        Supplied by a provider for a repository it hosts; ``None`` otherwise.
        """
        ...


class CompanionRefresh(Protocol):
    """Data served beside the mirror that a provider keeps fresh: a pull request's record.

    It is refreshed with the mirror, under its own key in the same coordinator, and
    counts toward the mirror's staleness, so the rules that keep a served page fresh
    keep it fresh too. :meth:`refresh` names every failure as an outcome it keeps.
    """

    @property
    def key(self) -> str:
        """The single-flight key of its refresh, distinct from the mirror's."""
        ...

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        """Whether it is older than *window_s* at *now*, from memory alone."""
        ...

    async def refresh(self) -> None:
        """Fetch it again; failures become outcomes rather than exceptions."""
        ...


class LastOutcome(TypedDict):
    operation: str
    outcome: str
    at: str


type SelectionState = Literal["pending", "found", "not_found", "fetch_failed", "superseded"]


@dataclass(frozen=True, slots=True)
class OpenedSelection:
    """A URL selection opened in the mirror, and the ``/view/`` address it opens at."""

    subject: GitRevisionSubject
    view_href: str


class FreshnessFields(TypedDict):
    """The freshness half of ``/api/source/status``.

    ``refreshable`` says whether the refresh and pin routes act on this server's
    subject. ``latest`` is the commit the pinned ref names in the mirror as last
    observed: equal to the pin when nothing moved, different when a refresh moved the
    ref, and ``None`` otherwise. ``ref_on_origin`` tells those apart: ``False`` when the
    origin no longer had the ref at the last fetch, ``None`` when there is no ref or it
    has not been observed. ``pull_request`` is the number a served pull-request URL
    named, kept until its data is served. ``selection_state`` follows a URL selection
    the mirror did not have when serving began: ``pending`` until a fetch for it ends,
    then ``found`` (and served) or ``not_found``, or ``fetch_failed`` when that fetch
    did not run, which the next refresh retries; ``superseded`` once a pin switch
    serves something else. ``None`` when there was none. ``selection_href`` is where a
    ``found`` selection opens, with its line anchor, so a page opened while it was
    pending can go there.
    """

    refreshable: bool
    latest: str | None
    ref_on_origin: bool | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    stale: bool
    pull_request: int | None
    selection_state: SelectionState | None
    selection_href: str | None


UNSERVED_FRESHNESS: Final[FreshnessFields] = {
    "refreshable": False,
    "latest": None,
    "ref_on_origin": None,
    "last_fetch_at": None,
    "last_outcome": None,
    "refreshing": False,
    "stale": False,
    "pull_request": None,
    "selection_state": None,
    "selection_href": None,
}

# Selections a pin request found missing, remembered until the fetch they started
# ends, so the next request for one answers found or not found rather than pending
# again. Bounded because the selections are request text.
MAX_REMEMBERED_MISSES: Final = 64

type SelectionOpener = Callable[[], Awaitable[OpenedSelection | None]]


# Outcomes after which the store holds what the origin had: the fetch ran.
_FETCHED_OUTCOMES: Final = frozenset({"succeeded", "default_branch_unknown"})


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _utc_timestamp() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return None


def followed_outcome(recorded: RecordedFreshness, *, since: str, ended: bool) -> str:
    """The outcome of another process's refresh that this one waited for.

    *since* is when this process found the store busy. Only a record written at or after
    it can be that refresh's: a refresh that was killed or cancelled writes none, and the
    record then still says what an earlier operation did. Otherwise, or when the wait
    ran out before the other refresh ended, the answer is ``failed``, which says nothing
    about the origin: a selection waiting on it stays waiting for the next refresh.
    """

    at = recorded.last_outcome_at
    if not ended or recorded.last_outcome is None or at is None or at < since:
        return "failed"
    return recorded.last_outcome


class RefreshCoordinator:
    """Background jobs keyed by what they refresh, run at most *limit* at a time.

    A job belongs to the coordinator, not to the request that started it: the request
    returns as soon as the job is scheduled. A second start for a key whose job is
    still running joins it. A job's own failure is logged here and never reaches a
    request; callers that need an outcome record it inside the job.
    """

    def __init__(self, *, limit: int = MAX_CONCURRENT_REFRESHES) -> None:
        self._semaphore = asyncio.Semaphore(limit)
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._closed = False

    def running(self, key: str) -> bool:
        job = self._jobs.get(key)
        return job is not None and not job.done()

    def start(
        self, key: str, work: Callable[[], Awaitable[None]], *, network: bool = True
    ) -> StartedOrJoined:
        """Start *work* for *key*, or join the job already running for it.

        A *network* job waits for one of the limited slots; a job that only watches
        local state, such as following another process's refresh, does not take one.
        """

        if self.running(key):
            return "joined"
        if self._closed:
            raise RuntimeError("the refresh coordinator is closed")
        job = asyncio.create_task(
            self._run(work, network=network), name=f"metabrowser-refresh:{key[:24]}"
        )
        self._jobs[key] = job

        def forget(done: asyncio.Task[None]) -> None:
            if self._jobs.get(key) is done:
                del self._jobs[key]

        job.add_done_callback(forget)
        return "started"

    async def _run(self, work: Callable[[], Awaitable[None]], *, network: bool) -> None:
        async with self._semaphore if network else contextlib.nullcontext():
            try:
                await work()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("a background refresh failed")

    async def drain(self, *, timeout_s: float) -> None:
        """Wait up to *timeout_s* for the jobs running now, for a one-shot command."""

        jobs = [job for job in self._jobs.values() if not job.done()]
        if jobs:
            await asyncio.wait(jobs, timeout=timeout_s)

    async def aclose(self) -> None:
        """Cancel every running job and wait for each to finish unwinding."""

        self._closed = True
        jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        self._jobs.clear()


class MirrorSession:
    """The served mirror, its refresh jobs, and what status reports about them."""

    def __init__(
        self,
        mirror: ServedMirror,
        coordinator: RefreshCoordinator,
        *,
        window_s: float = FRESHNESS_WINDOW_S,
        follow_elsewhere: bool = False,
        pull_request: int | None = None,
        pending_selection: SelectionOpener | None = None,
        fetch_on_miss: bool = False,
        companion: CompanionRefresh | None = None,
    ) -> None:
        self.mirror = mirror
        self.companion = companion
        self._fetch_on_miss = fetch_on_miss
        self._coordinator = coordinator
        self._window_s = window_s
        self._follow_elsewhere = follow_elsewhere
        self._pull_request = pull_request
        self._pending_selection = pending_selection
        self._selection_state: SelectionState | None = (
            "pending" if pending_selection is not None else None
        )
        self._selection_href: str | None = None
        # Fetches that ran to the end, and the outcome of the last refresh that ended.
        self._fetches_ran = 0
        self._last_fetch_outcome = "succeeded"
        # Refresh jobs that have ended, and for each missing selection the count when it
        # was found missing: a later count means a fetch ran since.
        self._refreshes_ended = 0
        # For each missing selection, both counts when it was found missing: a later
        # ended count means a refresh ended since, a later ran count that one fetched.
        self._misses: dict[tuple[str | None, str | None], tuple[int, int]] = {}
        self._recorded = RecordedFreshness(None, None, None, None)
        self._last_result: RefreshResult | None = None
        # The record as last observed when that result was set, to break a tie.
        self._recorded_with_result: RecordedFreshness | None = None
        self._last_success_at: str | None = None
        self._tip: tuple[str, str | None] | None = None
        self._pin_lock = asyncio.Lock()
        # The mirror's refresh and the pull request's each fetch into the store under its
        # fetch lock; within this server they take turns here first, so neither finds
        # the other holding it and reports a refresh running elsewhere.
        self._fetch_turn = asyncio.Lock()

    # ── Observation ─────────────────────────────────────────────

    async def observe(self) -> None:
        """Read the mirror's record and the pinned ref's tip again."""

        self._recorded = await self.mirror.recorded_freshness()
        await self._observe_tip()

    async def _observe_tip(self) -> None:
        # One observation or switch at a time: a refresh that ends while a switch is
        # resolving observes the new pin's ref after it, never the old one over it.
        async with self._pin_lock:
            subject = _served_revision()
            if subject is None or subject.ref is None:
                self._tip = None
                return
            self._tip = (subject.ref, await self.mirror.ref_tip(subject.ref))

    def last_fetch_at(self) -> str | None:
        recorded = self._recorded.last_fetch_at
        if self._last_success_at is None:
            return recorded
        if recorded is None:
            return self._last_success_at
        return max(recorded, self._last_success_at)

    def is_stale(self, now: datetime | None = None) -> bool:
        """Whether the mirror, or the data served beside it, is older than the window."""

        moment_now = now or _now_utc()
        return self._companion_stale(moment_now) or self._mirror_stale(moment_now)

    def _companion_stale(self, now: datetime) -> bool:
        return self.companion is not None and self.companion.is_stale(now, window_s=self._window_s)

    def _mirror_stale(self, now: datetime) -> bool:
        fetched = self.last_fetch_at()
        moment = _parse_timestamp(fetched) if fetched is not None else None
        if moment is None:
            return True
        return (now - moment).total_seconds() > self._window_s

    def freshness_fields(self, subject: GitRevisionSubject) -> FreshnessFields:
        """The freshness half of the status envelope, from memory alone."""

        latest: str | None = None
        on_origin: bool | None = None
        if self._tip is not None and subject.ref is not None and self._tip[0] == subject.ref:
            latest = self._tip[1]
            on_origin = latest is not None
        return {
            "refreshable": True,
            "latest": latest,
            "ref_on_origin": on_origin,
            "last_fetch_at": self.last_fetch_at(),
            "last_outcome": self._last_outcome(),
            "refreshing": self.refreshing() or self.companion_refreshing(),
            "stale": self.is_stale(),
            "pull_request": self._pull_request,
            "selection_state": self._selection_state,
            "selection_href": self._selection_href if self._selection_state == "found" else None,
        }

    def refreshing(self) -> bool:
        """Whether this server is refreshing, or following another process's refresh."""

        return self._coordinator.running(self.mirror.key) or self._coordinator.running(
            self._elsewhere_key
        )

    @property
    def _elsewhere_key(self) -> str:
        return f"{self.mirror.key}:elsewhere"

    def _last_outcome(self) -> LastOutcome | None:
        """The newer of this process's last refresh and the store's recorded operation.

        Another process's refresh writes the record after this one reported that it was
        refreshing elsewhere, and a record this process wrote is no newer than its own
        result, so the later timestamp wins. Timestamps have one-second resolution, so a
        tie goes to the record only when it changed after the result was set: a record
        from before it, such as the acquisition a moment earlier, does not hide it.
        """

        recorded = self._recorded
        from_record: LastOutcome | None = None
        if (
            recorded.last_operation is not None
            and recorded.last_outcome is not None
            and recorded.last_outcome_at is not None
        ):
            from_record = {
                "operation": recorded.last_operation,
                "outcome": recorded.last_outcome,
                "at": recorded.last_outcome_at,
            }
        result = self._last_result
        if result is None:
            return from_record
        if from_record is not None and (
            from_record["at"] > result.at
            or (from_record["at"] == result.at and recorded != self._recorded_with_result)
        ):
            return from_record
        return {"operation": "refresh", "outcome": result.outcome, "at": result.at}

    def _set_result(self, result: RefreshResult) -> None:
        self._last_result = result
        self._recorded_with_result = self._recorded

    # ── Refresh ─────────────────────────────────────────────────

    def request_refresh(self, *, for_selection: bool = False) -> StartedOrJoined:
        """Start a background refresh of the mirror, or join the one running.

        A URL selection still waiting, as after a fetch that failed, waits for this one.
        The data served beside the mirror is refreshed as its own job when it is stale,
        and when only it is stale, only it is refreshed. *for_selection* is the fetch a
        pin the mirror lacks waits for: the mirror's alone.
        """

        now = _now_utc()
        companion_stale = not for_selection and self._companion_stale(now)
        if companion_stale and self._pending_selection is None and not self._mirror_stale(now):
            return self.request_companion_refresh() or "joined"
        started = self._coordinator.start(self.mirror.key, self._refresh_job)
        if self._pending_selection is not None:
            self._selection_state = "pending"
        if companion_stale:
            self.request_companion_refresh()
        return started

    def request_companion_refresh(self) -> StartedOrJoined | None:
        """Start or join the refresh of the data served beside the mirror, if there is any."""

        companion = self.companion
        if companion is None:
            return None
        return self._coordinator.start(companion.key, self._companion_job)

    def companion_refreshing(self) -> bool:
        return self.companion is not None and self._coordinator.running(self.companion.key)

    async def _companion_job(self) -> None:
        companion = self.companion
        if companion is None:
            return
        try:
            async with self._fetch_turn:
                await companion.refresh()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("refreshing the data served beside the mirror failed")
        try:
            # Its fetch can move a ref the pin was resolved from, such as a pull
            # request's head, which status then reports as newer.
            await self.observe()
        except Exception:
            log.warning("could not observe the mirror after a refresh", exc_info=True)

    async def _refresh_job(self) -> None:
        try:
            async with self._fetch_turn:
                result = await self.mirror.refresh()
        except asyncio.CancelledError:
            self._set_result(RefreshResult("cancelled", _utc_timestamp()))
            raise
        except Exception:
            log.exception("refreshing the served mirror failed")
            result = RefreshResult("failed", _utc_timestamp())
        self._set_result(result)
        if result.outcome in _FETCHED_OUTCOMES:
            self._last_success_at = result.at
        # Another process's refresh is the fetch a waiting selection needs; follow it.
        following = result.outcome == "refreshing_elsewhere" and self._follow_elsewhere
        if not following:
            await self._after_fetch(result.outcome)
        try:
            await self.observe()
        except Exception:
            # The fetch already ended; only the report of it is behind.
            log.warning("could not observe the mirror after a refresh", exc_info=True)
        if following:
            self._coordinator.start(
                self._elsewhere_key, partial(self._follow, result), network=False
            )

    async def _after_fetch(self, outcome: str) -> None:
        """Serve a waiting URL selection if the fetch brought it, and count the fetch.

        A fetch that did not run (*outcome* is not a fetched one) says nothing about the
        selection, so it stays waiting as ``fetch_failed`` for the next refresh.
        """

        ran = outcome in _FETCHED_OUTCOMES
        try:
            if ran:
                await self._open_pending_selection()
            elif self._pending_selection is not None:
                self._selection_state = "fetch_failed"
        except Exception:
            self._selection_state = "not_found"
            log.warning("could not open the requested selection after a refresh", exc_info=True)
        finally:
            self._fetches_ran += int(ran)
            self._last_fetch_outcome = outcome
            self._refreshes_ended += 1

    async def _follow(self, busy: RefreshResult) -> None:
        """Wait for another process's refresh to end, then observe the store again.

        Without this, a server that found the store busy would report the old tip and
        fetch time until its own next refresh. Once the other refresh has ended, *busy*
        is no longer true, so it stops being this process's last outcome; the record
        then reports what the other refresh wrote, or what was there before when it
        wrote nothing.
        """

        waited = 0.0
        ended = False
        while waited < ELSEWHERE_WAIT_S:
            await asyncio.sleep(ELSEWHERE_POLL_S)
            waited += ELSEWHERE_POLL_S
            if not await self.mirror.refresh_running_elsewhere():
                ended = True
                break
        try:
            await self.observe()
        except Exception:
            log.warning("could not observe the mirror after another refresh", exc_info=True)
        await self._after_fetch(followed_outcome(self._recorded, since=busy.at, ended=ended))
        if ended and self._last_result is busy:
            self._last_result = None

    async def _open_pending_selection(self) -> None:
        """After the fetch a URL selection waited for: serve it, or say it is not there.

        The opener is taken under the pin lock, so a pin switch that ran while the fetch
        did, and cleared it, is never undone here.
        """

        async with self._pin_lock:
            opener, self._pending_selection = self._pending_selection, None
            if opener is None:
                return
            opened = await opener()
            if opened is None:
                self._selection_state = "not_found"
                return
            subject = opened.subject
            await replace_owned_subject(subject)
            self._tip = (subject.ref, subject.commit_oid) if subject.ref is not None else None
            self._selection_state = "found"
            self._selection_href = opened.view_href

    def start_pending_selection(self) -> None:
        """Fetch once for a URL selection the mirror did not have when serving began."""

        if self._pending_selection is not None:
            self.request_refresh()

    # ── Pin switching ───────────────────────────────────────────

    async def switch_pin(self, *, ref: str | None, oid: str | None) -> tuple[bool, SourceSession]:
        """Serve the commit a selection names; ``False`` when it is already served.

        Raises :class:`SelectionError` for a selection the mirror cannot serve. In a
        server that fetches on demand, one the mirror does not have starts one
        background fetch and raises :class:`SelectionPendingError`; asked again after
        that fetch ends, it is served or :class:`SelectionNotFoundError`. A one-shot
        command reads the mirror as it is and answers not found at once. Switches are
        serialized, so two concurrent requests end with one of them served.
        """

        async with self._pin_lock:
            try:
                subject = await self.mirror.open_selection(ref=ref, oid=oid)
            except SelectionNotFoundError as exc:
                if not self._fetch_on_miss:
                    raise
                raise self._missing((ref, oid), exc) from None
            self._misses.pop((ref, oid), None)
            if self._selection_state is not None:
                # The reader chose a pin, even the one served: a URL selection still
                # waiting must not replace it when its fetch ends, and a found one no
                # longer describes what the reader asked for.
                self._pending_selection = None
                self._selection_state = "superseded"
            current = _served_revision()
            if (
                current is not None
                and current.commit_oid == subject.commit_oid
                and current.ref == subject.ref
            ):
                await subject.aclose()
                return False, get_source_session()
            session = await replace_owned_subject(subject)
            if subject.ref is not None:
                # The ref was just resolved in the mirror, so the pin is its tip.
                self._tip = (subject.ref, subject.commit_oid)
            else:
                self._tip = None
            return True, session

    def _missing(
        self, key: tuple[str | None, str | None], not_found: SelectionNotFoundError
    ) -> SelectionError:
        """Pending while the fetch for *key* is still to run or running, then not found."""

        seen = self._misses.get(key)
        if seen is not None and seen[0] < self._refreshes_ended and not self.refreshing():
            del self._misses[key]
            # Not found only if a fetch ran to the end since the miss, not merely ended.
            if self._fetches_ran == seen[1]:
                return SelectionFetchFailedError(self._last_fetch_outcome)
            return not_found
        if seen is None:
            if len(self._misses) >= MAX_REMEMBERED_MISSES:
                self._misses.pop(next(iter(self._misses)))
            self._misses[key] = (self._refreshes_ended, self._fetches_ran)
        return SelectionPendingError(self.request_refresh(for_selection=True))


def _served_revision() -> GitRevisionSubject | None:
    subject = get_source_session().subject
    return subject if isinstance(subject, GitRevisionSubject) else None


# ── Configuration and lifespan ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class _ServedMirrorConfig:
    mirror: ServedMirror
    serving: bool
    pull_request: int | None
    pending_selection: SelectionOpener | None
    companion: CompanionRefresh | None


_served_mirror: _ServedMirrorConfig | None = None


def serve_mirror(
    mirror: ServedMirror | None,
    *,
    serving: bool = False,
    pull_request: int | None = None,
    pending_selection: SelectionOpener | None = None,
    companion: CompanionRefresh | None = None,
) -> None:
    """Tell the next application lifespan which mirror it serves, or that it serves none.

    *serving* is serve mode: the lifespan starts one background refresh when it opens a
    mirror whose last fetch is older than :data:`FRESHNESS_WINDOW_S`, a refresh that
    finds another process refreshing follows it until it ends, and a pin request for a
    ref or commit the mirror lacks fetches once. One-shot ``--show`` and ``--api`` pass
    none of it, so they never start work the command did not ask for, and a one-shot
    refresh ends when its own attempt does. *pull_request* is reported by status.
    *pending_selection* opens a URL selection the mirror did not have yet: in serve mode
    the lifespan starts one refresh for it, a one-shot command waits for the refresh it
    asks for, and the pin switches to it if that fetch brings it.
    *companion* is data a provider serves beside the mirror, such as a pull request's
    record: it is refreshed with the mirror and counts toward its staleness.
    """

    global _served_mirror
    _served_mirror = (
        None
        if mirror is None
        else _ServedMirrorConfig(mirror, serving, pull_request, pending_selection, companion)
    )


def _forget_served_mirror() -> None:
    # Choosing a filesystem root is choosing to serve it.
    serve_mirror(None)


register_root_callback(_forget_served_mirror)


def mirror_session(app: Any) -> MirrorSession | None:
    """The served mirror session on *app*, when the served subject has one."""

    session = getattr(app.state, "source_mirror", None)
    return session if isinstance(session, MirrorSession) else None


def refresh_coordinator(app: Any) -> RefreshCoordinator | None:
    coordinator = getattr(app.state, "refresh_jobs", None)
    return coordinator if isinstance(coordinator, RefreshCoordinator) else None


@asynccontextmanager
async def lifespan_refresh(app: Any) -> AsyncGenerator[None]:
    """Own the refresh coordinator and, when a mirror is served, its session.

    Entered after the served subject is attached. A failure to observe the mirror's
    freshness is logged and leaves it unknown; it never fails startup. At exit every
    background job is cancelled and awaited.
    """

    coordinator = RefreshCoordinator()
    app.state.refresh_jobs = coordinator
    app.state.source_mirror = None
    config = _served_mirror
    try:
        if config is not None and _served_revision() is not None:
            session = MirrorSession(
                config.mirror,
                coordinator,
                follow_elsewhere=config.serving,
                pull_request=config.pull_request,
                pending_selection=config.pending_selection,
                fetch_on_miss=config.serving,
                companion=config.companion,
            )
            try:
                await session.observe()
            except Exception:
                log.warning("could not read the served mirror's freshness", exc_info=True)
            app.state.source_mirror = session
            # A one-shot command fetches for a waiting selection only when it asks for a
            # refresh; a server fetches for it at once.
            if config.pending_selection is not None and config.serving:
                session.start_pending_selection()
            elif config.serving and session.is_stale():
                session.request_refresh()
        yield
    finally:
        app.state.source_mirror = None
        await coordinator.aclose()


async def drain_refreshes(app: Any, *, timeout_s: float) -> None:
    """Let a one-shot command finish the refresh its own request started."""

    coordinator = refresh_coordinator(app)
    if coordinator is not None:
        await coordinator.drain(timeout_s=timeout_s)


__all__ = [
    "FRESHNESS_WINDOW_S",
    "MAX_CONCURRENT_REFRESHES",
    "UNSERVED_FRESHNESS",
    "AmbiguousSelectionError",
    "CompanionRefresh",
    "FreshnessFields",
    "InvalidSelectionError",
    "LastOutcome",
    "MirrorSession",
    "OpenedSelection",
    "RecordedFreshness",
    "RefreshCoordinator",
    "RefreshResult",
    "SelectionError",
    "SelectionFetchFailedError",
    "SelectionNotACommitError",
    "SelectionNotFoundError",
    "SelectionPendingError",
    "SelectionState",
    "ServedMirror",
    "drain_refreshes",
    "followed_outcome",
    "lifespan_refresh",
    "mirror_session",
    "refresh_coordinator",
    "serve_mirror",
]
