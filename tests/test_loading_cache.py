"""Concurrency behavior of the shared immutable loading cache."""

import asyncio

import pytest

from metabrowser.loading_cache import LoadingCache


def test_loading_cache_shares_one_producer_and_keeps_different_keys_independent() -> None:
    async def run() -> None:
        cache = LoadingCache[str, int](max_values=1)
        started, finish = asyncio.Event(), asyncio.Event()
        calls = 0

        async def load() -> int:
            nonlocal calls
            calls += 1
            started.set()
            await finish.wait()
            return calls

        cancelled = asyncio.create_task(cache.get("same", load))
        await started.wait()
        joined = asyncio.create_task(cache.get("same", load))
        other = asyncio.create_task(cache.get("other", load))
        await asyncio.sleep(0)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        finish.set()
        assert await joined == await other == 2
        assert await cache.get("other", load) == 2
        assert calls == 2

    asyncio.run(run())


def test_a_failed_load_keeps_nothing_and_the_next_call_loads_again() -> None:
    async def run() -> None:
        cache = LoadingCache[str, int](max_values=0)
        calls = 0

        async def load() -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("first load fails")
            return calls

        with pytest.raises(ValueError, match="first load fails"):
            await cache.get("key", load)
        assert await cache.get("key", load) == 2
        assert await cache.get("key", load) == 3, "max_values=0 keeps no value"

    asyncio.run(run())
