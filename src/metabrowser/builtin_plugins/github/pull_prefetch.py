"""Background prefetch: refresh what a reader is likely to open next, within a budget, behind them.

A visible page names what it expects the reader to open, in its order of priority, with
``POST /api/plugin/github/pulls-prefetch``:

- ``records``: pull requests whose record to read when it is missing or the catalog says
  it changed (:mod:`.pull_freshness`): the anchored row, its J/K neighbours, the top open
  pull requests, the visible rows;
- ``changed``: also the pull requests this server most recently answered ``GET pull`` for,
  when the catalog says they changed, which is what a scan that just published asks for;
- ``files``: pull requests whose changed-files list to read when the files route would
  start an automatic refresh, which a head or base that moved does at once.

Nothing on the server starts this by itself, so it runs only while a page is visible and
online, and a hidden or offline page asks for nothing. The request replaces the lane's
queue, so a walk that moved on drops what it no longer needs.

Each served repository has one lane, a coordinator job that runs one item at a time.
Before each item it reads again, off the event loop, whether the item is still due, which
another process's refresh may have made it not, then whether the rate-limit governor
admits it (:mod:`.gh_budget`) and the caps have room. It stops, dropping the rest, when
the governor refuses, a cap is reached, or a reader's pull-request job of the repository is
queued or running; the page asks again later. A job is started under the pull request's own
key, so a reader's request for it joins and promotes it, and as a background job it takes
no network slot and yields any store turn to a reader's job (:mod:`.checkout`,
:mod:`metabrowser.mirror_refresh`).

The caps, measured against the fake ``gh`` in ``tests/test_github_pull_prefetch.py``: a
background record refresh asks for at most 8 core points (two account checks, the pull,
and five parts of a page each; a ``304`` is free and an account check is not), and a
one-page files list for 3 (two account checks and the page). So :data:`RECORDS_PER_HOUR`
and :data:`FILES_PER_HOUR` spend at most 40 × 8 + 20 × 3 = 380 core points an hour, 7.6% of
a 5,000-point limit. :data:`RECORDS_PER_SCAN` keeps one scan's changes from spending most
of an hour's records at once.

``GET`` reports the lane from memory: the running item, the queue, the caps and their
use, the governor, and the last :data:`MAX_RECENT` outcomes.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github import gh_budget, pulls
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.builtin_plugins.github.pull_list import rate_limit_holds, read_list_refresh
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.builtin_plugins.github.served_pull import ServedPulls

log = logging.getLogger(__name__)

PREFETCH_ROUTE: Final = "/api/plugin/github/pulls-prefetch"
# Numbers a request may name in each list: the anchored row, two neighbours, the top five
# open pull requests, and the visible rows of a list pane fit.
MAX_PREFETCH_NUMBERS: Final = 16
RECORDS_PER_SCAN: Final = 8
RECORDS_PER_HOUR: Final = 40
FILES_PER_HOUR: Final = 20
MAX_RECENT: Final = 16
# The numbers ``GET pull`` most recently answered, which ``changed`` adds.
MAX_VIEWED: Final = 16
_HOUR: Final = timedelta(hours=1)
_FIELDS: Final = frozenset({"records", "files", "changed"})

type ItemKind = Literal["record", "files"]
type PrefetchStart = Literal["started", "joined", "not_due", "deferred"]
type DeferReason = Literal["below_floor", "rate_hold", "hourly_cap", "scan_cap", "foreground_busy"]
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
    items = [Item("record", number) for number in ask.records]
    if ask.changed:
        named = set(ask.records)
        items += [
            Item("record", number, named=False)
            for number in reversed(lane.viewed)
            if number not in named
        ]
    return items + [Item("files", number) for number in ask.files]


def _repository_hold(served: ServedPulls, now: datetime) -> bool:
    """Whether the catalog's persisted stamp, which any process may have written, holds."""

    return rate_limit_holds(read_list_refresh(served.home, served.slug, "all"), now=now)


async def _governor(served: ServedPulls) -> gh_budget.Admission:
    now = pulls.utc_now()
    verdict = gh_budget.admission(("core",), now=now)
    if verdict.admitted and await asyncio.to_thread(_repository_hold, served, now):
        return gh_budget.Admission(False, "rate_hold")
    return verdict


async def request_prefetch(
    app: Any, host: PullHost, ask: PrefetchRequest
) -> tuple[PrefetchStart, DeferReason | None, int]:
    """Queue what *ask* names and start or join the lane: how it went, why not, and how many."""

    assert host.coordinator is not None
    lane = lane_of(host.pulls)
    items = _items(lane, ask)
    if not items:
        lane.queue.clear()
        return "not_due", None, 0
    verdict = await _governor(host.pulls)
    if not verdict.admitted:
        lane.queue.clear()
        return "deferred", verdict.reason, 0
    lane.queue = deque(items)
    started = host.coordinator.start(
        _key(host.pulls), partial(_run_lane, app, host, lane), network=False
    )
    return started, None, len(items)


_STOPS: Final = frozenset(
    {
        *(
            f"deferred:{reason}"
            for reason in ("below_floor", "rate_hold", "hourly_cap", "scan_cap", "foreground_busy")
        ),
        "failed:rate_limited",
        "failed:network_error",
        "failed:unexpected",
    }
)


async def _run_lane(app: Any, host: PullHost, lane: Lane) -> None:
    while lane.queue:
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
        if outcome in _STOPS:
            lane.queue.clear()


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

    if host.start_background is None or host.foreground_busy is None or host.job_key is None:
        return "skipped:unsupported"
    if host.running(item.number):
        return "joined"
    if host.foreground_busy():
        return "deferred:foreground_busy"
    served = host.pulls
    held, freshness = await asyncio.to_thread(record_and_freshness, served, item.number)
    if held is None:
        if not item.named:
            return "skipped:not_cached"
    elif freshness is None or freshness.verdict != "changed":
        return (
            "skipped:current"
            if freshness is not None and freshness.verdict == "current"
            else "skipped:unverified"
        )
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
    scan = f"{catalog.epoch}:{catalog.revision}" if catalog is not None else None
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

    if host.foreground_busy is not None and host.foreground_busy():
        return "deferred:foreground_busy"
    view = files_view(app, item.number)
    if view.repository is None or view.coordinator is None:
        return "skipped:not_github"
    if view.refreshing:
        return "joined"
    ask = FilesRefreshRequest(item.number, False)
    wanted, local = await asyncio.to_thread(files_refresh_wanted, view, ask)
    if not wanted:
        return "skipped:not_due"
    # A local comparison's list needs no GitHub and is not counted, but one Git cannot
    # give falls through to GitHub's, so the governor is asked either way.
    verdict = await _governor(host.pulls)
    if not verdict.admitted:
        return f"deferred:{verdict.reason}"
    now = pulls.utc_now()
    if local is None and lane.used(lane.file_starts, now) >= FILES_PER_HOUR:
        return "deferred:hourly_cap"
    started = start_files_refresh(view, ask, wanted=True, local=local, background=True)
    if started != "started":
        return started if started == "joined" else f"skipped:{started}"
    if local is None:
        lane.file_starts.append(now)
    if not await _wait(host, files_job_key(view.repository, item.number)):
        return "preempted"
    stamp = await asyncio.to_thread(
        read_files_refresh, view.repository.home, view.repository.slug, item.number
    )
    if stamp is None or stamp.at < utc_stamp(now):
        return "failed:unknown"
    return "refreshed" if stamp.outcome == "succeeded" else f"failed:{stamp.outcome}"


class BudgetWire(TypedDict):
    per_scan: int
    scan: str | None
    scan_used: int
    per_hour: int
    hour_used: int


class FilesBudgetWire(TypedDict):
    per_hour: int
    hour_used: int


class GovernorWire(TypedDict):
    floor: float
    admits: bool
    reason: str | None
    held_until: str | None
    observed: dict[str, gh_budget.ObservationWire]


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
        verdict = gh_budget.admission(("core",), now=now)
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
        ),
        recent=list(lane.recent),
    )


__all__ = [
    "FILES_PER_HOUR",
    "MAX_PREFETCH_NUMBERS",
    "PREFETCH_ROUTE",
    "RECORDS_PER_HOUR",
    "RECORDS_PER_SCAN",
    "Lane",
    "PrefetchEnvelope",
    "PrefetchRequest",
    "PrefetchRequestError",
    "lane_of",
    "note_viewed",
    "prefetch_envelope",
    "prefetch_request",
    "request_prefetch",
]
