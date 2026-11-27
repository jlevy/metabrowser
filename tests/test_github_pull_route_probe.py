"""The refresh route's probe branch: a visible page's automatic ask probes the record held.

The probe itself is :func:`.pulls.probe_pull_request` and its cadence :class:`.ServedPull`'s
(``tests/test_github_pull_freshness.py``). This is what the route makes of them: a probe
that finds nothing answers ``not_due``, one that finds a change starts the full read, a
probe slower than ``PROBE_WAIT_S`` answers ``not_due`` and goes on, a record the server
holds no longer is not probed, and the envelope is vouched for only by a probe of the very
record it carries (:func:`.pull_route.probed_at`).
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from metabrowser.builtin_plugins.github import gh_budget, pulls, served_pull
from metabrowser.builtin_plugins.github.pull_freshness import RecordFreshness
from metabrowser.builtin_plugins.github.pull_record import PullRecord
from metabrowser.builtin_plugins.github.pull_route import (
    PullHost,
    PullView,
    RefreshRequest,
    probed_at,
    start_refresh,
)
from metabrowser.builtin_plugins.github.served_pull import (
    ATTENDED_PROBE_S,
    FULL_REFRESH_S,
    ServedPull,
    ServedPulls,
)
from metabrowser.mirror_refresh import RefreshAsk, RefreshCoordinator
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import stand as stand


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


class _Route:
    """A server holding pull request 7's record, whose automatic asks the test sends."""

    def __init__(self, stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
        self.record = stand.refresh(7)
        self.held = ServedPull(stand.published, 7)
        self.held.saw_record(self.record.fetched_at)
        self.started: list[int] = []
        self.probes: list[PullRecord] = []
        self.answers: list[pulls.PullProbe] = []
        self.release: asyncio.Event | None = None
        kept = ServedPulls(stand.published, _kept=OrderedDict({7: self.held}))
        self.host = PullHost(kept, lambda _number: False, self._start)
        self.now = _parse(self.record.fetched_at) + timedelta(seconds=1)
        monkeypatch.setattr(pulls, "utc_now", lambda: self.now)
        monkeypatch.setattr(pulls, "probe_pull_request", self._probe)

    def _start(self, number: int, _ask: RefreshAsk) -> Any:
        self.started.append(number)
        return "started"

    async def _probe(self, _published: object, record: PullRecord, **_kwargs: object) -> Any:
        self.probes.append(record)
        if self.release is not None:
            await self.release.wait()
        return self.answers.pop(0)

    def ask(self) -> str:
        return asyncio.run(start_refresh(self.host, RefreshRequest(7, False)))


def test_an_unchanged_probe_answers_not_due_and_a_change_starts_the_full_read(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = _Route(stand, monkeypatch)
    route.answers.append(pulls.PullProbe("unchanged", {}))
    assert route.ask() == "not_due"
    assert len(route.probes) == 1 and route.started == []
    assert route.held.probed_at is not None
    route.now += timedelta(seconds=ATTENDED_PROBE_S)
    route.answers.append(pulls.PullProbe("changed", {}))
    assert route.ask() == "started"
    assert len(route.probes) == 2 and route.started == [7]


def test_a_probe_slower_than_probe_wait_s_answers_not_due_and_ends_on_its_own(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = _Route(stand, monkeypatch)
    monkeypatch.setattr(served_pull, "PROBE_WAIT_S", 0.01)
    route.answers.append(pulls.PullProbe("unchanged", {}))

    async def run() -> None:
        route.release = asyncio.Event()
        assert await start_refresh(route.host, RefreshRequest(7, False)) == "not_due"
        # The wait gave up; the probe did not, and what it finds is kept.
        assert route.held.probing and route.started == []
        route.release.set()
        task = route.held._probe_task  # pyright: ignore[reportPrivateUsage]
        assert task is not None
        await task

    asyncio.run(run())
    assert route.held.probed_at is not None


def test_a_record_the_server_no_longer_holds_is_not_probed(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server holds a newer record than the one on disk: no probe of the older one."""

    route = _Route(stand, monkeypatch)
    newer = _parse(route.record.fetched_at) + timedelta(seconds=1)
    route.held.saw_record(newer.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert route.ask() == "not_due"
    assert route.probes == [] and route.started == []


def test_the_envelope_is_vouched_for_only_by_a_probe_of_the_record_it_carries(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = _Route(stand, monkeypatch)
    route.answers.append(pulls.PullProbe("unchanged", {}))
    assert route.ask() == "not_due"
    record, held, now = route.record, route.held, route.now
    view = cast("PullView", SimpleNamespace(kept=held))

    def vouched(
        of: PullRecord = record,
        at: datetime = now,
        *,
        has_store: bool = False,
        freshness: RecordFreshness | None = None,
    ) -> str | None:
        return probed_at(view, of, now=at, has_store=has_store, freshness=freshness)

    assert vouched() == held.probed_at
    # Another record than the one probed.
    older = record.model_copy(update={"fetched_at": "2000-01-01T00:00:00Z"})
    assert vouched(older) is None
    # A record whose full read is overdue, whatever the probes say: one probed a second
    # ago, which vouches for it on its own, does not (review B9 on #709).
    later = now + timedelta(seconds=FULL_REFRESH_S + 1)
    probed, held.probed_at = (
        held.probed_at,
        (later - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    assert held.probe_vouches(later)
    assert vouched(at=later) is None
    held.probed_at = probed
    # One the catalog says GitHub changed since.
    changed = cast("RecordFreshness", SimpleNamespace(verdict="changed"))
    assert vouched(freshness=changed) is None
    # One written with no store, on a server that has one.
    storeless = record.model_copy(update={"comparison": None})
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_route.written_without_store",
        lambda candidate: candidate is storeless,
    )
    assert vouched(storeless, has_store=True) is None
    assert vouched(record, has_store=True) == held.probed_at


def test_below_the_floor_an_overdue_full_read_waits_while_probes_vouch_and_find_changes(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-qngw: the ask that would start the ``FULL_REFRESH_S`` read probes instead, the
    envelope stays vouched for so the page keeps asking, and a change is read at once."""

    route = _Route(stand, monkeypatch)
    route.now += timedelta(seconds=FULL_REFRESH_S + 1)
    gh_budget.observe(
        {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "40",
            "x-ratelimit-reset": str(int((route.now + timedelta(hours=1)).timestamp())),
        },
        resource="core",
    )
    route.answers.append(pulls.PullProbe("unchanged", {}))
    assert route.ask() == "not_due"
    assert len(route.probes) == 1 and route.started == []
    view = cast("PullView", SimpleNamespace(kept=route.held))
    assert route.held.full_read_overdue(route.now)
    vouched = probed_at(view, route.record, now=route.now, has_store=False, freshness=None)
    assert vouched is not None and vouched == route.held.probed_at
    route.now += timedelta(seconds=ATTENDED_PROBE_S)
    route.answers.append(pulls.PullProbe("changed", {}))
    assert route.ask() == "started"
    assert route.started == [7]
    # Above the floor the same overdue record is read in full without a probe.
    gh_budget.forget()
    above = _Route(stand, monkeypatch)
    above.now += timedelta(seconds=FULL_REFRESH_S + 1)
    assert above.ask() == "started" and above.probes == []


def test_an_automatic_ask_past_the_cap_on_probes_in_flight_answers_not_due(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-et0k: the page asks again at its next interval; nothing queues."""

    route = _Route(stand, monkeypatch)
    monkeypatch.setattr(served_pull, "MAX_PROBES_IN_FLIGHT", 0)
    assert route.ask() == "not_due"
    assert route.probes == [] and route.started == []


def test_a_served_probe_is_the_coordinators_job_and_a_one_shots_drain_waits_for_it(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: the route hands the probe the host's coordinator. Without it nothing a served
    probe does is cancelled at shutdown, and a one-shot command ends before its probe."""

    route = _Route(stand, monkeypatch)
    monkeypatch.setattr(served_pull, "PROBE_WAIT_S", 0.01)
    route.answers.append(pulls.PullProbe("unchanged", {}))

    async def run() -> None:
        coordinator = RefreshCoordinator()
        host = PullHost(
            route.host.pulls, route.host.running, route.host.start, coordinator=coordinator
        )
        route.release = asyncio.Event()
        assert await start_refresh(host, RefreshRequest(7, False)) == "not_due"
        assert coordinator.running(route.held.probe_key) and route.held.probing
        draining = asyncio.ensure_future(coordinator.drain(timeout_s=30))
        await asyncio.sleep(0.05)
        assert not draining.done() and route.held.probed_at is None
        route.release.set()
        await draining
        assert route.held.probed_at is not None and not route.held.probing
        await coordinator.aclose()

    asyncio.run(run())


def test_an_automatic_ask_of_a_server_that_is_shutting_down_answers_not_due(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A7: its coordinator has closed, and the ask raised where it now starts nothing."""

    route = _Route(stand, monkeypatch)

    async def run() -> str:
        coordinator = RefreshCoordinator()
        await coordinator.aclose()
        host = PullHost(
            route.host.pulls, route.host.running, route.host.start, coordinator=coordinator
        )
        return await start_refresh(host, RefreshRequest(7, False))

    assert asyncio.run(run()) == "not_due"
    assert route.probes == [] and route.started == []
