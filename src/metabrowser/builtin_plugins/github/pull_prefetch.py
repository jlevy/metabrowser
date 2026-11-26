"""Background prefetch: refresh what a reader is likely to open next, within a budget, behind them.

A visible page names what it expects the reader to open, in its order of priority, with
``POST /api/plugin/github/pulls-prefetch``:

- ``records``: pull requests whose record to read when it is missing or the catalog says
  it changed (:mod:`.pull_freshness`): the anchored row, its J/K neighbours, the top open
  pull requests, the visible rows;
- ``changed``: also the pull requests this server most recently answered ``GET pull`` for,
  when the catalog says they changed, which is what a scan that just published asks for;
- ``files``: pull requests whose changed-files list to read when the files route would
  start an automatic refresh, which a head or base that moved does at once: the rows the
  pointer or focus rested on, the open row, its neighbours, and the rows in view.

Nothing on the server starts this by itself, so it runs only while a page is visible and
online, and a hidden or offline page asks for nothing. The request replaces the lane's
queue, so a walk that moved on drops what it no longer needs.

Each served repository has one lane, a coordinator job that runs one item at a time.
First it makes the queued lists local where it can (:func:`_prepare_lists`): a list the
store can give, from a record's comparison of the newest known head or, for an open pull
request, from the head and base branch the list of pull requests names, compared with the
mirror's base branch, takes tens of milliseconds and no GitHub request, where a record takes
seconds. The heads the store lacks and the base branches arrive in one Git fetch for the
whole ask, at the store's turn as background work a reader's job preempts, and a served
checkout attaches its store for it if no reader has yet. A list already current is left
out, so an ask with nothing to list fetches nothing. Those lists go first; then the two
kinds take turns, a record and then a files list from GitHub, each in its own order, so
neither waits for the whole of the other: a cold server's missing records would otherwise
hold every list back for as long as they take. Measured 2026-11-17 on this repository's own
Pulls tab with a fresh cache, served from its checkout, 11 open rows in view at a load
average of 11 to 14: the last row's change line was drawn 40.6 s after the tab opened when
lists took turns with records, each record 3.6 to 4.7 s and each list from GitHub 0.3 to
2 s; with the lists made local first, 10.4 s, of which attaching the checkout's store took
2.3 to 2.5 s once, the merge bases of 11 heads 0.42 s at :data:`MERGE_BASES_AT_ONCE`
(1.3 s one at a time), and each list 42 to 134 ms. Before each item it reads again, off the event
loop, whether the item is still due, which another process's refresh may have made it
not, then whether the rate-limit governor admits it (:mod:`.gh_budget`) and the caps have
room. A list the store gives costs GitHub nothing, so the governor is not asked for it,
and an ask the governor refuses still lists what the store gives; should Git fail to give
a list after all, GitHub's is read only past the governor and inside the cap, as any list
from GitHub is. It stops, dropping the rest but those lists, when the governor refuses; a
cap that is reached drops the rest of its own kind, and the other goes on. The page asks
again later. A job is started under the pull request's own key, so a reader's request for
it joins and promotes it, and as a background job it takes no network slot, waits at a
store turn behind a reader's job, and is cancelled when one starts waiting (:mod:`.checkout`, :mod:`metabrowser.mirror_refresh`).
A preempted job gives its place in the caps back, and the lane stops there: what it had
queued would wait behind the reader too, and the page's next ask says what is wanted then.

The caps, measured against the fake ``gh`` in ``tests/golden/cli-github-pulls-prefetch.txt``,
count only what GitHub's API answers; a list the store gives is not counted
(``tests/golden/cli-github-pulls-prefetch-local-lists.txt``): a
background record refresh asks for at most 6 core points when each part fits on one page
(the pull and five parts; a ``304`` is free, and so is the account check after a
process's first, since it is conditional), and a one-page files list for 1. A part of more than 100 comments, reviews,
or check runs costs a point a page more. The lanes are kept in memory, one per repository
a server process serves; the arithmetic of :data:`RECORDS_PER_HOUR` and
:data:`FILES_PER_HOUR` is beside them. What bounds the lane's points, whatever its items
cost, is speculative work's share of the process's own ceiling
(:data:`~.gh_budget.SPECULATIVE_CORE_PER_HOUR`), which the lane's jobs are counted toward
and the governor refuses past. While the lane has work queued or running, the cores walk
leaves it what its caps can still spend this hour, and while a page has asked for it
within :data:`ASKED_WITHIN_S`, a scan's records (:func:`reserved`), so a walk that spends
first does not refuse it before its caps do; a lane no page asks for reserves nothing, and
the walk may then spend the rest of the share. What bounds the account as a whole
is the governor's floor, read from GitHub's own count of what remains (:mod:`.gh_budget`). :data:`RECORDS_PER_SCAN`
keeps one scan's changes from spending a whole hour's records at once; a scan is one
publication of the catalog, its ``fetched_at``, however many pages it read.

``GET`` reports the lane from memory: the running item, the queue, the caps and their
use, the governor, and the last :data:`MAX_RECENT` outcomes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import OrderedDict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from itertools import zip_longest
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict
from weakref import WeakKeyDictionary

from metabrowser import event_log
from metabrowser.builtin_plugins.github import gh_budget, pulls
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    rate_limit_holds,
    read_list_refresh,
)
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import LocalComparison
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls

log = logging.getLogger(__name__)

PREFETCH_ROUTE: Final = "/api/plugin/github/pulls-prefetch"
# Numbers a request may name in each list: the anchored row, two neighbours, the top five
# open pull requests, and the visible rows of a list pane fit.
MAX_PREFETCH_NUMBERS: Final = 16
# The merge bases the lane computes at once, each one Git process (`branch_endpoints`).
# Measured 2026-11-17 on this repository's checkout store, 11 open heads at a load average
# of 12 to 13: 1.3 s one at a time, 0.42 s four at a time.
MERGE_BASES_AT_ONCE: Final = 4
# The hour's caps are priced to fit speculative work's share of the process's own ceiling
# (``gh_budget.SPECULATIVE_CORE_PER_HOUR``), which refuses the lane whatever its items turn
# out to cost. At one page a part a record costs at most :data:`POINTS_PER_RECORD` and a
# files list from GitHub :data:`POINTS_PER_FILES_LIST`, so the two caps together spend at
# most 12 × 6 + 20 × 1 = 92 points an hour, under the share's 100. While the lane has work
# the cores walk leaves it what the caps can still spend at those prices, and between a
# page's asks a scan's records (:func:`reserved`), so the walk cannot take it before the
# lane asks (review B1 of #737, review A1 of #761); the catalog's
# backfill, the label set's read, and whatever the caps do not use are first come, first
# served with the lane. They were 40 and 100 before the ceiling, at most
# 40 × 8 + 100 × 3 = 620 points an hour at that day's prices, against a ceiling of 300 for
# all automatic work (review A1 of #737); ``tests/test_github_pull_prefetch.py`` pins the
# sum.
# A scan's cap is eight, above the seven records a page names as the ones it expects
# opened next, its top rows (``PREFETCH_TOP_ROWS`` in pulls-panel.js) and the open row's
# two neighbours, so one scan's changes do not crowd them out; it is two thirds of an
# hour's records.
RECORDS_PER_SCAN: Final = 8
RECORDS_PER_HOUR: Final = 12
# Lists GitHub must give, since one the store gives is not counted: the rows of one pane
# in view, at the 16 an ask names, with a few rested on.
FILES_PER_HOUR: Final = 20
# What a background record and a files list from GitHub cost at most when each part fits
# on one page: the pull and five parts, and the list's one page (the module docstring,
# measured against the fake ``gh`` in ``tests/golden/cli-github-pulls-prefetch.txt``).
# A background record reads no operational status, the GraphQL point a page's own read
# adds (``refresh_pull_request``), so the price leaves it out.
POINTS_PER_RECORD: Final = 6
POINTS_PER_FILES_LIST: Final = 1
# How long after a page's last ask its lane, idle, still keeps a scan's records from the
# cores walk (:func:`reserved`). The Pulls panel asks once for each scan it sees end
# (``prefetchAfterScan`` in pulls-panel.js). A scan is due ``FULL_REFRESH_S`` after the
# last one started while the list probe vouches for the catalog, and a freshness window
# after it otherwise (``pull_list_route.scan_is_due``). The panel starts a due scan at its
# next ask, the probe's or its poll's, at most ``SLOW_POLL_MS`` later, and polling fast
# while it runs, sees it end within ``FAST_POLL_MS`` (both in pull-page.js). So a live
# panel's asks are at most the longer interval plus those two apart, and the difference
# between two scans' run times; the rest of the window is slack for that difference and a
# timer made late, a judgment no test pins. The walk asks again at most ``SLOW_POLL_MS``
# after it is held (``pauseCoreQueue``), so a window shorter than the gap between two asks
# gave the walk the share in between: reserving only while the lane had work, a walk
# longer than one hour's share held the prefetch to 2 records an hour at 5,000 rows in
# review A1's model of #761. Over the process's ceiling a scan waits
# ``CEILING_FULL_READ_S``, but the ceiling then refuses the walk as well.
# ``tests/test_github_pull_prefetch.py`` pins the sum without the slack.
ASKED_WITHIN_S: Final = 150.0
MAX_RECENT: Final = 16
# The numbers ``GET pull`` most recently answered, which ``changed`` adds.
MAX_VIEWED: Final = 16
_HOUR: Final = timedelta(hours=1)
_FIELDS: Final = frozenset({"records", "files", "changed"})

type ItemKind = Literal["record", "files"]
type PrefetchStart = Literal["started", "joined", "not_due", "deferred"]
type DeferReason = Literal["below_floor", "rate_hold", "self_ceiling", "hourly_cap", "scan_cap"]
# An item's end: refreshed or failed, or why it started nothing, or why the lane stopped.
type ItemOutcome = str


class PrefetchRequestError(Exception):
    """A request the prefetch route refuses; its message names only the request."""


@dataclass(frozen=True, slots=True)
class PrefetchRequest:
    records: tuple[int, ...] = ()
    files: tuple[int, ...] = ()
    changed: bool = False


def _numbers(body: Mapping[str, object], name: str) -> tuple[int, ...]:
    value = body.get(name, [])
    if (
        not isinstance(value, list)
        or len(value) > MAX_PREFETCH_NUMBERS  # pyright: ignore[reportUnknownArgumentType]
        or any(
            type(number) is not int or not 1 <= number <= MAX_PULL_REQUEST_NUMBER
            for number in value  # pyright: ignore[reportUnknownVariableType]
        )
        or len(set(value)) != len(value)  # pyright: ignore[reportUnknownArgumentType]
    ):
        raise PrefetchRequestError(
            f'"{name}" is a list of at most {MAX_PREFETCH_NUMBERS} distinct pull-request numbers'
        )
    return tuple(value)  # pyright: ignore[reportUnknownArgumentType]


def prefetch_request(body: Mapping[str, object]) -> PrefetchRequest:
    """What a ``POST`` body names, or :class:`PrefetchRequestError`."""

    if set(body) - _FIELDS:
        raise PrefetchRequestError(
            'a prefetch request names only "records", "files", and "changed"'
        )
    changed = body.get("changed", False)
    if not isinstance(changed, bool):
        raise PrefetchRequestError('"changed" is true or false')
    return PrefetchRequest(_numbers(body, "records"), _numbers(body, "files"), changed)


@dataclass(frozen=True, slots=True)
class Item:
    """One thing to refresh. *named* says the page named it, so a missing record is read."""

    kind: ItemKind
    number: int
    named: bool = True


class ItemWire(TypedDict):
    kind: ItemKind
    number: int


class OutcomeWire(TypedDict):
    kind: ItemKind
    number: int
    outcome: ItemOutcome
    at: str


@dataclass(eq=False)
class Lane:
    """One repository's prefetch: its queue, its caps' use, and what it last did."""

    queue: deque[Item] = field(default_factory=deque[Item])
    running: Item | None = None
    scan: str | None = None
    scan_used: int = 0
    record_starts: deque[datetime] = field(default_factory=deque[datetime])
    file_starts: deque[datetime] = field(default_factory=deque[datetime])
    recent: deque[OutcomeWire] = field(
        default_factory=lambda: deque[OutcomeWire](maxlen=MAX_RECENT)
    )
    viewed: OrderedDict[int, None] = field(default_factory=OrderedDict[int, None])
    # The lists this ask made local, by number: the comparison its head fetch prepared, or
    # ``None`` once tried with none to give. Each ask starts again (:func:`request_prefetch`).
    prepared: dict[int, LocalComparison | None] = field(
        default_factory=dict[int, "LocalComparison | None"]
    )
    # Numbers whose list the store gives with no GitHub, which the lane lists first.
    local_ready: set[int] = field(default_factory=set[int])
    # Until when a head fetch that failed is not tried again, so an ask that moves on does
    # not repeat it at once; the lists go to GitHub meanwhile.
    heads_held_until: datetime | None = None
    # When a page last asked for the lane, refused or not (:func:`request_prefetch`).
    asked_at: datetime | None = None

    def note(self, item: Item, outcome: ItemOutcome) -> None:
        self.recent.append(
            OutcomeWire(
                kind=item.kind, number=item.number, outcome=outcome, at=utc_stamp(pulls.utc_now())
            )
        )

    def used(self, starts: deque[datetime], now: datetime) -> int:
        while starts and now - starts[0] >= _HOUR:
            starts.popleft()
        return len(starts)


_LANES: WeakKeyDictionary[ServedPulls, Lane] = WeakKeyDictionary()


def lane_of(served: ServedPulls) -> Lane:
    """The lane of a repository's pull requests in this server, made on first use."""

    lane = _LANES.get(served)
    if lane is None:
        lane = _LANES[served] = Lane()
    return lane


def forget_lanes() -> None:
    """Forget every lane, as a new process holds none; for tests."""

    _LANES.clear()


def reserved(now: datetime) -> int:
    """What the cores walk leaves the prefetch of speculative work's share at *now*.

    For each lane with work queued or running, what its caps can still spend this hour at
    the prices they are set at, and the price of the item running. For an idle lane a
    page asked for within :data:`ASKED_WITHIN_S`, one scan's records, at most what the
    hour's cap has left (:data:`RECORDS_PER_SCAN`). For any other lane, nothing.

    The running item's price covers the points its cap has counted and its job has not
    yet spent. A record is counted twice, at most :data:`POINTS_PER_RECORD` for each busy
    lane and only in the prefetch's favour, while its checks run, before its start is
    counted against the cap, and once its job has spent, until it ends (review A8 of
    #761).

    Reserving the caps' whole price in every hour, whatever the prefetch was doing, held a
    cold catalog's walk of 800 rows, 100 batches of a point, to 8 points an hour, about 13
    hours (review D1 of #737). Reserving nothing let a walk that spent first refuse the
    prefetch (review B1). Reserving only while a lane had work let a walk longer than one
    hour's share take the share between a page's asks, hour after hour (review A1 of
    #761). So a lane with work has its caps, one a page keeps asking for has a scan's
    records, and the walk spends what the rest leave. Read on the event loop, which
    changes the lanes.
    """

    price = {"record": POINTS_PER_RECORD, "files": POINTS_PER_FILES_LIST}
    asked = timedelta(seconds=ASKED_WITHIN_S)
    total = 0
    for lane in list(_LANES.values()):
        records = max(0, RECORDS_PER_HOUR - lane.used(lane.record_starts, now))
        if lane.queue or lane.running is not None:
            files = max(0, FILES_PER_HOUR - lane.used(lane.file_starts, now))
            total += records * POINTS_PER_RECORD + files * POINTS_PER_FILES_LIST
            total += price[lane.running.kind] if lane.running is not None else 0
        elif lane.asked_at is not None and timedelta(0) <= now - lane.asked_at <= asked:
            total += min(RECORDS_PER_SCAN, records) * POINTS_PER_RECORD
    return total


def note_viewed(served: ServedPulls, number: int) -> None:
    """Remember that ``GET pull`` answered *number*, most recent last, bounded."""

    viewed = lane_of(served).viewed
    viewed[number] = None
    viewed.move_to_end(number)
    while len(viewed) > MAX_VIEWED:
        viewed.popitem(last=False)


def _key(served: ServedPulls) -> str:
    return f"{served.source}:pulls-prefetch"


def _items(lane: Lane, ask: PrefetchRequest) -> list[Item]:
    records = [Item("record", number) for number in ask.records]
    if ask.changed:
        named = set(ask.records)
        records += [
            Item("record", number, named=False)
            for number in reversed(lane.viewed)
            if number not in named
        ]
    files = [Item("files", number) for number in ask.files]
    # The kinds take turns, each in its own order.
    return [item for pair in zip_longest(records, files) for item in pair if item is not None]


def _repository_hold(served: ServedPulls, now: datetime) -> bool:
    """Whether the catalog's persisted stamp, which any process may have written, holds."""

    return rate_limit_holds(read_list_refresh(served.home, served.slug, "all"), now=now)


async def _governor(served: ServedPulls) -> gh_budget.Admission:
    now = pulls.utc_now()
    verdict = gh_budget.admission(("core",), now=now, speculative=True)
    if verdict.admitted and await asyncio.to_thread(_repository_hold, served, now):
        return gh_budget.Admission(False, "rate_hold")
    return verdict


async def request_prefetch(
    app: Any, host: PullHost, ask: PrefetchRequest
) -> tuple[PrefetchStart, DeferReason | None, int]:
    """Queue what *ask* names and start or join the lane: how it went, why not, and how many."""

    assert host.coordinator is not None
    lane = lane_of(host.pulls)
    # A page is looking at the list, whatever the ask names or the governor says, so the
    # cores walk leaves the lane a scan's records until it stops asking (:func:`reserved`).
    lane.asked_at = pulls.utc_now()
    items = _items(lane, ask)
    if not items:
        lane.queue.clear()
        return "not_due", None, 0
    verdict = await _governor(host.pulls)
    if not verdict.admitted:
        # A list the store gives costs GitHub nothing, so the lists go on without the rest:
        # each one the store cannot give is refused as the records are (`_files`).
        items = [item for item in items if item.kind == "files"]
        if not items:
            lane.queue.clear()
            return "deferred", verdict.reason, 0
    lane.queue = deque(items)
    # Each ask prepares its lists again, as the heads and base branches are then: a list
    # already current is left out, so this costs a fetch only when there is a list to make.
    lane.prepared = {}
    lane.local_ready = set()
    started = host.coordinator.start(
        _key(host.pulls), partial(_run_lane, app, host, lane), network=False
    )
    # A reason beside a start says the lane lists only what the store gives.
    return started, verdict.reason, len(items)


_STOPS: Final = frozenset(
    {
        "deferred:below_floor",
        "deferred:rate_hold",
        "deferred:self_ceiling",
        "failed:rate_limited",
        "failed:network_error",
        "failed:unexpected",
        "preempted",
    }
)
# A cap is one kind's: reaching it drops the rest of that kind, and the other goes on.
_KIND_STOPS: Final = frozenset({"deferred:hourly_cap", "deferred:scan_cap"})


async def _run_lane(app: Any, host: PullHost, lane: Lane) -> None:
    # Nobody is looking at what the lane reads: every job it starts copies this context,
    # so what each spends counts toward speculative work's share of the ceiling.
    try:
        with gh_budget.speculative():
            await _work_lane(app, host, lane)
    finally:
        # A lane stopped before its end, as at shutdown, runs nothing it had queued, so it
        # holds nothing back from the cores walk either (:func:`reserved`).
        lane.queue.clear()


async def _work_lane(app: Any, host: PullHost, lane: Lane) -> None:
    while lane.queue:
        if any(item.kind == "files" and item.number not in lane.prepared for item in lane.queue):
            try:
                await _prepare_lists(host, lane)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A bug, which the log names; each list then goes as it would have.
                log.exception("preparing the prefetch's local lists failed")
            if not lane.queue:
                break
        item = lane.queue.popleft()
        lane.running = item
        try:
            if item.kind == "record":
                outcome = await _record(host, lane, item)
            else:
                outcome = await _files(app, host, lane, item)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A bug, which the log names; the lane stops rather than repeat it.
            log.exception("a prefetch item failed")
            outcome = "failed:unexpected"
        finally:
            lane.running = None
        lane.note(item, outcome)
        # A list the store gives costs GitHub nothing, so neither the governor's refusal nor
        # the cap of lists drops one queued; anything else that stops the lane does.
        if outcome in _STOPS:
            governor = outcome.startswith("deferred:")
            lane.queue = deque(other for other in lane.queue if governor and _free(lane, other))
        elif outcome in _KIND_STOPS:
            lane.queue = deque(
                other for other in lane.queue if other.kind != item.kind or _free(lane, other)
            )


def _free(lane: Lane, item: Item) -> bool:
    """Whether *item* is a list the store gives, which the lane asks no governor for."""

    return item.kind == "files" and item.number in lane.local_ready


def _listable_heads(
    served: ServedPulls, numbers: list[int]
) -> tuple[dict[int, tuple[str, str]], set[int]]:
    """Which of *numbers* to list from a head and base branch, and which a record's comparison
    lists. Blocking and bounded: a record and a catalog row each, through their caches."""

    from metabrowser.builtin_plugins.github.pull_files_route import list_source

    heads: dict[int, tuple[str, str]] = {}
    recorded: set[int] = set()
    for number in numbers:
        source = list_source(served.home, served.slug, number)
        if source == "record":
            recorded.add(number)
        elif source is not None:
            heads[number] = source
    return heads, recorded


async def _prepare_lists(host: PullHost, lane: Lane) -> None:
    """Make the queued lists local where the store can give them, then queue those first.

    A list is made only for a pull request whose cached list is not current
    (:func:`~.pull_files_route.list_source`). For an open pull request whose record has no
    comparison of its newest known head, the heads the store lacks and every base branch
    named arrive in one fetch (:func:`~metabrowser.cache.pull_refs.fetch_pull_heads`), so
    each is compared from its base branch as the origin has it now, as GitHub's list is, and
    its list is the store's manifest with no GitHub request (:mod:`.pull_files_refresh`).
    The fetch, and attaching a served checkout's store, run at the store's turn as
    background work, which a reader's job preempts (:class:`~metabrowser.mirror_refresh.
    StoreTurn`); preempted, or with a fetch that failed, the lists go to GitHub as before.
    The lists the store gives go first, since each takes tens of milliseconds where a record
    takes seconds.
    """

    numbers = sorted(
        {item.number for item in lane.queue if item.kind == "files"} - lane.prepared.keys()
    )
    for number in numbers:
        lane.prepared[number] = None
    if not numbers or host.store_turn is None:
        return
    # A job in the event log: on the Diff summary's path, since a list it makes local is
    # one GitHub need not answer.
    work = asyncio.get_running_loop().create_task(
        event_log.job(
            _prepare_at_turn(host, lane, numbers),
            "pull_prefetch.prepare_lists",
            attrs={"pulls": len(numbers)},
        )
    )
    try:
        await asyncio.wait((work,))
    except asyncio.CancelledError:
        work.cancel()
        await asyncio.wait((work,))
        raise
    if work.cancelled():
        log.debug("a reader's job preempted the prefetch's local lists")
        return
    work.result()
    # Stable: each kind keeps its own order, and the lists the store gives come first.
    lane.queue = deque(
        sorted(
            lane.queue,
            key=lambda item: not (item.kind == "files" and item.number in lane.local_ready),
        )
    )


async def _prepare_at_turn(host: PullHost, lane: Lane, numbers: list[int]) -> None:
    from metabrowser.builtin_plugins.github.checkout import (
        CheckoutRepository,
        attach_store_for_lists,
    )
    from metabrowser.builtin_plugins.github.pull_list import LocalComparison
    from metabrowser.cache.pull_refs import (
        PullRefError,
        branch_endpoints,
        fetch_pull_heads,
        has_commit,
    )
    from metabrowser.git.process import GitError

    assert host.store_turn is not None
    me = asyncio.current_task()
    assert me is not None
    async with host.store_turn(me.cancel):
        served = host.pulls
        published = served.published
        if isinstance(published, CheckoutRepository):
            # A served checkout attaches its store when a reader first compares; the lists
            # attach it sooner, since a store is what lists them without GitHub.
            published = await attach_store_for_lists(published)
        if published is None or isinstance(published, ListedRepository):
            return
        git_dir = published.git_dir
        heads, recorded = await asyncio.to_thread(_listable_heads, served, numbers)
        lane.local_ready |= recorded
        now = pulls.utc_now()
        if not heads or (lane.heads_held_until is not None and now < lane.heads_held_until):
            return
        started = time.monotonic()
        try:
            missing = [
                number
                for number, (head, _) in heads.items()
                if not await has_commit(published, head)
            ]
            await fetch_pull_heads(
                published, missing, base_branches=sorted({base for _, base in heads.values()})
            )
        except (PullRefError, GitError) as exc:
            # A list from a base branch the origin has since moved would be wrong, so none is
            # made; GitHub's are read instead.
            lane.heads_held_until = now + timedelta(seconds=FRESHNESS_WINDOW_S)
            log.debug("the prefetch could not fetch %d heads: %r", len(heads), exc)
            return
        log.debug(
            "the prefetch fetched %d heads and their base branches in %.0f ms",
            len(missing),
            (time.monotonic() - started) * 1000,
        )
        gate = asyncio.Semaphore(MERGE_BASES_AT_ONCE)

        async def prepare(number: int, head: str, base_ref: str) -> None:
            async with gate:
                try:
                    if not await has_commit(published, head):
                        return
                    endpoints = await branch_endpoints(published, head=head, base_branch=base_ref)
                except (PullRefError, GitError) as exc:
                    log.debug("pull request %s is listed from GitHub: %r", number, exc)
                    return
            # A merge base that is the head lists nothing: a pull request merged into its
            # base since the list of pull requests was read. GitHub's list says what it was.
            if endpoints is not None and endpoints.base != head:
                lane.prepared[number] = LocalComparison(
                    git_dir, endpoints.base, head, base_ref=base_ref
                )
                lane.local_ready.add(number)

        await asyncio.gather(*(prepare(number, *head) for number, head in heads.items()))


def _refund(starts: deque[datetime], at: datetime) -> None:
    """Give back the start counted *at*, if the hour has not already pruned it."""

    with contextlib.suppress(ValueError):
        starts.remove(at)


async def _wait(host: PullHost, key: str) -> bool:
    """Wait for the job under *key*, never cancelling it; whether it ran to its end."""

    assert host.coordinator is not None
    job = host.coordinator.job(key)
    if job is None:
        return True
    await asyncio.wait((job,))
    return not job.cancelled()


async def _record(host: PullHost, lane: Lane, item: Item) -> ItemOutcome:
    from metabrowser.builtin_plugins.github.pull_route import record_and_freshness
    from metabrowser.builtin_plugins.github.served_pull import written_without_store

    if host.start_background is None or host.job_key is None:
        return "skipped:unsupported"
    if host.running(item.number):
        return "joined"
    served = host.pulls
    held, freshness = await asyncio.to_thread(record_and_freshness, served, item.number)
    if held is None:
        if not item.named:
            return "skipped:not_cached"
    elif freshness is None or freshness.verdict != "changed":
        # `checks`: only an open pull request's checks are due, which its visible page reads.
        return f"skipped:{freshness.verdict if freshness is not None else 'unverified'}"
    else:
        companion = await served.companion(item.number)
        companion.saw_record(
            held.fetched_at, without_store=written_without_store(held), freshness=freshness
        )
        if not companion.is_stale(pulls.utc_now(), window_s=FRESHNESS_WINDOW_S):
            return "skipped:not_due"
    verdict = await _governor(served)
    if not verdict.admitted:
        return f"deferred:{verdict.reason}"
    catalog = await asyncio.to_thread(read_catalog, served.home, served.slug)
    # One publication, however many pages its scan read: the revision moves with each page.
    scan = f"{catalog.epoch}:{catalog.fetched_at}" if catalog is not None else None
    if scan != lane.scan:
        lane.scan, lane.scan_used = scan, 0
    now = pulls.utc_now()
    if lane.scan_used >= RECORDS_PER_SCAN:
        return "deferred:scan_cap"
    if lane.used(lane.record_starts, now) >= RECORDS_PER_HOUR:
        return "deferred:hourly_cap"
    started = host.start_background(item.number)
    if started != "started":
        return started if started == "joined" else f"skipped:{started}"
    lane.scan_used += 1
    lane.record_starts.append(now)
    if not await _wait(host, host.job_key(item.number)):
        # A reader's job cancelled it: what it spent is in the governor's observations, and
        # the place it took in the caps is given back.
        if lane.scan == scan:
            lane.scan_used -= 1
        _refund(lane.record_starts, now)
        return "preempted"
    outcome = (await served.companion(item.number)).outcome()
    # An outcome from before this job says nothing of it, as after an unexpected error.
    if outcome is None or outcome["at"] < utc_stamp(now):
        return "failed:unknown"
    return "refreshed" if outcome["outcome"] == "succeeded" else f"failed:{outcome['outcome']}"


async def _files(app: Any, host: PullHost, lane: Lane, item: Item) -> ItemOutcome:
    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRefreshRequest,
        files_job_key,
        files_refresh_wanted,
        files_view,
        start_files_refresh,
    )
    from metabrowser.builtin_plugins.github.pull_list import read_files_refresh

    view = files_view(app, item.number)
    if view.repository is None or view.coordinator is None:
        return "skipped:not_github"
    if view.refreshing:
        return "joined"
    ask = FilesRefreshRequest(item.number, False)
    wanted, local = await asyncio.to_thread(
        files_refresh_wanted, view, ask, lane.prepared.get(item.number)
    )
    if not wanted:
        return "skipped:not_due"
    # A list the store gives needs no GitHub and is not counted, so the governor is not
    # asked for it (review B1 of #737). One Git cannot give after all falls through to
    # GitHub's, which `may_ask_github` admits as any list from GitHub is admitted.
    # When the list was counted toward the hour's cap, which a preempted job gives back.
    counted: list[datetime] = []
    if local is None:
        admitted = await _admit_from_github(host, lane)
        if isinstance(admitted, str):
            return admitted
        counted.append(admitted)
    now = pulls.utc_now()
    refused: list[ItemOutcome] = []

    async def may_ask_github() -> bool:
        admitted = await _admit_from_github(host, lane)
        if isinstance(admitted, str):
            refused.append(admitted)
            return False
        counted.append(admitted)
        return True

    started = start_files_refresh(
        view,
        ask,
        wanted=True,
        local=local,
        background=True,
        fallback=may_ask_github if local is not None else None,
    )
    if started != "started":
        for at in counted:
            _refund(lane.file_starts, at)
        return started if started == "joined" else f"skipped:{started}"
    if not await _wait(host, files_job_key(view.repository, item.number)):
        for at in counted:
            _refund(lane.file_starts, at)
        return "preempted"
    if refused:
        # Git could not give the list and GitHub's was not read: nothing was published.
        return refused[0]
    stamp = await asyncio.to_thread(
        read_files_refresh, view.repository.home, view.repository.slug, item.number
    )
    if stamp is None or stamp.at < utc_stamp(now):
        return "failed:unknown"
    return "refreshed" if stamp.outcome == "succeeded" else f"failed:{stamp.outcome}"


async def _admit_from_github(host: PullHost, lane: Lane) -> datetime | ItemOutcome:
    """When a list from GitHub was counted toward the hour's cap, or why it may not be read."""

    verdict = await _governor(host.pulls)
    if not verdict.admitted:
        return f"deferred:{verdict.reason}"
    now = pulls.utc_now()
    if lane.used(lane.file_starts, now) >= FILES_PER_HOUR:
        return "deferred:hourly_cap"
    lane.file_starts.append(now)
    return now


class BudgetWire(TypedDict):
    per_scan: int
    scan: str | None
    scan_used: int
    per_hour: int
    hour_used: int


class FilesBudgetWire(TypedDict):
    per_hour: int
    hour_used: int


class CeilingWire(TypedDict):
    per_hour: int
    hour_used: int
    # Speculative work's share of it, and what that work has spent: at or past it the
    # governor refuses the lane with ``self_ceiling`` though the ceiling itself has room.
    speculative_per_hour: int
    speculative_hour_used: int
    # What the cores walk leaves the lanes of that share now, nothing while none has work
    # or was asked for lately (:func:`reserved`), and what the walk has spent.
    prefetch_reserved: int
    walk_hour_used: int


class GovernorWire(TypedDict):
    floor: float
    admits: bool
    reason: str | None
    held_until: str | None
    observed: dict[str, gh_budget.ObservationWire]
    # What this process's automatic work may spend in a rolling hour, and has.
    ceiling: CeilingWire


class PrefetchEnvelope(TypedDict):
    source: str | None
    running: ItemWire | None
    queued: list[ItemWire]
    records: BudgetWire
    files: FilesBudgetWire
    governor: GovernorWire
    recent: list[OutcomeWire]


def _wire(item: Item) -> ItemWire:
    return ItemWire(kind=item.kind, number=item.number)


async def prefetch_envelope(host: PullHost | None) -> PrefetchEnvelope:
    """The lane as memory has it, read on the event loop that changes it.

    Only the catalog's persisted rate hold is read from disk, off the loop, first.
    """

    verdict = gh_budget.Admission(True)
    if host is not None:
        verdict = await _governor(host.pulls)
    now = pulls.utc_now()
    lane = lane_of(host.pulls) if host is not None else Lane()
    if host is None:
        verdict = gh_budget.admission(("core",), now=now, speculative=True)
    return PrefetchEnvelope(
        source=host.pulls.source if host is not None else None,
        running=_wire(lane.running) if lane.running is not None else None,
        queued=[_wire(item) for item in lane.queue],
        records=BudgetWire(
            per_scan=RECORDS_PER_SCAN,
            scan=lane.scan,
            scan_used=lane.scan_used,
            per_hour=RECORDS_PER_HOUR,
            hour_used=lane.used(lane.record_starts, now),
        ),
        files=FilesBudgetWire(per_hour=FILES_PER_HOUR, hour_used=lane.used(lane.file_starts, now)),
        governor=GovernorWire(
            floor=gh_budget.BACKGROUND_FLOOR,
            admits=verdict.admitted,
            reason=verdict.reason,
            held_until=gh_budget.held_until(now),
            observed=gh_budget.observations(now),
            ceiling=CeilingWire(
                per_hour=gh_budget.AUTOMATIC_CORE_PER_HOUR,
                hour_used=gh_budget.automatic_spent(now),
                speculative_per_hour=gh_budget.SPECULATIVE_CORE_PER_HOUR,
                speculative_hour_used=gh_budget.speculative_spent(now),
                prefetch_reserved=reserved(now),
                walk_hour_used=gh_budget.walk_spent(now),
            ),
        ),
        recent=list(lane.recent),
    )


__all__ = [
    "ASKED_WITHIN_S",
    "FILES_PER_HOUR",
    "MAX_PREFETCH_NUMBERS",
    "POINTS_PER_FILES_LIST",
    "POINTS_PER_RECORD",
    "PREFETCH_ROUTE",
    "RECORDS_PER_HOUR",
    "RECORDS_PER_SCAN",
    "Lane",
    "PrefetchEnvelope",
    "PrefetchRequest",
    "PrefetchRequestError",
    "forget_lanes",
    "lane_of",
    "note_viewed",
    "prefetch_envelope",
    "prefetch_request",
    "request_prefetch",
    "reserved",
]
