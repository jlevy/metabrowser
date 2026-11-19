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
the schema names), ``name`` (a substring), ``client`` (the browser's request ID),
``span`` (that span's records and those of the spans it started), and ``min_ms`` (a
duration at least this long). ``sort`` is ``time`` (newest first) or ``duration``
(longest first); ``limit`` is at most :data:`MAX_LIMIT`.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser import event_log

DEFAULT_LIMIT: Final = 100
# The most records one answer carries: about 270 KB at the measured 268 bytes a record.
MAX_LIMIT: Final = 1000
_MAX_NAME_FILTER: Final = 200
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
        if self.client is not None and record.get("client") != self.client:
            return False
        if self.span is not None and self.span not in (record.get("span"), record.get("parent")):
            return False
        if self.min_ms is not None:
            duration = record.get("dur_ms")
            if not isinstance(duration, int | float) or duration < self.min_ms:
                return False
        return True


def _choices(raw: str | None, allowed: tuple[str, ...], field: str) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    chosen = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    unknown = [value for value in chosen if value not in allowed]
    if unknown:
        raise QueryError(f"{field} must be among {', '.join(allowed)}; not {', '.join(unknown)}")
    return chosen


def parse_query(params: dict[str, str]) -> Query:
    """The filters in a request's query string, or :class:`QueryError`."""

    known = {"file", "kind", "outcome", "event", "name", "client", "span", "min_ms", "sort"}
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
        kinds=_choices(params.get("kind"), event_log.KINDS, "kind"),
        outcomes=_choices(params.get("outcome"), event_log.OUTCOMES, "outcome"),
        events=_choices(params.get("event"), event_log.EVENT_TYPES, "event"),
        name=name,
        client=client,
        span=span,
        min_ms=min_ms,
        sort=sort,
        limit=DEFAULT_LIMIT if limit is None else limit,
    )


def _integer(raw: str | None, field: str, *, low: int, high: int) -> int | None:
    if raw is None or raw == "":
        return None
    if not raw.isdigit():
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
    chosen = query.file or writing_name or (files[0].name if files else None)
    answer["file"] = chosen
    if chosen is None:
        answer.update(scanned=0, matched=0, events=[])
    elif all(f.name != chosen for f in files):
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


EVENT_LOG_ROUTES = [Route("/api/event-log", api_event_log)]


__all__ = [
    "DEFAULT_LIMIT",
    "EVENT_LOG_ROUTES",
    "MAX_LIMIT",
    "Query",
    "QueryError",
    "api_event_log",
    "parse_query",
    "read_log",
]
