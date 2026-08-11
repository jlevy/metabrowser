"""Cancellation bridge for cooperative blocking work on asyncio threads."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from threading import Event


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
