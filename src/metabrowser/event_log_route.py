"""``GET /api/event-log``: where the event log is, and its records, filtered and sorted.

The route reads the durable log (:mod:`metabrowser.event_log`) that served processes
write to the user's state directory, so ``metab ROOT --api /api/event-log`` reads it
without a server, and a page can link to the records behind a failure. It answers:

``directory``, ``state``, and ``bounds``
    Where the log lives, whether it exists, and the sizes it is held to.
``writing``
    The segment this process writes, or ``null`` for a process that writes none, as a
    one-shot command does.
``files``
    Every segment in the directory, newest first, with its size, process, and start.
``file``, ``query``, ``scanned``, ``matched``, and ``events``
    The segment read, the filters as understood, how many records it holds, how many
    matched, and the first ``limit`` of those.
``open``
    The spans this process has started and not ended: what it is waiting on now.

Filters: ``file`` (a listed segment; the default is the one this process writes, else
the newest), ``kind``, ``outcome``, and ``event`` (comma-separated lists of the values
the schema names), ``name`` (a substring), ``cause`` (one of
:data:`metabrowser.network_cause.CAUSES`), ``client`` (a request's client ID, which the
work it started carries too, or a page's ID, which finds every request the page sent
and every report it made, since each request's ID is the page's and ``-<n>``), ``span``
(that span's records and those of the spans it started), and ``min_ms`` (a duration at
least this long). ``sort`` is ``time`` (newest first) or ``duration``
(longest first); ``limit`` is at most :data:`MAX_LIMIT`.

``GET /api/event-log/failures`` counts the failures since ``since`` (an hour ago by
default; ``until`` closes the window), across every segment written to since then,
grouped by cause: what each was, how many, which work, when first and last, the latest
message, and links to the records. ``probe`` is the latest connectivity probe that
failed (:func:`metabrowser.network_cause.probe`). ``kind`` limits the count to those
kinds; by default one failure is counted once for each span that records it: a ``gh``
call that gave up, the probe that explained it, and the job it failed are three, so
``kind=subprocess`` counts calls. A page's reports (``browser`` records, from
:mod:`metabrowser.event_log_reports`) are not counted among the causes: they are what
the page saw of a failure the server's records name, so they are listed apart, under
``page_reports``.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser import event_log, network_cause
from metabrowser.event_log_reports import api_event_log_client

DEFAULT_LIMIT: Final = 100
# The most records one answer carries: about 270 KB at the measured 268 bytes a record.
MAX_LIMIT: Final = 1000
_MAX_NAME_FILTER: Final = 200
# A whole number as the query string gives it: ASCII digits only (``str.isdigit`` also
# takes ``²``, which ``int`` refuses), and few enough that ``int`` never refuses the length.
_WHOLE_NUMBER: Final = re.compile(r"[0-9]{1,18}")
_SORTS: Final = ("time", "duration")


class QueryError(ValueError):
    """A filter the route cannot apply; the message says which and why."""


@dataclass(frozen=True, slots=True)
class Query:
    """The filters of one read, as the answer echoes them."""

    file: str | None = None
    kinds: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    name: str | None = None
    client: str | None = None
    cause: str | None = None
    span: int | None = None
    min_ms: float | None = None
    sort: str = "time"
    limit: int = DEFAULT_LIMIT

    def describe(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "kind": list(self.kinds),
            "outcome": list(self.outcomes),
            "event": list(self.events),
            "name": self.name,
            "client": self.client,
            "cause": self.cause,
            "span": self.span,
            "min_ms": self.min_ms,
            "sort": self.sort,
            "limit": self.limit,
        }

    def matches(self, record: dict[str, Any]) -> bool:
        if self.kinds and record.get("kind") not in self.kinds:
            return False
        if self.outcomes and record.get("outcome") not in self.outcomes:
            return False
        if self.events and record.get("event") not in self.events:
            return False
        if self.name is not None and self.name not in str(record.get("name", "")):
            return False
        if self.cause is not None:
            attrs = record.get("attrs")
            if not isinstance(attrs, dict) or attrs.get("cause") != self.cause:
                return False
        if self.client is not None:
            client = record.get("client")
            if not isinstance(client, str) or (
                client != self.client and not client.startswith(f"{self.client}-")
            ):
                return False
        if self.span is not None and self.span not in (record.get("span"), record.get("parent")):
            return False
        if self.min_ms is not None:
            duration = record.get("dur_ms")
            if not isinstance(duration, int | float) or duration < self.min_ms:
                return False
        return True


def choices(raw: str | None, allowed: tuple[str, ...], field: str) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    chosen = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    unknown = [value for value in chosen if value not in allowed]
    if unknown:
        raise QueryError(f"{field} must be among {', '.join(allowed)}; not {', '.join(unknown)}")
    return chosen


def parse_query(params: dict[str, str]) -> Query:
    """The filters in a request's query string, or :class:`QueryError`."""

    known = {
        "file",
        "kind",
        "outcome",
        "event",
        "name",
        "client",
        "cause",
        "span",
        "min_ms",
        "sort",
    }
    unknown = sorted(set(params) - known - {"limit"})
    if unknown:
        raise QueryError(f"unknown parameter {', '.join(unknown)}")
    file = params.get("file") or None
    if file is not None and event_log.parse_file_name(file) is None:
        raise QueryError("file must name a segment of the event log")
    name = params.get("name") or None
    if name is not None and len(name) > _MAX_NAME_FILTER:
        raise QueryError(f"name is longer than {_MAX_NAME_FILTER} characters")
    client = params.get("client") or None
    if client is not None and len(client) > 64:
        raise QueryError("client is longer than 64 characters")
    cause = params.get("cause") or None
    if cause is not None and cause not in network_cause.CAUSES:
        raise QueryError(f"cause must be among {', '.join(network_cause.CAUSES)}")
    span = _integer(params.get("span"), "span", low=1, high=2**53)
    min_ms: float | None = None
    if params.get("min_ms"):
        try:
            min_ms = float(params["min_ms"])
        except ValueError as exc:
            raise QueryError("min_ms must be a number") from exc
        if not math.isfinite(min_ms) or min_ms < 0:
            raise QueryError("min_ms must be a number of milliseconds, zero or more")
    sort = params.get("sort") or "time"
    if sort not in _SORTS:
        raise QueryError(f"sort must be {' or '.join(_SORTS)}")
    limit = _integer(params.get("limit"), "limit", low=1, high=MAX_LIMIT)
    return Query(
        file=file,
        kinds=choices(params.get("kind"), event_log.KINDS, "kind"),
        outcomes=choices(params.get("outcome"), event_log.OUTCOMES, "outcome"),
        events=choices(params.get("event"), event_log.EVENT_TYPES, "event"),
        name=name,
        client=client,
        cause=cause,
        span=span,
        min_ms=min_ms,
        sort=sort,
        limit=DEFAULT_LIMIT if limit is None else limit,
    )


def _integer(raw: str | None, field: str, *, low: int, high: int) -> int | None:
    if raw is None or raw == "":
        return None
    if _WHOLE_NUMBER.fullmatch(raw) is None:
        raise QueryError(f"{field} must be a whole number")
    value = int(raw)
    if not low <= value <= high:
        raise QueryError(f"{field} must be from {low} to {high}")
    return value


def _iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log(query: Query, *, state: Path, directory: Path) -> tuple[int, dict[str, Any]]:
    """``(status, answer)`` for *query* against the log in *directory*. Blocking."""

    from metabrowser import home

    writing = event_log.current_file()
    writing_name = writing.name if writing is not None and writing.parent == directory else None
    files = event_log.list_files(directory)
    answer: dict[str, Any] = {
        "schema_version": event_log.SCHEMA_VERSION,
        "directory": str(directory),
        "state": "present" if directory.is_dir() else "absent",
        "writing": writing_name,
        "bounds": {
            "max_file_bytes": event_log.MAX_FILE_BYTES,
            "max_total_bytes": event_log.MAX_TOTAL_BYTES,
            "max_line_bytes": event_log.MAX_LINE_BYTES,
            "open_after_ms": event_log.OPEN_AFTER_MS,
        },
        "files": [
            {
                "name": f.name,
                "bytes": f.bytes,
                "modified": _iso(f.modified),
                "pid": f.pid,
                "started": f.started,
                "segment": f.segment,
            }
            for f in files
        ],
        "query": query.describe(),
    }
    listed = {f.name for f in files}
    # The segment this process writes, unless it is gone from the directory, as when
    # a person deleted it; the process starts a fresh one within a watch interval.
    current = writing_name if writing_name in listed else None
    chosen = query.file or current or (files[0].name if files else None)
    answer["file"] = chosen
    if chosen is None:
        answer.update(scanned=0, matched=0, events=[])
    elif chosen not in listed:
        return 404, {"error": f"no segment named {chosen}", "code": "event_log_file_missing"}
    else:
        try:
            data = home.read_private_file_bounded(
                state,
                f"{event_log.EVENTS_DIRECTORY}/{chosen}",
                max_bytes=event_log.MAX_FILE_BYTES + event_log.MAX_LINE_BYTES,
                shared="refuse",
            )
        except FileNotFoundError:
            return 404, {"error": f"no segment named {chosen}", "code": "event_log_file_missing"}
        except (home.PrivateStorageError, home.PrivateFileTooLargeError, OSError) as exc:
            return 409, {
                "error": f"the segment cannot be read: {exc}",
                "code": "event_log_unreadable",
            }
        records = list(event_log.parse_lines(data))
        matched = [record for record in records if query.matches(record)]
        if query.sort == "duration":
            matched.sort(key=lambda r: r.get("dur_ms") or 0, reverse=True)
        else:
            matched.reverse()
        answer.update(scanned=len(records), matched=len(matched), events=matched[: query.limit])
    answer["open"] = [
        {
            "span": s.span,
            "parent": s.parent,
            "kind": s.kind,
            "name": s.name,
            "age_ms": s.age_ms,
            "client": s.client,
            "attrs": s.attrs,
        }
        for s in event_log.open_spans()
    ]
    return 200, answer


async def api_event_log(request: Request) -> JSONResponse:
    """The event log's location, bounds, segments, and filtered records."""

    try:
        query = parse_query(dict(request.query_params))
    except QueryError as exc:
        return JSONResponse({"error": str(exc), "code": "invalid_query"}, status_code=400)
    try:
        state, directory = event_log.log_directory()
    except ValueError as exc:
        return JSONResponse({"error": str(exc), "code": "event_log_unconfigured"}, status_code=409)
    status, answer = await asyncio.to_thread(read_log, query, state=state, directory=directory)
    return JSONResponse(answer, status_code=status)


# ── Recent failures ────────────────────────────────────────────────────────

# The outcomes a failure summary counts: work that failed or gave up. ``abandoned`` (a
# server that stopped) and ``cancelled`` (a client that left) are not failures of the
# work.
FAILURE_OUTCOMES: Final = ("failed", "timeout", "never_completed")
# The most segments a summary reads: every segment the directory can hold at
# event_log.MAX_TOTAL_BYTES, segments of event_log.MAX_FILE_BYTES each.
_MAX_SEGMENTS: Final = event_log.MAX_TOTAL_BYTES // event_log.MAX_FILE_BYTES
_MOMENT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# The most examples of each cause a summary names.
_EXAMPLES: Final = 3


def parse_moment(raw: str | None, field: str) -> datetime | None:
    """A ``since`` or ``until`` parameter as a UTC moment, ``None`` when not given, or
    :class:`QueryError`."""

    if raw is None or raw == "":
        return None
    if not _MOMENT.match(raw):
        raise QueryError(f"{field} must be a UTC time such as 2026-11-19T21:00:00Z")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise QueryError(f"{field} must be a real moment") from exc


def record_time(record: dict[str, Any]) -> datetime | None:
    """When *record* was written, or ``None`` for a record with no time the log writes."""

    stamp = record.get("ts")
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def window_segments(
    *, state: Path, directory: Path, since: datetime
) -> Iterator[tuple[str, bytes]]:
    """The name and bytes of each segment that can hold a record since *since*. Blocking.

    Every segment written to since then, newest first, at most every segment the directory
    can hold, each read only to the size the writer bounds a segment to; one that cannot
    be read is left out. A summary of a window (:func:`summarize_failures`, and the GitHub
    plugin's request report) reads the log through this, one segment at a time.
    """

    from metabrowser import home

    for f in event_log.list_files(directory)[:_MAX_SEGMENTS]:
        if datetime.fromtimestamp(f.modified, UTC) < since:
            continue  # Written to last before the window opened.
        try:
            data = home.read_private_file_bounded(
                state,
                f"{event_log.EVENTS_DIRECTORY}/{f.name}",
                max_bytes=event_log.MAX_FILE_BYTES + event_log.MAX_LINE_BYTES,
                shared="refuse",
            )
        except (
            FileNotFoundError,
            home.PrivateStorageError,
            home.PrivateFileTooLargeError,
            OSError,
        ):
            continue
        yield f.name, data


def _record_link(file: str, record: dict[str, Any]) -> str:
    """Where ``/api/event-log`` lists *record*: by its span, or, for a record that has
    none, as a page's report has not, by its segment, kind, client, and name."""

    span = record.get("span")
    if isinstance(span, int):
        return f"/api/event-log?file={file}&span={span}"
    params = {"file": file, "kind": str(record.get("kind", ""))}
    client = record.get("client")
    if isinstance(client, str) and client:
        params["client"] = client
    name = str(record.get("name", ""))
    if name:
        params["name"] = name[:_MAX_NAME_FILTER]
    return f"/api/event-log?{urlencode(params)}"


def _failure_text(attrs: dict[str, Any]) -> str | None:
    """What the record says went wrong, most specific first."""

    for key in ("message", "failure_message", "error", "stderr_tail"):
        value = attrs.get(key)
        if isinstance(value, str) and value:
            return value
    stalled = attrs.get("stalled")
    if isinstance(stalled, str) and stalled:
        # A process that timed out silently: where it stalled is all there is to say.
        return f"timed out {stalled}"
    return None


class FailureTally:
    """Failures counted by cause, one record at a time.

    ``/api/event-log/failures`` counts a window across the directory's segments, and the
    event log view's Errors counts one file whole; both group, rank, and set apart the
    page's reports the same way, so a failure reads alike in Details and in the view.
    A record's group is its ``cause`` (:mod:`metabrowser.network_cause`'s vocabulary),
    else the ``failure`` state its work noted, else its outcome. *link* says where a
    reader finds one record, or is ``None`` for a reader with no such place.
    """

    def __init__(
        self,
        *,
        kinds: tuple[str, ...] = (),
        link: Callable[[str, dict[str, Any]], str] | None = _record_link,
    ) -> None:
        self._kinds = kinds
        self._link = link
        self._groups: dict[str, dict[str, Any]] = {}
        # What the pages saw: listed apart from the causes (the module's docstring says why).
        self._page_outcomes: dict[str, int] = {}
        self._page_names: dict[str, int] = {}
        self._page_examples: list[dict[str, Any]] = []
        # For each group, the rank and time of the record its message came from.
        self._said_at: dict[str, tuple[int, str]] = {}
        self._total = 0
        self._probe: dict[str, Any] | None = None

    @property
    def total(self) -> int:
        return self._total

    @property
    def probe(self) -> dict[str, Any] | None:
        """The latest probe that failed, whatever the kind filter."""

        return self._probe

    def _where(self, file: str | None, record: dict[str, Any]) -> dict[str, Any]:
        if self._link is None or file is None:
            return {}
        return {"details": self._link(file, record)}

    def add(self, record: dict[str, Any], *, file: str | None, origin: str | None = None) -> None:
        """Count *record* if it is a failure: the end of work that failed or gave up.

        *file* names the segment it came from, which the records kept for it say; ``None``
        for a reader that reads one file and has nothing to name. *origin* is a reader's own
        name for the record, which an example it keeps carries as ``key``: the views of one
        file name each span ``pid:span``, so an example can be opened where it happened.
        """

        where: dict[str, Any] = {} if file is None else {"file": file}
        if origin is not None:
            where["key"] = origin

        if record.get("event") != "end" or record.get("outcome") not in FAILURE_OUTCOMES:
            return
        kind = str(record.get("kind", ""))
        attrs = record.get("attrs")
        attrs = attrs if isinstance(attrs, dict) else {}
        if kind == "probe" and (
            self._probe is None or str(record.get("ts")) > str(self._probe["ts"])
        ):
            self._probe = {
                "ts": record.get("ts"),
                **where,
                "span": record.get("span"),
                **attrs,
            }
        if self._kinds and kind not in self._kinds:
            return
        if kind == "browser":
            # A page's never_completed wait for a refresh and the gh call that timed out
            # under it are one failure, seen from two sides, and a slow 5xx the page
            # reports is a request the server recorded as failed: counting the page's
            # side would count it twice and could rank it above the cause.
            outcome = str(record.get("outcome"))
            name = str(record.get("name", ""))
            self._page_outcomes[outcome] = self._page_outcomes.get(outcome, 0) + 1
            self._page_names[name] = self._page_names.get(name, 0) + 1
            seen: dict[str, Any] = {
                "ts": str(record.get("ts")),
                **where,
                "pid": record.get("pid"),
                "client": record.get("client"),
                "name": name,
                "outcome": outcome,
                "dur_ms": record.get("dur_ms"),
                "status": attrs.get("status"),
                "path": attrs.get("path"),
                **self._where(file, record),
            }
            self._page_examples = sorted([*self._page_examples, seen], key=lambda e: str(e["ts"]))[
                -_EXAMPLES:
            ]
            return
        self._total += 1
        cause, source = (
            (attrs["cause"], "cause")
            if isinstance(attrs.get("cause"), str)
            else (attrs["failure"], "state")
            if isinstance(attrs.get("failure"), str)
            else (str(record.get("outcome")), "outcome")
        )
        group = self._groups.setdefault(
            cause,
            {
                "cause": cause,
                "source": source,
                "count": 0,
                "kinds": {},
                "names": {},
                "first": record.get("ts"),
                "last": record.get("ts"),
                "message": None,
                "addresses": [],
                "examples": [],
            },
        )
        # The addresses a connection failed to: gh names one, a probe each it tried.
        # DNS can answer a GitHub name with different addresses from one lookup to the
        # next, and a network can reach some and not others.
        failed_to = [attrs.get("address")]
        tried = attrs.get("addresses")
        if isinstance(tried, list):
            failed_to += [
                a.get("address")
                for a in tried  # pyright: ignore[reportUnknownVariableType]
                if isinstance(a, dict) and a.get("result") != "connected"  # pyright: ignore[reportUnknownMemberType]
            ]
        for address in failed_to:
            if isinstance(address, str) and address not in group["addresses"]:
                group["addresses"].append(address)
        group["count"] += 1
        group["kinds"][kind] = group["kinds"].get(kind, 0) + 1
        name = str(record.get("name", ""))
        group["names"][name] = group["names"].get(name, 0) + 1
        stamp = str(record.get("ts"))
        group["first"] = min(str(group["first"]), stamp)
        group["last"] = max(str(group["last"]), stamp)
        # The message a reader saw, from the job or probe that reported it, outranks
        # a process's raw error text; among equals, the latest wins.
        text = _failure_text(attrs)
        rank = 1 if kind == "subprocess" else 0
        said = self._said_at.get(cause)
        if text is not None and (
            said is None or rank < said[0] or (rank == said[0] and stamp >= said[1])
        ):
            self._said_at[cause] = (rank, stamp)
            group["message"] = text
        example: dict[str, Any] = {
            "ts": stamp,
            **where,
            "pid": record.get("pid"),
            "span": record.get("span"),
            "kind": kind,
            "name": name,
            "outcome": record.get("outcome"),
            "dur_ms": record.get("dur_ms"),
            "address": attrs.get("address"),
            **self._where(file, record),
        }
        group["examples"] = sorted([*group["examples"], example], key=lambda e: str(e["ts"]))[
            -_EXAMPLES:
        ]

    def causes(self) -> list[dict[str, Any]]:
        """The groups, most frequent first, each with its newest examples first."""

        ranked = sorted(self._groups.values(), key=lambda g: (g["count"], g["last"]), reverse=True)
        return [{**group, "examples": list(reversed(group["examples"]))} for group in ranked]

    def page_reports(self) -> dict[str, Any]:
        """What the pages reported failing, apart from the causes."""

        return {
            "count": sum(self._page_outcomes.values()),
            "outcomes": self._page_outcomes,
            "names": self._page_names,
            "examples": list(reversed(self._page_examples)),
        }


def summarize_failures(
    *, state: Path, directory: Path, since: datetime, until: datetime | None, kinds: tuple[str, ...]
) -> dict[str, Any]:
    """Failures since *since*, grouped by cause, across every segment that can hold one.

    A record's group is its ``cause`` (:mod:`metabrowser.network_cause`'s vocabulary),
    else the ``failure`` state its work noted, else its outcome. Blocking.
    """

    tally = FailureTally(kinds=kinds)
    read: list[str] = []
    scanned = 0
    for name, data in window_segments(state=state, directory=directory, since=since):
        read.append(name)
        for record in event_log.parse_lines(data):
            scanned += 1
            moment = record_time(record)
            if moment is None or moment < since or (until is not None and moment > until):
                continue
            tally.add(record, file=name)
    return {
        "schema_version": event_log.SCHEMA_VERSION,
        "directory": str(directory),
        "state": "present" if directory.is_dir() else "absent",
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "until": until.strftime("%Y-%m-%dT%H:%M:%SZ") if until is not None else None,
        "kinds": list(kinds),
        "files": read,
        "scanned": scanned,
        "failures": tally.total,
        "causes": tally.causes(),
        "probe": tally.probe,
        "page_reports": tally.page_reports(),
    }


async def api_event_log_failures(request: Request) -> JSONResponse:
    """Failures in the event log since a moment (an hour ago by default), by cause."""

    params = dict(request.query_params)
    try:
        unknown = sorted(set(params) - {"since", "until", "kind"})
        if unknown:
            raise QueryError(f"unknown parameter {', '.join(unknown)}")
        since = parse_moment(params.get("since"), "since")
        until = parse_moment(params.get("until"), "until")
        kinds = choices(params.get("kind"), event_log.KINDS, "kind")
    except QueryError as exc:
        return JSONResponse({"error": str(exc), "code": "invalid_query"}, status_code=400)
    if since is None:
        since = datetime.now(UTC) - timedelta(seconds=event_log.RECENT_WINDOW_S)
    try:
        state, directory = event_log.log_directory()
    except ValueError as exc:
        return JSONResponse({"error": str(exc), "code": "event_log_unconfigured"}, status_code=409)
    answer = await asyncio.to_thread(
        summarize_failures, state=state, directory=directory, since=since, until=until, kinds=kinds
    )
    return JSONResponse(answer)


EVENT_LOG_ROUTES = [
    Route("/api/event-log", api_event_log),
    Route("/api/event-log/failures", api_event_log_failures),
    # What a page saw: its slow and pending requests, freezes, and late waits. Spelled out,
    # as devtools/check_parity.py reads registrations; it is event_log_reports.REPORT_ROUTE,
    # which tests/test_event_log_reports.py posts to through the application.
    Route("/api/event-log/client", api_event_log_client, methods=["POST"]),
]


__all__ = [
    "DEFAULT_LIMIT",
    "EVENT_LOG_ROUTES",
    "FAILURE_OUTCOMES",
    "MAX_LIMIT",
    "FailureTally",
    "Query",
    "QueryError",
    "choices",
    "api_event_log",
    "api_event_log_failures",
    "parse_moment",
    "parse_query",
    "read_log",
    "record_time",
    "summarize_failures",
    "window_segments",
]
