"""Concurrency behavior of the shared immutable loading cache."""

import asyncio
from collections.abc import Awaitable, Callable

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


def test_a_weight_bound_keeps_the_most_recently_used_values_under_it() -> None:
    async def run() -> None:
        cache = LoadingCache[str, bytes](max_values=100, max_weight=10, weigh=len)

        def loader(value: bytes) -> Callable[[], Awaitable[bytes]]:
            async def load() -> bytes:
                return value

            return load

        await cache.get("a", loader(b"aaaa"))
        await cache.get("b", loader(b"bbbb"))
        assert cache.weight == 8
        assert cache.kept("a") is not None  # now the most recently used
        await cache.get("c", loader(b"cccc"))
        assert cache.kept("b") is None, "the least recently used value goes first"
        assert cache.kept("a") is not None and cache.kept("c") is not None
        assert cache.weight == 8
        # Heavier than the whole bound: returned, not kept, and nothing else evicted.
        assert await cache.get("big", loader(b"x" * 11)) == b"x" * 11
        assert cache.kept("big") is None
        assert cache.weight == 8

    asyncio.run(run())


def test_a_weight_bound_needs_its_weigh_function() -> None:
    with pytest.raises(ValueError, match="together"):
        LoadingCache[str, bytes](max_values=1, max_weight=10)
