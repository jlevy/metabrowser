"""The prefetch lane: what it runs, in what order, and where it stops.

``tests/test_cli_github_pulls_prefetch_golden.py`` runs the route through the CLI with the
fake ``gh``; these drive the lane over a fake host on the real coordinator, so the caps,
the governor, a reader's work, and preemption are each pinned without Git.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import (
    gh_budget,
    pull_files_route,
    pull_prefetch,
    pull_route,
    pulls,
)
from metabrowser.builtin_plugins.github.pull_freshness import RecordFreshness
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_prefetch import (
    FILES_PER_HOUR,
    RECORDS_PER_HOUR,
    RECORDS_PER_SCAN,
    PrefetchRequest,
    PrefetchRequestError,
    lane_of,
    note_viewed,
    prefetch_envelope,
    prefetch_request,
    request_prefetch,
)
from metabrowser.builtin_plugins.github.served_pull import PullRefreshOutcome, ServedPull
from metabrowser.mirror_refresh import RefreshCoordinator

SOURCE = "https://github.com/octo/demo"
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
FETCHED = "2026-09-17T09:00:00Z"


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Pulls:
    """What the lane needs of a repository's set: where it is and each number's state."""

    def __init__(self, home: Path) -> None:
        self.home, self.slug, self.source = home, "demo", SOURCE
        self.published = ListedRepository(home, "demo", "octo", "demo")
        self.held: dict[int, ServedPull] = {}

    async def companion(self, number: int) -> ServedPull:
        return self.held.setdefault(
            number, ServedPull(published=self.published, number=number, fetched_at=FETCHED)
        )


class _Host:
    """A host whose background refresh ends when the test says, or at once."""

    def __init__(self, home: Path) -> None:
        self.pulls = _Pulls(home)
        self.coordinator = RefreshCoordinator()
        self.started: list[int] = []
        self.gates: dict[int, asyncio.Event] = {}
        self.on_refresh: dict[int, Any] = {}

    def job_key(self, number: int) -> str:
        return f"store:pull/{number}"

    def running(self, number: int) -> bool:
        return self.coordinator.running(self.job_key(number))

    def start_background(self, number: int) -> str:
        async def work() -> None:
            self.started.append(number)
            gate = self.gates.get(number)
            if gate is not None:
                await gate.wait()
            if number in self.on_refresh:
                self.on_refresh[number]()
            held = await self.pulls.companion(number)
            held.last = PullRefreshOutcome(
                outcome="succeeded", message=None, reset_at=None, at=_stamp(NOW)
            )

        return self.coordinator.start(self.job_key(number), work, network=False)


def _verdict(kind: str) -> RecordFreshness:
    if kind == "changed":
        return RecordFreshness("changed", FETCHED, "fetch", False, False, _stamp(NOW))
    if kind == "current":
        return RecordFreshness("current", _stamp(NOW), "catalog", False, False)
    if kind == "checks":
        return RecordFreshness("checks", _stamp(NOW), "catalog", False, False)
    return RecordFreshness("unverified", FETCHED, "fetch", False, False)


@pytest.fixture
def stand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[_Host, dict[int, str], list[int]]]:
    """A host, each number's verdict (absent: no record), and the catalog's publication.

    A publication is one scan's ``fetched_at``; ``host.pages`` is the checkpoint's revision,
    which moves with each page a scan publishes.
    """

    gh_budget.forget()
    host = _Host(tmp_path)
    verdicts: dict[int, str] = {}
    revision = [1]
    clock = [NOW]

    def record_and_freshness(_served: object, number: int) -> tuple[Any, Any]:
        kind = verdicts.get(number)
        if kind is None:
            return None, None
        return SimpleNamespace(fetched_at=FETCHED, unavailable={}), _verdict(kind)

    monkeypatch.setattr(pull_route, "record_and_freshness", record_and_freshness)
    pages = [1]
    monkeypatch.setattr(
        pull_prefetch,
        "read_catalog",
        lambda *_: SimpleNamespace(
            epoch="e",
            revision=pages[0],
            fetched_at=_stamp(NOW + timedelta(minutes=revision[0])),
        ),
    )
    monkeypatch.setattr(pull_prefetch, "_repository_hold", lambda *_: False)
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    host.clock = clock  # pyright: ignore[reportAttributeAccessIssue]
    host.pages = pages  # pyright: ignore[reportAttributeAccessIssue]
    yield host, verdicts, revision
    gh_budget.forget()


def _run(host: _Host, ask: PrefetchRequest) -> tuple[str, str | None, int]:
    async def scenario() -> tuple[str, str | None, int]:
        answer = await request_prefetch(None, host, ask)  # pyright: ignore[reportArgumentType]
        await host.coordinator.drain(timeout_s=10)
        await host.coordinator.drain(timeout_s=10)
        return answer

    return asyncio.run(scenario())


def _report(host: _Host) -> Any:
    return asyncio.run(prefetch_envelope(host))  # pyright: ignore[reportArgumentType]


def _recent(host: _Host) -> list[tuple[str, int, str]]:
    return [
        (entry["kind"], entry["number"], entry["outcome"])
        for entry in lane_of(host.pulls).recent  # pyright: ignore[reportArgumentType]
    ]


def test_named_records_are_read_when_missing_or_changed_and_skipped_otherwise(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, _revision = stand
    verdicts.update({8: "current", 7: "changed", 6: "unverified", 5: "checks"})
    assert _run(host, PrefetchRequest(records=(9, 8, 7, 6, 5))) == ("started", None, 5)
    assert host.started == [9, 7]
    # Only an open pull request's checks are due for 5, which its own visible page reads.
    assert _recent(host) == [
        ("record", 9, "refreshed"),
        ("record", 8, "skipped:current"),
        ("record", 7, "refreshed"),
        ("record", 6, "skipped:unverified"),
        ("record", 5, "skipped:checks"),
    ]


def test_changed_adds_what_this_server_answered_most_recently_but_never_a_missing_one(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, _revision = stand
    verdicts.update({10: "changed", 12: "changed"})
    for number in (10, 11, 12):
        note_viewed(host.pulls, number)  # pyright: ignore[reportArgumentType]
    assert _run(host, PrefetchRequest(records=(12,), changed=True))[0] == "started"
    assert _recent(host) == [
        ("record", 12, "refreshed"),
        ("record", 11, "skipped:not_cached"),
        ("record", 10, "refreshed"),
    ]


def test_a_scan_refreshes_at_most_its_cap_and_a_new_scan_starts_another(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, revision = stand
    numbers = tuple(range(100, 100 + RECORDS_PER_SCAN + 2))
    verdicts.update(dict.fromkeys(numbers, "changed"))
    _run(host, PrefetchRequest(records=numbers))
    assert host.started == list(numbers[:RECORDS_PER_SCAN])
    # The lane stopped at the cap and dropped the rest of its queue.
    assert _recent(host)[-1] == ("record", numbers[RECORDS_PER_SCAN], "deferred:scan_cap")
    assert len(_recent(host)) == RECORDS_PER_SCAN + 1
    assert _report(host)["records"]["scan_used"] == RECORDS_PER_SCAN  # pyright: ignore[reportArgumentType]

    # Review A9: another page of the same scan is the same publication, and the cap holds.
    for number in numbers[:RECORDS_PER_SCAN]:
        del host.pulls.held[number]
    host.pages[0] += 1  # pyright: ignore[reportAttributeAccessIssue]
    _run(host, PrefetchRequest(records=numbers[RECORDS_PER_SCAN:]))
    assert len(host.started) == RECORDS_PER_SCAN
    assert _recent(host)[-1] == ("record", numbers[RECORDS_PER_SCAN], "deferred:scan_cap")

    revision[0] = 2
    _run(host, PrefetchRequest(records=numbers[RECORDS_PER_SCAN:]))
    assert host.started[RECORDS_PER_SCAN:] == list(numbers[RECORDS_PER_SCAN:])


def test_an_hours_records_are_capped_and_the_cap_frees_an_hour_later(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, revision = stand
    numbers = list(range(200, 200 + RECORDS_PER_HOUR + 1))
    verdicts.update(dict.fromkeys(numbers, "changed"))
    for start in range(0, RECORDS_PER_HOUR, RECORDS_PER_SCAN):
        revision[0] += 1
        _run(host, PrefetchRequest(records=tuple(numbers[start : start + RECORDS_PER_SCAN])))
    assert len(host.started) == RECORDS_PER_HOUR
    revision[0] += 1
    _run(host, PrefetchRequest(records=(numbers[-1],)))
    assert _recent(host)[-1] == ("record", numbers[-1], "deferred:hourly_cap")
    assert _report(host)["records"]["hour_used"] == RECORDS_PER_HOUR  # pyright: ignore[reportArgumentType]
    host.clock[0] = NOW + timedelta(hours=1)  # pyright: ignore[reportAttributeAccessIssue]
    _run(host, PrefetchRequest(records=(numbers[-1],)))
    assert host.started[-1] == numbers[-1]


def test_the_governor_refuses_up_front_and_stops_the_lane_part_way(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, _revision = stand
    verdicts.update({7: "changed", 8: "changed", 9: "changed"})
    reset = str(int((NOW + timedelta(minutes=30)).timestamp()))
    low = {
        "x-ratelimit-limit": "5000",
        "x-ratelimit-remaining": "1250",
        "x-ratelimit-reset": reset,
    }
    gh_budget.observe(low, resource="core")
    assert _run(host, PrefetchRequest(records=(7,))) == ("deferred", "below_floor", 0)
    assert host.started == [] and not lane_of(host.pulls).queue  # pyright: ignore[reportArgumentType]

    gh_budget.forget()
    # The first refresh's own response reports the budget at the floor.
    host.on_refresh[7] = lambda: gh_budget.observe(low, resource="core")
    _run(host, PrefetchRequest(records=(7, 8, 9)))
    assert host.started == [7]
    assert _recent(host)[-1] == ("record", 8, "deferred:below_floor")
    envelope = _report(host)  # pyright: ignore[reportArgumentType]
    assert envelope["governor"]["admits"] is False
    assert envelope["governor"]["observed"]["core"]["remaining"] == 1250


def test_a_rate_limit_hold_defers_everything(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    host, verdicts, _revision = stand
    verdicts[7] = "changed"
    gh_budget.hold(_stamp(NOW + timedelta(minutes=5)), now=NOW)
    assert _run(host, PrefetchRequest(records=(7,))) == ("deferred", "rate_hold", 0)


def test_a_preempted_job_is_said_so_and_a_new_request_replaces_the_queue(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    """Review B2: a preempted job gives its place in the caps back, and the lane stops.

    What it had queued would wait behind the reader's job too; the page's next ask says
    what is wanted then.
    """

    host, verdicts, _revision = stand
    verdicts.update({7: "changed", 8: "changed", 9: "changed"})

    async def scenario() -> None:
        host.gates[7] = asyncio.Event()
        await request_prefetch(None, host, PrefetchRequest(records=(7, 8)))  # pyright: ignore[reportArgumentType]
        for _ in range(50):
            await asyncio.sleep(0)
        assert host.started == [7]
        envelope = await prefetch_envelope(host)  # pyright: ignore[reportArgumentType]
        assert envelope["running"] == {"kind": "record", "number": 7}
        assert envelope["queued"] == [{"kind": "record", "number": 8}]
        # The reader moved on: the page now wants 9, and 8 is no longer queued.
        assert (await request_prefetch(None, host, PrefetchRequest(records=(9,))))[0] == "joined"  # pyright: ignore[reportArgumentType]
        host.coordinator.cancel(host.job_key(7))
        await host.coordinator.drain(timeout_s=10)
        await host.coordinator.drain(timeout_s=10)

    asyncio.run(scenario())
    assert host.started == [7]
    assert _recent(host) == [("record", 7, "preempted")]
    records = _report(host)["records"]
    assert (records["scan_used"], records["hour_used"]) == (0, 0)
    assert not lane_of(host.pulls).queue  # pyright: ignore[reportArgumentType]
    _run(host, PrefetchRequest(records=(9,)))
    assert host.started == [7, 9]
    assert _recent(host)[-1] == ("record", 9, "refreshed")


def test_files_are_listed_within_their_own_cap(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    host, _verdicts, _revision = stand
    repository = host.pulls.published
    stamps: dict[int, Any] = {}
    started: list[int] = []

    def files_view(_app: object, number: int) -> Any:
        return SimpleNamespace(
            number=number,
            repository=repository,
            coordinator=host.coordinator,
            refreshing=host.coordinator.running(f"files/{number}"),
        )

    def start_files_refresh(
        view: Any, ask: Any, *, wanted: bool, local: Any, background: bool
    ) -> str:
        assert wanted and background and local is None

        async def work() -> None:
            started.append(ask.number)
            stamps[ask.number] = SimpleNamespace(outcome="succeeded", at=_stamp(NOW))

        return host.coordinator.start(f"files/{ask.number}", work, network=False)

    monkeypatch.setattr(pull_files_route, "files_view", files_view)
    monkeypatch.setattr(pull_files_route, "start_files_refresh", start_files_refresh)
    monkeypatch.setattr(pull_files_route, "files_job_key", lambda _repo, number: f"files/{number}")
    monkeypatch.setattr(
        pull_files_route,
        "files_refresh_wanted",
        lambda view, _ask: (view.number != 5, None),
    )
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_list.read_files_refresh",
        lambda _home, _slug, number: stamps.get(number),
    )
    numbers = tuple(range(1, FILES_PER_HOUR + 3))
    _run(host, PrefetchRequest(files=numbers[:8]))
    assert ("files", 5, "skipped:not_due") in _recent(host)
    for start in range(8, len(numbers), 8):
        _run(host, PrefetchRequest(files=numbers[start : start + 8]))
    assert 5 not in started and len(started) == FILES_PER_HOUR
    assert _recent(host)[-1] == ("files", numbers[-1], "deferred:hourly_cap")
    assert _report(host)["files"]["hour_used"] == FILES_PER_HOUR  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "body",
    [
        {"numbers": [7]},
        {"records": [7, 7]},
        {"records": list(range(1, 18))},
        {"records": [0]},
        {"records": ["7"]},
        {"files": [True]},
        {"changed": "yes"},
    ],
)
def test_a_request_outside_its_shape_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(PrefetchRequestError):
        prefetch_request(body)


def test_nothing_named_starts_nothing(stand: tuple[_Host, dict[int, str], list[int]]) -> None:
    host, _verdicts, _revision = stand
    assert prefetch_request({}) == PrefetchRequest()
    assert _run(host, PrefetchRequest()) == ("not_due", None, 0)
