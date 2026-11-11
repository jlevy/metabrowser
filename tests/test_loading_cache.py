"""Concurrency behavior of the bounded immutable loading cache."""

import asyncio

import pytest

from metabrowser.cache.loading import LoadingCache, LoadingCacheBusyError


def test_loading_cache_shares_one_producer_and_keeps_different_keys_independent() -> None:
    async def run() -> None:
        cache = LoadingCache[str, int](max_values=1, max_loads=2)
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
        with pytest.raises(LoadingCacheBusyError):
            await cache.get("full", load)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        finish.set()
        assert await joined == await other == 2
        assert await cache.get("other", load) == 2
        assert calls == 2

    asyncio.run(run())
