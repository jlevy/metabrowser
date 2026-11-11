"""The mirror session with data served beside it: turns, staleness, and following.

A fake mirror and a fake companion drive the real :class:`MirrorSession` and
:class:`RefreshCoordinator`, so the order of jobs is observed without Git or gh.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import (
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

    async def ref_tip(self, ref: str) -> str | None:
        return None

    async def list_refs(self, kind: RefKind) -> tuple[MirrorRef, ...]:
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
