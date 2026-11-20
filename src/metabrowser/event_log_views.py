"""The event log as a person reads it: spans nested under their parents, timed and counted.

``metabrowser.event_log`` writes one JSON record per line, and a span is up to three of
them: a ``start`` (a job writes one), ``open`` records while it runs late, and an ``end``
with its duration and outcome. This module reads one segment's bytes into a
:class:`Table` of items, each span put together from its records, and answers the four
views the event log's built-in plugin (``builtin_plugins/event_log``) shows, each a plain
function of a table and a filter, so ``metab ROOT --api`` reads every one:

``timeline``
    The items in time order, nested: a request, the job it started, the process the job
    ran. A page of the children of one span, or of the roots.
``slowest``
    The slowest items, longest first, each with the spans above it, and the
    distribution of every item's time.
``by_kind``
    For each kind of record and each name within it, how many, how they ended, and how
    long they took.
``errors``
    The failures grouped by cause, as ``/api/event-log/failures`` groups them
    (:class:`metabrowser.event_log_route.FailureTally`), the page's reports apart, and
    the work that had not ended when the log did.

**Time.** A span's start is its ``start`` record's moment, else its ``end`` record's moment
less its duration, else its latest ``open`` record's moment less the age that record
carries. A span with no ``end`` record is *unfinished*: the server stopped, or was killed
mid-line, before it finished, and its age is measured to the log's last record.

**Filters.** The views take the filters ``/api/event-log`` does (``kind``, ``outcome``,
``name``, ``client``, ``cause``, ``min_ms``), with the same meaning, through the same
:class:`~metabrowser.event_log_route.Query`. A filtered timeline keeps each span that
matches and the spans above it, so a slow ``git`` process is shown inside the request that
waited for it.

**Bounds.** A file is read to :data:`MAX_VIEW_BYTES`, the size of one segment as the log
bounds it, and refused above it: a file the log did not write, or several joined, is for
the Raw JSON view. A response carries at most :data:`MAX_LIMIT` rows.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Literal

from cachetools import LRUCache

from metabrowser import event_log
from metabrowser.event_log_route import (
    FAILURE_OUTCOMES,
    FailureTally,
    Query,
    QueryError,
    choices,
    parse_query,
)

# The most bytes one view reads: a segment as the writer bounds it (``MAX_FILE_BYTES``, and
# the line that crosses it), so every file the log wrote opens whole. A larger file is not
# a segment of the log. Measured 2026-11-19 on one macOS machine at a load average near 19,
# Python 3.14: a segment at the bound, 2.09 MB of 8,191 records and 7,908 spans in the
# writer's shapes (mostly requests, a refresh job with its processes every 25th), is put
# together in 62 ms (the median of seven), and each view of the result takes 3 to 9 ms.
MAX_VIEW_BYTES: Final[int] = event_log.MAX_FILE_BYTES + event_log.MAX_LINE_BYTES

# The rows in one answer. A request's row is about 375 bytes of JSON, so a page of
# ``DEFAULT_TIMELINE_ROWS`` is 75 KB built in 2 ms, and ``MAX_LIMIT``, which is 375 KB, in
# 3 ms. The page draws a row in 14 DOM nodes, and a page of 200 in 53 to 83 ms in headless
# Chrome at that load, however many rows it already shows (event-log-views.js,
# ``paintTimeline``), which is the first thing a person waits on and why a page is not the
# whole segment. ``DEFAULT_SLOWEST_ROWS`` is the 50 slowest, 22 KB, which the Latency view
# draws whole.
DEFAULT_TIMELINE_ROWS: Final = 200
DEFAULT_SLOWEST_ROWS: Final = 50
MAX_LIMIT: Final = 1000
# The names each kind lists, most time first; the answer says how many more there are.
NAMES_SHOWN: Final = 12
# The work still running at the log's end that Errors lists, longest first, and the
# spans above one that a row names, nearest first.
UNFINISHED_SHOWN: Final = 50
PATH_DEPTH: Final = 6
# Where the distribution of times is cut, in milliseconds: the slow threshold
# (``event_log.OPEN_AFTER_MS``) is one edge, so "slow" means one thing here and in the
# log. The answer carries the edges, and the page reads them from it.
LATENCY_EDGES_MS: Final[tuple[float, ...]] = (
    1.0,
    10.0,
    100.0,
    500.0,
    event_log.OPEN_AFTER_MS,
    10_000.0,
)
# How many segments' tables the server keeps, keyed by the content's fingerprint, so a
# page that asks for the next screen of a timeline, or opens a span, reads no file again.
# One table of a segment at the bound held 18.9 MB (``tracemalloc``, the segment above),
# so three are at most about 57 MB; a person browsing a log has one or two open, and every
# view of one log shares its table.
MAX_TABLES_KEPT: Final = 3

ItemType = Literal["span", "mark", "report"]
SortKey = tuple[float, int]
# Where a span's start comes from, worst to best: the moment of the first record seen, an
# ``open`` record's moment less its age, an ``end`` record's less its duration, and a
# ``start`` record's own, which a job writes.
_FROM_OPEN: Final = 1
_FROM_END: Final = 2
_FROM_START: Final = 3


class ViewError(ValueError):
    """A request the views cannot answer; ``code`` says why, for the route's answer."""

    def __init__(self, message: str, code: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(slots=True)
class Item:
    """One thing the log says happened: a span, a mark, or what a page reported."""

    type: ItemType
    key: str
    kind: str
    name: str
    # Seconds since the epoch; for a span, when it began.
    start: float
    pid: int
    line: int
    event: str = ""
    span: int | None = None
    parent: int | None = None
    client: str | None = None
    dur_ms: float | None = None
    outcome: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict[str, Any])
    opens: int = 0
    ended: bool = False
    # The key of the span above, when this file holds it; ``orphan`` is a span that names
    # a parent the file does not (it began in an earlier segment).
    parent_key: str | None = None
    orphan: bool = False
    # The end record, kept for the failure tally.
    record: dict[str, Any] | None = None
    # Which record the start came from, so a better one replaces a worse (``_FROM_*``).
    start_rank: int = 0

    def begin(self, moment: float, rank: int) -> None:
        """Take *moment* as the span's start unless a better record gave one."""

        if rank >= self.start_rank:
            self.start = moment
            self.start_rank = rank

    @property
    def unfinished(self) -> bool:
        return self.type == "span" and not self.ended

    @property
    def sort_key(self) -> SortKey:
        return (self.start, self.line)


@dataclass(slots=True)
class Table:
    """One segment, read: its items, and who is nested under whom."""

    items: list[Item]
    spans: dict[str, Item]
    # Items by the span above them; ``None`` keys the roots, which include every mark and
    # report. Each list is in time order.
    children: dict[str | None, list[Item]]
    records: int
    skipped: int
    first: float
    last: float
    pids: list[int]
    size: int = 0

    def elapsed_ms(self, item: Item) -> float | None:
        """How long *item* took, or, for an unfinished span, how long it had run when
        the log ended; ``None`` for a mark, or a report that is not the end of a wait."""

        if item.type == "report":
            # A report written while a wait was still running (an ``open`` record) holds
            # the time so far, and the report that ends it the whole: only the whole is
            # a time to rank.
            return item.dur_ms if item.event == "end" else None
        if item.dur_ms is not None:
            return item.dur_ms
        if item.unfinished:
            return max(0.0, (self.last - item.start) * 1000)
        return None

    def offset_ms(self, item: Item) -> float:
        return round((item.start - self.first) * 1000, 1)


def _seconds(stamp: object) -> float | None:
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.fromisoformat(stamp).timestamp()
    except ValueError:
        return None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _attrs(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}  # pyright: ignore[reportUnknownArgumentType]


def _span_key(pid: int, span: int) -> str:
    return f"{pid}:{span}"


def build_table(data: bytes) -> Table:
    """The records in *data* put together as spans, marks, and reports. Blocking.

    Lines that are not records of this schema's version (a torn last line, a later
    version) are counted in ``skipped`` and read no further, as every reader of the log
    does (:func:`metabrowser.event_log.parse_lines`).
    """

    spans: dict[str, Item] = {}
    points: list[Item] = []
    lines = [raw for raw in data.splitlines() if raw.strip()]
    records = 0
    last = 0.0
    first = math.inf
    pids: dict[int, None] = {}
    for number, record in enumerate(event_log.parse_lines(data), start=1):
        moment = _seconds(record.get("ts"))
        if moment is None:
            continue
        records += 1
        last = max(last, moment)
        pid = _whole(record.get("pid")) or 0
        pids[pid] = None
        kind = _text(record.get("kind")) or "unknown"
        name = _text(record.get("name")) or ""
        event = _text(record.get("event")) or ""
        duration = _number(record.get("dur_ms"))
        span = _whole(record.get("span"))
        if kind == "browser" or span is None:
            began = (
                moment - duration / 1000 if duration is not None and kind == "browser" else moment
            )
            first = min(first, began)
            point = Item(
                "mark" if event == "mark" else "report",
                f"{pid}@{number}",
                kind,
                name,
                began,
                pid,
                number,
                event=event,
                client=_text(record.get("client")),
                dur_ms=duration,
                outcome=_text(record.get("outcome")),
                attrs=_attrs(record.get("attrs")),
            )
            point.record = record if kind == "browser" and event == "end" else None
            point.ended = True
            points.append(point)
            continue
        key = _span_key(pid, span)
        item = spans.get(key)
        if item is None:
            item = Item("span", key, kind, name, moment, pid, number, span=span)
            spans[key] = item
        item.name = item.name or name
        item.parent = item.parent if item.parent is not None else _whole(record.get("parent"))
        item.client = item.client or _text(record.get("client"))
        item.attrs.update(_attrs(record.get("attrs")))
        if event == "start":
            item.begin(moment, _FROM_START)
        elif event == "open":
            item.opens += 1
            if duration is not None:
                item.begin(moment - duration / 1000, _FROM_OPEN)
        elif event == "end":
            item.ended = True
            item.dur_ms = duration
            item.outcome = _text(record.get("outcome"))
            item.record = record
            if duration is not None:
                item.begin(moment - duration / 1000, _FROM_END)
        first = min(first, item.start)
    return _link(
        list(spans.values()),
        points,
        spans,
        records=records,
        skipped=len(lines) - records,
        first=first if first != math.inf else last,
        last=last,
        pids=list(pids),
        size=len(data),
    )


def _link(
    span_items: list[Item],
    points: list[Item],
    spans: dict[str, Item],
    *,
    records: int,
    skipped: int,
    first: float,
    last: float,
    pids: list[int],
    size: int,
) -> Table:
    for item in span_items:
        if item.parent is None:
            continue
        above = _span_key(item.pid, item.parent)
        if above == item.key:
            continue
        if above in spans:
            item.parent_key = above
        else:
            item.orphan = True
    # A file that nests spans in a circle, which no writer produces, still shows each of
    # them: the link that closes the circle becomes a root.
    for item in span_items:
        seen = {item.key}
        at = item
        while at.parent_key is not None:
            if at.parent_key in seen:
                at.parent_key = None
                break
            seen.add(at.parent_key)
            at = spans[at.parent_key]
    ordered = sorted([*span_items, *points], key=lambda i: i.sort_key)
    children: dict[str | None, list[Item]] = defaultdict(list)
    for item in ordered:
        children[item.parent_key].append(item)
    return Table(ordered, spans, dict(children), records, skipped, first, last, pids, size)


_TABLES: LRUCache[tuple[str, str], Table] = LRUCache(maxsize=MAX_TABLES_KEPT)


def remembered(identity: str, fingerprint: str) -> Table | None:
    """The table built for content that has not changed since, or ``None``."""

    return _TABLES.get((identity, fingerprint))


def remember(identity: str, fingerprint: str, table: Table) -> None:
    _TABLES[(identity, fingerprint)] = table


# ── Filters and rows ─────────────────────────────────────────────────────────────────


def parse_filter(params: dict[str, str]) -> Query:
    """The filters among *params*, as ``/api/event-log`` takes them, or a ``ViewError``."""

    filters = {
        key: params[key]
        for key in ("kind", "outcome", "name", "client", "cause", "min_ms")
        if key in params
    }
    try:
        return parse_query(filters)
    except QueryError as exc:
        raise ViewError(str(exc), "invalid_query") from exc


def describe_filter(query: Query) -> dict[str, Any]:
    return {
        "kind": list(query.kinds),
        "outcome": list(query.outcomes),
        "name": query.name,
        "client": query.client,
        "cause": query.cause,
        "min_ms": query.min_ms,
    }


def _filtering(query: Query) -> bool:
    return bool(
        query.kinds
        or query.outcomes
        or query.name is not None
        or query.client is not None
        or query.cause is not None
        or query.min_ms is not None
    )


def _matches(query: Query, table: Table, item: Item) -> bool:
    return query.matches(
        {
            "kind": item.kind,
            "name": item.name,
            "outcome": item.outcome,
            "client": item.client,
            "attrs": item.attrs,
            "dur_ms": table.elapsed_ms(item),
        }
    )


def _state(item: Item) -> str:
    if item.type == "span":
        return "ended" if item.ended else "unfinished"
    return "report" if item.type == "report" else "mark"


def _row(table: Table, item: Item) -> dict[str, Any]:
    """*item* as the answers carry it."""

    row: dict[str, Any] = {
        "type": item.type,
        "key": item.key,
        "kind": item.kind,
        "name": item.name,
        "start_ms": table.offset_ms(item),
        "dur_ms": item.dur_ms,
        "outcome": item.outcome,
        "state": _state(item),
        "client": item.client,
        "pid": item.pid,
        "span": item.span,
        "parent": item.parent_key,
        "attrs": item.attrs,
    }
    elapsed = table.elapsed_ms(item)
    row["elapsed_ms"] = None if elapsed is None else round(elapsed, 1)
    if item.unfinished:
        row["opens"] = item.opens
    if item.orphan:
        row["orphan"] = True
    if item.type == "report":
        row["event"] = item.event
    return row


def _above(table: Table, item: Item) -> list[dict[str, str]]:
    """The spans above *item*, from the outermost down, as their kinds and names."""

    chain: list[dict[str, str]] = []
    at = item
    while at.parent_key is not None and len(chain) < PATH_DEPTH:
        at = table.spans[at.parent_key]
        chain.append({"key": at.key, "kind": at.kind, "name": at.name})
    chain.reverse()
    return chain


def log_summary(table: Table) -> dict[str, Any]:
    """What the file holds, for the head of every answer."""

    def iso(moment: float) -> str:
        return datetime.fromtimestamp(moment, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return {
        "schema_version": event_log.SCHEMA_VERSION,
        # The words a filter chooses among: the writer's, so a page names none of its own.
        "kinds": list(event_log.KINDS),
        "outcomes": list(event_log.OUTCOMES),
        "bytes": table.size,
        "records": table.records,
        "skipped": table.skipped,
        "spans": len(table.spans),
        "unfinished": sum(1 for item in table.spans.values() if not item.ended),
        "started": iso(table.first) if table.items else None,
        "ended": iso(table.last) if table.items else None,
        "extent_ms": round((table.last - table.first) * 1000, 1) if table.items else 0.0,
        "pids": table.pids,
    }


def _limit(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    if not value.isascii() or not value.isdigit() or len(value) > 9:
        raise ViewError("limit must be a whole number", "invalid_query")
    number = int(value)
    if not 1 <= number <= MAX_LIMIT:
        raise ViewError(f"limit must be from 1 to {MAX_LIMIT}", "invalid_query")
    return number


def _offset(value: str | None) -> int:
    if value is None or value == "":
        return 0
    if not value.isascii() or not value.isdigit() or len(value) > 9:
        raise ViewError("offset must be a whole number", "invalid_query")
    return int(value)


# ── Timeline ─────────────────────────────────────────────────────────────────────────


def _kept(table: Table, query: Query) -> set[str] | None:
    """The keys of the spans a filtered timeline shows: those that match, and every span
    above one. ``None`` when nothing filters, which keeps everything."""

    if not _filtering(query):
        return None
    kept: set[str] = set()
    for item in table.spans.values():
        if not _matches(query, table, item):
            continue
        at: Item | None = item
        while at is not None and at.key not in kept:
            kept.add(at.key)
            at = table.spans.get(at.parent_key) if at.parent_key is not None else None
    return kept


def _counted(table: Table, kept: set[str] | None) -> dict[str, int]:
    """For each span, how many spans are below it that the filter shows.

    Held apart from the table, which requests share, so two filters read it at once.
    """

    depth: dict[str, int] = {}

    def depth_of(item: Item) -> int:
        cached = depth.get(item.key)
        if cached is not None:
            return cached
        steps = 0
        at = item
        while at.parent_key is not None:
            steps += 1
            at = table.spans[at.parent_key]
        depth[item.key] = steps
        return steps

    below: dict[str, int] = defaultdict(int)
    # Deepest first, so each span's count is whole before its parent takes it.
    for item in sorted(table.spans.values(), key=depth_of, reverse=True):
        if item.parent_key is None or (kept is not None and item.key not in kept):
            continue
        below[item.parent_key] += 1 + below[item.key]
    return below


def timeline(
    table: Table,
    query: Query,
    *,
    parent: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    """The children of *parent*, or the roots, in time order, a page of them.

    Each row says how many spans sit directly under it and how many below, so the page
    can offer to open it. A filter keeps the matching spans and those above them, and a
    row's ``matched`` says which it is.
    """

    if parent is not None and parent not in table.spans:
        raise ViewError(f"no span {parent} in this log", "span_missing", status=404)
    kept = _kept(table, query)
    below = _counted(table, kept)

    def shown(item: Item) -> bool:
        if kept is None:
            return True
        if item.type == "span":
            return item.key in kept
        return _matches(query, table, item)

    siblings = [item for item in table.children.get(parent, []) if shown(item)]
    rows: list[dict[str, Any]] = []
    for item in siblings[offset : offset + limit]:
        row = _row(table, item)
        row["children"] = sum(1 for child in table.children.get(item.key, []) if shown(child))
        row["below"] = below.get(item.key, 0)
        row["matched"] = kept is None or _matches(query, table, item)
        rows.append(row)
    return {
        "view": "timeline",
        "log": log_summary(table),
        "query": describe_filter(query),
        "parent": parent,
        "total": len(siblings),
        "offset": offset,
        "limit": limit,
        "max_limit": MAX_LIMIT,
        "has_more": offset + limit < len(siblings),
        "rows": rows,
    }


# ── Latency ──────────────────────────────────────────────────────────────────────────


def _bucket(elapsed: float) -> int:
    for index, edge in enumerate(LATENCY_EDGES_MS):
        if elapsed < edge:
            return index
    return len(LATENCY_EDGES_MS)


def _histogram(times: list[float]) -> list[int]:
    counts = [0] * (len(LATENCY_EDGES_MS) + 1)
    for elapsed in times:
        counts[_bucket(elapsed)] += 1
    return counts


def _percentile(sorted_times: list[float], percent: float) -> float | None:
    """The nearest-rank percentile of a sorted list: the smallest time at least *percent*
    of the times do not exceed."""

    if not sorted_times:
        return None
    rank = max(1, math.ceil(percent / 100 * len(sorted_times)))
    return round(sorted_times[rank - 1], 1)


def _timed(table: Table, query: Query) -> list[tuple[float, Item]]:
    """Every span and report that took time and matches, each with its time."""

    timed: list[tuple[float, Item]] = []
    for item in table.items:
        if item.type == "mark":
            continue
        elapsed = table.elapsed_ms(item)
        if elapsed is not None and _matches(query, table, item):
            timed.append((elapsed, item))
    return timed


def slowest(table: Table, query: Query, *, limit: int) -> dict[str, Any]:
    """The longest spans and reports, with the distribution of every one's time.

    An unfinished span counts for as long as it had run when the log ended.
    """

    timed = _timed(table, query)
    ranked = sorted(timed, key=lambda pair: (-pair[0], pair[1].sort_key))
    items: list[dict[str, Any]] = []
    for _, item in ranked[:limit]:
        row = _row(table, item)
        row["path"] = _above(table, item)
        items.append(row)
    return {
        "view": "slowest",
        "log": log_summary(table),
        "query": describe_filter(query),
        "edges_ms": list(LATENCY_EDGES_MS),
        "histogram": _histogram([elapsed for elapsed, _ in timed]),
        "timed": len(timed),
        "limit": limit,
        "max_limit": MAX_LIMIT,
        "items": items,
    }


# ── By kind ──────────────────────────────────────────────────────────────────────────


def _outcome_of(item: Item) -> str:
    if item.unfinished:
        return "unfinished"
    return item.outcome or "none"


def _statistics(times: list[float]) -> dict[str, Any]:
    ordered = sorted(times)
    return {
        "p50_ms": _percentile(ordered, 50),
        "p95_ms": _percentile(ordered, 95),
        "max_ms": round(ordered[-1], 1) if ordered else None,
        "total_ms": round(sum(ordered), 1),
    }


def by_kind(table: Table, query: Query) -> dict[str, Any]:
    """Per kind, and per name within it: how many, how they ended, and how long they took."""

    groups: dict[str, list[Item]] = defaultdict(list)
    for item in table.items:
        if _matches(query, table, item):
            groups[item.kind].append(item)
    order = [kind for kind in event_log.KINDS if kind in groups]
    order += sorted(kind for kind in groups if kind not in event_log.KINDS)
    everything: list[float] = []
    kinds: list[dict[str, Any]] = []
    for kind in order:
        members = groups[kind]
        times = [t for item in members if (t := table.elapsed_ms(item)) is not None]
        everything += times
        outcomes: dict[str, int] = {}
        for item in members:
            word = _outcome_of(item)
            outcomes[word] = outcomes.get(word, 0) + 1
        by_name: dict[str, list[Item]] = defaultdict(list)
        for item in members:
            by_name[item.name].append(item)
        names: list[dict[str, Any]] = []
        for name, named in by_name.items():
            named_times = [t for item in named if (t := table.elapsed_ms(item)) is not None]
            names.append(
                {
                    "name": name,
                    "count": len(named),
                    "failed": sum(
                        1 for item in named if item.unfinished or item.outcome in FAILURE_OUTCOMES
                    ),
                    **_statistics(named_times),
                }
            )
        names.sort(key=lambda row: (-row["total_ms"], -row["count"], row["name"]))
        kinds.append(
            {
                "kind": kind,
                "count": len(members),
                "timed": len(times),
                "outcomes": dict(sorted(outcomes.items(), key=lambda pair: (-pair[1], pair[0]))),
                **_statistics(times),
                "histogram": _histogram(times),
                "names": names[:NAMES_SHOWN],
                "names_more": max(0, len(names) - NAMES_SHOWN),
            }
        )
    return {
        "view": "kinds",
        "log": log_summary(table),
        "query": describe_filter(query),
        "edges_ms": list(LATENCY_EDGES_MS),
        "histogram": _histogram(everything),
        "kinds": kinds,
    }


# ── Errors ───────────────────────────────────────────────────────────────────────────


def errors(table: Table, kinds: tuple[str, ...]) -> dict[str, Any]:
    """The failures grouped by cause, the page's reports apart, and the unfinished work.

    The grouping is ``/api/event-log/failures``'s, over the whole file rather than a
    window. A span with no ``end`` record is listed apart, longest first: it is work the
    log shows started and never finished, which no outcome says. ``cancelled`` and
    ``abandoned`` spans are counted but are not failures of the work.
    """

    tally = FailureTally(kinds=kinds, link=None)
    for item in table.items:
        if item.record is not None:
            tally.add(item.record, file=None)
    unfinished = sorted(
        (
            (elapsed, item)
            for item in table.spans.values()
            if item.unfinished
            and (not kinds or item.kind in kinds)
            and (elapsed := table.elapsed_ms(item)) is not None
        ),
        key=lambda pair: (-pair[0], pair[1].sort_key),
    )
    unfinished_rows: list[dict[str, Any]] = []
    for _, item in unfinished[:UNFINISHED_SHOWN]:
        row = _row(table, item)
        row["path"] = _above(table, item)
        unfinished_rows.append(row)
    quiet: dict[str, int] = {}
    for item in table.spans.values():
        if item.outcome in ("cancelled", "abandoned") and (not kinds or item.kind in kinds):
            quiet[item.outcome] = quiet.get(item.outcome, 0) + 1
    return {
        "view": "errors",
        "log": log_summary(table),
        "kinds": list(kinds),
        "failures": tally.total,
        "causes": _with_keys(tally.causes(), table),
        "probe": tally.probe,
        "page_reports": tally.page_reports(),
        "unfinished": {
            "total": len(unfinished),
            "shown": len(unfinished_rows),
            "rows": unfinished_rows,
        },
        "not_failures": dict(sorted(quiet.items())),
    }


def _with_keys(causes: list[dict[str, Any]], table: Table) -> list[dict[str, Any]]:
    """Each example with the key of its span, which the timeline opens, and the spans above."""

    by_span: dict[int, list[Item]] = defaultdict(list)
    for item in table.spans.values():
        if item.span is not None:
            by_span[item.span].append(item)
    for group in causes:
        for example in group["examples"]:
            matches = [
                item
                for item in by_span.get(example.get("span") or -1, [])
                if item.ended and item.name == example["name"] and item.kind == example["kind"]
            ]
            if matches:
                example["key"] = matches[0].key
                example["path"] = _above(table, matches[0])
    return causes


def parse_kinds(raw: str | None) -> tuple[str, ...]:
    """The kinds in a comma-separated list, or a ``ViewError``."""

    try:
        return choices(raw, event_log.KINDS, "kind")
    except QueryError as exc:
        raise ViewError(str(exc), "invalid_query") from exc


def parse_page(params: dict[str, str], *, default_limit: int) -> tuple[int, int]:
    """``(offset, limit)`` from *params*."""

    return _offset(params.get("offset")), _limit(params.get("limit"), default_limit)


__all__ = [
    "DEFAULT_SLOWEST_ROWS",
    "DEFAULT_TIMELINE_ROWS",
    "LATENCY_EDGES_MS",
    "MAX_LIMIT",
    "MAX_TABLES_KEPT",
    "MAX_VIEW_BYTES",
    "Item",
    "Table",
    "ViewError",
    "build_table",
    "by_kind",
    "describe_filter",
    "errors",
    "log_summary",
    "parse_filter",
    "parse_kinds",
    "parse_page",
    "remember",
    "remembered",
    "slowest",
    "timeline",
]
