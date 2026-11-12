"""Stop serving when stdin reaches EOF (``--exit-on-eof``).

A parent that starts ``metab`` and holds its stdin open, as the macOS app does, gives the
server a lifeline: however the parent ends, the kernel closes the pipe's write end, and
the server reads EOF. A parent that crashes or is force-quit cannot stop its servers;
this way they stop themselves, and nothing has to find them later by pid, a number the
kernel may by then have given to an unrelated process.

The flag is opt-in, since a server started from a shell with stdin at ``/dev/null``
would otherwise stop at once. Whatever arrives on stdin before EOF is read and dropped.

The watch begins as soon as serve mode has its command line (:func:`stop_when_stdin_closes`),
before anything that can block: reading ROOT, dotenv files, the server's and plugins'
imports, KPress's assets, a Git source's acquisition, or the port search. A parent that
ends while startup is held on a slow disk or a network therefore stops the server too.
Only the interpreter's start, the CLI's own imports, and argument parsing come first.
"""

from __future__ import annotations

import os
import select
import threading
from collections.abc import Callable
from typing import Final, NoReturn

from metabrowser.cli.common import write_notice_now_or_never
from metabrowser.errors import CLIError
from metabrowser.git.process import (
    kill_live_process_groups,
    stop_process_groups,
    wait_for_process_group_spawns,
)

STDIN_CLOSED_NOTICE: Final[bytes] = b"Stopping Metabrowser: stdin closed.\n"
# A parent going away is an orderly end of serving, not a failure.
STDIN_CLOSED_EXIT_STATUS: Final[int] = 0
# What one read takes from the pipe; the bytes are dropped.
_READ_BYTES: Final[int] = 64 * 1024
# How long a stop waits for a group's spawn that was under way to end, which kills the
# group and exits. A Git spawn took 2.9 ms (median) and 3.9 ms (max) from its start to
# its registration over 50 runs on a loaded M-series Mac (2026-11-11), so the bound is
# reached only when the event loop does not get back to the spawn; the stop then kills
# what it knows and exits anyway.
_SPAWN_WAIT_S: Final[float] = 2.0


def require_open_stdin(*, fd: int = 0) -> None:
    """Refuse to serve with the flag when there is no stdin to watch.

    A closed descriptor would read as an immediate end, so the server would stop as soon
    as it started, which no caller asking for the flag means.
    """
    try:
        os.fstat(fd)
    except OSError as exc:
        raise CLIError(f"--exit-on-eof needs an open stdin to watch: {exc.strerror}") from exc


def _read_until_eof(fd: int) -> None:
    """Read and drop what arrives on ``fd`` until its end.

    A read error counts as the end too: a stdin that can no longer be read, such as a
    terminal that hung up, has lost its parent just as surely. ``EAGAIN`` does not: a
    stdin inherited with ``O_NONBLOCK`` reads it while its writer is alive and has sent
    nothing yet. The wait for it to be readable blocks, so it does not spin, and it
    returns at the end as well as for data. The flag is left as inherited, because it
    belongs to the open file, which other processes may share.
    """

    while True:
        try:
            chunk = os.read(fd, _READ_BYTES)
        except BlockingIOError:
            try:
                select.select([fd], [], [])
            except OSError:
                return
            continue
        except OSError:
            return
        if not chunk:
            return


def watch_for_eof(on_eof: Callable[[], object], *, fd: int = 0) -> threading.Thread:
    """Read ``fd`` on a daemon thread until EOF, then call ``on_eof`` once."""

    def watch() -> None:
        _read_until_eof(fd)
        on_eof()

    thread = threading.Thread(target=watch, name="metabrowser-stdin-lifeline", daemon=True)
    thread.start()
    return thread


def stop_when_stdin_closes(*, fd: int = 0) -> threading.Thread:
    """Refuse a stdin that is not open, then stop the process when it closes."""

    require_open_stdin(fd=fd)
    return watch_for_eof(stop_for_closed_stdin, fd=fd)


def _exit_for_closed_stdin() -> NoReturn:
    os._exit(STDIN_CLOSED_EXIT_STATUS)


def stop_for_closed_stdin() -> NoReturn:
    """Stop the process on the spot, as one Ctrl-C does (see ``serve._stop_now``).

    Runs on the watcher thread while the main thread serves. The notice is a raw write,
    which takes no lock the main thread may hold, and is skipped when stderr cannot take
    it now, so a full stderr nobody reads cannot hold the stop up. ``os._exit`` ends
    every thread at once, so neither a request in flight nor a worker thread stuck in a
    slow read keeps the process alive.

    Git and ``gh`` that run in process groups of their own are killed first, by
    :func:`stop_process_groups`, which also refuses new ones. A group whose spawn is
    under way on the event loop is killed by that spawn as soon as it exists, and the
    spawn then exits; this thread waits for it, up to a bound, and exits itself if the
    loop never gets back to the spawn.
    """
    write_notice_now_or_never(2, STDIN_CLOSED_NOTICE)
    if not stop_process_groups(_exit_for_closed_stdin):
        wait_for_process_group_spawns(_SPAWN_WAIT_S)
        kill_live_process_groups()
    _exit_for_closed_stdin()


__all__ = [
    "STDIN_CLOSED_EXIT_STATUS",
    "STDIN_CLOSED_NOTICE",
    "require_open_stdin",
    "stop_for_closed_stdin",
    "stop_when_stdin_closes",
    "watch_for_eof",
]
