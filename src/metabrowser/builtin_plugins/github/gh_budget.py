"""The account's GitHub rate budget as its responses report it, and whether background work may spend it.

Every response :func:`~.gh.gh_api` and :func:`~.gh.gh_graphql` parse, refusals and ``304``
answers included, carries ``x-ratelimit-limit``, ``-remaining``, ``-reset`` (epoch seconds),
``-used``, and ``-resource``, ``core`` for REST and ``graphql`` for GraphQL (seen on both
on 2026-11-11). :func:`observe` keeps the newest of each resource for this process, until
its reset. A ``rate_limited`` refusal holds every resource until its ``reset_at``, or for a
freshness window when GitHub gave none (:func:`hold`).

The budget belongs to the account, not to Metabrowser: at the start of that measurement
the account had already spent 416 core and 162 GraphQL points of the hour from other
clients. So background work is admitted only while each observed resource it spends has
more than :data:`BACKGROUND_FLOOR` of its limit remaining and no hold applies
(:func:`admission`). With nothing observed it is admitted, and its first response is
observed.

Four kinds of work go below the floor, and only a hold stops them (the owner's rule,
2026-11-22):

- a reader's own action (Retry, Refresh, Fetch), which is never asked;
- the probes of the pull request on a visible page, conditional reads GitHub does not
  count when it answers ``304``; and
- the full read of a change such a probe finds, or the catalog reports, on that pull
  request: the floor is a reserve for the reader, and this is the page the reader is
  looking at; and
- for the same reason, the probe of a visible list, the scan a change it finds starts,
  the scan of the open pull requests' statuses a change or a moved base starts and its
  re-read of answers GitHub was still computing (:mod:`.pull_status_scan`), and the
  cores of the rows on screen (:func:`.pull_cores.request_preparation`), which this
  process's own ceiling still holds.

Everything else automatic stops below it: prefetch, backfill, the cores walk, stacks,
labels, the timeline, the periodic scans of the catalog and of its statuses, and the
files read, which ask :func:`admission`, and the reads a visible page's clock alone asks for, a record's
:data:`~.served_pull.FULL_REFRESH_S` full read (:meth:`.served_pull.ServedPull.below_floor`)
and an open one's status once a window, which spends GraphQL and so waits below that
budget's floor alone (:meth:`.served_pull.ServedPull.status_below_floor`).

The observations and the hold are this process's, and belong to the account the last
account check named (:func:`note_account`, called by :func:`~.gh.gh_account` and
:func:`~.gh.gh_active_account`): a switch to another account forgets both, since its
token has its own budget. A response already in flight when the account changed can
still be observed for the new one until its next check, at most one refresh's requests.
``remaining`` is the account's, so several servers on one account stop together.

Beside the account's budget this process keeps a ceiling on its own automatic work,
:data:`AUTOMATIC_CORE_PER_HOUR`. What the process spends it counts itself (:func:`spent`):
one for each REST answer that is not ``304``, and each GraphQL query's reported cost, in
the hour before now. ``x-ratelimit-used`` cannot count it, being the account's counter:
two of one process's responses 204 s apart differed by 208 calls, one of them its own, and
on 2026-11-22 the account's GraphQL ``remaining`` fell 433 points between two of one
script's queries a moment apart, each of cost 1. A reader's own action is not counted
(:func:`readers_own`), and is never limited. Past the ceiling (:func:`over_ceiling`),
background work is not admitted, probes slow to the full-read interval, and full reads to
:data:`CEILING_FULL_READ_S`, until enough of the hour's spending is an hour old.

Speculative work, which nobody is looking at, has its own share of that ceiling,
:data:`SPECULATIVE_CORE_PER_HOUR`: the prefetch of records and files lists, the catalog's
backfill past every reader's prefix, the cores walk past the rows on screen, and the label
set's periodic read. It runs inside :func:`speculative`, so what it spends counts toward
the share as well as the ceiling, and it asks :func:`admission` with ``speculative=True``,
which refuses it with ``self_ceiling`` once the share is spent. What is on screen, the
probes, the reads their changes start, the cores of visible rows, stacks, and the
timeline, is never refused for the share, so it keeps the rest of the ceiling whatever
speculative work spent (the owner's rule on review A1 of #737: what is on screen updates
within seconds, everything else every minute or two, inside the rate limit).

Inside the share the catalog's backfill past every reader's prefix and the prefetch go
before the cores walk past the rows on screen, whose cost grows with the catalog. The walk
runs inside ``speculative(walk=True)`` and asks with ``reserved`` set to what the
prefetch's caps can still spend this hour while a lane has work queued or running, to a
scan's records while a page has asked for the lane lately, and to nothing for a lane no
page asks for (:func:`.pull_prefetch.reserved`). So a walk that spends first does not
refuse the prefetch before its own caps do (review B1 of #737, review A1 of #761), and a
walk nobody's prefetch is asked beside spends the rest of the share (review D1 of #737).
The walk also waits while the backfill has pages the budget admits (review A2 of #761).
The backfill reserves nothing for anyone: it reads a page of rows a GraphQL point, once
per catalog epoch, and Quick Search across every state and the ref chooser's pull
requests by branch are complete only once it has.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, TypedDict

# A reserve for the reader and the account's other clients, not a measure of Metabrowser's
# own use. Below it only a reader's own action and a change found on the pull request on
# screen are read (the module docstring has the rule). A full read costs at most 6 core
# points, the pull and five parts of a page each, now that the account checks are
# conditional (:func:`~.gh.gh_account`), so 1,250 of 5,000 cover 200 such reads, a
# reader's Refresh or a change a probe found, with room beside them for the point a probe
# costs when GitHub answers it ``200``. That was measured when a record read its check runs
# and status; it reads three parts now, 4 points, and its status a GraphQL point, so the
# same floor covers about 300.
BACKGROUND_FLOOR: Final = 0.25
# How long a refusal that named no reset time holds: the refresh coordinator's window, as
# ``pull_list_refresh`` waits after one.
UNKNOWN_RESET_HOLD_S: Final = 60.0
# What this process's automatic work may spend in a rolling hour, in ``core`` calls and
# GraphQL points together. Six Metabrowser servers ran on one account on 2026-11-22 while
# its other clients spent about 1,500 of its 5,000 ``core`` an hour, so the ceiling is
# sized for six: 300 a server is at most 1,800 if all six reach it, which with those 1,500
# leaves the reader the 1,250 that ``BACKGROUND_FLOOR`` reserves and 450 beside it. One
# visible page whose repository is pushed to once a minute spends about 120 an hour on its
# two probes' ``200``s, and 40 catalog scans add 40 points: 160, before the full reads its
# changes start, the cores of its rows, and its timeline. Speculative work is held to its
# own share below, so what is on screen reaches the ceiling only by its own spending, with
# two such pages or CI running on one. That is arithmetic, not a measurement. See
# docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md.
AUTOMATIC_CORE_PER_HOUR: Final = 300
# The part of that ceiling speculative work may spend in a rolling hour: a third. What is
# on screen keeps the other 200 whatever speculative work spends, which covers the 160 the
# comment above prices one busy visible page at, with 40 beside it. Past its share
# speculative work is refused (``admission(..., speculative=True)``) and resumes as the
# hour rolls. The prefetch's caps are priced against this number beside
# ``RECORDS_PER_HOUR`` in ``pull_prefetch.py``, and the cores walk leaves the prefetch that
# price, less what the caps have used, while it has work, and a scan's records while a page
# asks for it (``reserved`` there). Only a scripted first visit has been measured against
# either number (the plan named above): ``GET /api/plugin/github/pulls-prefetch`` reports
# both, and what the hour has used of each, under ``governor.ceiling``, for ``metab --api``
# to read.
SPECULATIVE_CORE_PER_HOUR: Final = 100
# How far apart automatic full reads of one thing are held while the process is over its
# ceiling: the plan's five minutes, 12 reads an hour for each visible record or list.
CEILING_FULL_READ_S: Final = 300.0
# The rolling hour, kept as one count a minute: 60 numbers however much is spent.
_SPEND_BUCKET_S: Final = 60
_SPEND_BUCKETS: Final = 60
# Resources are header text, so the ones kept are bounded: GitHub names a handful.
_MAX_RESOURCES: Final = 8
_RESOURCE: Final = re.compile(r"[a-z_]{1,32}")
_COUNT: Final = re.compile(r"[0-9]{1,9}")
_EPOCH: Final = re.compile(r"[0-9]{1,12}")

type AdmissionReason = Literal["below_floor", "rate_hold", "self_ceiling"]


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RateObservation:
    """One resource's budget as a response reported it, valid until ``reset_at``."""

    resource: str
    limit: int
    remaining: int
    reset_at: str


class ObservationWire(TypedDict):
    limit: int
    remaining: int
    reset_at: str


@dataclass(frozen=True, slots=True)
class Admission:
    """Whether background work may start now, and if not, why."""

    admitted: bool
    reason: AdmissionReason | None = None


_OBSERVED: dict[str, RateObservation] = {}
_held_until: str | None = None
_account: str | None = None
# What automatic work spent in each minute of the last hour, by minute since the epoch.
_SPENT: dict[int, int] = {}
# The part of it speculative work spent, counted in both.
_SPECULATIVE_SPENT: dict[int, int] = {}
# The part of that the cores walk spent, counted in all three, which only reports it.
_WALK_SPENT: dict[int, int] = {}
# The event loop counts and worker threads read (``refresh_wanted`` of the list, stacks,
# labels, and files asks :func:`admission` in one), so both hold this, and a reader sums a
# copy: a bucket added during an iteration would raise ``RuntimeError``.
_SPENT_LOCK: Final = threading.Lock()
# Whether the work running in this context is a reader's own action. A task started
# inside :func:`readers_own` inherits it, as the refresh job a reader's click starts does.
_READERS_OWN: ContextVar[bool] = ContextVar("metabrowser_gh_readers_own", default=False)
# Whether the work running in this context is speculative, inherited the same way, and
# whether it is the cores walk's.
_SPECULATIVE: ContextVar[bool] = ContextVar("metabrowser_gh_speculative", default=False)
_WALK: ContextVar[bool] = ContextVar("metabrowser_gh_walk", default=False)


def note_account(login: str) -> None:
    """Keep the budget for *login*, the active account an account check just named.

    Another account than the last forgets every observation and the hold.
    """

    global _account, _held_until
    if _account is not None and login != _account:
        _OBSERVED.clear()
        _forget_spending()
        _held_until = None
    _account = login


def observe(headers: Mapping[str, str], *, resource: str) -> None:
    """Keep what *headers* (lowercased) say of the budget; *resource* when they name none."""

    named = headers.get("x-ratelimit-resource", resource)
    limit, remaining = (
        headers.get("x-ratelimit-limit", ""),
        headers.get("x-ratelimit-remaining", ""),
    )
    reset = headers.get("x-ratelimit-reset", "")
    if not (
        _RESOURCE.fullmatch(named)
        and _COUNT.fullmatch(limit)
        and _COUNT.fullmatch(remaining)
        and _EPOCH.fullmatch(reset)
        and int(limit) > 0
    ):
        return
    try:
        reset_at = _stamp(datetime.fromtimestamp(int(reset), tz=UTC))
    except (OverflowError, OSError, ValueError):
        return
    if named not in _OBSERVED and len(_OBSERVED) >= _MAX_RESOURCES:
        return
    _OBSERVED[named] = RateObservation(named, int(limit), int(remaining), reset_at)


def hold(reset_at: str | None, *, now: datetime) -> None:
    """Hold background work after a ``rate_limited`` refusal, never shortening a hold."""

    global _held_until
    deadline = reset_at or _stamp(now + timedelta(seconds=UNKNOWN_RESET_HOLD_S))
    try:
        _parse(deadline)
    except ValueError:
        deadline = _stamp(now + timedelta(seconds=UNKNOWN_RESET_HOLD_S))
    if _held_until is None or deadline > _held_until:
        _held_until = deadline


def held_until(now: datetime) -> str | None:
    """When the hold lifts, or ``None`` when none applies at *now*."""

    return _held_until if _held_until is not None and now < _parse(_held_until) else None


def observations(now: datetime) -> dict[str, ObservationWire]:
    """Each resource's budget as last observed, leaving out those past their reset."""

    return {
        name: ObservationWire(limit=seen.limit, remaining=seen.remaining, reset_at=seen.reset_at)
        for name, seen in sorted(_OBSERVED.items())
        if now < _parse(seen.reset_at)
    }


@contextmanager
def readers_own() -> Generator[None]:
    """Mark the work started inside as a reader's own action, which no ceiling counts.

    A route enters it around the start of what a reader's click asked for; the job's task
    copies the context when it is created, so its requests are the reader's too. A job
    already running that the click only joins stays automatic, and is counted.
    """

    token = _READERS_OWN.set(True)
    try:
        yield
    finally:
        _READERS_OWN.reset(token)


@contextmanager
def speculative(*, walk: bool = False) -> Generator[None]:
    """Mark the work started inside as speculative, counted toward its share of the ceiling.

    A lane enters it around work nobody is looking at; a task created inside copies the
    context, so a job the lane starts is speculative too. A reader's own action stays
    uncounted inside it. The cores *walk*'s batches are counted as the walk's as well, for
    :func:`walk_spent` to report.
    """

    token = _SPECULATIVE.set(True)
    walk_token = _WALK.set(walk)
    try:
        yield
    finally:
        _WALK.reset(walk_token)
        _SPECULATIVE.reset(token)


def speculating() -> bool:
    """Whether the work running in this context is speculative (:func:`speculative`)."""

    return _SPECULATIVE.get()


def _minute(now: datetime) -> int:
    return int(now.timestamp()) // _SPEND_BUCKET_S


def _forget_spending() -> None:
    with _SPENT_LOCK:
        _SPENT.clear()
        _SPECULATIVE_SPENT.clear()
        _WALK_SPENT.clear()


def spent(cost: int, *, now: datetime) -> None:
    """Count *cost* this process just spent at *now*, unless a reader's own action spent it.

    Speculative work's is counted toward its share as well, and the cores walk's as the
    walk's (:func:`speculative`).
    """

    if cost <= 0 or _READERS_OWN.get():
        return
    minute = _minute(now)
    counts: tuple[dict[int, int], ...] = (_SPENT,)
    if _SPECULATIVE.get():
        counts = (_SPENT, _SPECULATIVE_SPENT, *((_WALK_SPENT,) if _WALK.get() else ()))
    with _SPENT_LOCK:
        for count in counts:
            for old in [each for each in count if each <= minute - _SPEND_BUCKETS]:
                del count[old]
            count[minute] = count.get(minute, 0) + cost


def _hour(count: dict[int, int], now: datetime) -> int:
    minute = _minute(now)
    with _SPENT_LOCK:
        buckets = tuple(count.items())
    return sum(cost for each, cost in buckets if minute - _SPEND_BUCKETS < each <= minute)


def automatic_spent(now: datetime) -> int:
    """What this process's automatic work spent in the hour before *now*."""

    return _hour(_SPENT, now)


def speculative_spent(now: datetime) -> int:
    """What this process's speculative work spent in the hour before *now*."""

    return _hour(_SPECULATIVE_SPENT, now)


def walk_spent(now: datetime) -> int:
    """What this process's cores walk, past the rows on screen, spent in the hour."""

    return _hour(_WALK_SPENT, now)


def over_ceiling(now: datetime) -> bool:
    """Whether automatic work has spent :data:`AUTOMATIC_CORE_PER_HOUR` in the last hour."""

    return automatic_spent(now) >= AUTOMATIC_CORE_PER_HOUR


def full_read_interval(usual_s: float, *, now: datetime) -> float:
    """How far apart automatic full reads are held at *now*: *usual_s*, or the ceiling's."""

    return max(usual_s, CEILING_FULL_READ_S) if over_ceiling(now) else usual_s


def admission(
    resources: Iterable[str],
    *,
    now: datetime,
    floor: float = BACKGROUND_FLOOR,
    ceiling: bool = True,
    speculative: bool = False,
    reserved: int = 0,
) -> Admission:
    """Whether background work that spends *resources* may start at *now*.

    Not during a hold, below the floor of a resource it spends, nor, unless *ceiling* is
    false, while this process is over its own ceiling. A periodic full read of what is
    visible passes ``ceiling=False`` and slows itself instead (:func:`full_read_interval`).
    *speculative* work is refused as well, with the ceiling's reason, once speculative work
    has spent its own share of that ceiling (:data:`SPECULATIVE_CORE_PER_HOUR`) less
    *reserved*, the part of it the caller leaves to other speculative work: what the cores
    walk leaves the prefetch (:func:`.pull_prefetch.reserved`).
    """

    if held_until(now) is not None:
        return Admission(False, "rate_hold")
    for name in resources:
        seen = _OBSERVED.get(name)
        if seen is None or now >= _parse(seen.reset_at):
            continue
        if seen.remaining <= floor * seen.limit:
            return Admission(False, "below_floor")
    if ceiling and (
        over_ceiling(now)
        or (speculative and speculative_spent(now) + max(0, reserved) >= SPECULATIVE_CORE_PER_HOUR)
    ):
        return Admission(False, "self_ceiling")
    return Admission(True)


def forget() -> None:
    """Drop every observation and hold, as a new process starts with none; for tests."""

    global _account, _held_until
    _OBSERVED.clear()
    _forget_spending()
    _held_until = None
    _account = None


__all__ = [
    "AUTOMATIC_CORE_PER_HOUR",
    "BACKGROUND_FLOOR",
    "CEILING_FULL_READ_S",
    "SPECULATIVE_CORE_PER_HOUR",
    "UNKNOWN_RESET_HOLD_S",
    "Admission",
    "AdmissionReason",
    "ObservationWire",
    "RateObservation",
    "admission",
    "automatic_spent",
    "forget",
    "full_read_interval",
    "held_until",
    "hold",
    "note_account",
    "observations",
    "observe",
    "over_ceiling",
    "readers_own",
    "speculative",
    "speculating",
    "speculative_spent",
    "spent",
    "walk_spent",
]
