"""``GET /api/plugin/github/gh-requests``: what the server asked of GitHub, from the event log.

Every ``gh`` process is a span in the event log (:func:`.gh._run`), and its end record
says what it asked and how it went: its command (``args``, without values), how long gh
ran, the budget it was charged to (``budget``, :func:`.gh_budget.current_budget`), the
lane it served (``lane``, :func:`.gh_lanes.current_lane`), the request's ``fingerprint``
(:func:`.gh.fingerprint`), and, for a read of GitHub's answer,
its ``http_status`` and ``cost``, the number :mod:`.gh_budget` counted. Its parent is
the job it ran in, or the request that ran it, whose own record says how long it waited
for a network slot (``queued_ms``, :class:`metabrowser.mirror_refresh.NetworkSlots`).
This module reads those records over a window and says what they add up to, so the
GitHub traffic of a session of browsing can be measured before and after a change.

Parameters: ``since`` and ``until``, UTC moments as ``/api/event-log/failures`` takes
them, ``since`` an hour ago by default; ``pid``, one server's process; and ``buckets``,
how many equal parts the time in flight is cut into, :data:`DEFAULT_BUCKETS` by default.

The answer counts each ``gh`` call that ended in the window:

``requests``
    Every call, as one row.
``lanes``
    A row for each lane a call served (:mod:`.gh_lanes`), most urgent first: ``visible``
    (a page on screen, or a reader's own action), ``attended`` (read for what is on screen
    and not shown), ``prefetch``, and ``background``, and ``unknown`` for a call recorded
    before calls recorded their lane.
``budgets``
    A row for each budget a call is charged to, as :mod:`.gh_budget` counts them:
    ``reader`` (a reader's own action), ``automatic``, ``speculative``, and ``walk`` (the
    cores walk past the rows on screen), and ``unknown`` for a call recorded before calls
    recorded their budget.
``jobs``
    A row for each job the calls ran in, the most calls first: the job's name, or the
    request's for a call a request ran itself (``kind`` says which); ``none`` for a call
    that ran in no span, and ``unknown`` for one whose parent no segment read holds.
``in_flight``
    How many calls ran at once: the most and when it was first reached, the time spent at
    each count, and the most and the mean in each of ``buckets`` equal parts of the time
    from the first call's start to the last one's end.
``unrecorded``
    What a report of GitHub requests would want that the log does not hold, each with why.

A row holds:

``requests`` and ``commands``
    How many calls, and how many were REST (``gh api <path>``), GraphQL
    (``gh api graphql``), or ``other`` commands (``gh auth status``, ``gh --version``).
``statuses`` and ``no_status``
    How many ``gh api`` calls GitHub answered with each HTTP status; and of those with no
    status on record, how many ``failed`` before an answer, how many asked for none
    (``unread``: a call without ``--include``, as the first clone's size check is), and how
    many were recorded before calls recorded their status (``unrecorded``).
``core`` and ``graphql_points``
    What the answers cost: REST ``core`` calls, one for every answer but a ``304``, and
    GraphQL points, each query's reported cost; the numbers :mod:`.gh_budget` counted.
``share_304``
    The share of REST answers that were ``304``, or ``null`` with none.
``conditional`` and ``cache_hits``
    The REST answers to calls that carried an ETag, and those that were ``304``: the copy
    the server held was still current, and GitHub did not count the call.
``latency``
    The median, 95th percentile (nearest rank), longest, and total of the calls' times
    (:func:`metabrowser.event_log_views.time_statistics`). A call's time is gh's, from
    its start to its exit (:meth:`metabrowser.event_log.Span.stop`).
``duplicates``
    The calls that asked what an identical call of the same process (one ``fingerprint``)
    was still asking when they started (``in_flight``), and the calls that started within
    :data:`DUPLICATE_WINDOW_S` of an identical call's answer (``repeated``).
``peak_in_flight``
    The most of the row's calls running at once.
``queued``
    How long the spans the row's calls ran in waited for a network slot: how many recorded
    one, and the median, 95th percentile, longest, and total wait. A span that took several
    slots, as a scan takes one for each page, recorded their sum.

A call is in the window when it ended in it, and it starts at its end record's time less
its duration, to the millisecond. A call still running when the log is read is not
counted until it ends.

**Bounds.** The segments are those ``/api/event-log/failures`` reads
(:func:`metabrowser.event_log_route.window_segments`): the ones written since ``since``,
each read to a segment's bound, at most the directory's; the work is one parse of each
line, which is that route's too. The answer lists at most :data:`MAX_JOBS` jobs and says
how many more there are, and at most :data:`MAX_BUCKETS` parts of the time in flight.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal

from metabrowser import event_log
from metabrowser.builtin_plugins.github.gh_budget import BUDGETS
from metabrowser.builtin_plugins.github.gh_lanes import LANES
from metabrowser.builtin_plugins.github.served_pull import PROBE_FLOOR_S
from metabrowser.event_log_route import (
    QueryError,
    parse_moment,
    record_time,
    window_segments,
)
from metabrowser.event_log_views import time_statistics

# A call that starts this soon after an identical call of its process was answered is a
# repeated read: the probe floor (served_pull.PROBE_FLOOR_S), the shortest gap any of the
# plugin's clocks keeps between two reads of one thing, so no cadence asked for it. Two
# account checks a few hundred milliseconds apart, one for each job a refresh starts, are
# such a pair.
DUPLICATE_WINDOW_S: Final = PROBE_FLOOR_S
# The parts the time in flight is cut into by default: a minute each over the default
# window of an hour, when calls fill it. A browsing session of a few minutes asks for more.
DEFAULT_BUCKETS: Final = 60
# The most parts one answer carries: ten a minute over an hour, about 30 KB of JSON.
MAX_BUCKETS: Final = 600
# The most jobs one answer lists. The plugin starts about two dozen kinds of job, each
# named for its function (event_log.job_name), so this lists every one; a call a request
# runs itself is named for the request's method and path, which the routes bound.
MAX_JOBS: Final = 40
# Decimal places a share keeps.
_SHARE_DIGITS: Final = 3
# The header a conditional call sends, as gh.loggable_args keeps it: its name, and no value.
_CONDITIONAL_ARG: Final = "if-none-match:"

type Command = Literal["rest", "graphql", "other"]
type OwnerKind = Literal["job", "request", "none", "unknown"]
COMMANDS: Final[tuple[Command, ...]] = ("rest", "graphql", "other")
# Every budget a row is kept for, :mod:`.gh_budget`'s and one for calls that record none.
REPORTED_BUDGETS: Final[tuple[str, ...]] = (*BUDGETS, "unknown")
# Every lane a row is kept for, :mod:`.gh_lanes`'s in its order and one for calls that
# record none.
REPORTED_LANES: Final[tuple[str, ...]] = (*LANES, "unknown")

UNRECORDED: Final[dict[str, str]] = {
    "first_answer_seen": (
        "when a page first showed GitHub's answer: a page reports a wait only once it is "
        "late, so the time to a first answer is not in the log"
    ),
    "local_cache_hits": (
        "reads the server answered from its own store: those make no gh call, so cache_hits "
        "counts only the 304s GitHub answered"
    ),
    "store_turn_waits": (
        "time a job waited for its turn at the store: queued counts only the waits for a "
        "network slot"
    ),
}


@dataclass(frozen=True, slots=True)
class Query:
    """The window and the process one report reads."""

    since: datetime
    until: datetime | None = None
    pid: int | None = None
    buckets: int = DEFAULT_BUCKETS

    def describe(self) -> dict[str, Any]:
        return {
            "since": _stamp(self.since),
            "until": _stamp(self.until) if self.until is not None else None,
            "pid": self.pid,
            "buckets": self.buckets,
        }


def _whole(raw: str | None, field: str, *, low: int, high: int) -> int | None:
    if raw is None or raw == "":
        return None
    if not (raw.isascii() and raw.isdigit()) or len(raw) > 10:
        raise QueryError(f"{field} must be a whole number")
    value = int(raw)
    if not low <= value <= high:
        raise QueryError(f"{field} must be from {low} to {high}")
    return value


def parse_query(params: dict[str, str], *, now: datetime) -> Query:
    """The report's parameters, or :class:`~metabrowser.event_log_route.QueryError`."""

    unknown = sorted(set(params) - {"since", "until", "pid", "buckets"})
    if unknown:
        raise QueryError(f"unknown parameter {', '.join(unknown)}")
    since = parse_moment(params.get("since"), "since")
    until = parse_moment(params.get("until"), "until")
    if since is None:
        since = now - timedelta(seconds=event_log.RECENT_WINDOW_S)
    if until is not None and until < since:
        raise QueryError("until must not be before since")
    buckets = _whole(params.get("buckets"), "buckets", low=1, high=MAX_BUCKETS)
    return Query(
        since=since,
        until=until,
        pid=_whole(params.get("pid"), "pid", low=1, high=2**31 - 1),
        buckets=DEFAULT_BUCKETS if buckets is None else buckets,
    )


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _instant(seconds: float) -> str:
    """*seconds* since the epoch as the log writes a record's time: UTC, to the millisecond."""

    return datetime.fromtimestamp(seconds, UTC).isoformat(timespec="milliseconds")[:-6] + "Z"


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


@dataclass(frozen=True, slots=True)
class _Owner:
    """A span a call can run in, as its records name it."""

    kind: str
    name: str
    queued_ms: float | None


# A server process, as its segments name it: when it started, and its process ID. Span IDs
# are unique within one, and the start tells a process from a later one given the same ID.
type Process = tuple[str, int]


@dataclass(frozen=True, slots=True)
class _Call:
    """One ``gh`` call that ended in the window, as its end record says."""

    order: int
    process: Process
    pid: int
    parent: int | None
    start: float
    end: float
    dur_ms: float
    command: Command
    status: int | None
    cost: int | None
    conditional: bool
    budget: str
    lane: str
    fingerprint: str | None
    failed: bool
    recorded: bool


def _command(name: str, args: list[Any]) -> Command:
    if name != "gh api":
        return "other"
    return "graphql" if "graphql" in args[1:2] else "rest"


def _call(order: int, process: Process, record: dict[str, Any], moment: datetime) -> _Call | None:
    """*record* as a call, or ``None`` when it is not the end of a ``gh`` process."""

    name = record.get("name")
    if (
        record.get("event") != "end"
        or record.get("kind") != "subprocess"
        or not isinstance(name, str)
        or not (name == "gh" or name.startswith("gh "))
    ):
        return None
    duration = _number(record.get("dur_ms"))
    if duration is None or duration < 0:
        return None
    raw_attrs = record.get("attrs")
    attrs: dict[str, Any] = raw_attrs if isinstance(raw_attrs, dict) else {}  # pyright: ignore[reportUnknownVariableType]
    raw_args = attrs.get("args")
    args: list[Any] = raw_args if isinstance(raw_args, list) else []  # pyright: ignore[reportUnknownVariableType]
    budget = attrs.get("budget")
    recorded = budget in BUDGETS
    lane = attrs.get("lane")
    fingerprint = attrs.get("fingerprint")
    end = moment.timestamp()
    return _Call(
        order=order,
        process=process,
        pid=process[1],
        parent=_count(record.get("parent")),
        start=end - duration / 1000,
        end=end,
        dur_ms=duration,
        command=_command(name, args),
        status=_count(attrs.get("http_status")),
        cost=_count(attrs.get("cost")),
        conditional=any(
            isinstance(arg, str) and arg.lower().startswith(_CONDITIONAL_ARG) for arg in args
        ),
        budget=budget if isinstance(budget, str) and recorded else "unknown",
        lane=lane if isinstance(lane, str) and lane in LANES else "unknown",
        fingerprint=fingerprint if isinstance(fingerprint, str) else None,
        failed=record.get("outcome") != "ok",
        recorded=recorded,
    )


def _owner(record: dict[str, Any], known: _Owner | None) -> _Owner | None:
    """What *record*, of a job or a request, adds to what is known of its span."""

    kind = record.get("kind")
    name = record.get("name")
    if kind not in ("job", "request") or not isinstance(name, str):
        return known
    raw_attrs = record.get("attrs")
    attrs: dict[str, Any] = raw_attrs if isinstance(raw_attrs, dict) else {}  # pyright: ignore[reportUnknownVariableType]
    queued = _number(attrs.get("queued_ms"))
    # A span's wait only grows as it takes slots, and the segments are read newest first,
    # so the most any of its records says is what it waited in all.
    if known is not None and known.queued_ms is not None:
        queued = known.queued_ms if queued is None else max(queued, known.queued_ms)
    return _Owner(str(kind), name, queued)


type _Owners = dict[tuple[Process, int], _Owner]


@dataclass(slots=True)
class _Read:
    calls: list[_Call]
    owners: _Owners
    files: list[str]
    scanned: int


def _read(query: Query, *, state: Path, directory: Path) -> _Read:
    calls: list[_Call] = []
    owners: _Owners = {}
    files: list[str] = []
    scanned = 0
    for name, data in window_segments(state=state, directory=directory, since=query.since):
        files.append(name)
        named = event_log.parse_file_name(name)
        started = named[0] if named is not None else ""
        for record in event_log.parse_lines(data):
            scanned += 1
            pid = _count(record.get("pid"))
            if pid is None or (query.pid is not None and pid != query.pid):
                continue
            process = (started, pid)
            span = _count(record.get("span"))
            if span is not None and record.get("kind") in ("job", "request"):
                owned = _owner(record, owners.get((process, span)))
                if owned is not None:
                    owners[(process, span)] = owned
                continue
            moment = record_time(record)
            if (
                moment is None
                or moment < query.since
                or (query.until is not None and moment > query.until)
            ):
                continue
            call = _call(len(calls), process, record, moment)
            if call is not None:
                calls.append(call)
    return _Read(calls, owners, files, scanned)


def _duplicates(calls: Iterable[_Call]) -> dict[int, str]:
    """For each call that repeats an identical one of its process, how: by its order.

    ``in_flight`` when an identical call that started before it had not ended when it
    started; ``repeated`` when the latest such call ended at most
    :data:`DUPLICATE_WINDOW_S` before it started.
    """

    alike: dict[tuple[Process, str], list[_Call]] = defaultdict(list)
    for call in calls:
        if call.fingerprint is not None:
            alike[(call.process, call.fingerprint)].append(call)
    found: dict[int, str] = {}
    for group in alike.values():
        group.sort(key=lambda c: (c.start, c.order))
        answered = -math.inf
        for call in group:
            if answered > call.start:
                found[call.order] = "in_flight"
            elif call.start - answered <= DUPLICATE_WINDOW_S:
                found[call.order] = "repeated"
            answered = max(answered, call.end)
    return found


def _changes(calls: Iterable[_Call]) -> list[tuple[float, int]]:
    """Each call's start and end as a change in how many run, in time order. At one moment
    an end comes before a start, so a call that starts as another ends does not overlap it."""

    return sorted(
        [change for call in calls for change in ((call.start, 1), (call.end, -1))],
        key=lambda change: (change[0], change[1]),
    )


def _peak(calls: Iterable[_Call]) -> int:
    """The most of *calls* running at once, for any time at all."""

    most = running = 0
    changes = _changes(calls)
    for index, (moment, step) in enumerate(changes):
        running += step
        held = index + 1 < len(changes) and changes[index + 1][0] > moment
        if held:
            most = max(most, running)
    return most


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, _SHARE_DIGITS) if whole else None


def _row(calls: list[_Call], *, owners: _Owners, repeats: dict[int, str]) -> dict[str, Any]:
    """What *calls* add up to (the module's docstring names each field)."""

    commands = dict.fromkeys(COMMANDS, 0)
    statuses: dict[int, int] = defaultdict(int)
    no_status = {"failed": 0, "unread": 0, "unrecorded": 0}
    core = points = conditional = hits = rest_answers = answered_304 = 0
    duplicates = {"in_flight": 0, "repeated": 0}
    waits: dict[tuple[Process, int], float] = {}
    for call in calls:
        commands[call.command] += 1
        how = repeats.get(call.order)
        if how is not None:
            duplicates[how] += 1
        if call.parent is not None:
            owner = owners.get((call.process, call.parent))
            if owner is not None and owner.queued_ms is not None:
                waits[(call.process, call.parent)] = owner.queued_ms
        if call.command == "other":
            continue
        if call.status is None:
            key = "unrecorded" if not call.recorded else "failed" if call.failed else "unread"
            no_status[key] += 1
            continue
        statuses[call.status] += 1
        if call.command == "graphql":
            points += call.cost or 0
            continue
        core += call.cost or 0
        rest_answers += 1
        conditional += call.conditional
        if call.status == 304:
            answered_304 += 1
            hits += call.conditional
    queued = list(waits.values())
    return {
        "requests": len(calls),
        "commands": commands,
        "statuses": {str(status): statuses[status] for status in sorted(statuses)},
        "no_status": no_status,
        "core": core,
        "graphql_points": points,
        "share_304": _share(answered_304, rest_answers),
        "conditional": conditional,
        "cache_hits": hits,
        "latency": time_statistics([call.dur_ms for call in calls]),
        "duplicates": duplicates,
        "peak_in_flight": _peak(calls),
        "queued": {"spans": len(queued), **time_statistics(queued)},
    }


def _job(call: _Call, owners: _Owners) -> tuple[OwnerKind, str | None]:
    """The job *call* ran in, or the request that ran it."""

    if call.parent is None:
        return "none", None
    owner = owners.get((call.process, call.parent))
    if owner is None:
        return "unknown", None
    return ("job" if owner.kind == "job" else "request"), owner.name


def _in_flight(calls: list[_Call], *, buckets: int) -> dict[str, Any]:
    """How many of *calls* ran at once over the time from the first start to the last end."""

    if not calls:
        return {
            "peak": 0,
            "peak_at": None,
            "first": None,
            "last": None,
            "levels_ms": {},
            "bucket_ms": None,
            "series": [],
        }
    first = min(call.start for call in calls)
    last = max(call.end for call in calls)
    width = (last - first) / buckets
    peaks = [0] * buckets
    areas = [0.0] * buckets
    levels: dict[int, float] = defaultdict(float)
    peak, peak_at = 0, first
    running, previous = 0, first
    for moment, step in _changes(calls):
        if moment > previous:
            levels[running] += moment - previous
            if running > peak:
                peak, peak_at = running, previous
            if width > 0:
                low = min(int((previous - first) / width), buckets - 1)
                high = min(int((moment - first) / width), buckets - 1)
                for index in range(low, high + 1):
                    start = first + index * width
                    overlap = min(moment, start + width) - max(previous, start)
                    if overlap > 0:
                        areas[index] += running * overlap
                        peaks[index] = max(peaks[index], running)
            previous = moment
        running += step
    return {
        "peak": peak,
        "peak_at": _instant(peak_at) if peak else None,
        "first": _instant(first),
        "last": _instant(last),
        "levels_ms": {str(level): round(levels[level] * 1000, 1) for level in sorted(levels)},
        "bucket_ms": round(width * 1000, 1),
        "series": [
            {
                "at_ms": round(index * width * 1000, 1),
                "peak": peaks[index],
                "mean": round(areas[index] / width, 2) if width > 0 else 0.0,
            }
            for index in range(buckets)
        ],
    }


def report(query: Query, *, state: Path, directory: Path) -> dict[str, Any]:
    """The request report for *query* from the log in *directory*. Blocking."""

    read = _read(query, state=state, directory=directory)
    calls = read.calls
    repeats = _duplicates(calls)
    by_lane: dict[str, list[_Call]] = {lane: [] for lane in REPORTED_LANES}
    by_budget: dict[str, list[_Call]] = {budget: [] for budget in REPORTED_BUDGETS}
    by_job: dict[tuple[OwnerKind, str | None], list[_Call]] = defaultdict(list)
    for call in calls:
        by_lane[call.lane].append(call)
        by_budget[call.budget].append(call)
        by_job[_job(call, read.owners)].append(call)
    ranked = sorted(by_job.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1] or ""))

    def row(of: list[_Call]) -> dict[str, Any]:
        return _row(of, owners=read.owners, repeats=repeats)

    return {
        "schema_version": event_log.SCHEMA_VERSION,
        "directory": str(directory),
        "state": "present" if directory.is_dir() else "absent",
        "query": query.describe(),
        "files": read.files,
        "scanned": read.scanned,
        "pids": sorted({call.pid for call in calls}),
        "duplicate_window_s": DUPLICATE_WINDOW_S,
        "requests": row(calls),
        "lanes": {lane: row(of) for lane, of in by_lane.items()},
        "budgets": {budget: row(of) for budget, of in by_budget.items()},
        "jobs": [{"job": name, "kind": kind, **row(of)} for (kind, name), of in ranked[:MAX_JOBS]],
        "jobs_more": max(0, len(ranked) - MAX_JOBS),
        "in_flight": _in_flight(calls, buckets=query.buckets),
        "unrecorded": UNRECORDED,
    }


__all__ = [
    "COMMANDS",
    "DEFAULT_BUCKETS",
    "DUPLICATE_WINDOW_S",
    "MAX_BUCKETS",
    "MAX_JOBS",
    "REPORTED_BUDGETS",
    "REPORTED_LANES",
    "UNRECORDED",
    "Query",
    "parse_query",
    "report",
]
