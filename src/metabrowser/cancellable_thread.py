"""Cancellation bridges for blocking work on asyncio threads."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from contextlib import suppress
from threading import Event

log = logging.getLogger(__name__)


async def run_cancellable_thread[ResultT](work: Callable[[Event], ResultT], /) -> ResultT:
    """Run blocking work and signal it to finish before propagating cancellation."""
    cancel_event = Event()
    worker = asyncio.create_task(asyncio.to_thread(work, cancel_event))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancel_event.set()
        # Preserve the caller's cancellation after giving the worker a chance
        # to leave the executor; its cleanup result is no longer actionable.
        with suppress(Exception, asyncio.CancelledError):
            await worker
        raise


async def run_acquiring_thread[ResultT](
    work: Callable[[], ResultT], /, *, release: Callable[[ResultT], None]
) -> ResultT:
    """Run blocking work that acquires something, and release it if no one receives it.

    A thread cannot be interrupted, so when the awaiting task is cancelled while *work*
    is still running, what *work* goes on to acquire — a file lock, a claimed staging
    entry — would otherwise belong to no one until the process exits. Cancellation
    propagates at once; when *work* finishes, its result goes to *release* in a worker
    thread, so the release does not run file-system work on the event loop either.
    """

    worker = asyncio.ensure_future(asyncio.to_thread(work))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        worker.add_done_callback(functools.partial(_release_unreceived, release))
        raise


def _release_unreceived[ResultT](
    release: Callable[[ResultT], None], worker: asyncio.Future[ResultT]
) -> None:
    if worker.cancelled() or worker.exception() is not None:
        return
    result = worker.result()
    try:
        released = asyncio.get_running_loop().run_in_executor(None, release, result)
    except RuntimeError:
        # The loop or its executor is shutting down; release here rather than never.
        release(result)
        return
    released.add_done_callback(_log_release_failure)


def _log_release_failure(released: asyncio.Future[None]) -> None:
    if not released.cancelled() and (error := released.exception()) is not None:
        log.warning("could not release work abandoned by a cancelled task", exc_info=error)


__all__ = ["run_acquiring_thread", "run_cancellable_thread"]
