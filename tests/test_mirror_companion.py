"""The mirror session with data served beside it: turns, staleness, and following.

A fake mirror and a fake companion drive the real :class:`MirrorSession` and
:class:`RefreshCoordinator`, so the order of jobs is observed without Git or gh.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import (
    MirrorSession,
    RecordedFreshness,
    RefreshCoordinator,
    RefreshResult,
)
from metabrowser.repository_context import RepositoryContext
from metabrowser.source import reset_source_session

_OLD = "2020-01-01T00:00:00Z"


@pytest.fixture(autouse=True)
def _no_session_left() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Observing reads the process's source session; leave none behind for later tests."""

    yield
    reset_source_session()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Mirror:
    key = "store"

    def __init__(
        self,
        events: list[str],
        *,
        fetched_at: str | None = _OLD,
        busy_at: str | None = None,
        recorded_at: str | None = None,
    ) -> None:
        self.events = events
        self.fetched_at = fetched_at
        self.busy_at = busy_at
        self.recorded_at = recorded_at

    async def open_selection(self, *, ref: str | None, oid: str | None) -> GitRevisionSubject:
        raise AssertionError("not reached")

    async def refresh(self) -> RefreshResult:
        self.events.append("mirror")
        if self.busy_at is not None:
            return RefreshResult("refreshing_elsewhere", self.busy_at)
        return RefreshResult("succeeded", _now())

    async def recorded_freshness(self) -> RecordedFreshness:
        if self.recorded_at is None:
            return RecordedFreshness(self.fetched_at, None, None, None)
        return RecordedFreshness(self.fetched_at, "refresh", "succeeded", self.recorded_at)

    async def ref_tip(self, ref: str) -> str | None:
        return None

    async def refresh_running_elsewhere(self) -> bool:
        return False

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        return None


class _Companion:
    key = "store:pull/7"

    def __init__(self, events: list[str], *, stale: bool) -> None:
        self.events = events
        self.stale = stale
        self.gate: asyncio.Event | None = None
        self.started = asyncio.Event()

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        return self.stale

    async def refresh(self) -> None:
        self.events.append("pull start")
        self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        self.events.append("pull end")


async def _settle(coordinator: RefreshCoordinator) -> None:
    # A job can start another as it ends, as a refresh that follows another process's.
    for _ in range(3):
        await coordinator.drain(timeout_s=5)
    await coordinator.aclose()


def test_the_mirror_waits_its_turn_behind_the_pull_requests_fetch() -> None:
    """Within one server the two fetches take turns instead of finding the lock held."""

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        companion = _Companion(events, stale=True)
        companion.gate = asyncio.Event()
        session = MirrorSession(_Mirror(events), coordinator, companion=companion)
        session.request_companion_refresh()
        await companion.started.wait()
        session.request_refresh(for_selection=True)
        for _ in range(10):
            await asyncio.sleep(0)
        assert events == ["pull start"], "the mirror's fetch must wait for the pull request's"
        companion.gate.set()
        await _settle(coordinator)
        return events

    assert asyncio.run(scenario()) == ["pull start", "pull end", "mirror"]


@pytest.mark.parametrize(
    ("serving", "mirror_fresh", "pull_stale", "for_selection", "expected"),
    [
        (True, True, True, False, ["pull start", "pull end"]),
        (True, False, False, False, ["mirror"]),
        (True, False, True, False, ["mirror", "pull start", "pull end"]),
        (True, True, True, True, ["mirror"]),
        # A one-shot command asked for the mirror's refresh, fresh or not.
        (False, True, True, False, ["mirror", "pull start", "pull end"]),
    ],
)
def test_a_refresh_fetches_only_what_is_stale_and_a_pin_miss_only_the_mirror(
    serving: bool, mirror_fresh: bool, pull_stale: bool, for_selection: bool, expected: list[str]
) -> None:
    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _Mirror(events, fetched_at=_now() if mirror_fresh else _OLD)
        session = MirrorSession(
            mirror,
            coordinator,
            fetch_on_miss=serving,
            companion=_Companion(events, stale=pull_stale),
        )
        await session.observe()
        session.request_refresh(for_selection=for_selection)
        await _settle(coordinator)
        return events

    assert sorted(asyncio.run(scenario())) == sorted(expected)
