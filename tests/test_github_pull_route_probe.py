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

from metabrowser.builtin_plugins.github import pulls, served_pull
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

    def _start(self, number: int) -> Any:
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
    # A record whose full read is overdue, whatever the probes say.
    assert vouched(at=now + timedelta(seconds=FULL_REFRESH_S + 1)) is None
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
