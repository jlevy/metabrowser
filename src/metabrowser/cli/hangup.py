"""Treat a terminal hangup like Ctrl-C while the CLI waits on acquisition.

Acquisition Git runs as the leader of its own process group, so that a timeout or a
cancellation can kill the helpers it forks. That also takes it out of the terminal's
foreground group: when the terminal hangs up, ``SIGHUP`` reaches only this process.
Left at its default action, Python would die on the spot and orphan Git and its
helpers, still fetching into staging. :func:`run_cancelling_on_hangup` instead cancels
the main task, as ``asyncio.run`` does for ``SIGINT``; the cancellation kills Git's
process group on its way out, and the process then exits with 129 (128 + SIGHUP), the
status a shell reports for a hangup (mb-163x).
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Coroutine
from typing import Any, Final

HANGUP_EXIT_STATUS: Final[int] = 129


class _HungUp(Exception):
    """The main task was cancelled because the terminal hung up."""


def run_cancelling_on_hangup[T](main: Coroutine[Any, Any, T]) -> T:
    """``asyncio.run(main)``, cancelled by ``SIGHUP`` as it is by ``SIGINT``.

    Outside the main thread, or where the platform has no ``SIGHUP``, this is plain
    ``asyncio.run``.
    """

    hangup = getattr(signal, "SIGHUP", None)

    async def runner() -> T:
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        hung_up = False

        def on_hangup() -> None:
            nonlocal hung_up
            hung_up = True
            if task is not None:
                task.cancel()

        installed = False
        if hangup is not None:
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(hangup, on_hangup)
                installed = True
        try:
            return await main
        except asyncio.CancelledError:
            if hung_up:
                raise _HungUp from None
            raise
        finally:
            if installed and hangup is not None:
                loop.remove_signal_handler(hangup)

    try:
        return asyncio.run(runner())
    except _HungUp:
        raise SystemExit(HANGUP_EXIT_STATUS) from None


__all__ = ["HANGUP_EXIT_STATUS", "run_cancelling_on_hangup"]
