"""Treat a terminal hangup or a termination request like Ctrl-C while the CLI acquires.

Acquisition Git runs as the leader of its own process group, so that a timeout or a
cancellation can kill the helpers it forks. That also takes it out of the terminal's
foreground group: when the terminal hangs up, ``SIGHUP`` reaches only this process, and
``kill <pid>`` sends ``SIGTERM`` to it alone. Left at their default action, Python would
die on the spot and orphan Git and its helpers, still fetching into staging.
:func:`run_cancelling_on_hangup` instead cancels the main task, as ``asyncio.run`` does
for ``SIGINT``; the cancellation kills Git's process group on its way out, and the
process then exits with 128 plus the signal number, the status a shell reports for it
(mb-163x).

A signal the process inherited as ignored stays ignored, so ``nohup metab …`` keeps
acquiring after the terminal closes, and whatever handler was installed before is put
back afterwards.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Callable, Coroutine
from types import FrameType
from typing import Any, Final

HANGUP_EXIT_STATUS: Final[int] = 129
TERMINATION_EXIT_STATUS: Final[int] = 143
_CANCELLING_SIGNALS: Final[tuple[tuple[str, int], ...]] = (
    ("SIGHUP", HANGUP_EXIT_STATUS),
    ("SIGTERM", TERMINATION_EXIT_STATUS),
)

type _Handler = Callable[[int, FrameType | None], Any] | int | None


class _Stopped(Exception):
    """The main task was cancelled because a cancelling signal arrived."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def _cancelling_signals() -> list[tuple[signal.Signals, int]]:
    found: list[tuple[signal.Signals, int]] = []
    for name, status in _CANCELLING_SIGNALS:
        number = getattr(signal, name, None)
        if isinstance(number, signal.Signals):
            found.append((number, status))
    return found


def run_cancelling_on_hangup[T](main: Coroutine[Any, Any, T]) -> T:
    """``asyncio.run(main)``, cancelled by ``SIGHUP`` or ``SIGTERM`` as by ``SIGINT``.

    A signal that is ignored on entry is left alone. Outside the main thread, or where
    the platform has neither signal, this is plain ``asyncio.run``.
    """

    async def runner() -> T:
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        received: list[int] = []

        def on_signal(status: int) -> None:
            if not received:
                received.append(status)
                if task is not None:
                    task.cancel()

        installed: list[tuple[signal.Signals, _Handler]] = []
        for number, status in _cancelling_signals():
            try:
                previous: _Handler = signal.getsignal(number)
            except ValueError:
                continue
            if previous == signal.SIG_IGN:
                continue
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(number, on_signal, status)
                installed.append((number, previous))
        try:
            return await main
        except asyncio.CancelledError:
            if received:
                raise _Stopped(received[0]) from None
            raise
        finally:
            for number, previous in installed:
                loop.remove_signal_handler(number)
                if previous is not None:
                    signal.signal(number, previous)

    try:
        return asyncio.run(runner())
    except _Stopped as stopped:
        raise SystemExit(stopped.status) from None


__all__ = ["HANGUP_EXIT_STATUS", "TERMINATION_EXIT_STATUS", "run_cancelling_on_hangup"]
