"""Hold a step on its event loop until another thread opens a gate.

A test that stands a stub in for an awaited step, a ``gh`` read, a fetch, or a refresh,
often holds it until the test thread has asked the server something: the stub waits on a
``threading.Event`` the test sets. Waiting there in ``asyncio.to_thread(gate.wait)``
keeps one of the loop's default-executor threads for the whole hold, which the step the
stub stands in for does not: it awaits pipes or sockets on the loop. The server's own
next step can then find no thread. The same goes for a test's own coroutine that waits
for a signal from work running in the pool, such as a stub's ``entered.set()`` from a
worker thread: its wait shares the pool with that work.

CPython's ``ThreadPoolExecutor`` can count an idle thread that is not there: a job
submitted while a worker has found its queue empty, but not yet counted itself idle,
starts a thread; the worker takes the job, and the new thread counts itself idle too.
The next job to spend that count starts no thread, so with every live thread held it
waits behind them, for a gate the test opens only once the request that submitted it has
answered. That hung a selected core's ``POST pull-refresh`` on 3.14t (mb-xorh).
:func:`held_until` waits on the loop instead and keeps no thread;
``tests/test_suite_gates.py`` fails on a test module that hands a gate's ``wait`` or
``acquire`` to a worker thread, and ``tests/test_loop_gate.py`` holds the helper.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Final

# How often a step held by :func:`held_until` looks at its gate. A look is one turn of
# the loop, and a release waits for the next look, so this is what a release adds to the
# step's latency: against the 0.3 to 0.4 s a selected-core scenario of
# tests/test_github_pulls.py took on 3.14t (2026-11-17).
HELD_POLL_S: Final = 0.005


async def held_until(
    gate: threading.Event | threading.Semaphore, timeout_s: float | None = None
) -> bool:
    """Hold the calling step on its event loop until another thread opens *gate*.

    The step is a stub or a test's own coroutine. An ``Event`` opens once it is set, and
    the answer is what ``gate.wait(timeout_s)`` would return. A ``Semaphore`` opens once
    this step takes one of its permits, and the answer is what
    ``gate.acquire(timeout=timeout_s)`` would return. Either way no worker thread is kept
    while the step waits.

    Several steps held on one ``Semaphore`` take its permits in whatever order they next
    look, unlike threads blocked in ``acquire``, which are woken oldest first. A caller
    whose order matters holds one step at a time.
    """

    def opened() -> bool:
        if isinstance(gate, threading.Event):
            return gate.is_set()
        return gate.acquire(blocking=False)

    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    while not opened():
        if deadline is not None and time.monotonic() >= deadline:
            return False
        await asyncio.sleep(HELD_POLL_S)
    return True
