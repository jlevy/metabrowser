"""``held_until`` answers as the blocking wait it replaces would, and keeps no thread.

Every caller's gate opens in a passing run, so these are the only tests of the paths
where it does not: the bound, and a permit already taken.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from tests.loop_gate import held_until


def test_an_event_answers_as_its_wait_would() -> None:
    async def scenario() -> tuple[bool, bool, bool, float]:
        unset, opened = threading.Event(), threading.Event()
        opened.set()
        began = time.monotonic()
        timed_out = await held_until(unset, 0.05)
        waited = time.monotonic() - began
        return timed_out, await held_until(opened, 0.05), await held_until(opened), waited

    timed_out, opened, unbounded, waited = asyncio.run(scenario())
    assert (timed_out, opened, unbounded) == (False, True, True)
    assert waited >= 0.05, "the hold gave up before its bound"


def test_a_semaphore_answers_as_its_acquire_would_and_takes_the_permit() -> None:
    async def scenario() -> tuple[bool, bool, bool]:
        slot = threading.Semaphore(1)
        return await held_until(slot, 0.01), await held_until(slot, 0.01), slot.acquire(False)

    assert asyncio.run(scenario()) == (True, False, False)


class _RefusingPool(ThreadPoolExecutor):
    """A default executor that fails any job handed to it."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        raise AssertionError(f"a worker thread was asked for {fn!r}")


def test_a_gate_opened_by_another_thread_ends_the_hold_without_a_worker() -> None:
    async def scenario() -> bool:
        asyncio.get_running_loop().set_default_executor(_RefusingPool(max_workers=1))
        gate = threading.Event()
        opener = threading.Timer(0.02, gate.set)
        opener.start()
        try:
            return await held_until(gate, 5)
        finally:
            opener.join(5)

    assert asyncio.run(scenario()) is True
