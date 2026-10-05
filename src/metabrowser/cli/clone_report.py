"""What a command says on stderr while it clones a source, and when it finds one cached.

A first clone of a large repository runs for minutes. It says where the clone goes, once,
then how far it has got, then that it is done and what comes next:

.. code-block:: text

    cloning https://github.com/owner/repo into ~/.cache/metabrowser
    cloning https://github.com/owner/repo: receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)
    cloned https://github.com/owner/repo in 104 s (742.0 MiB); starting the server

On a terminal the middle line is one status line, rewritten in place. Anywhere else it
is a whole line every :data:`LOG_INTERVAL_S`, so a log stays short. The numbers are
Git's own progress, which :mod:`metabrowser.git.progress` hands over as integers: no
text Git or the origin wrote is printed here, only this module's words and those
numbers.

Everything goes to stderr. The destination is the cache directory, named on the user's
own terminal. A route's answer names a path in the cache in one place only: the
``location`` of a served mirror in :class:`metabrowser.source_routes.SourceStatus`.

Every line is written from the event loop that awaits Git, so one that could not be
written at once is dropped (:func:`_writable_now`): a terminal stopped with Ctrl-S, or a
pipe nobody reads, must not hold up the loop that enforces Git's deadline and delivers a
cancellation. A stream whose reader has gone is written to no more, and the command's
exit status is not changed by it.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
import sys
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Final, TextIO

from metabrowser.cache.paths import CACHE_ROOT
from metabrowser.cache.records import canonical_now
from metabrowser.git.progress import GitProgress, ProgressStage
from metabrowser.git.tree_source import display_segment
from metabrowser.paths_safe import tilde_path

# Without a terminal, how long after the last line the next status line is written.
# Measured 2026-10-01 (Git 2.50.1, anonymous https): github.com/cli/cli, 80 MiB, cloned
# in 9.5 s, so a clone that size writes its two bracketing lines and no status line; the
# report this was written for was 740 MB in about 100 s, which is nine. The 900 s
# acquisition deadline bounds a log at 90. The interval is a third of the 30 s stall
# bound (``HTTP_LOW_SPEED_TIME_S``), so a transfer that stops shows as the same numbers
# under a growing time at least twice before the bound ends it.
LOG_INTERVAL_S: Final = 10.0

# On a terminal, the least time between two redraws of the status line. Git writes a
# record for every percent of every stage, 255 of them in that 9.5 s clone and 83 in its
# busiest second; ten redraws a second read as continuous.
REDRAW_INTERVAL_S: Final = 0.1

# How often the status is shown again when Git has reported nothing new, so the elapsed
# time keeps counting through a phase that has no progress, and through a stall.
TICK_S: Final = 1.0

_STAGE_TEXT: Final[dict[ProgressStage, str]] = {
    "enumerating": "the origin is enumerating objects",
    "counting": "the origin is counting objects",
    "compressing": "the origin is compressing objects",
    "receiving": "receiving objects",
    "unpacking": "unpacking objects",
    "resolving": "resolving deltas",
    "checking": "checking connectivity",
}
_FALLBACK_COLUMNS: Final = 80

# The clock elapsed times are read from; a transcript replaces it to pin them.
_monotonic = time.monotonic


def format_size(size: int) -> str:
    """*size* bytes in binary units, to the precision a progress line needs."""

    if size < 1024:
        return f"{size} byte" + ("" if size == 1 else "s")
    if size < 1024**2:
        return f"{size / 1024:.1f} KiB"
    if size < 1024**3:
        return f"{size / 1024**2:.1f} MiB"
    return f"{size / 1024**3:.2f} GiB"


def format_elapsed(seconds: float) -> str:
    """Tenths of a second while that says something, whole seconds after.

    Cut, not rounded: a time shown is a time that has passed.
    """

    return f"{int(seconds * 10) / 10:.1f} s" if seconds < 10 else f"{int(seconds)} s"


def format_age(seconds: float) -> str:
    """How long ago, in the one unit a reader needs."""

    if seconds < 60:
        return "less than a minute ago"
    if seconds < 3600:
        count, unit = int(seconds // 60), "minute"
    elif seconds < 48 * 3600:
        count, unit = int(seconds // 3600), "hour"
    else:
        count, unit = int(seconds // 86400), "day"
    return f"{count} {unit}{'' if count == 1 else 's'} ago"


def describe_progress(progress: GitProgress) -> str:
    """One progress record in this module's words: the stage, how far, and how fast."""

    text = _STAGE_TEXT[progress.stage]
    percent = progress.percent
    text += f": {progress.done:,}" if percent is None else f": {percent}%"
    if progress.received_bytes is not None:
        text += f", {format_size(progress.received_bytes)}"
        if progress.bytes_per_second:
            text += f" at {format_size(progress.bytes_per_second)}/s"
    return text


def cache_directory_display(home: Path) -> str:
    """Where clones are kept under *home*, as a person would type it.

    The cache directory, with the home directory as ``~``: it is what holds every clone
    and what someone would measure or move aside. A store's own directory is named by a
    hash, which says nothing to a reader. A control character in the path is replaced,
    as in every name shown on a terminal.
    """

    directory = home / CACHE_ROOT
    try:
        shown = tilde_path(directory, Path.home())
    except (OSError, RuntimeError):
        shown = str(directory)
    return display_segment(shown.encode("utf-8", "surrogateescape"))


def _writable_now(stream: TextIO) -> bool:
    """Whether a write to *stream* would return at once.

    A stream with no descriptor, such as one a test captures into, always is; so is
    any stream where the question cannot be asked, as on Windows. For a pipe the answer
    holds for a line of up to ``PIPE_BUF`` bytes, 512 at the least, which is longer
    than any line here unless the URL and the home path are both very long.
    """

    try:
        _, writable, _ = select.select([], [stream.fileno()], [], 0)
    except (AttributeError, OSError, ValueError):
        return True
    return bool(writable)


def _columns(stream: TextIO) -> int:
    """The terminal's width, or 80 where it reports none, as a new pseudo-terminal does."""

    try:
        columns = os.get_terminal_size(stream.fileno()).columns
    except (AttributeError, OSError, ValueError):
        return _FALLBACK_COLUMNS
    return columns if columns > 0 else _FALLBACK_COLUMNS


class CloneReport:
    """One command's account of acquiring one source, written to stderr.

    ``phase`` and ``progress`` are the two reporters acquisition calls, and a cache hit
    calls neither, so a hit writes nothing unless the command asks with
    :meth:`cache_hit`. *then* is what the command does after a clone, for the last line.
    """

    def __init__(
        self, url: str, destination: str, *, then: str = "", stream: TextIO | None = None
    ) -> None:
        self._url = url
        self._destination = destination
        self._then = then
        self._stream = sys.stderr if stream is None else stream
        try:
            self._terminal = self._stream.isatty()
        except (AttributeError, ValueError):
            self._terminal = False
        self._started = _monotonic()
        self._cloning = False
        self._status = ""
        self._received: int | None = None
        self._last_shown = self._started
        self._drawn = 0
        self._gone = False

    def phase(self, phase: str) -> None:
        """A phase of the clone has started; ``done`` ends it."""

        if not self._cloning:
            self._cloning = True
            self._write(f"cloning {self._url} into {self._destination}\n")
            # The interval to the first status line runs from here, not from when the
            # command started: what came before the clone may have taken a while.
            self._last_shown = _monotonic()
        if phase == "done":
            self._finish()
            return
        self._status = phase
        self._show(now=True)

    def progress(self, progress: GitProgress) -> None:
        """Git reported how far the fetch has got."""

        # The size is what this side counted as it arrived, never the origin's word.
        if progress.stage == "receiving" and not progress.remote:
            self._received = progress.received_bytes or self._received
        self._status = describe_progress(progress)
        self._show()

    def tick(self) -> None:
        """Time has passed: show the status again if it is due."""

        if self._cloning:
            self._show()

    @contextlib.asynccontextmanager
    async def ticking(self) -> AsyncGenerator[None]:
        """Call :meth:`tick` every :data:`TICK_S` while the body runs."""

        async def tick() -> None:
            while True:
                await asyncio.sleep(TICK_S)
                self.tick()

        ticker = asyncio.ensure_future(tick())
        try:
            yield
        finally:
            # Not awaited: waiting here could swallow a cancellation of the command
            # that arrives in the same instant. The loop collects a cancelled task.
            ticker.cancel()

    def end_status_line(self) -> None:
        """End the status line on the terminal, so what is written next starts a line.

        The line stays where it is, and the next status is drawn on a line of its own.
        A log record written during the clone is preceded by this.
        """

        if self._drawn and self._write("\n"):
            self._drawn = 0

    def close(self) -> None:
        """End a status line a failure or a cancellation left on the terminal.

        The line stays: it says how far the clone had got when it stopped.
        """

        self.end_status_line()
        self._cloning = False

    def cache_hit(self, last_fetch_at: str | None) -> None:
        """Say that the source was already cloned, where, and how old the fetch is."""

        line = f"using the clone of {self._url} cached in {self._destination}"
        age = _age_of(last_fetch_at)
        self._write((line if age is None else f"{line}, fetched {age}") + "\n")

    def _elapsed(self) -> str:
        return format_elapsed(_monotonic() - self._started)

    def _width(self) -> int:
        # One column short of the terminal's, so the cursor never wraps to a second
        # line that a carriage return could not take back.
        return max(_columns(self._stream) - 1, 1)

    def _finish(self) -> None:
        line = f"cloned {self._url} in {self._elapsed()}"
        if self._received is not None:
            line += f" ({format_size(self._received)})"
        if self._then:
            line += f"; {self._then}"
        self._cloning = False
        # The status line is blanked and the last line written over it, in one write.
        blank = "\r" + " " * min(self._drawn, self._width()) + "\r" if self._drawn else ""
        if self._write(blank + line + "\n"):
            self._drawn = 0

    def _show(self, *, now: bool = False) -> None:
        """Show the status if it is due, or at once on a terminal when *now*.

        A terminal redraws its one line. Without one a whole line is written, and only
        every :data:`LOG_INTERVAL_S`, whatever *now* says: a phase is not worth a line
        of a log by itself.
        """

        at = _monotonic()
        since = at - self._last_shown
        if self._terminal:
            if not now and since < REDRAW_INTERVAL_S:
                return
        elif since < LOG_INTERVAL_S:
            return
        status = f"{self._status} ({self._elapsed()})"
        if not self._terminal:
            if self._write(f"cloning {self._url}: {status}\n"):
                self._last_shown = at
            return
        width = self._width()
        status = status[:width]
        # Blanks over what a longer status left, and never past the width: a terminal
        # made narrower since then must not be made to wrap.
        blanks = min(max(self._drawn - len(status), 0), width - len(status))
        # A status that was dropped is due again at the next record or tick, not an
        # interval later.
        if self._write("\r" + status + " " * blanks):
            self._last_shown = at
            self._drawn = len(status)

    def _write(self, text: str) -> bool:
        """Write *text* at once, or not at all; whether it was written.

        A stream that is closed, or whose reader has gone, is not worth failing a clone
        over, and is not tried again.
        """

        if self._gone or not _writable_now(self._stream):
            return False
        try:
            self._stream.write(text)
            self._stream.flush()
        except (OSError, ValueError):
            self._gone = True
            return False
        return True


def _age_of(timestamp: str | None) -> str | None:
    """How long ago a record's canonical *timestamp* was, by the clock records use."""

    if timestamp is None:
        return None
    try:
        then = datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
        now = datetime.fromisoformat(canonical_now().removesuffix("Z") + "+00:00")
    except ValueError:
        return None
    return format_age((now - then).total_seconds())


__all__ = [
    "LOG_INTERVAL_S",
    "REDRAW_INTERVAL_S",
    "TICK_S",
    "CloneReport",
    "cache_directory_display",
    "describe_progress",
    "format_age",
    "format_elapsed",
    "format_size",
]
