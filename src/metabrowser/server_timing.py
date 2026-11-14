"""Named phases of one request's server time, for ``Server-Timing`` and the request log.

``_SlowRequestLogMiddleware`` in ``server.py`` opens a record for each request with
:func:`begin`. Code on the request's path adds the time a phase took with
:func:`phase`, on the event loop or in a thread the request awaits:
``asyncio.to_thread`` and Starlette's thread pool run with a copy of the request's
context, and the record in it is the same list. The phases are:

``read``
    Reading what the answer is made from: a request body, a file, its classification.
``render``
    Turning a document into the answer, as KPress does.
``git``
    Waiting on a ``git`` process.
``encode``
    Turning the answer into bytes: JSON serialization, and gzip compression
    (:class:`TimedGZipMiddleware`).

A phase opened inside another one adds nothing, so a ``git`` call inside a ``read`` is
not counted twice. Phases that run side by side, as ``asyncio.gather`` runs them, are
each counted in full, so their sum can exceed the request's own time.

**What the header can say.** A response's headers are sent before its body, so
``Server-Timing`` holds ``srv``, the time to the start of the response, and the phases
finished by then. For a JSON answer that is nearly everything: its body is serialized,
and gzip compresses it, before the headers go. A streamed body, such as a static file,
is read and compressed after them, which no header can report. The request log records
the rest: with ``METABROWSER_REQUEST_LOG=verbose``, or for a request slower than the
slow-request threshold, a line gives the time to the end of the body, the time to the
start of the response, and every phase's total.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware, GZipResponder, IdentityResponder

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class Record:
    """Each phase's running total for one request, in the order the phases first finished.

    A sum per name rather than a list of entries, so a streamed body's thousands of gzip
    chunks are all counted and the record stays as small as the handful of phase names
    (review B of #372, B2). A task the request starts that outlives it inherits its
    context, record included, so a record stops taking additions when its request ends.
    """

    __slots__ = ("_lock", "_open", "_totals")

    def __init__(self) -> None:
        # Threads the request awaits add to it too.
        self._lock = threading.Lock()
        self._totals: dict[str, float] = {}
        self._open = True

    def add(self, name: str, ms: float) -> None:
        with self._lock:
            if self._open:
                self._totals[name] = self._totals.get(name, 0.0) + ms

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


def header_value(record: Record, srv_ms: float) -> str:
    """The ``Server-Timing`` value: ``srv``, then each phase finished so far."""
    metrics = [("srv", srv_ms), *record.totals()]
    return ", ".join(f"{name};dur={ms:.1f}" for name, ms in metrics)


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
    that method changes, so an upgrade re-reads this copy.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        responder: ASGIApp
        if "gzip" in Headers(scope=scope).get("Accept-Encoding", ""):
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
    "header_value",
    "log_value",
    "phase",
]
