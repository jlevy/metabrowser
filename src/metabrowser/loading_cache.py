"""Shared loads of immutable values on one event loop.

A caller asks for a key's value with the coroutine that produces it. A ready value is
returned at once, a load already running is joined, and otherwise this call's load starts
and later callers join it. Cancelling a waiter cancels only that waiter: the load goes on
for the others and finishes even when every waiter has gone. A failed or cancelled load
keeps nothing, so the next call loads again.

What is kept is bounded by a count and, given a *weigh* function, by a total weight too:
the least recently used values go first, and a value heavier than the whole bound is
returned to its callers and not kept.

Not specific to the repository cache: the GitHub plugin shares a comparison's manifest
load this way, and a revision page's Markdown render; ``encoded_assets`` keeps the
application's own assets in memory by their bytes.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from functools import partial


class LoadingCache[K: Hashable, V]:
    """Return a ready value or share one producer, keeping at most *max_values* values.

    With *weigh*, the kept values' weights also stay at or under *max_weight*.
    """

    def __init__(
        self,
        *,
        max_values: int,
        max_weight: int | None = None,
        weigh: Callable[[V], int] | None = None,
    ) -> None:
        if (max_weight is None) != (weigh is None):
            raise ValueError("max_weight and weigh are given together")
        self._max_values = max_values
        self._max_weight = max_weight
        self._weigh = weigh
        self._ready: OrderedDict[K, V] = OrderedDict()
        self._weights: dict[K, int] = {}
        self._weight = 0
        self._loading: dict[K, asyncio.Task[V]] = {}

    @property
    def weight(self) -> int:
        """The total weight of the values kept now; 0 without *weigh*."""
        return self._weight

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
        value = task.result()
        weight = 0 if self._weigh is None else self._weigh(value)
        if self._max_weight is not None and weight > self._max_weight:
            return
        self._ready[key] = value
        self._weights[key] = weight
        self._weight += weight
        while len(self._ready) > self._max_values or (
            self._max_weight is not None and self._weight > self._max_weight
        ):
            evicted, _value = self._ready.popitem(last=False)
            self._weight -= self._weights.pop(evicted)


__all__ = ["LoadingCache"]
