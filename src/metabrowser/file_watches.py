"""File watches on the page's event stream: the paths each ``/api/events`` connection
watches, the generation each was last seen at, and the poll that sends ``file.changed``.

A page holds one event stream (``docs/project/architecture/arch-live-delivery.md``), and
the inventory behind it delivers a change only for a path it indexes, to the depth the
stream's scope draws. An open table needs to hear of a change to its own file, which may
be ignored, deep, or a database whose owner writes through a ``-wal`` beside it. So a
page registers the paths it shows on its own connection (``POST /api/events/watch`` in
``events_route.py``), and this module keeps them:

- :class:`FileWatches` holds, for each open connection, its watched paths and the
  generation each was last seen at, bounded by :data:`FILE_WATCH_MAX_PATHS`.
- :meth:`FileWatches.poll` asks each distinct watched path's generation once and sends
  one :class:`~metabrowser.events.FileChanged` to each connection that saw another, so a
  burst of writes between two polls is one event.
- :meth:`FileWatches.run` polls every :data:`FILE_WATCH_POLL_INTERVAL_S`, and sooner, but
  no sooner than :data:`FILE_WATCH_MIN_SPACING_S` after the last poll, when the inventory
  reports a change at a watched path, an ancestor of one, or a sidecar of one
  (:meth:`FileWatches.nudge`).
- :func:`watch_generation` is what a poll compares: a table source's own
  ``generation()`` for a path whose kind has one (``table_source.py``), so a database's
  generation is the one its reads sample, and the file's identity, size, and modification
  time for any other path; None when nothing readable is there.

Every path is polled, the ones the inventory delivers too: the inventory's coverage of a
path (its ignore rules, its watcher's state, a source's sidecars) is not a fact this
module can read cheaply, and a poll costs a stat and, for a table, a classification
(the measurement is at :data:`FILE_WATCH_MAX_PATHS`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from metabrowser.content_errors import ContentReadError
from metabrowser.events import FileChanged
from metabrowser.source import resolve_session_identity
from metabrowser.table_source import (
    NoTableSourceError,
    TablePathNotFoundError,
    TableSourceError,
    open_table_source,
    stat_generation,
)

LOG = logging.getLogger(__name__)

# The most paths one connection may watch at once. A page watches the table it shows and
# each container whose children its tree has open, so a reader's page needs a handful; the
# bound is what one page may make every poll cost. Measured on 2026-11-20 on a shared
# 4-core Linux container at a load average near 6 (devtools/measure_file_watch_poll.py,
# medians of 50 polls): a poll of 32 watched delimited files, each classified and its
# source's generation asked, took 9 to 10 ms from start to end, 3.1 to 3.4 ms of it on
# the event loop, and of 32 plain text files 7.7 ms, 2.3 ms on the loop; 128 delimited
# files took 65 ms, 16 ms on the loop, so the cost per path grows past the bound. At one
# poll a second, a page at the bound holds the loop about 0.3% of the time, and the six
# pages a browser connects at once about 2%.
FILE_WATCH_MAX_PATHS = 32

# How often every watched path is polled. One second is the latency a live table shows a
# write the inventory does not report (an ignored file, a deep one, a database's log),
# and the cadence of the cost above.
FILE_WATCH_POLL_INTERVAL_S = 1.0

# The least time between two polls, however often the inventory reports a change at a
# watched path. A writer that commits continuously makes the inventory report its file
# on every batch; this keeps the poll, and the `file.changed` it sends, to four a second,
# which a table coalesces again within its own window.
FILE_WATCH_MIN_SPACING_S = 0.25

# The largest registration body the route reads: a connection id, a path, a generation,
# and a flag. Paths are inventory paths, which the inventory bounds far below this.
FILE_WATCH_MAX_BODY_BYTES = 8 * 1024

WatchGeneration = Callable[[str], Awaitable[str | None]]
Send = Callable[[str, FileChanged], None]


class UnknownConnectionError(Exception):
    """The connection id names no open ``/api/events`` connection of this process."""

    code = "unknown_connection"


class TooManyWatchesError(Exception):
    """The connection already watches :data:`FILE_WATCH_MAX_PATHS` paths."""

    code = "too_many_watches"


async def watch_generation(path: str) -> str | None:
    """The generation a watch on *path* compares, or None when nothing readable is there.

    A path whose kind has a table source answers that source's ``generation()``, the
    token its reads sample; any other path, a folder included, answers
    :func:`~metabrowser.table_source.stat_generation` of what is there.
    """

    try:
        opened = await open_table_source(path)
    except (NoTableSourceError, TablePathNotFoundError):
        return await _stat_generation(path)
    except (TableSourceError, ContentReadError):
        return None
    try:
        return await asyncio.to_thread(opened.source.generation)
    except (TableSourceError, OSError):
        return None


async def _stat_generation(path: str) -> str | None:
    def stat() -> str | None:
        try:
            target = resolve_session_identity(path)
        except ContentReadError:
            return None
        if target is None:
            return None
        try:
            return stat_generation(target)
        except OSError:
            return None

    return await asyncio.to_thread(stat)


def _touches(dirty: str, watched: str) -> bool:
    """Whether an inventory change at *dirty* may change what *watched* names.

    True for the path itself, an ancestor of it (the file a container address names, or
    a folder), and a sidecar of either: a name with a ``-suffix`` beside it, as SQLite's
    ``-wal``, ``-shm``, and ``-journal`` are. Not for the served root, which the
    inventory marks changed with every write anywhere; a watched file's own change marks
    the file itself. A false positive costs one poll, which finds the generation
    unchanged.
    """

    for candidate in (dirty, dirty.rsplit("-", 1)[0]):
        if candidate and (candidate == watched or watched.startswith(candidate + "/")):
            return True
    return False


@dataclass(slots=True)
class _Connection:
    watched: dict[str, str | None]


class FileWatches:
    """The watched paths of every open connection, and the poll that reports changes.

    All methods run on the event loop. *generation_of* computes a path's generation, and
    *send* queues an event on one connection's stream.
    """

    def __init__(
        self,
        *,
        send: Send,
        generation_of: WatchGeneration = watch_generation,
        max_paths: int = FILE_WATCH_MAX_PATHS,
        interval_s: float = FILE_WATCH_POLL_INTERVAL_S,
        spacing_s: float = FILE_WATCH_MIN_SPACING_S,
    ) -> None:
        self._send = send
        self._generation_of = generation_of
        self._max_paths = max_paths
        self._interval_s = interval_s
        self._spacing_s = spacing_s
        self._connections: dict[str, _Connection] = {}
        self._wake = asyncio.Event()
        self._last_poll = -math.inf

    @property
    def max_paths(self) -> int:
        return self._max_paths

    def open(self, connection: str) -> None:
        """Begin keeping watches for a newly attached connection."""

        self._connections.setdefault(connection, _Connection(watched={}))

    def close(self, connection: str) -> None:
        """Drop a connection and every watch it held."""

        self._connections.pop(connection, None)

    def is_open(self, connection: str) -> bool:
        return connection in self._connections

    def watched(self, connection: str) -> dict[str, str | None]:
        """A copy of one connection's watched paths and their last generations."""

        held = self._connections.get(connection)
        return dict(held.watched) if held is not None else {}

    async def register(self, connection: str, path: str) -> str | None:
        """Watch *path* on *connection* and answer its generation now.

        The answer is the baseline later polls compare with, so a change between the
        page's read and this registration shows as a generation other than the one the
        page holds. Raises :class:`UnknownConnectionError` or
        :class:`TooManyWatchesError`.
        """

        self._admit(connection, path)
        generation = await self._generation_of(path)
        # The connection may have ended, or filled its watches, while the generation was read.
        held = self._admit(connection, path)
        held.watched[path] = generation
        return generation

    def unregister(self, connection: str, path: str) -> bool:
        """Stop watching *path*; whether it was watched. Raises :class:`UnknownConnectionError`."""

        held = self._connections.get(connection)
        if held is None:
            raise UnknownConnectionError(connection)
        was = path in held.watched
        held.watched.pop(path, None)
        return was

    def _admit(self, connection: str, path: str) -> _Connection:
        held = self._connections.get(connection)
        if held is None:
            raise UnknownConnectionError(connection)
        if path not in held.watched and len(held.watched) >= self._max_paths:
            raise TooManyWatchesError(connection)
        return held

    def nudge(self, dirty_paths: Iterable[str], *, everything: bool = False) -> None:
        """Poll soon when an inventory change may touch a watched path."""

        if not self._connections:
            return
        watched = {path for held in self._connections.values() for path in held.watched}
        if not watched:
            return
        if everything or any(_touches(dirty, path) for dirty in dirty_paths for path in watched):
            self._wake.set()

    async def poll(self) -> int:
        """Ask each distinct watched path's generation once; send what changed. Returns
        the number of events sent."""

        self._last_poll = time.monotonic()
        paths = sorted({path for held in self._connections.values() for path in held.watched})
        current: dict[str, str | None] = {}
        for path in paths:
            try:
                current[path] = await self._generation_of(path)
            except Exception:
                # One path's failure must not stop the others' watches; it is asked again
                # at the next poll.
                LOG.exception("file watch: could not read the generation of %s", path)
        sent = 0
        for connection, held in list(self._connections.items()):
            for path, generation in current.items():
                if path in held.watched and held.watched[path] != generation:
                    held.watched[path] = generation
                    self._send(connection, FileChanged(path=path, generation=generation))
                    sent += 1
        return sent

    async def run(self) -> None:
        """Poll on the interval, and soon after a nudge, until cancelled."""

        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._interval_s)
            self._wake.clear()
            wait = self._last_poll + self._spacing_s - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            if not any(held.watched for held in self._connections.values()):
                continue
            try:
                await self.poll()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("file watch: a poll failed")


__all__ = [
    "FILE_WATCH_MAX_BODY_BYTES",
    "FILE_WATCH_MAX_PATHS",
    "FILE_WATCH_MIN_SPACING_S",
    "FILE_WATCH_POLL_INTERVAL_S",
    "FileWatches",
    "TooManyWatchesError",
    "UnknownConnectionError",
    "watch_generation",
]
