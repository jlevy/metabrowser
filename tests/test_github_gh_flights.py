"""Overlapping validated GitHub CLI reads and their subprocess ownership."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh

_PATH = "repos/octo/demo/commits/abc/status"
_QUERY = "query Page($cursor: String) { viewer { login } }"
_OK = gh._Completed(0, b'HTTP/2.0 200 OK\r\n\r\n{"data":{"ok":true}}', b"")


@dataclass
class _Request:
    args: tuple[str, ...]
    max_bytes: int
    release: asyncio.Event = field(default_factory=asyncio.Event)
    error: gh.GhError | None = None


class _Runner:
    def __init__(self) -> None:
        self.requests: list[_Request] = []
        self.teardown_started = asyncio.Event()
        self.finish_teardown = asyncio.Event()

    async def __call__(
        self, args: Sequence[str], *, max_bytes: int, **_options: object
    ) -> gh._Completed:
        request = _Request(tuple(args), max_bytes)
        self.requests.append(request)
        try:
            await request.release.wait()
        except asyncio.CancelledError:
            self.teardown_started.set()
            await self.finish_teardown.wait()
            raise
        if request.error is not None:
            raise request.error
        if request.args[:2] == ("auth", "status"):
            return gh._Completed(
                0, b'{"hosts":{"github.com":[{"active":true,"login":"octo"}]}}', b""
            )
        if 'If-None-Match: "x"' in args:
            return gh._Completed(1, b"HTTP/2.0 304 Not Modified\r\n\r\n", b"")
        return _OK


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> _Runner:
    monkeypatch.setenv("GH_TOKEN", "fixture-a")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(gh, "gh_executable", lambda: "/fixture/gh")
    runner = _Runner()
    monkeypatch.setattr(gh, "_run", runner)
    return runner


async def _schedule() -> None:
    # The read task registers, then its producer can start.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.parametrize("eager", [False, True])
def test_identical_reads_share_output_but_parse_independently(runner: _Runner, eager: bool) -> None:
    async def check() -> None:
        if eager:
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        first = asyncio.create_task(gh.gh_api(_PATH))
        second = asyncio.create_task(gh.gh_api(_PATH, now=datetime(2026, 1, 1, tzinfo=UTC)))
        await _schedule()
        for request in runner.requests:
            request.release.set()
        left, right = await asyncio.gather(first, second)
        assert len(runner.requests) == 1
        assert left == right
        assert left is not right and left.headers is not right.headers
        third = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        assert len(runner.requests) == 2
        runner.requests[-1].release.set()
        assert await third == left

    asyncio.run(check())


def test_conditional_reads_cursors_types_and_limits_are_distinct(runner: _Runner) -> None:
    async def check() -> None:
        reads = (
            asyncio.create_task(gh.gh_api(_PATH)),
            asyncio.create_task(gh.gh_api(_PATH, etag='"x"')),
            asyncio.create_task(gh.gh_api(_PATH, etag='"x"')),
        )
        queries = (
            asyncio.create_task(gh.gh_graphql(_QUERY, {"cursor": "1"})),
            asyncio.create_task(gh.gh_graphql(_QUERY, {"cursor": "1"})),
            asyncio.create_task(gh.gh_graphql(_QUERY, {"cursor": "2"})),
            asyncio.create_task(gh.gh_graphql(_QUERY, {"cursor": 1})),
            asyncio.create_task(gh.gh_graphql(_QUERY, {"cursor": "1"}, max_bytes=100)),
        )
        await _schedule()
        for request in runner.requests:
            request.release.set()
        responses = await asyncio.gather(*reads)
        results = await asyncio.gather(*queries)
        assert [response.status for response in responses] == [200, 304, 304]
        assert results == [{"ok": True}] * 5 and results[0] is not results[1]
        assert len(runner.requests) == 6

    asyncio.run(check())


def test_changed_or_unproven_credentials_do_not_share(
    runner: _Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check() -> None:
        first = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        monkeypatch.setenv("GH_TOKEN", "fixture-b")
        second = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        monkeypatch.delenv("GH_TOKEN")
        remaining = [asyncio.create_task(gh.gh_api(_PATH)) for _ in range(2)]
        await _schedule()
        for request in runner.requests:
            request.release.set()
        await asyncio.gather(first, second, *remaining)
        assert len(runner.requests) == 4

    asyncio.run(check())


def test_generic_commands_and_account_probes_stay_independent(runner: _Runner) -> None:
    async def check() -> None:
        probes = [asyncio.create_task(gh.gh_account()) for _ in range(2)]
        commands = [asyncio.create_task(gh.run_gh(["api", _PATH])) for _ in range(2)]
        await _schedule()
        for request in runner.requests:
            request.release.set()
        assert await asyncio.gather(*probes) == ["octo", "octo"]
        assert await asyncio.gather(*commands) == [_OK.stdout, _OK.stdout]
        assert len(runner.requests) == 4

    asyncio.run(check())


def test_cancelling_one_waiter_leaves_the_other_waiting(runner: _Runner) -> None:
    async def check() -> None:
        first = asyncio.create_task(gh.gh_api(_PATH))
        second = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        first.cancel()
        runner.finish_teardown.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        for request in runner.requests:
            request.release.set()
        assert (await second).status == 200
        assert len(runner.requests) == 1
        assert not runner.teardown_started.is_set()

    asyncio.run(check())


def test_last_waiter_keeps_key_until_teardown(runner: _Runner) -> None:
    async def check() -> None:
        first = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        first.cancel()
        await runner.teardown_started.wait()
        retry = asyncio.create_task(gh.gh_api(_PATH))
        try:
            await _schedule()
            assert len(runner.requests) == 1
        finally:
            runner.finish_teardown.set()
            for request in runner.requests:
                request.release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        await _schedule()
        assert len(runner.requests) == 2
        runner.requests[-1].release.set()
        assert (await retry).status == 200

    asyncio.run(check())


def test_shared_typed_failure_leaves_the_key_retryable(runner: _Runner) -> None:
    async def check() -> None:
        waiters = [asyncio.create_task(gh.gh_api(_PATH)) for _ in range(2)]
        await _schedule()
        (request,) = runner.requests
        request.error = gh.GhError("timed out", state="network_error")
        request.release.set()
        for waiter in waiters:
            with pytest.raises(gh.GhError) as error:
                await waiter
            assert error.value.state == "network_error"
        retry = asyncio.create_task(gh.gh_api(_PATH))
        await _schedule()
        assert len(runner.requests) == 2
        runner.requests[-1].release.set()
        assert (await retry).status == 200

    asyncio.run(check())


def test_last_waiter_reaps_a_child_still_spawning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "fixture-a")
    monkeypatch.setattr(gh, "gh_executable", lambda: sys.executable)
    real_spawn = asyncio.create_subprocess_exec

    async def check() -> None:
        started = asyncio.Event()
        return_child = asyncio.Event()
        children: list[asyncio.subprocess.Process] = []

        async def paused_spawn(*_args: str, **kwargs: Any) -> asyncio.subprocess.Process:
            child = await real_spawn(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
            children.append(child)
            started.set()
            await return_child.wait()
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", paused_spawn)
        waiter = asyncio.create_task(gh.gh_api(_PATH))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            waiter.cancel()
            await _schedule()
            assert not waiter.done()
        finally:
            return_child.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, timeout=5)
        (child,) = children
        assert child.returncode is not None

    asyncio.run(check())
