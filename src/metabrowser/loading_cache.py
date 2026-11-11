"""Shared loads of immutable values on one event loop.

A caller asks for a key's value with the coroutine that produces it. A ready value is
returned at once, a load already running is joined, and otherwise this call's load starts
and later callers join it. Cancelling a waiter cancels only that waiter: the load goes on
for the others and finishes even when every waiter has gone. A failed or cancelled load
keeps nothing, so the next call loads again.

Not specific to the repository cache: the GitHub plugin shares a comparison's manifest
load this way, and a revision page's Markdown render.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from functools import partial


class LoadingCache[K: Hashable, V]:
    """Return a ready value or share one producer, keeping at most *max_values* values."""

    def __init__(self, *, max_values: int) -> None:
        self._max_values = max_values
        self._ready: OrderedDict[K, V] = OrderedDict()
        self._loading: dict[K, asyncio.Task[V]] = {}

    def kept(self, key: K) -> tuple[V] | None:
        """The value kept for *key*, in a tuple, or ``None`` when none is kept. Starts nothing."""
        if key not in self._ready:
            return None
        self._ready.move_to_end(key)
        return (self._ready[key],)

    async def get(self, key: K, load: Callable[[], Awaitable[V]]) -> V:
        if key in self._ready:
            self._ready.move_to_end(key)
            return self._ready[key]
        task = self._loading.get(key)
        if task is None:

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


__all__ = ["LoadingCache"]
