"""The prefetch lane: what it runs, in what order, and where it stops.

``tests/test_cli_github_pulls_prefetch_golden.py`` runs the route through the CLI with the
fake ``gh``; these drive the lane over a fake host on the real coordinator, so the caps,
the governor, a reader's work, and preemption are each pinned without Git.
"""

from __future__ import annotations

import asyncio
from collections import deque
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
        # Set when the number's background refresh starts, for a test that waits for it.
        self.entered: dict[int, asyncio.Event] = {}
        self.on_refresh: dict[int, Any] = {}

    def job_key(self, number: int) -> str:
        return f"store:pull/{number}"

    def running(self, number: int) -> bool:
        return self.coordinator.running(self.job_key(number))

    def start_background(self, number: int) -> str:
        async def work() -> None:
            self.started.append(number)
            if number in self.entered:
                self.entered[number].set()
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


def test_the_lane_leaves_what_is_on_screen_the_ceiling_it_needs(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    """A1 of review A on #737, in the terms of the code before it: records that each cost a
    fifth of the ceiling stopped the lane only once it had spent the whole ceiling, and the
    page on screen then paid for that with probes slowed, full reads held five minutes
    apart, the cores of its rows held, and its timeline refused."""

    host, _verdicts, _revision = stand
    numbers = (9, 10, 11, 12, 13, 14)
    for number in numbers:
        host.on_refresh[number] = lambda: gh_budget.spent(
            gh_budget.AUTOMATIC_CORE_PER_HOUR // 5, now=NOW
        )
    _run(host, PrefetchRequest(records=numbers))
    assert host.started[:2] == [9, 10]
    assert not gh_budget.over_ceiling(NOW)
    assert gh_budget.admission(("graphql",), now=NOW).admitted
    assert gh_budget.full_read_interval(90.0, now=NOW) == 90.0


def test_the_caps_priced_at_a_page_a_part_fit_speculative_works_share() -> None:
    """The arithmetic beside the caps: 6 points a record and 1 a list (A1, review A of #737),
    and what the catalog's part of the share leaves them (B1, review B of #737)."""

    priced = RECORDS_PER_HOUR * 6 + FILES_PER_HOUR * 1
    assert priced <= gh_budget.SPECULATIVE_CORE_PER_HOUR
    assert priced + gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR <= (
        gh_budget.SPECULATIVE_CORE_PER_HOUR
    )
    assert gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR > 0
    assert RECORDS_PER_SCAN <= RECORDS_PER_HOUR


def _walk(batches: int) -> int:
    """A cores walk of *batches* of rows, each one GraphQL point, as ``pull_cores`` admits
    and counts them: how many it was let read."""

    read = 0
    for _batch in range(batches):
        if not gh_budget.admission(("graphql",), now=NOW, speculative=True, catalog=True).admitted:
            break
        with gh_budget.speculative(catalog=True):
            gh_budget.spent(1, now=NOW)
        read += 1
    return read


def test_a_cold_walk_that_spends_first_leaves_the_prefetch_its_caps(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1 of review B on #737: with one first-come share, a cold catalog's walk of 800 rows,
    100 batches of 8, spent all of it, and the prefetch was then refused with
    ``self_ceiling``. The walk now stops at the catalog's part of the share, and the lane
    asked after it reads every record and list its caps allow, each at the price the caps
    are set at."""

    host, verdicts, revision = stand
    listed = _stub_files(host, monkeypatch)
    stubbed = pull_files_route.start_files_refresh

    def paid(*args: Any, **kwargs: Any) -> str:
        # In the lane's context, so counted as the lane's, as the job's requests would be.
        gh_budget.spent(1, now=NOW)
        return stubbed(*args, **kwargs)

    monkeypatch.setattr(pull_files_route, "start_files_refresh", paid)
    assert _walk(800 // 8) == gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR
    assert not gh_budget.over_speculative_share(NOW)
    records = tuple(range(700, 700 + RECORDS_PER_HOUR))
    verdicts.update(dict.fromkeys(records, "changed"))
    for number in records:
        host.on_refresh[number] = lambda: gh_budget.spent(6, now=NOW)
    files = tuple(range(1, FILES_PER_HOUR + 1))
    asks = (
        PrefetchRequest(records=records[:RECORDS_PER_SCAN], files=files[:8]),
        PrefetchRequest(records=records[RECORDS_PER_SCAN:], files=files[8:16]),
        PrefetchRequest(files=files[16:]),
    )
    for ask in asks:
        revision[0] += 1
        assert _run(host, ask)[:2] == ("started", None)
    assert [number for number in host.started if number > 0] == list(records)
    assert listed == list(files)
    assert not [entry for entry in _recent(host) if entry[2].startswith("deferred")]
    ceiling = _report(host)["governor"]["ceiling"]
    assert (ceiling["speculative_hour_used"], ceiling["catalog_hour_used"]) == (
        gh_budget.SPECULATIVE_CORE_PER_HOUR,
        gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR,
    )
    # The walk, which is refused, got none of it.
    assert _walk(1) == 0


def test_the_catalogs_part_holds_the_walk_and_the_backfill_and_not_the_lane_or_the_labels() -> None:
    """The order inside the share: the lane and the label set are refused only at all of it."""

    with gh_budget.speculative(catalog=True):
        gh_budget.spent(gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR, now=NOW)
    assert gh_budget.admission(
        ("graphql",), now=NOW, speculative=True, catalog=True
    ) == gh_budget.Admission(False, "self_ceiling")
    assert gh_budget.admission(("core",), now=NOW, speculative=True).admitted
    assert gh_budget.speculative_spent(NOW) == gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR
    # What the lane spends counts toward the share, not the catalog's part of it.
    with gh_budget.speculative():
        gh_budget.spent(1, now=NOW)
    assert gh_budget.catalog_spent(NOW) == gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR
    # And the whole share, spent, refuses the catalog's work as well as the lane.
    gh_budget.forget()
    with gh_budget.speculative():
        gh_budget.spent(gh_budget.SPECULATIVE_CORE_PER_HOUR, now=NOW)
    assert gh_budget.catalog_spent(NOW) == 0
    assert not gh_budget.admission(("graphql",), now=NOW, speculative=True, catalog=True).admitted
    gh_budget.forget()


def test_what_the_lanes_jobs_spend_is_speculative_and_the_lane_stops_at_its_share(
    stand: tuple[_Host, dict[int, str], list[int]],
) -> None:
    """A1 of review A on #737: the lane spent the ceiling that the screen then paid for."""

    host, _verdicts, _revision = stand
    share = gh_budget.SPECULATIVE_CORE_PER_HOUR
    host.on_refresh[9] = lambda: gh_budget.spent(6, now=NOW)
    host.on_refresh[10] = lambda: gh_budget.spent(share - 6, now=NOW)
    assert _run(host, PrefetchRequest(records=(9,))) == ("started", None, 1)
    assert (gh_budget.speculative_spent(NOW), gh_budget.automatic_spent(NOW)) == (6, 6)
    ceiling = _report(host)["governor"]["ceiling"]
    assert ceiling == {
        "per_hour": gh_budget.AUTOMATIC_CORE_PER_HOUR,
        "hour_used": 6,
        "speculative_per_hour": share,
        "speculative_hour_used": 6,
        "catalog_per_hour": gh_budget.CATALOG_SPECULATIVE_CORE_PER_HOUR,
        "catalog_hour_used": 0,
    }
    # 10's read spends the rest of the share, and the lane stops there, dropping 11.
    assert _run(host, PrefetchRequest(records=(10, 11, 12))) == ("started", None, 3)
    assert host.started == [9, 10]
    assert _recent(host)[-2:] == [
        ("record", 10, "refreshed"),
        ("record", 11, "deferred:self_ceiling"),
    ]
    assert not lane_of(host.pulls).queue  # pyright: ignore[reportArgumentType]
    assert _run(host, PrefetchRequest(records=(11,))) == ("deferred", "self_ceiling", 0)
    governor = _report(host)["governor"]
    assert (governor["admits"], governor["reason"]) == (False, "self_ceiling")
    assert governor["ceiling"]["speculative_hour_used"] == share
    # What is on screen is admitted all the while: the ceiling has two thirds left.
    assert not gh_budget.over_ceiling(NOW)
    assert gh_budget.admission(("graphql",), now=NOW).admitted
    host.clock[0] = NOW + timedelta(hours=1)  # pyright: ignore[reportAttributeAccessIssue]
    assert _run(host, PrefetchRequest(records=(11,))) == ("started", None, 1)
    assert host.started == [9, 10, 11]


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
        host.entered[7] = asyncio.Event()
        await request_prefetch(None, host, PrefetchRequest(records=(7, 8)))  # pyright: ignore[reportArgumentType]
        # The lane reads the record, the governor's hold, and the catalog off the loop before
        # it starts 7: three thread hops, which fifty turns of the loop did not cover on CI.
        await asyncio.wait_for(host.entered[7].wait(), 10)
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
        view: Any, ask: Any, *, wanted: bool, local: Any, background: bool, fallback: Any
    ) -> str:
        assert wanted and background and local is None and fallback is None

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
        lambda view, _ask, _prepared: (view.number != 5, None),
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


def _stub_files(host: _Host, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Lists that are always due and end at once; each one listed is also ``-number`` in
    ``host.started``, so one order holds both kinds."""

    listed: list[int] = []

    def files_view(_app: object, number: int) -> Any:
        return SimpleNamespace(
            number=number,
            repository=host.pulls.published,
            coordinator=host.coordinator,
            refreshing=False,
        )

    def start_files_refresh(
        _view: Any, ask: Any, *, wanted: bool, local: Any, background: bool, fallback: Any
    ) -> str:
        assert wanted and background and local is None and fallback is None

        async def work() -> None:
            listed.append(ask.number)
            host.started.append(-ask.number)

        return host.coordinator.start(f"files/{ask.number}", work, network=False)

    monkeypatch.setattr(pull_files_route, "files_view", files_view)
    monkeypatch.setattr(pull_files_route, "start_files_refresh", start_files_refresh)
    monkeypatch.setattr(pull_files_route, "files_job_key", lambda _repo, number: f"files/{number}")
    monkeypatch.setattr(
        pull_files_route, "files_refresh_wanted", lambda _view, _ask, _prepared: (True, None)
    )
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_list.read_files_refresh",
        lambda _home, _slug, _number: SimpleNamespace(outcome="succeeded", at=_stamp(NOW)),
    )
    return listed


def test_the_kinds_take_turns_each_in_its_own_order(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record and then a list, so a cold server's missing records do not hold back every
    list behind them; the longer kind runs on alone once the other is done."""

    host, verdicts, _revision = stand
    _stub_files(host, monkeypatch)
    verdicts.update(dict.fromkeys((300, 301, 302), "changed"))
    _run(host, PrefetchRequest(records=(300, 301, 302), files=(1, 2)))
    assert host.started == [300, -1, 301, -2, 302]


def test_a_records_cap_drops_the_records_and_the_lists_queued_behind_it_still_run(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    host, verdicts, _revision = stand
    listed = _stub_files(host, monkeypatch)
    earlier = tuple(range(400, 400 + RECORDS_PER_SCAN - 1))
    verdicts.update(dict.fromkeys((*earlier, 500, 501, 502), "changed"))
    _run(host, PrefetchRequest(records=earlier))
    # One record of this scan is left: 500 takes it, and 501 meets the cap with two lists
    # still queued behind it.
    _run(host, PrefetchRequest(records=(500, 501, 502), files=(1, 2, 3)))
    assert host.started[len(earlier) :] == [500, -1, -2, -3]
    assert listed == [1, 2, 3]
    recent = _recent(host)
    capped = recent.index(("record", 501, "deferred:scan_cap"))
    assert recent[capped + 1 :] == [("files", 2, "refreshed"), ("files", 3, "refreshed")]


def test_a_files_cap_drops_the_lists_and_the_records_queued_behind_it_still_run(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    host, verdicts, _revision = stand
    listed = _stub_files(host, monkeypatch)
    # One list of this hour is left: 1 takes it, and 2 meets the cap with two records still
    # queued behind it.
    lane_of(host.pulls).file_starts.extend([NOW] * (FILES_PER_HOUR - 1))  # pyright: ignore[reportArgumentType]
    verdicts.update(dict.fromkeys((600, 601, 602), "changed"))
    _run(host, PrefetchRequest(records=(600, 601, 602), files=(1, 2, 3)))
    assert listed == [1]
    assert host.started == [600, -1, 601, 602]
    recent = _recent(host)
    capped = recent.index(("files", 2, "deferred:hourly_cap"))
    assert recent[capped + 1 :] == [("record", 602, "refreshed")]


def _store_lists(
    host: _Host, monkeypatch: pytest.MonkeyPatch, given: set[int], *, git_fails: bool = False
) -> list[tuple[int, bool | None]]:
    """Lists the store gives for the numbers in *given*, which the lane prepares first, and
    GitHub's for the rest; each started is ``(number, fallback)``, where *fallback* is what
    the lane answered when Git could not give a local one (*git_fails*), else ``None``."""

    started: list[tuple[int, bool | None]] = []
    _stub_files(host, monkeypatch)

    async def prepare(_host: Any, lane: Any) -> None:
        numbers = {item.number for item in lane.queue if item.kind == "files"}
        for number in numbers:
            lane.prepared[number] = None
        lane.local_ready |= numbers & given
        lane.queue = deque(
            sorted(lane.queue, key=lambda item: not (item.kind == "files" and item.number in given))
        )

    def wanted(view: Any, _ask: Any, _prepared: Any) -> tuple[bool, Any]:
        return True, SimpleNamespace(git_dir="store") if view.number in given else None

    def start_files_refresh(
        _view: Any, ask: Any, *, wanted: bool, local: Any, background: bool, fallback: Any
    ) -> str:
        assert wanted and background
        assert (local is None) is (fallback is None), "only a list the store gives falls back"

        async def work() -> None:
            answer = await fallback() if git_fails and fallback is not None else None
            started.append((ask.number, answer))
            host.started.append(-ask.number)

        return host.coordinator.start(f"files/{ask.number}", work, network=False)

    monkeypatch.setattr(pull_prefetch, "_prepare_lists", prepare)
    monkeypatch.setattr(pull_files_route, "files_refresh_wanted", wanted)
    monkeypatch.setattr(pull_files_route, "start_files_refresh", start_files_refresh)
    return started


def test_lists_the_store_gives_are_not_refused_with_the_rest(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1 of review B on #737: the refusal stopped files lists that cost GitHub nothing,
    since the lane asked the governor before it looked at whether the store gives one."""

    host, verdicts, _revision = stand
    started = _store_lists(host, monkeypatch, {1, 2})
    with gh_budget.speculative():
        gh_budget.spent(gh_budget.SPECULATIVE_CORE_PER_HOUR, now=NOW)
    verdicts[9] = "changed"
    # The record is dropped at once; the lists go, and GitHub's is refused when it comes.
    assert _run(host, PrefetchRequest(records=(9,), files=(3, 1, 2))) == (
        "started",
        "self_ceiling",
        3,
    )
    assert started == [(1, None), (2, None)]
    assert _recent(host) == [
        ("files", 1, "refreshed"),
        ("files", 2, "refreshed"),
        ("files", 3, "deferred:self_ceiling"),
    ]
    assert _report(host)["files"]["hour_used"] == 0
    # With no list in the ask, the refusal is the answer.
    assert _run(host, PrefetchRequest(records=(9,))) == ("deferred", "self_ceiling", 0)
    assert 9 not in host.started


def test_a_list_git_cannot_give_after_all_is_read_from_github_only_past_the_governor(
    stand: tuple[_Host, dict[int, str], list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    host, _verdicts, _revision = stand
    started = _store_lists(host, monkeypatch, {1, 2}, git_fails=True)
    assert _run(host, PrefetchRequest(files=(1,))) == ("started", None, 1)
    # Admitted, it is a list from GitHub, and the hour's cap counts it.
    assert started == [(1, True)]
    assert _report(host)["files"]["hour_used"] == 1
    with gh_budget.speculative():
        gh_budget.spent(gh_budget.SPECULATIVE_CORE_PER_HOUR, now=NOW)
    # Refused, the lane says why, counts nothing, and the next list the store gives goes.
    assert _run(host, PrefetchRequest(files=(1, 2))) == ("started", "self_ceiling", 2)
    assert started[1:] == [(1, False), (2, False)]
    assert _recent(host)[-2:] == [
        ("files", 1, "deferred:self_ceiling"),
        ("files", 2, "deferred:self_ceiling"),
    ]
    assert _report(host)["files"]["hour_used"] == 1


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
