"""Keep the served mirror fresh in the background, and switch its pin.

A server serving a repository mirror answers every page from the mirror and never makes
a request wait on the network. Network work runs as background jobs that a request
starts or joins and then returns: the :class:`RefreshCoordinator` on the application
state keeps one job per key (a store key today; a store and pull request later) so
concurrent requests join the running one, and a semaphore bounds how many run at once.
A job outlives the request that started it, its failures become typed outcomes rather
than exceptions, and the application lifespan cancels whatever is still running at
shutdown.

:class:`MirrorSession` ties the served mirror to that coordinator and to the source
session. It answers what ``GET /api/source/status`` reports about freshness from
memory -- the tip of the pinned ref as last observed, the last fetch time and outcome,
whether a refresh is running -- so the status route runs no Git and reads no store. The
observations are taken again when a job finishes and when the pin changes. Switching
the pin resolves a selection in the mirror, opens the new subject, and replaces the
served one under a new generation.

This module holds no cache or Git code of its own. The CLI hands the server a
:class:`ServedMirror` implementation (``cache/served_mirror.py``) through
:func:`serve_mirror`, so a server that serves a folder never imports the cache.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar, Final, Literal, Protocol, TypedDict

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


class AmbiguousSelectionError(SelectionError):
    """An abbreviated commit ID matches more than one commit in the mirror."""

    code = "ambiguous_selection"
    http_status = 409


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

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        """What lets rendered links into this mirror's hosted repository open locally.

        Supplied by a provider for a repository it hosts; ``None`` otherwise.
        """
        ...


class LastOutcome(TypedDict):
    operation: str
    outcome: str
    at: str


type SelectionState = Literal["pending", "found", "not_found"]


class FreshnessFields(TypedDict):
    """The freshness half of ``/api/source/status``.

    ``refreshable`` says whether the refresh and pin routes act on this server's
    subject. ``latest`` is the commit the pinned ref names in the mirror as last
    observed: equal to the pin when nothing moved, different when a refresh brought
    newer commits, and ``None`` without a ref or after the origin deleted it.
    ``pull_request`` is the number a served pull-request URL named, kept until its data
    is served. ``selection_state`` follows a URL selection the mirror did not have
    when serving began: ``pending`` while one background fetch runs, then ``found``
    (and served) or ``not_found``; ``None`` when there was none.
    """

    refreshable: bool
    latest: str | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    stale: bool
    pull_request: int | None
    selection_state: SelectionState | None


UNSERVED_FRESHNESS: Final[FreshnessFields] = {
    "refreshable": False,
    "latest": None,
    "last_fetch_at": None,
    "last_outcome": None,
    "refreshing": False,
    "stale": False,
    "pull_request": None,
    "selection_state": None,
}

# Selections a pin request found missing, remembered until the fetch they started
# ends, so the next request for one answers found or not found rather than pending
# again. Bounded because the selections are request text.
MAX_REMEMBERED_MISSES: Final = 64

type SelectionOpener = Callable[[], Awaitable[GitRevisionSubject | None]]


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _utc_timestamp() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return None


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

    def start(self, key: str, work: Callable[[], Awaitable[None]]) -> StartedOrJoined:
        """Start *work* for *key*, or join the job already running for it."""

        if self.running(key):
            return "joined"
        if self._closed:
            raise RuntimeError("the refresh coordinator is closed")
        job = asyncio.create_task(self._run(work), name=f"metabrowser-refresh:{key[:16]}")
        self._jobs[key] = job

        def forget(done: asyncio.Task[None]) -> None:
            if self._jobs.get(key) is done:
                del self._jobs[key]

        job.add_done_callback(forget)
        return "started"

    async def _run(self, work: Callable[[], Awaitable[None]]) -> None:
        async with self._semaphore:
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
        pull_request: int | None = None,
        pending_selection: SelectionOpener | None = None,
        fetch_on_miss: bool = False,
    ) -> None:
        self.mirror = mirror
        self._fetch_on_miss = fetch_on_miss
        self._coordinator = coordinator
        self._window_s = window_s
        self._pull_request = pull_request
        self._pending_selection = pending_selection
        self._selection_state: SelectionState | None = (
            "pending" if pending_selection is not None else None
        )
        # Refresh jobs that have ended, and for each missing selection the count when it
        # was found missing: a later count means a fetch ran since.
        self._refreshes_ended = 0
        self._misses: dict[tuple[str | None, str | None], int] = {}
        self._recorded = RecordedFreshness(None, None, None, None)
        self._last_result: RefreshResult | None = None
        self._last_success_at: str | None = None
        self._tip: tuple[str, str | None] | None = None
        self._pin_lock = asyncio.Lock()

    # ── Observation ─────────────────────────────────────────────

    async def observe(self) -> None:
        """Read the mirror's record and the pinned ref's tip again."""

        self._recorded = await self.mirror.recorded_freshness()
        await self._observe_tip()

    async def _observe_tip(self) -> None:
        subject = _served_revision()
        if subject is None or subject.ref is None:
            self._tip = None
            return
        tip = await self.mirror.ref_tip(subject.ref)
        # A pin switch during the lookup recorded its own ref's tip; keep that one.
        if _served_revision() is subject:
            self._tip = (subject.ref, tip)

    def last_fetch_at(self) -> str | None:
        recorded = self._recorded.last_fetch_at
        if self._last_success_at is None:
            return recorded
        if recorded is None:
            return self._last_success_at
        return max(recorded, self._last_success_at)

    def is_stale(self, now: datetime | None = None) -> bool:
        fetched = self.last_fetch_at()
        moment = _parse_timestamp(fetched) if fetched is not None else None
        if moment is None:
            return True
        elapsed = ((now or _now_utc()) - moment).total_seconds()
        return elapsed > self._window_s

    def freshness_fields(self, subject: GitRevisionSubject) -> FreshnessFields:
        """The freshness half of the status envelope, from memory alone."""

        latest: str | None = None
        if self._tip is not None and subject.ref is not None and self._tip[0] == subject.ref:
            latest = self._tip[1]
        return {
            "refreshable": True,
            "latest": latest,
            "last_fetch_at": self.last_fetch_at(),
            "last_outcome": self._last_outcome(),
            "refreshing": self._coordinator.running(self.mirror.key),
            "stale": self.is_stale(),
            "pull_request": self._pull_request,
            "selection_state": self._selection_state,
        }

    def _last_outcome(self) -> LastOutcome | None:
        if self._last_result is not None:
            return {
                "operation": "refresh",
                "outcome": self._last_result.outcome,
                "at": self._last_result.at,
            }
        recorded = self._recorded
        if (
            recorded.last_operation is None
            or recorded.last_outcome is None
            or recorded.last_outcome_at is None
        ):
            return None
        return {
            "operation": recorded.last_operation,
            "outcome": recorded.last_outcome,
            "at": recorded.last_outcome_at,
        }

    # ── Refresh ─────────────────────────────────────────────────

    def request_refresh(self) -> StartedOrJoined:
        """Start a background refresh of the mirror, or join the one running."""

        return self._coordinator.start(self.mirror.key, self._refresh_job)

    async def _refresh_job(self) -> None:
        try:
            result = await self.mirror.refresh()
        except asyncio.CancelledError:
            self._last_result = RefreshResult("cancelled", _utc_timestamp())
            raise
        except Exception:
            log.exception("refreshing the served mirror failed")
            result = RefreshResult("failed", _utc_timestamp())
        self._last_result = result
        if result.outcome == "succeeded":
            self._last_success_at = result.at
        try:
            await self._open_pending_selection()
        except Exception:
            self._selection_state = "not_found"
            log.warning("could not open the requested selection after a refresh", exc_info=True)
        finally:
            self._refreshes_ended += 1
        try:
            await self.observe()
        except Exception:
            # The fetch already ended; only the report of it is behind.
            log.warning("could not observe the mirror after a refresh", exc_info=True)

    async def _open_pending_selection(self) -> None:
        """After the fetch a URL selection waited for: serve it, or say it is not there."""

        opener, self._pending_selection = self._pending_selection, None
        if opener is None:
            return
        async with self._pin_lock:
            subject = await opener()
            if subject is None:
                self._selection_state = "not_found"
                return
            await replace_owned_subject(subject)
            self._tip = (subject.ref, subject.commit_oid) if subject.ref is not None else None
            self._selection_state = "found"

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

        seen_at = self._misses.get(key)
        if (
            seen_at is not None
            and seen_at < self._refreshes_ended
            and not self._coordinator.running(self.mirror.key)
        ):
            del self._misses[key]
            return not_found
        if seen_at is None:
            if len(self._misses) >= MAX_REMEMBERED_MISSES:
                self._misses.pop(next(iter(self._misses)))
            self._misses[key] = self._refreshes_ended
        return SelectionPendingError(self.request_refresh())


def _served_revision() -> GitRevisionSubject | None:
    subject = get_source_session().subject
    return subject if isinstance(subject, GitRevisionSubject) else None


# ── Configuration and lifespan ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class _ServedMirrorConfig:
    mirror: ServedMirror
    refresh_when_stale: bool
    pull_request: int | None
    pending_selection: SelectionOpener | None


_served_mirror: _ServedMirrorConfig | None = None


def serve_mirror(
    mirror: ServedMirror | None,
    *,
    refresh_when_stale: bool = False,
    pull_request: int | None = None,
    pending_selection: SelectionOpener | None = None,
) -> None:
    """Tell the next application lifespan which mirror it serves, or that it serves none.

    *refresh_when_stale* starts one background refresh when the lifespan opens a mirror
    whose last fetch is older than :data:`FRESHNESS_WINDOW_S`. Serve mode passes it;
    one-shot ``--show`` and ``--api`` do not, so they never start network work that
    the command did not ask for; the same flag lets a pin request for a ref or commit
    the mirror lacks fetch once. *pull_request* is reported by status.
    *pending_selection* opens a URL selection the mirror did not have yet: the lifespan
    starts one refresh for it, and the pin switches to it if that fetch brings it.
    """

    global _served_mirror
    _served_mirror = (
        None
        if mirror is None
        else _ServedMirrorConfig(mirror, refresh_when_stale, pull_request, pending_selection)
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
                pull_request=config.pull_request,
                pending_selection=config.pending_selection,
                fetch_on_miss=config.refresh_when_stale,
            )
            try:
                await session.observe()
            except Exception:
                log.warning("could not read the served mirror's freshness", exc_info=True)
            app.state.source_mirror = session
            if config.pending_selection is not None:
                session.start_pending_selection()
            elif config.refresh_when_stale and session.is_stale():
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
    "FreshnessFields",
    "InvalidSelectionError",
    "LastOutcome",
    "MirrorSession",
    "RecordedFreshness",
    "RefreshCoordinator",
    "RefreshResult",
    "SelectionError",
    "SelectionNotFoundError",
    "SelectionPendingError",
    "SelectionState",
    "ServedMirror",
    "drain_refreshes",
    "lifespan_refresh",
    "mirror_session",
    "refresh_coordinator",
    "serve_mirror",
]
