"""The mirror session with data served beside it: turns, staleness, and following.

A fake mirror and a fake companion drive the real :class:`MirrorSession` and
:class:`RefreshCoordinator`, so the order of jobs is observed without Git or gh.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MAX_FIRST_IN_A_ROW,
    MAX_PULL_JOBS,
    CommitFetchAnswer,
    MirrorDisplay,
    MirrorRef,
    MirrorSession,
    RecordedFreshness,
    RefKind,
    RefreshCoordinator,
    RefreshResult,
    SelectionNotFoundError,
    SelectionPendingError,
    StoreTurn,
)
from metabrowser.repository_context import RepositoryContext

_OLD = "2020-01-01T00:00:00Z"


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

    async def open_selection(
        self, *, ref: str | None, oid: str | None, keep_refs: tuple[str, ...] = ()
    ) -> GitRevisionSubject:
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

    async def origin_tip(self, ref: str) -> str | None:
        raise AssertionError("not reached")

    async def ref_tip(self, ref: str) -> str | None:
        return None

    async def ref_tips(self, refs: Sequence[str]) -> dict[str, str]:
        return {}

    async def default_ref(self) -> str | None:
        return None

    async def list_refs(self, kind: RefKind, *, default_ref: str | None) -> tuple[MirrorRef, ...]:
        raise AssertionError("not reached")

    async def refresh_running_elsewhere(self) -> bool:
        return False

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        return None

    @property
    def display(self) -> MirrorDisplay:
        return MirrorDisplay(name="store", origin="file:///origin.git", location="/store")


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


class _Set:
    """The one pull request these tests serve, as a provider's set hands it over."""

    def __init__(self, served: _Companion) -> None:
        self.served = served

    def key(self, number: int) -> str:
        return self.served.key

    async def companion(self, number: int) -> _Companion:
        return self.served

    async def attend(self, number: int) -> _Companion:
        return self.served


async def _attending(
    mirror: _Mirror,
    coordinator: RefreshCoordinator,
    companion: _Companion,
    *,
    serving: bool = False,
) -> MirrorSession:
    """A session attending to *companion*, as the application lifespan starts one."""

    session = MirrorSession(
        mirror, coordinator, fetch_on_miss=serving, pull_requests=_Set(companion)
    )
    await session.attend(7)
    return session


async def _settle(coordinator: RefreshCoordinator) -> None:
    # The drain waits for a job another starts as it ends, as a refresh that follows another
    # process's.
    await coordinator.drain(timeout_s=5)
    await coordinator.aclose()


def test_the_mirror_waits_its_turn_behind_the_pull_requests_fetch() -> None:
    """Within one server the two fetches take turns instead of finding the lock held."""

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        companion = _Companion(events, stale=True)
        companion.gate = asyncio.Event()
        session = await _attending(_Mirror(events), coordinator, companion)
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


def test_any_pull_requests_refresh_takes_its_turn_and_counts_only_when_attended() -> None:
    """A pull request the session is not attending to runs under the same turn at the store,
    and neither its staleness nor its refresh is the mirror's."""

    class _Numbered(_Set):
        def __init__(self, events: list[str]) -> None:
            self.events = events
            self.by_number: dict[int, _Companion] = {}

        def key(self, number: int) -> str:
            return f"store:pull/{number}"

        async def companion(self, number: int) -> _Companion:
            served = self.by_number.setdefault(number, _Companion(self.events, stale=True))
            served.key = self.key(number)
            return served

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        pulls = _Numbered(events)
        session = MirrorSession(
            _Mirror(events, fetched_at=_now()), coordinator, pull_requests=pulls, fetch_on_miss=True
        )
        await session.observe()
        eight = await pulls.companion(8)
        eight.gate = asyncio.Event()
        assert session.request_pull_refresh(8) == "started"
        assert session.request_pull_refresh(8) == "joined"
        await eight.started.wait()
        assert session.pull_refreshing(8) is True and session.pull_refreshing(9) is False
        # It is nothing to the session's own state, and to the status built from it.
        assert session.companion is None and session.companion_refreshing() is False
        assert session.is_stale() is False and session.refreshing() is False
        session.request_refresh(for_selection=True)
        for _ in range(10):
            await asyncio.sleep(0)
        assert events == ["pull start"], "the mirror's fetch must wait for the pull request's"
        eight.gate.set()
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
        session = await _attending(
            mirror, coordinator, _Companion(events, stale=pull_stale), serving=serving
        )
        await session.observe()
        session.request_refresh(for_selection=for_selection)
        await _settle(coordinator)
        return events

    assert sorted(asyncio.run(scenario())) == sorted(expected)


@pytest.mark.parametrize(
    ("mirror_fresh", "pull_stale", "retry", "answer", "expected"),
    [
        # Inside the freshness window a page's own request fetches nothing at all,
        (True, False, False, ("fresh", None), []),
        # or only the stale pull request, and still says the mirror was not fetched.
        (True, True, False, ("fresh", "started"), ["pull start", "pull end"]),
        # Outside the window it fetches the mirror, and the pull request when stale.
        (False, False, False, ("started", None), ["mirror"]),
        (False, True, False, ("started", "started"), ["mirror", "pull start", "pull end"]),
        # A reader's retry fetches both, however fresh they are.
        (True, False, True, ("started", "started"), ["mirror", "pull start", "pull end"]),
    ],
)
def test_a_commit_fetch_has_a_floor_that_only_a_retry_lifts(
    mirror_fresh: bool,
    pull_stale: bool,
    retry: bool,
    answer: tuple[str, str | None],
    expected: list[str],
) -> None:
    """A link in served content can send a reader to any commit's address, so the fetch a
    page asks for by itself runs only for what is older than the freshness window."""

    async def scenario() -> tuple[tuple[str, str | None], list[str]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _Mirror(events, fetched_at=_now() if mirror_fresh else _OLD)
        session = await _attending(
            mirror, coordinator, _Companion(events, stale=pull_stale), serving=True
        )
        await session.observe()
        answered = session.request_commit_fetch(retry=retry)
        await _settle(coordinator)
        return (answered.refresh, answered.pull_refresh), events

    answered, events = asyncio.run(scenario())
    assert answered == answer
    assert sorted(events) == sorted(expected)


def test_a_commit_fetch_joins_the_mirror_fetch_but_not_the_pull_requests() -> None:
    """A fetch of the mirror that is running is the fetch, even inside the window; a
    refresh of the pull request alone is not, and the answer does not call it one."""

    async def scenario() -> tuple[str, str, list[str]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        companion = _Companion(events, stale=False)
        companion.gate = asyncio.Event()
        session = await _attending(
            _Mirror(events, fetched_at=_now()), coordinator, companion, serving=True
        )
        await session.observe()
        session.request_companion_refresh()
        await companion.started.wait()
        beside = session.request_commit_fetch(retry=False).refresh
        assert session.refreshing() is False and session.companion_refreshing() is True
        session.request_refresh(for_selection=True)
        joined = session.request_commit_fetch(retry=False).refresh
        companion.gate.set()
        await _settle(coordinator)
        return beside, joined, events

    beside, joined, events = asyncio.run(scenario())
    assert (beside, joined) == ("fresh", "joined")
    assert events.count("mirror") == 1


# ── Who goes next at the store, and what a waiting job holds ─────────


class _Gated:
    """A numbered pull request's refresh that runs until the test lets it end."""

    def __init__(self, events: list[str], number: int) -> None:
        self.events = events
        self.number = number
        self.key = f"store:pull/{number}"
        self.gate = asyncio.Event()

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        return True

    async def refresh(self) -> None:
        self.events.append(f"pull {self.number}")
        await self.gate.wait()
        self.gate.clear()


class _GatedSet:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.by_number: dict[int, _Gated] = {}

    def key(self, number: int) -> str:
        return f"store:pull/{number}"

    async def companion(self, number: int) -> _Gated:
        return self.by_number.setdefault(number, _Gated(self.events, number))

    async def attend(self, number: int) -> _Gated:
        return await self.companion(number)


class _GatedMirror(_Mirror):
    """A mirror whose fetch runs until the test lets it end, and that has no selection."""

    def __init__(self, events: list[str]) -> None:
        super().__init__(events)
        self.gate = asyncio.Event()

    async def open_selection(
        self, *, ref: str | None, oid: str | None, keep_refs: tuple[str, ...] = ()
    ) -> GitRevisionSubject:
        raise SelectionNotFoundError("not in the mirror")

    async def refresh(self) -> RefreshResult:
        self.events.append("mirror")
        await self.gate.wait()
        self.gate.clear()
        return RefreshResult("succeeded", _now())


async def _spin() -> None:
    for _ in range(50):
        await asyncio.sleep(0)


class _Stand:
    """The real session and coordinator over gated fakes, for the order of jobs."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.coordinator = RefreshCoordinator()
        self.pulls = _GatedSet(self.events)
        self.mirror = _GatedMirror(self.events)
        self.session = MirrorSession(
            self.mirror, self.coordinator, pull_requests=self.pulls, fetch_on_miss=True
        )

    async def end(self, number: int) -> None:
        """Let pull request *number*'s running refresh end, and whatever follows it start."""

        assert self.events[-1] == f"pull {number}", self.events
        self.pulls.by_number[number].gate.set()
        await _spin()

    async def end_mirror(self) -> None:
        assert self.events[-1] == "mirror", self.events
        self.mirror.gate.set()
        await _spin()

    async def finish(self) -> None:
        for number, pull in self.pulls.by_number.items():
            if self.session.pull_refreshing(number):
                pull.gate.set()
        self.mirror.gate.set()
        await _spin()
        await self.coordinator.aclose()

    async def warm(self, by: str = "the mirror's") -> None:
        """Put the stand in a server's usual state: jobs that go first have run with nothing
        else waiting, as the mirror's does once a window for any served page, or the attended
        pull request's own, more often than the store's turn lets such jobs go in a row ahead
        of a waiting one. Then forget them, so a test sees only its own jobs."""

        if by != "the mirror's":
            await self.session.attend(7)
        for _ in range(MAX_FIRST_IN_A_ROW + 1):
            if by == "the mirror's":
                assert self.session.request_refresh(for_selection=True) == "started"
                await _spin()
                await self.end_mirror()
            else:
                assert self.session.request_pull_refresh(7) == "started"
                await _spin()
                await self.end(7)
        assert not self.session.refreshing() and not self.session.pull_refreshing(7)
        self.events.clear()


def test_a_job_waiting_its_turn_holds_no_slot_so_a_list_refresh_starts_at_once() -> None:
    """A list's refresh needs no turn at the store, so jobs that are only waiting for one
    must not keep it from a network slot."""

    async def scenario() -> list[str]:
        stand = _Stand()
        for number in (8, 9, 10, 11):
            assert stand.session.request_pull_refresh(number) == "started"
        assert stand.session.request_refresh(for_selection=True) == "started"
        await _spin()
        assert stand.events == ["pull 8"]

        async def list_job() -> None:
            stand.events.append("list")

        assert stand.coordinator.start("store:pulls", list_job) == "started"
        await _spin()
        seen = list(stand.events)
        await stand.finish()
        return seen

    assert asyncio.run(scenario()) == ["pull 8", "list"]


@pytest.mark.parametrize("mirror_first", [False, True])
def test_a_store_job_with_the_turn_waits_for_a_slot_and_runs_when_one_frees(
    mirror_first: bool,
) -> None:
    """The turn is taken before the slot, by every job at the store, so two lists holding
    both slots hold up the fetch only until one ends, and nothing can deadlock."""

    async def scenario() -> list[str]:
        stand = _Stand()
        lists = asyncio.Event()

        async def list_job() -> None:
            stand.events.append("list")
            await lists.wait()

        stand.coordinator.start("store:pulls/open", list_job)
        stand.coordinator.start("store:pulls/closed", list_job)
        await _spin()
        if mirror_first:
            stand.session.request_refresh(for_selection=True)
            await _spin()
        stand.session.request_pull_refresh(8)
        if not mirror_first:
            await _spin()
            stand.session.request_refresh(for_selection=True)
        await _spin()
        assert stand.events == ["list", "list"], "both slots are the lists'"
        lists.set()
        await _spin()
        if mirror_first:
            await stand.end_mirror()
            await stand.end(8)
        else:
            await stand.end(8)
            await stand.end_mirror()
        await stand.finish()
        return stand.events[2:]

    expected = ["mirror", "pull 8"] if mirror_first else ["pull 8", "mirror"]
    assert asyncio.run(scenario()) == expected


def test_the_mirrors_refresh_goes_ahead_of_every_queued_pull_request() -> None:
    """A page of code waits for the mirror's fetch; a queue of other pull requests a reader
    asked for must not stand in front of it."""

    async def scenario() -> list[str]:
        stand = _Stand()
        for number in (8, 9, 10, 11):
            assert stand.session.request_pull_refresh(number) == "started"
        await _spin()
        assert stand.session.request_refresh(for_selection=True) == "started"
        await _spin()
        await stand.end(8)
        await stand.end_mirror()
        await stand.end(9)
        await stand.end(10)
        await stand.end(11)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == ["pull 8", "mirror", "pull 9", "pull 10", "pull 11"]


def test_the_attended_pull_request_goes_ahead_of_queued_ones_even_if_attended_late() -> None:
    """Who goes first is decided when a turn is given, so a job queued before its number was
    attended goes ahead too, and one whose number stopped being attended waits its place."""

    async def scenario() -> list[str]:
        stand = _Stand()
        await stand.session.attend(7)
        for number in (8, 9, 10):
            assert stand.session.request_pull_refresh(number) == "started"
        await _spin()
        assert stand.session.request_pull_refresh(7) == "started"
        await _spin()
        await stand.end(8)
        await stand.end(7)
        # 9 is next, in order. Attending to 11's job, queued behind it, puts it ahead of 10.
        assert stand.session.request_pull_refresh(11) == "started"
        await _spin()
        await stand.session.attend(11)
        await stand.end(9)
        await stand.end(11)
        await stand.end(10)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == [f"pull {n}" for n in (8, 7, 9, 11, 10)]


def test_a_job_whose_number_stopped_being_attended_waits_its_place() -> None:
    async def scenario() -> list[str]:
        stand = _Stand()
        await stand.session.attend(7)
        assert stand.session.request_pull_refresh(8) == "started"
        await _spin()
        assert stand.session.request_pull_refresh(9) == "started"
        assert stand.session.request_pull_refresh(7) == "started"
        await _spin()
        await stand.session.attend(20)
        await stand.end(8)
        await stand.end(9)
        await stand.end(7)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == ["pull 8", "pull 9", "pull 7"]


def test_a_refresh_of_both_starts_with_the_mirror_as_it_was_asked_for_first() -> None:
    """A server reads the mirror's record before a fetch. That read is inside the job's turn:
    outside it, the attended pull request's job got to the store first, and the mirror's fetch
    of a moment waited behind a refresh of several seconds."""

    class _ReadsItsRecord(_GatedMirror):
        async def recorded_freshness(self) -> RecordedFreshness:
            await asyncio.sleep(0)
            return await super().recorded_freshness()

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        pulls = _GatedSet(events)
        session = MirrorSession(
            _ReadsItsRecord(events),
            coordinator,
            pull_requests=pulls,
            fetch_on_miss=True,
            follow_elsewhere=True,
        )
        await session.attend(7)
        assert session.request_refresh() == "started"
        await _spin()
        seen = list(events)
        await coordinator.aclose()
        return seen

    assert asyncio.run(scenario()) == ["mirror"]


def test_the_mirror_and_the_attended_pull_request_cannot_starve_each_other() -> None:
    """Each goes in the order it asked, whichever keeps asking again as soon as it can."""

    async def scenario() -> list[str]:
        stand = _Stand()
        await stand.session.attend(7)
        # The mirror asks and asks again; the attended pull request must still run each time.
        stand.session.request_refresh(for_selection=True)
        await _spin()
        assert stand.events == ["mirror"]
        stand.session.request_pull_refresh(7)
        await _spin()
        for _ in range(3):
            await stand.end_mirror()
            assert stand.events[-1] == "pull 7", "the attended job goes after the mirror's"
            stand.session.request_refresh(for_selection=True)
            await _spin()
            await stand.end(7)
            assert stand.events[-1] == "mirror", "the mirror's goes after the attended job"
            stand.session.request_pull_refresh(7)
            await _spin()
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == ["mirror", "pull 7"] * 4


def test_a_queued_pull_request_waits_through_at_most_one_job_of_each_that_goes_first() -> None:
    """The mirror and the attended pull request asking for ever do not starve the rest."""

    async def scenario() -> list[str]:
        stand = _Stand()
        session = stand.session
        await session.attend(7)
        assert session.request_pull_refresh(8) == "started"
        await _spin()
        for number in (9, 10):
            assert session.request_pull_refresh(number) == "started"
        session.request_refresh(for_selection=True)
        session.request_pull_refresh(7)
        await _spin()
        await stand.end(8)
        await stand.end_mirror()
        # The mirror asks again at once, and 9 still goes before it.
        session.request_refresh(for_selection=True)
        await _spin()
        await stand.end(7)
        session.request_pull_refresh(7)
        await _spin()
        await stand.end(9)
        await stand.end_mirror()
        session.request_refresh(for_selection=True)
        await _spin()
        await stand.end(7)
        await stand.end(10)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == [
        "pull 8",
        "mirror",
        "pull 7",
        "pull 9",
        "mirror",
        "pull 7",
        "pull 10",
        "mirror",
    ]


@pytest.mark.parametrize("alone", ["the mirror's", "the attended's"])
def test_jobs_that_went_first_with_nothing_waiting_do_not_hold_back_the_next_first(
    alone: str,
) -> None:
    """A server open a while has fetched the mirror alone once a window, or refreshed the
    attended pull request alone. Those went ahead of nothing, so on the first contention after
    them the attended job still goes ahead of a pull request asked for after it, and that one
    then waits for one of each that goes first, as from a fresh start."""

    async def scenario() -> list[str]:
        stand = _Stand()
        await stand.warm(by=alone)
        session = stand.session
        await session.attend(7)
        assert session.request_refresh(for_selection=True) == "started"
        await _spin()
        assert stand.events == ["mirror"]
        assert session.request_pull_refresh(7) == "started"
        await _spin()
        assert session.request_pull_refresh(8) == "started"
        await _spin()
        # Each that goes first asks again as soon as it can; 8 still goes after one of each.
        await stand.end_mirror()
        session.request_refresh(for_selection=True)
        await _spin()
        await stand.end(7)
        session.request_pull_refresh(7)
        await _spin()
        await stand.end_mirror()
        seen = list(stand.events)
        await stand.finish()
        return seen

    assert asyncio.run(scenario()) == ["mirror", "pull 7", "mirror", "pull 8"]


@pytest.mark.parametrize("cancelled", ["as the turn passes", "as its turn came"])
def test_a_job_cancelled_while_it_waits_gives_up_its_place(cancelled: str) -> None:
    """A job cancelled while the turn passes is skipped, and one cancelled after its turn came
    and before it woke passes the turn on. Either way the next job runs."""

    async def scenario() -> list[str]:
        order: list[str] = []
        turn = StoreTurn()

        async def job(name: str, gate: asyncio.Event | None = None) -> None:
            async with turn(lambda: False):
                order.append(name)
                if gate is not None:
                    await gate.wait()

        gate = asyncio.Event()
        running = asyncio.create_task(job("running", gate))
        await _spin()
        doomed = asyncio.create_task(job("cancelled"))
        last = asyncio.create_task(job("last"))
        await _spin()
        gate.set()
        if cancelled == "as its turn came":
            # The running job ends and gives the turn; the given job has not woken yet.
            await asyncio.sleep(0)
            assert running.done()
        doomed.cancel()
        await asyncio.gather(doomed, return_exceptions=True)
        # A turn nobody passed on leaves the last job waiting for ever: say so, and do not
        # wait for the test's timeout.
        await asyncio.wait({last}, timeout=5)
        assert last.done(), f"the turn was not passed on; ran {order}"
        await running
        return order

    assert asyncio.run(scenario()) == ["running", "last"]


def test_a_pending_miss_waits_for_the_job_it_started_whichever_is_attended_by_then() -> None:
    """A commit the mirror lacks can be a newer one of the attended pull request, and the
    attended number can change while that job runs. A miss answered from the number attended
    now says "not found" for a commit that may arrive a few seconds later."""

    async def scenario() -> tuple[bool, bool, bool]:
        stand = _Stand()
        session = stand.session
        missing = "a" * 40

        async def ask() -> None:
            await session.switch_pin(ref=None, oid=missing)

        await session.attend(7)
        session.request_refresh(for_selection=True)
        await _spin()
        with pytest.raises(SelectionPendingError):
            await ask()
        await stand.end_mirror()
        assert stand.events[-1] == "pull 7" and session.pull_refreshing(7)

        await session.attend(8)
        # 7's job is still running, so the miss is still waiting on it. The ask also starts
        # the job of the number attended now, which could bring the commit too.
        with pytest.raises(SelectionPendingError):
            await ask()
        still_seven = session.pull_refreshing(7)
        await stand.end(7)
        # The ask started the mirror's fetch again, and that goes first.
        await stand.end_mirror()
        # Now only 8's job runs, which the miss also waits on.
        assert stand.events[-1] == "pull 8" and not session.pull_refreshing(7)
        with pytest.raises(SelectionPendingError):
            await ask()
        then_eight = session.pull_refreshing(8)
        await stand.end(8)
        await stand.end_mirror()
        with pytest.raises(SelectionNotFoundError):
            await ask()
        answered = not session.refreshing() and not session.pull_refreshing(8)
        await stand.finish()
        return still_seven, then_eight, answered

    assert asyncio.run(scenario()) == (True, True, True)


async def _fill_the_queue(stand: _Stand) -> None:
    """Eight other numbers, and the attended 7 one over, then 20 attended: 20 has no room."""

    await stand.session.attend(7)
    for number in range(8, 16):
        assert stand.session.request_pull_refresh(number) == "started"
    assert stand.session.request_pull_refresh(7) == "started"
    await stand.session.attend(20)
    assert stand.session.request_companion_refresh() == "too_many"


def test_a_source_refresh_the_queue_has_no_room_for_says_so_and_starts_nothing() -> None:
    """When only the attended pull request is stale, a refusal of its job is the answer: a
    "joined" would say work was accepted that was not."""

    async def scenario() -> tuple[str, list[str]]:
        stand = _Stand()
        fresh = _Mirror(stand.events, fetched_at=_now())
        stand.session = MirrorSession(
            fresh, stand.coordinator, pull_requests=stand.pulls, fetch_on_miss=True
        )
        await stand.session.observe()
        await _fill_the_queue(stand)
        await _spin()
        answered = stand.session.request_refresh()
        await _spin()
        seen = list(stand.events)
        await stand.finish()
        return answered, seen

    answered, seen = asyncio.run(scenario())
    assert answered == "too_many"
    assert seen == ["pull 8"], "nothing else started"


def test_a_commit_fetch_the_queue_has_no_room_for_says_so_beside_the_mirrors() -> None:
    """The mirror is fetched, and the answer says the pull request's refresh was refused, so
    a commit page does not say the origin lacks a commit only that refresh would bring."""

    async def scenario() -> tuple[CommitFetchAnswer, bool]:
        stand = _Stand()
        fresh = _Mirror(stand.events, fetched_at=_now())
        stand.session = MirrorSession(
            fresh, stand.coordinator, pull_requests=stand.pulls, fetch_on_miss=True
        )
        await stand.session.observe()
        await _fill_the_queue(stand)
        answered = stand.session.request_commit_fetch(retry=True)
        await _spin()
        refreshing = stand.session.pull_refreshing(20)
        await stand.finish()
        return answered, refreshing

    answered, refreshing = asyncio.run(scenario())
    assert (answered.refresh, answered.pull_refresh) == ("started", "too_many")
    assert refreshing is False


def test_a_pending_miss_whose_pull_request_job_was_refused_waits_for_room() -> None:
    """A full queue refused the attended pull request's job, so it has not run, and the commit
    may be one only it brings: the miss stays pending, and a later ask that finds room starts
    the job and then waits for it. A fetch of the mirror that ran since the miss is not asked
    for again on every ask meanwhile: only that job can bring more."""

    async def scenario() -> None:
        stand = _Stand()
        session = stand.session
        missing = "a" * 40

        async def ask() -> None:
            await session.switch_pin(ref=None, oid=missing)

        session.request_refresh(for_selection=True)
        await _spin()
        assert stand.events == ["mirror"]
        await _fill_the_queue(stand)
        with pytest.raises(SelectionPendingError):
            await ask()
        await stand.end_mirror()
        assert stand.events[-1] == "pull 8"
        # The mirror's fetch ended, and the queue is still full: still pending, not "not found",
        # and the mirror is not fetched again.
        with pytest.raises(SelectionPendingError) as waiting:
            await ask()
        assert waiting.value.refresh == "joined"
        assert not session.pull_refreshing(20) and not session.refreshing()
        await stand.end(8)
        assert stand.events.count("mirror") == 1, stand.events
        # Now there is room, so this ask starts 20's job, and the miss waits for it.
        with pytest.raises(SelectionPendingError) as waiting:
            await ask()
        assert waiting.value.refresh == "started"
        assert session.pull_refreshing(20) and not session.refreshing()
        while session.refreshing() or any(
            session.pull_refreshing(number) for number in (*range(9, 16), 7, 20)
        ):
            for pull in stand.pulls.by_number.values():
                pull.gate.set()
            stand.mirror.gate.set()
            await _spin()
        with pytest.raises(SelectionNotFoundError):
            await ask()
        await stand.finish()

    asyncio.run(scenario())


def test_attending_changes_the_number_and_its_refresh_together() -> None:
    """While the set reads the new number's state, the session is still on the old one, so a
    refresh asked for then is the old one's, as its staleness is."""

    class _SlowSet(_GatedSet):
        def __init__(self, events: list[str]) -> None:
            super().__init__(events)
            self.read = asyncio.Event()

        async def attend(self, number: int) -> _Gated:
            await self.read.wait()
            return await self.companion(number)

    async def scenario() -> None:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        pulls = _SlowSet(events)
        session = MirrorSession(_Mirror(events), coordinator, pull_requests=pulls)
        pulls.read.set()
        await session.attend(7)
        seven = session.companion
        pulls.read.clear()
        attending = asyncio.create_task(session.attend(8))
        await _spin()
        assert session.companion is seven
        assert session.request_companion_refresh() == "started"
        assert session.pull_refreshing(7) and not session.pull_refreshing(8)
        pulls.read.set()
        await attending
        assert session.companion is await pulls.companion(8)
        await coordinator.aclose()

    asyncio.run(scenario())


# ── Background jobs give way ─────────────────────────────────────


def test_a_background_job_yields_the_store_to_a_readers_job_at_once() -> None:
    """A reader who opens another pull request waits for a prefetch to unwind, not to end."""

    async def scenario() -> list[str]:
        stand = _Stand()
        session = stand.session
        assert session.request_pull_refresh(8, background=True) == "started"
        await _spin()
        assert stand.events == ["pull 8"] and not session._pull_jobs  # pyright: ignore[reportPrivateUsage]
        assert session.request_pull_refresh(9) == "started"
        await _spin()
        assert not session.pull_refreshing(8)
        await stand.end(9)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == ["pull 8", "pull 9"]


def test_a_readers_request_promotes_the_background_job_it_joins() -> None:
    """Joined by a reader, a prefetch is the reader's: it is not cancelled, and it counts."""

    async def scenario() -> list[str]:
        stand = _Stand()
        session = stand.session
        assert session.request_pull_refresh(8, background=True) == "started"
        await _spin()
        assert session.request_pull_refresh(8) == "joined"
        assert session._pull_jobs == {"store:pull/8"}  # pyright: ignore[reportPrivateUsage]
        assert session.request_pull_refresh(9) == "started"
        await _spin()
        assert session.pull_refreshing(8)
        await stand.end(8)
        await stand.end(9)
        await stand.finish()
        return stand.events

    assert asyncio.run(scenario()) == ["pull 8", "pull 9"]


def test_a_background_job_waits_behind_every_other_and_holds_no_slot() -> None:
    async def scenario() -> tuple[list[str], int]:
        stand = _Stand()
        session = stand.session
        assert session.request_pull_refresh(7) == "started"
        await _spin()
        assert session.request_pull_refresh(8, background=True) == "started"
        assert session.request_pull_refresh(9) == "started"
        await _spin()
        await stand.end(7)
        await stand.end(9)
        assert stand.events[-1] == "pull 8"
        # Both network slots are free while the background job runs.
        slot = stand.coordinator.slot()
        free = 0
        for _ in range(2):
            await asyncio.wait_for(slot.acquire(), timeout=1)
            free += 1
        for _ in range(free):
            slot.release()
        await stand.end(8)
        await stand.finish()
        return stand.events, free

    assert asyncio.run(scenario()) == (["pull 7", "pull 9", "pull 8"], 2)


def test_the_restart_of_a_pull_job_a_reader_joined_runs_however_many_reader_jobs_run_then() -> None:
    """Review A5 of #762: the reader's job for 50 took its place among the reader's jobs
    when the reader joined it as it stopped. By the time it has unwound,
    :data:`MAX_PULL_JOBS` other reader jobs run, one of them a prefetch a reader promoted,
    which no bound refuses. The restart is no new start, so it is not refused either."""

    async def scenario() -> tuple[list[str], int, bool, list[str]]:
        stand = _Stand()
        session = stand.session
        coordinator = stand.coordinator
        key = stand.pulls.key(50)
        assert session.request_pull_refresh(50, background=True) == "started"
        await _spin()
        assert stand.events == ["pull 50"]
        # A reader's job for another pull request arrives: 50's is told to stop.
        assert session.request_pull_refresh(1) == "started"
        await asyncio.sleep(0)
        stopped = coordinator.job(key)
        assert stopped is not None and stopped.cancelling()
        assert session.request_pull_refresh(50) == "joined"
        # The reader's other jobs fill the bound with 50's...
        starts = [session.request_pull_refresh(number) for number in range(2, MAX_PULL_JOBS)]
        assert session.request_pull_refresh(99) == "too_many"
        # ...and one more joins it, a prefetch a reader opened.
        assert session.request_pull_refresh(100, background=True) == "started"
        assert session.request_pull_refresh(100) == "joined"
        others = len(session._pull_jobs - {key})
        # Its done callbacks, the restart among them, run before this wait's.
        await asyncio.wait({stopped}, timeout=5)
        assert stopped.done()
        restarted = coordinator.job(key)
        for _ in range(MAX_PULL_JOBS + 3):
            for pull in stand.pulls.by_number.values():
                pull.gate.set()
            await _spin()
        await stand.finish()
        return starts, others, restarted is not None and restarted is not stopped, stand.events

    starts, others, restarted, events = asyncio.run(scenario())
    assert starts == ["started"] * (MAX_PULL_JOBS - 2)
    assert others == MAX_PULL_JOBS
    assert restarted is True
    assert events.count("pull 50") == 2, events


def test_background_jobs_count_toward_no_bound() -> None:
    async def scenario() -> tuple[str, str]:
        stand = _Stand()
        session = stand.session
        background = session.request_pull_refresh(100, background=True)
        for number in range(1, MAX_PULL_JOBS + 1):
            assert session.request_pull_refresh(number) == "started"
        await _spin()
        refused = session.request_pull_refresh(MAX_PULL_JOBS + 1)
        await stand.finish()
        return background, refused

    assert asyncio.run(scenario()) == ("started", "too_many")


def test_the_turn_gives_background_waiters_nothing_ahead_of_others() -> None:
    """Background waiters go last, in order, and leave the first-in-a-row count alone."""

    async def scenario() -> list[str]:
        order: list[str] = []
        turn = StoreTurn()
        gate = asyncio.Event()

        async def job(name: str, *, first: bool = False, background: bool = False) -> None:
            async with turn(lambda: first, background=lambda: background):
                order.append(name)
                if name == "running":
                    await gate.wait()

        running = asyncio.create_task(job("running"))
        await _spin()
        waiting = [
            asyncio.create_task(job("background 1", background=True)),
            asyncio.create_task(job("other")),
            asyncio.create_task(job("background 2", background=True)),
            *(asyncio.create_task(job(f"first {n}", first=True)) for n in range(3)),
        ]
        await _spin()
        gate.set()
        await asyncio.gather(running, *waiting)
        return order

    # Two firsts go ahead of the other, then it goes, then the last first; background last.
    assert asyncio.run(scenario()) == [
        "running",
        "first 0",
        "first 1",
        "other",
        "first 2",
        "background 1",
        "background 2",
    ]


# ── The idle refresh ─────────────────────────────────────────────────


class _HeldFetch(_Mirror):
    """A mirror whose fetch holds until released, and says when it was stopped."""

    def __init__(self, events: list[str], *, outcome: str = "succeeded") -> None:
        super().__init__(events)
        self.gate = asyncio.Event()
        self.started = asyncio.Event()
        self.outcome = outcome

    async def refresh(self) -> RefreshResult:
        self.events.append("mirror start")
        self.started.set()
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.events.append("mirror stopped")
            raise
        self.events.append("mirror end")
        return RefreshResult(self.outcome, _now())


async def _idle_for(session: MirrorSession, seconds: float) -> None:
    """Run the server's idle timer for *seconds*, then stop it as shutdown does."""

    timer = asyncio.create_task(session.run_idle_refresh())
    await asyncio.sleep(seconds)
    timer.cancel()
    await asyncio.gather(timer, return_exceptions=True)


def test_an_idle_server_fetches_a_mirror_older_than_the_idle_interval_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no page asking, the server's own timer fetches a mirror that has grown old,
    and then not again until the interval has passed."""

    monkeypatch.setattr("metabrowser.mirror_refresh.IDLE_CHECK_FLOOR_S", 0.01)

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session = MirrorSession(_Mirror(events), coordinator, fetch_on_miss=True)
        await session.observe()
        await _idle_for(session, 0.3)
        await coordinator.aclose()
        return events

    assert asyncio.run(scenario()) == ["mirror"]


def test_an_idle_server_leaves_a_mirror_inside_the_idle_interval_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.mirror_refresh.IDLE_CHECK_FLOOR_S", 0.01)

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session = MirrorSession(_Mirror(events, fetched_at=_now()), coordinator)
        await session.observe()
        await _idle_for(session, 0.2)
        await coordinator.aclose()
        return events

    assert asyncio.run(scenario()) == []


def test_the_idle_refresh_follows_another_processs_fetch_instead_of_repeating_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The store's record is read again when the fetch comes due: one another process
    wrote meanwhile is this server's too, and the origin is not asked again."""

    monkeypatch.setattr("metabrowser.mirror_refresh.IDLE_CHECK_FLOOR_S", 0.01)

    async def scenario() -> tuple[list[str], str | None]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _Mirror(events)
        session = MirrorSession(mirror, coordinator)
        await session.observe()
        # Another process fetched the store since this server last read its record.
        mirror.fetched_at = _now()
        await _idle_for(session, 0.2)
        await coordinator.aclose()
        return events, session.last_fetch_at()

    events, fetched = asyncio.run(scenario())
    assert events == []
    assert fetched is not None and fetched != _OLD


def test_a_failed_idle_fetch_is_tried_again_only_after_the_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.mirror_refresh.IDLE_CHECK_FLOOR_S", 0.01)

    class _Unreachable(_Mirror):
        async def refresh(self) -> RefreshResult:
            self.events.append("mirror")
            return RefreshResult("network_unreachable", _now())

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session = MirrorSession(_Unreachable(events), coordinator)
        await session.observe()
        await _idle_for(session, 0.3)
        first = list(events)
        # The same server with a short interval tries again, so it is the interval that held it.
        monkeypatch.setattr("metabrowser.mirror_refresh.STORE_IDLE_REFRESH_S", 0.02)
        await _idle_for(session, 0.3)
        await coordinator.aclose()
        return [*first, "|", *events[len(first) :]]

    events = asyncio.run(scenario())
    assert events[:2] == ["mirror", "|"]
    assert len(events) > 2


def test_the_idle_fetch_gives_way_to_a_readers_job_at_the_store() -> None:
    """Background work: when a job a reader waits on wants the store, the idle fetch is
    stopped, not waited for, and it is nobody's refresh to report as cancelled."""

    async def scenario() -> tuple[list[str], object, bool]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _HeldFetch(events)
        companion = _Companion(events, stale=True)
        session = await _attending(mirror, coordinator, companion, serving=True)
        assert session.request_idle_refresh() == "started"
        await mirror.started.wait()
        refreshing = session.refreshing()
        session.request_companion_refresh()
        await _settle(coordinator)
        return events, session._last_outcome(), refreshing

    events, outcome, refreshing = asyncio.run(scenario())
    assert events == ["mirror start", "mirror stopped", "pull start", "pull end"]
    assert outcome is None
    assert refreshing is True


def test_the_idle_fetch_takes_no_network_slot() -> None:
    """A job a reader waits on holding every slot does not hold the idle fetch back, and
    the idle fetch holds none a reader's job would wait for."""

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator(limit=1)
        release = asyncio.Event()

        async def a_list() -> None:
            events.append("list start")
            await release.wait()

        coordinator.start("list", a_list)
        await _spin()
        session = MirrorSession(_Mirror(events), coordinator, fetch_on_miss=True)
        session.request_idle_refresh()
        await _spin()
        seen = list(events)
        release.set()
        await _settle(coordinator)
        return seen

    assert asyncio.run(scenario()) == ["list start", "mirror"]


def test_a_readers_refresh_that_joins_the_idle_fetch_makes_it_theirs() -> None:
    """From then on a page waits on it, so it goes first and nothing stops it."""

    async def scenario() -> tuple[list[str], str, object]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _HeldFetch(events)
        companion = _Companion(events, stale=True)
        session = await _attending(mirror, coordinator, companion, serving=True)
        session.request_idle_refresh()
        await mirror.started.wait()
        joined = session.request_refresh(for_selection=True)
        session.request_companion_refresh()
        await _spin()
        mirror.gate.set()
        await _settle(coordinator)
        return events, joined, session._last_outcome()

    events, joined, outcome = asyncio.run(scenario())
    assert joined == "joined"
    assert events == ["mirror start", "mirror end", "pull start", "pull end"]
    assert isinstance(outcome, dict) and outcome["outcome"] == "succeeded"


# ── A request that joins the idle fetch ──────────────────────────────


async def _stopping_idle_fetch(
    events: list[str], coordinator: RefreshCoordinator
) -> tuple[MirrorSession, _HeldFetch]:
    """A session whose idle fetch a reader's pull-request job has just told to stop: the
    cancellation is asked for and not yet delivered, which takes one more loop step."""

    mirror = _HeldFetch(events)
    session = await _attending(mirror, coordinator, _Companion(events, stale=True), serving=True)
    assert session.request_idle_refresh() == "started"
    await mirror.started.wait()
    session.request_companion_refresh()
    await asyncio.sleep(0)
    return session, mirror


def test_a_readers_refresh_that_joins_an_idle_fetch_being_stopped_is_fetched_all_the_same() -> None:
    """Review A1 of #721: the reader's Refresh was answered ``joined``, the fetch it joined
    was then cancelled, nothing fetched, and status reported a cancelled refresh."""

    async def scenario() -> tuple[list[str], str, object, bool]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session, mirror = await _stopping_idle_fetch(events, coordinator)
        joined = session.request_refresh(for_selection=True)
        await _spin()
        running = session.refreshing()
        mirror.gate.set()
        await _settle(coordinator)
        return events, joined, session._last_outcome(), running

    events, joined, outcome, running = asyncio.run(scenario())
    assert joined == "joined"
    assert running is True, "the reader's fetch runs once the stopped one has unwound"
    assert events.count("mirror start") == 2 and events[:2] == ["mirror start", "mirror stopped"]
    assert "mirror end" in events
    assert isinstance(outcome, dict) and outcome["outcome"] == "succeeded"


def test_a_page_ask_that_joins_an_idle_fetch_being_stopped_reports_no_cancelled_refresh() -> None:
    """Review A1 of #721: a page whose reader pressed nothing showed a failed refresh."""

    async def scenario() -> tuple[list[str], str, object, bool]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session, mirror = await _stopping_idle_fetch(events, coordinator)
        answer = await session.page_ask()
        await _spin()
        quiet = session._refresh_quiet()
        mirror.gate.set()
        await _settle(coordinator)
        return events, answer, session._last_outcome(), quiet

    events, answer, outcome, quiet = asyncio.run(scenario())
    assert answer == "joined"
    assert "mirror end" in events
    assert isinstance(outcome, dict) and outcome["outcome"] == "succeeded"
    # The page's fetch, which nobody pressed for, stays quiet.
    assert quiet is True


def test_a_url_selection_that_joins_an_idle_fetch_being_stopped_is_not_left_pending() -> None:
    """Review A1 of #721: the selection was marked pending for a fetch that never ran."""

    async def scenario() -> tuple[list[str], str | None]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        opened: list[str] = []

        async def opener() -> None:
            opened.append("asked")
            return None

        mirror = _HeldFetch(events)
        session = MirrorSession(
            mirror,
            coordinator,
            fetch_on_miss=True,
            pending_selection=opener,
            pull_requests=_Set(_Companion(events, stale=True)),
        )
        await session.attend(7)
        session.request_idle_refresh()
        await mirror.started.wait()
        session.request_companion_refresh()
        await asyncio.sleep(0)
        session.start_pending_selection()
        await _spin()
        mirror.gate.set()
        await _settle(coordinator)
        return opened, session._selection_state

    opened, state = asyncio.run(scenario())
    assert opened == ["asked"], "the fetch the selection waited for ran to its end"
    assert state == "not_found"


def test_a_readers_refresh_that_joins_a_queued_idle_fetch_stops_background_work() -> None:
    """Review A3 of #721: an idle fetch queues as background work and stops nothing; the
    reader's Refresh that joins it must stop the background job holding the turn, as it
    does when no idle fetch is queued, and not wait for that job to finish."""

    async def scenario(*, idle_queued: bool) -> tuple[list[str], list[str]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session = MirrorSession(_Mirror(events), coordinator, fetch_on_miss=True)
        stopped: list[str] = []
        release = asyncio.Event()

        async def prefetch() -> None:
            async with session.background_store_turn(lambda: stopped.append("prefetch")):
                events.append("prefetch start")
                await release.wait()

        task = asyncio.create_task(prefetch())
        await _spin()
        if idle_queued:
            session.request_idle_refresh()
            await _spin()
            assert stopped == [], "background work does not stop background work"
        session.request_refresh(for_selection=True)
        await _spin()
        seen = list(stopped)
        release.set()
        await task
        await _settle(coordinator)
        return seen, events

    for idle_queued in (True, False):
        stopped, events = asyncio.run(scenario(idle_queued=idle_queued))
        assert stopped == ["prefetch"], f"idle fetch queued: {idle_queued}"
        assert events == ["prefetch start", "mirror"]


def test_a_readers_request_that_joins_a_queued_background_pull_stops_background_work() -> None:
    """The same gap for a prefetched pull request a reader then asks for (review A3)."""

    async def scenario() -> list[str]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session = await _attending(
            _Mirror(events, fetched_at=_now()), coordinator, _Companion(events, stale=True)
        )
        stopped: list[str] = []
        release = asyncio.Event()

        async def prefetch() -> None:
            async with session.background_store_turn(lambda: stopped.append("prefetch")):
                await release.wait()

        task = asyncio.create_task(prefetch())
        await _spin()
        assert session.request_pull_refresh(7, background=True) == "started"
        await _spin()
        assert stopped == []
        assert session.request_pull_refresh(7) == "joined"
        await _spin()
        seen = list(stopped)
        release.set()
        await task
        await _settle(coordinator)
        return seen

    assert asyncio.run(scenario()) == ["prefetch"]


def test_a_page_ask_that_joins_the_idle_fetch_keeps_it_running_and_quiet() -> None:
    """A visible page waits on it from then on, so a pull request's job no longer stops
    it; nobody pressed for it, so status still calls it quiet (review A5 of #721)."""

    async def scenario() -> tuple[list[str], str, bool]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _HeldFetch(events)
        companion = _Companion(events, stale=True)
        session = await _attending(mirror, coordinator, companion, serving=True)
        session.request_idle_refresh()
        await mirror.started.wait()
        answer = await session.page_ask()
        session.request_companion_refresh()
        await _spin()
        quiet = session._refresh_quiet()
        mirror.gate.set()
        await _settle(coordinator)
        return events, answer, quiet

    events, answer, quiet = asyncio.run(scenario())
    assert answer == "joined"
    assert events == ["mirror start", "mirror end", "pull start", "pull end"]
    # The pull request's job was waiting by then, which a reader does see.
    assert quiet is False


def test_an_idle_fetch_a_readers_job_stopped_is_tried_again_only_a_window_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review A5 of #721: nothing failed when the hold after a preemption was deleted.
    The timer sleeps for as long as :meth:`MirrorSession._idle_due_in` says, so what it
    says is what is held to the clock here."""

    clock = [1000.0]
    monkeypatch.setattr("metabrowser.mirror_refresh._monotonic", lambda: clock[0])

    async def scenario() -> tuple[list[str], float, float]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _HeldFetch(events)
        companion = _Companion(events, stale=True)
        session = await _attending(mirror, coordinator, companion, serving=True)
        await session.observe()
        assert session._idle_due_in(clock[0]) <= 0, "a mirror this old is due at once"
        session.request_idle_refresh()
        await mirror.started.wait()
        session.request_companion_refresh()
        await _settle(coordinator)
        stopped = session._idle_due_in(clock[0])
        clock[0] += FRESHNESS_WINDOW_S
        return events, stopped, session._idle_due_in(clock[0])

    events, stopped, later = asyncio.run(scenario())
    assert events == ["mirror start", "mirror stopped", "pull start", "pull end"]
    assert stopped == FRESHNESS_WINDOW_S
    assert later <= 0


def test_status_calls_a_fetch_nobody_asked_for_quiet_until_a_reader_joins_it() -> None:
    """Review A2 of #721: the idle fetch made every visible page say "Refreshing…"."""

    async def scenario() -> list[tuple[bool, bool]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _HeldFetch(events)
        session = MirrorSession(mirror, coordinator, fetch_on_miss=True)
        seen = [(session.refreshing(), session._refresh_quiet())]
        session.request_idle_refresh()
        await mirror.started.wait()
        seen.append((session.refreshing(), session._refresh_quiet()))
        session.request_refresh(for_selection=True)
        seen.append((session.refreshing(), session._refresh_quiet()))
        mirror.gate.set()
        await _settle(coordinator)
        seen.append((session.refreshing(), session._refresh_quiet()))
        return seen

    assert asyncio.run(scenario()) == [(False, False), (True, True), (True, False), (False, False)]


class _Elsewhere(_Mirror):
    """A mirror whose store another process is fetching until the test says it has ended."""

    def __init__(self, events: list[str]) -> None:
        super().__init__(events, busy_at=_now())
        self.other_done = False

    async def refresh_running_elsewhere(self) -> bool:
        return not self.other_done


def test_a_quiet_fetch_stays_quiet_while_it_follows_another_processs_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review B1 of #721: two servers on one store go stale together, so one's fetch
    often finds the other's running; the row then said "Refreshing…" for as long as the
    other fetched. A reader's Refresh during the follow is theirs, and shows."""

    monkeypatch.setattr("metabrowser.mirror_refresh.ELSEWHERE_POLL_S", 0.01)

    async def scenario() -> tuple[list[object], list[tuple[bool, bool]]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        mirror = _Elsewhere(events)
        session = MirrorSession(mirror, coordinator, fetch_on_miss=True, follow_elsewhere=True)
        answers: list[object] = []
        seen: list[tuple[bool, bool]] = []
        for ask in ("page", "idle", "idle, then a reader"):
            mirror.other_done = False
            answers.append(
                await session.page_ask() if ask == "page" else session.request_idle_refresh()
            )
            seen.append((session.refreshing(), session._refresh_quiet()))
            await _spin()
            # This server's own job has ended; it follows the other process's fetch.
            assert not coordinator.running(mirror.key)
            if ask == "idle, then a reader":
                session.request_refresh(for_selection=True)
            seen.append((session.refreshing(), session._refresh_quiet()))
            mirror.other_done = True
            await coordinator.drain(timeout_s=5)
        await coordinator.aclose()
        return answers, seen

    answers, seen = asyncio.run(scenario())
    assert answers == ["started", "started", "started"]
    assert seen == [
        (True, True),
        (True, True),
        (True, True),
        (True, True),
        (True, True),
        (True, False),
    ]


def test_a_page_ask_before_the_restart_of_a_stopped_idle_fetch_does_not_quiet_a_readers_refresh() -> (
    None
):
    """Review B2 of #721: the reader's Refresh joined an idle fetch being stopped. A page's
    ask handled in the one loop step between that job's end and its restart started the
    fetch as quiet, and the reader's refresh, which then joined it, showed nothing.

    Review C3 of #721: status is read in that step too, before the restart, so the page's
    ask is what starts the fetch loud; the restart leaves the quiet alone."""

    async def scenario() -> tuple[list[object], list[str]]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session, mirror = await _stopping_idle_fetch(events, coordinator)
        seen: list[object] = [session.request_refresh(for_selection=True)]

        def a_page_asks() -> None:
            # Queued behind the stopped job's last step: it runs once that job is done and
            # before the job's done callbacks, which restart the fetch.
            asking = session.page_ask()
            try:
                asking.send(None)
            except StopIteration as answered:
                seen.append(answered.value)
            seen.append(("before the restart", session.refreshing(), session._refresh_quiet()))

        asyncio.get_running_loop().call_soon(a_page_asks)
        await _spin()
        seen.append((session.refreshing(), session._refresh_quiet()))
        mirror.gate.set()
        await _settle(coordinator)
        return seen, events

    seen, events = asyncio.run(scenario())
    assert seen == ["joined", "started", ("before the restart", True, False), (True, False)]
    assert events.count("mirror start") == 2, "one fetch after the stopped one, not two"


def test_the_restart_of_a_stopped_fetch_does_not_depend_on_the_idle_flag() -> None:
    """Review B4 of #721: the cancel handler clears the idle flag before the task is done.
    Nothing awaits between the two today; if something ever does, a request that joins
    there must still get its fetch, so the task is asked, not the flag."""

    async def scenario() -> tuple[list[str], object]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        session, mirror = await _stopping_idle_fetch(events, coordinator)
        # As a request would find it after the handler ran and before the task ended.
        session._idle_fetch = False
        session.request_refresh(for_selection=True)
        await _spin()
        mirror.gate.set()
        await _settle(coordinator)
        return events, session._last_outcome()

    events, outcome = asyncio.run(scenario())
    assert "mirror end" in events
    assert isinstance(outcome, dict) and outcome["outcome"] == "succeeded"


def test_a_readers_request_that_joins_a_background_pull_being_stopped_gets_its_job() -> None:
    """Bead mb-iz5l (review B3 of #721): a reader's job arrived at the store, so the
    prefetched pull request's job holding the turn was told to stop; before it had
    unwound the reader opened that pull request. The request was answered ``joined``,
    the job ended cancelled, and nothing fetched the pull request.

    Review C3 of #721: the reader's job is counted before the stopped one has unwound,
    from the join, as well as once it starts again."""

    async def scenario() -> tuple[list[str], str, bool, bool, bool]:
        events: list[str] = []
        coordinator = RefreshCoordinator()
        stops = [True]

        class _Stoppable(_Companion):
            async def refresh(self) -> None:
                events.append("pull start")
                if stops:
                    stops.pop()
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        events.append("pull stopped")
                        raise
                events.append("pull end")

        session = await _attending(
            _Mirror(events, fetched_at=_now()), coordinator, _Stoppable(events, stale=True)
        )
        assert session.request_pull_refresh(7, background=True) == "started"
        await _spin()
        # A reader's Refresh of the mirror arrives: the background job is told to stop.
        session.request_refresh(for_selection=True)
        await asyncio.sleep(0)
        joined = session.request_pull_refresh(7)
        key = _Companion.key
        assert coordinator.job(key) is not None, "the stopped job has not unwound"
        counted_at_join = key in session._pull_jobs
        # Asked again before the stopped job has unwound: still one job after it.
        assert session.request_pull_refresh(7) == "joined"
        await _spin()
        running = session.pull_refreshing(7)
        counted = key in session._pull_jobs
        await _settle(coordinator)
        return events, joined, running, counted_at_join, counted

    events, joined, running, counted_at_join, counted = asyncio.run(scenario())
    assert joined == "joined"
    assert events == ["pull start", "pull stopped", "mirror", "pull start", "pull end"]
    assert counted_at_join is True, "the reader's job counts from the join"
    assert counted is True, "the reader's job counts among the reader's jobs"
    # By then the reader's job has run or is running; it is never simply gone.
    assert running is True or events[-1] == "pull end"
