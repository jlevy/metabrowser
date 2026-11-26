"""Named phases of one request's server time, for ``Server-Timing`` and the request log.

``_SlowRequestLogMiddleware`` in ``server.py`` opens a record for each request with
:func:`begin`. Code on the request's path adds the time a phase took with
:func:`phase`, on the event loop or in a thread the request awaits:
``asyncio.to_thread`` and Starlette's thread pool run with a copy of the request's
context, and the record in it is the same list. The phases are:

``read``
    Reading what the answer is made from: a request body, a file, its classification, a
    plugin's or KPress's asset.
``render``
    Turning a document into the answer, as KPress does.
``git``
    Waiting on a ``git`` process.
``encode``
    Turning the answer into bytes: JSON serialization, and gzip compression
    (:class:`TimedGZipMiddleware`).
``queue``
    Waiting for a slot another request holds, as a pull request's rendered diff waits
    for its one projection.
``start``
    Waiting for a worker process to start, as a page's rendered-diff prefetch waits for
    the Markdown child.

A phase opened inside another one adds nothing, so a ``git`` call inside a ``read`` is
not counted twice. Phases that run side by side, as ``asyncio.gather`` runs them, are
each counted in full, so their sum can exceed the request's own time.

**What a phase measures.** A phase is wall-clock time, not CPU time, and it is taken on
the request's path around the work it names: a phase around
``await asyncio.to_thread(...)`` includes the wait for a pool thread and for the event
loop to resume the request, and one on the event loop, such as the gzip middleware's
``encode``, holds the loop for its whole span. Every route times a phase this way, the
asset store (:mod:`metabrowser.encoded_assets`) included, so one phase name means one
quantity in every family (review B of #455, B4). Timing inside the thread instead would
leave out the queueing a loaded pool adds, which is part of what the request waited for.

**Git processes.** Beside the times, a record counts the Git processes the request
started: :func:`git_process_started` is called by ``git/process.py`` each time a spawn
succeeds, inside a phase or not, so the count is every process and not only those the
``git`` time covers. The header says it in the ``git`` entry's description,
``git;dur=41.2;desc="2 processes"``, and a request whose Git ran inside another phase
gets a ``git`` entry with the description alone (H116). Work a request joins rather than
starts is counted where it started: a comparison's listing that another request is already
computing (``builtin_plugins/diff/comparison_cache.py``) is counted in that request, while it
is open, and not in the one that waits for it, which says nothing of it.

**What the header can say.** A response's headers are sent before its body, so
``Server-Timing`` holds ``srv``, the time to the start of the response, and the phases
finished by then. For a JSON answer that is nearly everything: its body is serialized,
and gzip compresses it, before the headers go. A streamed body, such as a static file,
is read and compressed after them, which no header can report. The request log records
the rest: with ``METABROWSER_REQUEST_LOG=verbose``, or for a request slower than the
slow-request threshold, a line gives the time to the end of the body, the time to the
start of the response, and every phase's total. The verbose line also gives the end of
the body as ``end_ms``, to a tenth of a millisecond, which
``explorations/performance-loop/server-time.mjs`` reads over a page load. Both are taken
when the application returns, so they include a response's background tasks and the
waits for the client to drain the body, which grow with the bytes sent.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from starlette.middleware.gzip import GZipMiddleware, GZipResponder, IdentityResponder

from metabrowser import delivery

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class Record:
    """Each phase's running total for one request, in the order the phases first finished.

    A sum per name rather than a list of entries, so a streamed body's thousands of gzip
    chunks are all counted and the record stays as small as the handful of phase names
    (review B of #372, B2). A task the request starts that outlives it inherits its
    context, record included, so a record stops taking additions when its request ends.
    """

    __slots__ = ("_git_processes", "_lock", "_open", "_totals")

    def __init__(self) -> None:
        # Threads the request awaits add to it too.
        self._lock = threading.Lock()
        self._totals: dict[str, float] = {}
        self._git_processes = 0
        self._open = True

    def add(self, name: str, ms: float) -> None:
        with self._lock:
            if self._open:
                self._totals[name] = self._totals.get(name, 0.0) + ms

    def add_git_process(self) -> None:
        with self._lock:
            if self._open:
                self._git_processes += 1

    def git_processes(self) -> int:
        """How many Git processes the request started."""
        with self._lock:
            return self._git_processes

    def close(self) -> None:
        with self._lock:
            self._open = False

    def totals(self) -> list[tuple[str, float]]:
        """Each phase's total, in the order the phases first finished."""
        with self._lock:
            return list(self._totals.items())


_RECORD: ContextVar[Record | None] = ContextVar("metabrowser_server_timing", default=None)
# Whether a phase is open in this context, so a nested one adds nothing.
_OPEN: ContextVar[bool] = ContextVar("metabrowser_server_timing_open", default=False)


def begin() -> tuple[Record, Token[Record | None]]:
    """Open a record for the request this context serves."""
    record = Record()
    return record, _RECORD.set(record)


def end(record: Record, token: Token[Record | None]) -> None:
    """Close the record :func:`begin` opened."""
    record.close()
    _RECORD.reset(token)


@contextmanager
def phase(name: str) -> Generator[None]:
    """Add the time the block takes to the request's *name* phase.

    Costs two clock reads; outside a request, or inside another phase, it records
    nothing.
    """
    record = _RECORD.get()
    if record is None or _OPEN.get():
        yield
        return
    opened = _OPEN.set(True)
    started = time.perf_counter()
    try:
        yield
    finally:
        record.add(name, (time.perf_counter() - started) * 1000)
        _OPEN.reset(opened)


def git_process_started() -> None:
    """Count one Git process for the request this context serves; outside one, nothing."""
    record = _RECORD.get()
    if record is not None:
        record.add_git_process()


def header_value(record: Record, srv_ms: float) -> str:
    """The ``Server-Timing`` value: ``srv``, then each phase finished so far.

    The ``git`` entry carries the count of Git processes started so far as its description.
    """
    metrics = [f"{name};dur={ms:.1f}" for name, ms in [("srv", srv_ms), *record.totals()]]
    processes = record.git_processes()
    if processes:
        described = f'desc="{processes} process{"" if processes == 1 else "es"}"'
        timed = next((i for i, text in enumerate(metrics) if text.startswith("git;")), None)
        if timed is None:
            metrics.append(f"git;{described}")
        else:
            metrics[timed] = f"{metrics[timed]};{described}"
    return ", ".join(metrics)


def log_value(record: Record) -> str:
    """The phases for the request log: ``read:1.2,encode:0.4``, or ``-`` for none."""
    return ",".join(f"{name}:{ms:.1f}" for name, ms in record.totals()) or "-"


class _TimedGZipResponder(GZipResponder):
    def apply_compression(self, body: bytes, *, more_body: bool) -> bytes:
        with phase("encode"):
            return super().apply_compression(body, more_body=more_body)


class TimedGZipMiddleware(GZipMiddleware):
    """Starlette's gzip middleware, with the compression it does counted as ``encode``.

    The research of 2026-11-11 measured level 6 at about 33 MB/s on the event loop, about
    93 ms for a cold landing's 3.1 MB, and ``Server-Timing`` showed none of it. The choice
    of responder is Starlette's own, copied from ``GZipMiddleware.__call__`` in Starlette
    1.3.1 so the gzip one can be the timed one; ``tests/test_server_timing.py`` fails when
    that method changes, so an upgrade re-reads this copy. One test differs from
    Starlette's: whether a request is sent gzip is :func:`metabrowser.delivery.gzip_wanted`,
    which leaves a loopback client of a server started for local use uncompressed (H115)
    and otherwise is Starlette's own test of ``Accept-Encoding``.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        responder: ASGIApp
        if delivery.gzip_wanted(scope):
            responder = _TimedGZipResponder(
                self.app, self.minimum_size, compresslevel=self.compresslevel
            )
        else:
            responder = IdentityResponder(self.app, self.minimum_size)
        await responder(scope, receive, send)


__all__ = [
    "Record",
    "TimedGZipMiddleware",
    "begin",
    "end",
    "git_process_started",
    "header_value",
    "log_value",
    "phase",
]
