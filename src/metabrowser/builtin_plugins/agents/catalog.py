"""The catalog: every session of a home, kept current by a background worker.

A request never reads a transcript. It takes a :class:`Snapshot` of what the catalog
holds now and may start a pass, which runs on a worker thread and has two parts:

1. **The fast pass** is the provider's ``discover``: a ``stat`` walk of Claude Code's
   transcripts with their first and last records, or indexed reads of Codex's thread
   store. It gives every session's size, times, place, title, and children, and it
   replaces the catalog's session list at once.
2. **The summary pass** runs the provider's ``summarize`` on each session whose cache key
   changed, newest first, and stores the result (see :mod:`.store`). A session whose key
   is unchanged keeps its summary, and one whose summary is already cached on disk is
   loaded instead of read. The pass ends when it has read
   :data:`SUMMARY_PASS_BUDGET_BYTES` of transcripts, so one pass is bounded work and the
   next continues where it stopped.

One worker serves one home at a time (single-flight): a request that arrives while a pass
runs joins it, and a request that needs a pass newer than the running one asks for one
more. The worker is a daemon thread tied to the served root: :func:`reset` runs when the
root changes, drops every catalog, and tells each worker to stop at its next session.
Nothing here runs on the event loop.

The cache directory may be unavailable. The catalog then holds summaries in memory only,
reports ``cache: unavailable``, and every route still answers.

A request that cannot wait for a pass (``metab --api``, a test, a golden) asks for
:meth:`HomeCatalog.complete`, which waits, bounded by :data:`SYNC_TIMEOUT_SECONDS`, until
the catalog is fully summarized.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from metabrowser.plugin_api import register_root_callback

from . import claude, codex
from .model import (
    DriftCollector,
    DriftSummary,
    Home,
    LiveSession,
    PidProbe,
    SessionSummary,
    default_pid_probe,
    merge_drift,
)
from .readers import clip
from .store import SummaryStore, session_key

_LOG = logging.getLogger(__name__)

# Measurements. Every limit in this package was set from one run over the maintainer's real
# homes, read-only, on an Apple M1 Pro (10 cores, 32 GB) whose load average was 18 to 115
# throughout, so every time below is pessimistic. Only aggregates are recorded.
#
# Claude Code: 2,404 transcripts, 7.2 GB; median 1.9 MB, 99th percentile 20 MB, largest
# 144 MB; 1.7 million records; the largest session holds 47,749 records.
#   fast pass (`discover`)      4.3 to 6.8 s     peak memory 51 MB
#   summary pass, every session 198.6 s          peak memory 236 MB
#   one summary, largest        4.6 to 11.4 s    20 to 36 MB/s on sessions over 1 MB
#   whole catalog through the routes (`sync=1`, 2,190 sessions): cold 370 s; warm, with
#   2,189 of 2,190 summaries loaded from the cache, 20 s (fast pass plus cache loads)
# Codex: 22,302 threads, rollouts 9.5 GB, largest 514 MB; 16,125 threads have 2.0 million
# history items, the largest thread 27,682; a thread's title can be 647,106 characters.
#   fast pass, newest 5,000     1.8 to 2.3 s     peak memory 66 MB
#   fast pass, all 22,302       23.8 s           peak memory 618 MB before titles were cut
#   summary pass, newest 5,000  487.8 s          peak memory 132 MB; 15 MB/s over 1 MB
#   one summary, largest        32.7 to 56.9 s
# A cache entry (one summary as JSON) is 8.5 KB at most; a session row 1.3 KB at the 99th
# percentile.
#
# The limits follow:
# - `readers.MAX_READ_BYTES`, `codex.DISCOVER_LIMIT`, `codex.MAX_ITEMS`, and
#   `codex.TITLE_READ_CHARS` bound one read.
# - `store.MAX_ENTRY_BYTES` is 7.5 times the largest entry.
# - `routes.PAGE_MAX` keeps a page under a megabyte at the 99th-percentile row, and
#   `routes.RECORDS_SCAN_MAX` is 1.6 times the largest session's records.
# - The fast pass is bounded by `REFRESH_DUTY_FACTOR`, and the summary pass by its byte
#   budget.

# A pass that a request starts waits until the last one's fast pass, times this factor,
# has gone by, so the worker spends at most one tenth of its time on fast passes however
# large the home is (about 24 s for the largest measured home, so one every four minutes
# when the machine is as loaded as it was).
REFRESH_DUTY_FACTOR: Final = 10.0

# The shortest time between two passes that a request starts, however quick a pass was.
REFRESH_MIN_INTERVAL_SECONDS: Final = 5.0

# How long the first request for a home waits for the fast pass before it answers with an
# empty, scanning catalog. A pass over a small home finishes inside it and answers
# complete; the measured homes took seconds, so a view shows progress and polls.
FIRST_PASS_WAIT_SECONDS: Final = 0.25

# How long a synchronous request (`sync=1`) waits for the catalog to be fully summarized,
# across as many passes as that takes, before it answers with what it has and
# `progress.complete` false. The measured Claude Code home took 199 s to summarize in
# full, so this covers it with room; a Codex store of 22,000 threads does not finish
# inside it on a loaded machine, and the caller sees the partial progress.
SYNC_TIMEOUT_SECONDS: Final = 600.0

# How many bytes of transcripts one summary pass reads before it ends. Sessions loaded
# from the cache do not count. A pass that ends here continues at once while a request is
# watching, and otherwise waits for the next request. At the slowest measured rate
# (15 MB/s) this is about two minutes of reading, so the fast pass that begins each pass
# (4 to 24 s) is a small part of it, and the measured homes take a handful of passes.
SUMMARY_PASS_BUDGET_BYTES: Final = 2 * 1024 * 1024 * 1024

# The most characters of a session title the catalog keeps. A title is the first line of
# a name or prompt, redacted; the display is one line.
TITLE_MAX_CHARS: Final = 200

# How long one liveness check is reused. `live` runs a process probe per Claude Code pid
# file (about 16 on the measured machine), so a view polling every second must not repeat
# it.
LIVE_TTL_SECONDS: Final = 2.0

# Replaceable by tests: the clock every pass stamps with, and the pid-liveness probe.
CLOCK: Callable[[], float] = time.time
PROBE: PidProbe = default_pid_probe

CacheState = Literal["unknown", "ok", "unavailable"]
CatalogState = Literal["idle", "scanning", "summarizing", "error"]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One session: its summary so far, the key it was computed under, and its drift.

    ``summarized`` is False until the summary pass has read the session (or loaded it
    from the cache), and ``summary`` is then the fast pass's. ``failed`` marks a read
    that raised, which the next pass tries again.
    """

    summary: SessionSummary
    key: str
    summarized: bool = False
    failed: bool = False
    drift: DriftSummary = field(default_factory=DriftSummary)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What a catalog holds at one moment. ``sessions`` is newest first."""

    home: Home
    entries: tuple[CatalogEntry, ...]
    drift: DriftSummary
    state: CatalogState
    total: int
    summarized: int
    from_cache: int
    read: int
    failed: int
    pending_budget: bool
    fast_at: float | None
    summary_at: float | None
    cache: CacheState
    cache_write_errors: int
    passes: int


class HomeCatalog:
    """The sessions of one home, with the worker that keeps them current."""

    def __init__(self, home: Home) -> None:
        self.home = home
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._fast_ready = threading.Event()
        self._by_id: dict[str, CatalogEntry] = {}
        self._fast_drift = DriftSummary()
        self._thread: threading.Thread | None = None
        self._cancelled = False
        self._again = False
        self._started = 0
        self._completed = 0
        self._last_start: float | None = None
        self._now_override: float | None = None
        self._state: CatalogState = "idle"
        self._cache: CacheState = "unknown"
        self._store: SummaryStore | None = None
        self._summarized = 0
        self._from_cache = 0
        self._read = 0
        self._failed = 0
        self._budget_hit = False
        self._watched = False
        self._fast_seconds = 0.0
        self._fast_at: float | None = None
        self._summary_at: float | None = None
        self._live: tuple[float, list[LiveSession]] | None = None

    # -- requests ---------------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        """The catalog as it is now; never waits for a pass."""

        with self._lock:
            entries = list(self._by_id.values())
            drifts = [e.drift for e in entries if e.summarized]
            return Snapshot(
                home=self.home,
                entries=tuple(entries),
                drift=merge_drift([self._fast_drift, *drifts]),
                state=self._state,
                total=len(entries),
                summarized=self._summarized,
                from_cache=self._from_cache,
                read=self._read,
                failed=self._failed,
                pending_budget=self._budget_hit,
                fast_at=self._fast_at,
                summary_at=self._summary_at,
                cache=self._cache,
                cache_write_errors=self._store.write_errors if self._store else 0,
                passes=self._completed,
            )

    def refresh(self, first_pass_wait: float = FIRST_PASS_WAIT_SECONDS) -> None:
        """Start a pass when none runs and the last one is old; wait briefly on a first one.

        A request calls this and then :meth:`snapshot`. It never waits for more than
        *first_pass_wait*, and only while no pass has produced a session list yet.
        """

        with self._lock:
            if self._cancelled:
                return
            self._watched = True
            if self._thread is None and self._should_start():
                self._spawn()
        if not self._fast_ready.is_set() and first_pass_wait > 0:
            self._fast_ready.wait(first_pass_wait)

    def complete(self, now: float | None = None, timeout: float = SYNC_TIMEOUT_SECONDS) -> bool:
        """Run passes until every session is summarized or *timeout* passes.

        Returns True when the catalog is fully summarized. The first pass this starts is
        newer than the call, so a change made before the call is seen. *now* stamps the
        passes (a golden fixes it); it defaults to the clock.
        """

        deadline = time.monotonic() + timeout
        first = True
        while True:
            with self._cond:
                if self._cancelled:
                    return False
                self._watched = True
                if first:
                    self._now_override = now
                    first = False
                if self._thread is None:
                    self._spawn()
                else:
                    self._again = True
                target = self._started + (1 if self._again else 0)
                while self._completed < target and not self._cancelled:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                if self._cancelled:
                    return False
                if not self._budget_hit and self._state != "error":
                    return True
                if self._state == "error" or time.monotonic() >= deadline:
                    return False

    def live(self, now: float) -> list[LiveSession]:
        """Sessions something vouches for at *now*; reused for :data:`LIVE_TTL_SECONDS`."""

        with self._lock:
            cached = self._live
        if cached is not None and abs(now - cached[0]) < LIVE_TTL_SECONDS:
            return cached[1]
        if self.home.agent == "claude":
            found = claude.live(self.home, now, PROBE)
        else:
            found = codex.live(self.home, now)
        with self._lock:
            self._live = (now, found)
        return found

    def cancel(self) -> None:
        """Stop the worker at its next session and refuse new passes."""

        with self._cond:
            self._cancelled = True
            self._cond.notify_all()

    # -- the worker -------------------------------------------------------------------

    def _should_start(self) -> bool:
        if self._last_start is None:
            return True
        wait = max(REFRESH_MIN_INTERVAL_SECONDS, REFRESH_DUTY_FACTOR * self._fast_seconds)
        return time.monotonic() - self._last_start >= wait

    def _spawn(self) -> None:
        """Start the worker. The caller holds the lock and has seen no worker."""

        self._started += 1
        self._last_start = time.monotonic()
        self._state = "scanning"
        thread = threading.Thread(target=self._run, name="agents-catalog", daemon=True)
        self._thread = thread
        thread.start()

    def _run(self) -> None:
        try:
            while True:
                try:
                    self._pass()
                except (OSError, sqlite3.Error):
                    _LOG.exception("agents catalog pass failed")
                    with self._lock:
                        self._state = "error"
                with self._cond:
                    self._completed = self._started
                    self._cond.notify_all()
                    # A pass that ended at its byte budget continues while a request is
                    # watching; otherwise the next request continues it.
                    if (self._again or (self._budget_hit and self._watched)) and (
                        not self._cancelled
                    ):
                        self._again = False
                        self._started += 1
                        self._last_start = time.monotonic()
                        self._state = "scanning"
                        continue
                    if self._state != "error":
                        self._state = "idle"
                    self._thread = None
                    return
        finally:
            with self._cond:
                if self._thread is threading.current_thread():
                    # Only an unexpected error leaves the worker registered at this point.
                    self._thread = None
                    self._state = "error"
                    self._completed = self._started
                    self._cond.notify_all()

    def _pass(self) -> None:
        with self._lock:
            stamp = self._now_override if self._now_override is not None else CLOCK()
            self._now_override = None
            self._watched = False
        if self._store is None:
            self._store = SummaryStore.open(self.home.agent, self.home.path)
        with self._lock:
            self._cache = "ok" if self._store is not None else "unavailable"
        drift = DriftCollector()
        began = time.monotonic()
        found = (
            claude.discover(self.home)
            if self.home.agent == "claude"
            else codex.discover(self.home, codex.DISCOVER_LIMIT, drift)
        )
        keyed = [(s, session_key(s, self.home.path)) for s in map(_bounded, found)]
        with self._lock:
            self._fast_seconds = time.monotonic() - began
        self._publish(keyed, drift.freeze(), stamp)
        self._summarize(stamp)

    def _publish(
        self, keyed: list[tuple[SessionSummary, str]], drift: DriftSummary, stamp: float
    ) -> None:
        """Replace the session list with the fast pass's, keeping summaries whose key held."""

        with self._cond:
            previous = self._by_id
            fresh: dict[str, CatalogEntry] = {}
            for session, key in keyed:
                old = previous.get(session.session_id)
                if old is not None and old.key == key:
                    # A read that failed is tried again.
                    fresh[session.session_id] = replace(old, failed=False)
                else:
                    fresh[session.session_id] = CatalogEntry(session, key)
            self._by_id = fresh
            self._fast_drift = drift
            self._fast_at = stamp
            self._summarized = sum(1 for e in fresh.values() if e.summarized)
            self._failed = sum(1 for e in fresh.values() if e.failed)
            self._from_cache = 0
            self._read = 0
            self._budget_hit = False
            self._state = "summarizing"
        self._fast_ready.set()

    def _summarize(self, stamp: float) -> None:
        with self._lock:
            todo = [
                (sid, e.key, e.summary)
                for sid, e in self._by_id.items()
                if not e.summarized and not e.failed
            ]
        store = self._store
        spent = 0
        for session_id, key, fast in todo:
            with self._lock:
                if self._cancelled:
                    return
            if spent >= SUMMARY_PASS_BUDGET_BYTES:
                with self._lock:
                    self._budget_hit = True
                return
            loaded = store.load(key) if store is not None else None
            if loaded is not None:
                summary, drift = loaded
                from_cache = True
            else:
                from_cache = False
                try:
                    summary, drift = (claude if fast.agent == "claude" else codex).summarize(
                        self.home, fast
                    )
                except (OSError, sqlite3.Error):
                    _LOG.exception("agents summary failed for one session")
                    self._record(session_id, key, None, DriftSummary(), False)
                    continue
                spent += fast.size_bytes
                if store is not None:
                    store.save(key, summary, drift)
            self._record(session_id, key, _bounded(summary), drift, from_cache)
        with self._lock:
            if self._cancelled:
                return
            self._summary_at = stamp
        if store is not None:
            with self._lock:
                keep = [e.key for e in self._by_id.values()]
            store.prune(keep)

    def _record(
        self,
        session_id: str,
        key: str,
        summary: SessionSummary | None,
        drift: DriftSummary,
        from_cache: bool,
    ) -> None:
        with self._lock:
            entry = self._by_id.get(session_id)
            if entry is None or entry.key != key:
                return
            if summary is None:
                self._by_id[session_id] = replace(entry, failed=True)
                self._failed += 1
                return
            self._by_id[session_id] = replace(entry, summary=summary, drift=drift, summarized=True)
            self._summarized += 1
            if from_cache:
                self._from_cache += 1
            else:
                self._read += 1


def _bounded(summary: SessionSummary) -> SessionSummary:
    """*summary* with its title cut to one redacted line of :data:`TITLE_MAX_CHARS`."""

    if summary.title is None:
        return summary
    title = clip(summary.title[: 10 * TITLE_MAX_CHARS], TITLE_MAX_CHARS) or None
    return summary if title == summary.title else replace(summary, title=title)


# -- the registry ---------------------------------------------------------------------

_registry: dict[tuple[str, str], HomeCatalog] = {}
_registry_lock = threading.Lock()


def catalog_for(home: Home) -> HomeCatalog:
    """The one catalog of *home*, created on first use."""

    key = (home.agent, str(home.path))
    with _registry_lock:
        catalog = _registry.get(key)
        if catalog is None:
            catalog = HomeCatalog(home)
            _registry[key] = catalog
        return catalog


def reset() -> None:
    """Drop every catalog and stop its worker; the served root changed."""

    with _registry_lock:
        catalogs = list(_registry.values())
        _registry.clear()
    for catalog in catalogs:
        catalog.cancel()


register_root_callback(reset)
