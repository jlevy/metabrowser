"""Bounded shared loads for immutable values on one event loop."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from functools import partial


class LoadingCacheBusyError(Exception):
    """All producer slots are occupied by different keys."""


class LoadingCache[K: Hashable, V]:
    """Return a ready value or share one producer. Cancelling a waiter is local."""

    def __init__(self, *, max_values: int, max_loads: int | None = None) -> None:
        self._max_values = max_values
        self._max_loads = max_loads
        self._ready: OrderedDict[K, V] = OrderedDict()
        self._loading: dict[K, asyncio.Task[V]] = {}

    async def get(self, key: K, load: Callable[[], Awaitable[V]]) -> V:
        if key in self._ready:
            self._ready.move_to_end(key)
            return self._ready[key]
        task = self._loading.get(key)
        if task is None:
            if self._max_loads is not None and len(self._loading) >= self._max_loads:
                raise LoadingCacheBusyError

            async def produce() -> V:
                # Register ownership first, including under eager task factories.
                await asyncio.sleep(0)
                return await load()

            task = asyncio.create_task(produce())
            self._loading[key] = task
            task.add_done_callback(partial(self._finished, key))
        await asyncio.wait((task,))
        return task.result()

    def _finished(self, key: K, task: asyncio.Task[V]) -> None:
        del self._loading[key]
        if task.cancelled() or task.exception() is not None:
            return
        self._ready[key] = task.result()
        if len(self._ready) > self._max_values:
            self._ready.popitem(last=False)
