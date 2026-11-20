"""The ``agents`` plugin's catalog routes: ``catalog``, ``sessions``, ``session``,
``records``, and ``live``.

Each is a synchronous data-hook handler, so it runs in the server's threadpool, and none
reads a transcript to answer except ``records``, which streams one session within its
scan bound. Every other route answers from the catalog's snapshot (see :mod:`.catalog`)
and starts a background pass when the last one is old.

Parameters name a folder (``folder``, a served-root-relative directory that is or holds a
home) and, for one session, either ``agent`` with ``id`` or ``path``, the session's source
file. ``sync=1`` waits until the catalog is fully summarized, for the command line and
tests; ``now`` (Unix seconds) replaces the clock of the response and its liveness checks,
never the catalog's own pass times. One ``sync=1`` request waits at a time, for one
deadline across its homes; another answers at once with the progress so far.

Every response is a JSON object with a fixed key order. Every file path in it (``folder``,
``home``, ``source_paths``) is relative to the served root. A ``project`` is the working
directory the agent recorded, an absolute path on the machine that ran it, with the
current user's home directory shown as ``~`` and no other user's. A failure is
``{"error", "code", "param"}`` with status 400 for a bad parameter and 404 for a folder or
session that is not there.
"""

from __future__ import annotations

import os
import time
from bisect import bisect_right
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.plugin_api import (
    UnsupportedSourceCapabilityError,
    relativize_path,
    resolve_directory,
    resolve_path,
    served_root,
)

from . import catalog as catalogs
from . import claude, codex
from .homes import home_of, homes_in
from .kinds import KINDS
from .model import (
    ORIGINS,
    DriftSummary,
    Event,
    Home,
    LiveSession,
    SessionSummary,
    merge_drift,
    parse_timestamp,
)
from .readers import clip

# The limits below were set from the measurements recorded in :mod:`.catalog`.

# Rows a `sessions` page returns by default, and the most it will.
PAGE_DEFAULT: Final = 100
PAGE_MAX: Final = 500

# Events a `records` page returns by default, and the most it will.
RECORDS_DEFAULT: Final = 200
RECORDS_MAX: Final = 2000

# The most events one `records` request examines, matching or not. A filter that matches
# rarely stops here with `truncated` and a `next_cursor` to continue from.
RECORDS_SCAN_MAX: Final = 100_000

# The most live sessions and children one response lists.
LIVE_MAX: Final = 200
CHILDREN_MAX: Final = 200

# The most characters of a live session's name or project, which come from a pid file.
LIVE_TEXT_MAX_CHARS: Final = 200

# The projects and the models a `sessions` response lists as facets, most sessions first.
PROJECT_FACET_MAX: Final = 50
MODEL_FACET_MAX: Final = 50

# The most days `catalog` reports sessions for, newest.
PER_DAY_MAX: Final = 400

# The lower bound of each session-size bucket, in bytes: 0, then 1 KiB times powers of 4
# up to 4 GiB. The last bucket has no upper bound.
SIZE_BUCKET_LOWER_BOUNDS: Final = (0, *(1024 * 4**k for k in range(12)))

# The most characters of any one parameter value read.
MAX_PARAM_CHARS: Final = 1024

SORTS: Final = (
    "activity",
    "start",
    "duration",
    "turns",
    "records",
    "size",
    "title",
    "agent",
    "origin",
    "project",
    "status",
    "model",
)
STATUSES: Final = ("running", "finished", "failed", "unknown")
AGENTS: Final = ("claude", "codex")

# Which measure families each engine computes. Only the built-in engine exists yet.
ENGINES: Final = {"session": "builtin", "drift": "builtin"}


class _Refusal(Exception):
    """A request the route turns into a typed JSON error."""

    def __init__(self, status: int, code: str, message: str, param: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.param = param

    def response(self) -> JSONResponse:
        return JSONResponse(
            {"error": self.message, "code": self.code, "param": self.param}, status_code=self.status
        )


def _bad(param: str, message: str) -> _Refusal:
    return _Refusal(400, "bad_param", message, param)


# -- parameters -----------------------------------------------------------------------


def _text(request: Request, name: str) -> str | None:
    value = request.query_params.get(name)
    if value is None or value == "":
        return None
    if len(value) > MAX_PARAM_CHARS:
        raise _bad(name, f"{name} is longer than {MAX_PARAM_CHARS} characters")
    return value


def _integer(request: Request, name: str, default: int, low: int, high: int) -> int:
    raw = _text(request, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise _bad(name, f"{name} must be an integer") from None
    if not low <= value <= high:
        raise _bad(name, f"{name} must be between {low} and {high}")
    return value


def _choice(request: Request, name: str, allowed: Sequence[str]) -> str | None:
    raw = _text(request, name)
    if raw is None:
        return None
    if raw not in allowed:
        raise _bad(name, f"{name} must be one of: {', '.join(allowed)}")
    return raw


def _choices(request: Request, name: str, allowed: Sequence[str]) -> tuple[str, ...]:
    raw = _text(request, name)
    if raw is None:
        return ()
    values = tuple(dict.fromkeys(part for part in raw.split(",") if part))
    for value in values:
        if value not in allowed:
            raise _bad(name, f"{name} values must be among: {', '.join(allowed)}")
    return values


def _moment(request: Request, name: str) -> float | None:
    raw = _text(request, name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    parsed = parse_timestamp(raw)
    if parsed is None:
        raise _bad(name, f"{name} must be Unix seconds or an ISO 8601 time")
    return parsed


def _flag(request: Request, name: str) -> bool:
    return (_text(request, name) or "").lower() in ("1", "true", "yes")


# -- folders and sessions -------------------------------------------------------------


def _relative(path: Path) -> str | None:
    """*path* relative to the served root, ``""`` for the root, ``None`` outside it."""

    relative = relativize_path(str(path))
    if relative is None:
        return None
    if relative == ".":
        return ""
    if os.path.isabs(relative):
        return None
    return relative


def _clipped(text: str | None) -> str | None:
    """A free-text field from a file the agent wrote, as one redacted line."""

    return clip(text, LIVE_TEXT_MAX_CHARS) if text else None


def _project(cwd: str | None) -> str | None:
    """The working directory with the user's home directory shown as ``~``."""

    if cwd is None:
        return None
    user_home = os.path.expanduser("~")
    if user_home not in ("~", "/") and (cwd == user_home or cwd.startswith(user_home + os.sep)):
        return "~" + cwd[len(user_home) :]
    return cwd


@dataclass(slots=True)
class _Scope:
    """What a request resolved: its folder, its homes' snapshots, and its clock."""

    folder: str
    now: float
    snapshots: list[catalogs.Snapshot]
    homes: dict[tuple[str, str], str]  # (agent, absolute path) -> relative path
    live: list[tuple[Home, LiveSession]]

    def relative(self, home: Home) -> str:
        return self.homes[(home.agent, str(home.path))]

    def rows(self, snap: catalogs.Snapshot) -> list[tuple[SessionSummary, str, bool]]:
        """One home's sessions with its relative path and whether each is summarized.

        A session a liveness check vouched for is ``running``.
        """

        running = {item.session_id for home, item in self.live if home == snap.home}
        relative = self.relative(snap.home)
        return [
            (
                replace(e.summary, status="running")
                if e.summary.session_id in running
                else e.summary,
                relative,
                e.summarized,
            )
            for e in snap.entries
        ]

    def sessions(self) -> list[tuple[SessionSummary, str, bool]]:
        """Every session of every home, with ``running`` applied."""

        return [row for snap in self.snapshots for row in self.rows(snap)]


def _resolve_homes(folder_param: str) -> tuple[str, list[Home]]:
    try:
        resolved = resolve_directory(folder_param)
    except UnsupportedSourceCapabilityError:
        raise _Refusal(
            400, "unsupported_source", "Agent homes are read from a served folder", "folder"
        ) from None
    if resolved is None:
        raise _Refusal(404, "not_found", "No such folder", "folder")
    homes = list(homes_in(resolved))
    if not homes:
        raise _Refusal(
            404, "no_agent_homes", "This folder holds no Claude Code or Codex home", "folder"
        )
    folder = _relative(resolved)
    return ("" if folder is None else folder), homes


def _scope(
    request: Request,
    *,
    homes: list[Home] | None = None,
    folder: str | None = None,
    wait: bool = True,
) -> _Scope:
    if homes is None or folder is None:
        folder, homes = _resolve_homes(_text(request, "folder") or "")
    now = _moment(request, "now")
    sync = _flag(request, "sync")
    clock = now if now is not None else catalogs.CLOCK()
    snapshots: list[catalogs.Snapshot] = []
    relative: dict[tuple[str, str], str] = {}
    live: list[tuple[Home, LiveSession]] = []
    generation = catalogs.generation()
    # One request waits at a time, for one deadline shared by all its homes; a request
    # that cannot take the slot answers at once with the progress so far.
    waiting = sync and catalogs.SYNC_SLOT.acquire(blocking=False)
    deadline = time.monotonic() + catalogs.SYNC_TIMEOUT_SECONDS
    try:
        for home in homes:
            catalog = catalogs.catalog_for(home, generation)
            if waiting:
                catalog.complete(max(0.0, deadline - time.monotonic()))
            else:
                catalog.refresh(catalogs.FIRST_PASS_WAIT_SECONDS if wait else 0.0)
            snapshots.append(catalog.snapshot())
            live.extend((home, item) for item in catalog.live(clock))
            home_relative = _relative(home.path)
            relative[(home.agent, str(home.path))] = "" if home_relative is None else home_relative
    finally:
        if waiting:
            catalogs.SYNC_SLOT.release()
    return _Scope(folder, clock, snapshots, relative, live)


# -- JSON shapes ----------------------------------------------------------------------


def _day(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%d")


def _source_files(paths: Iterable[str]) -> list[str]:
    files: list[str] = []
    for raw in paths:
        relative = _relative(Path(raw))
        if relative:
            files.append(relative)
    return files


def _started(session: SessionSummary) -> float | None:
    return session.started_at if session.started_at is not None else session.last_activity


def _duration(session: SessionSummary) -> float | None:
    if session.started_at is None or session.ended_at is None:
        return None
    return max(0.0, session.ended_at - session.started_at)


def _row(session: SessionSummary, home: str, summarized: bool) -> dict[str, object]:
    return {
        "agent": session.agent,
        "session_id": session.session_id,
        "home": home,
        "title": session.title,
        "parent_id": session.parent_id,
        "child_ids": list(session.child_ids),
        "origin": session.origin,
        "project": _project(session.cwd),
        "git_branch": session.git_branch,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "last_activity": session.last_activity,
        "duration_seconds": _duration(session),
        "size_bytes": session.size_bytes,
        "records": session.records,
        "replayed_records": session.replayed_records,
        "turns": session.turns,
        "models": list(session.models),
        "status": session.status,
        "summarized": summarized,
        "source_paths": _source_files(session.source_paths),
    }


def _drift_json(drift: DriftSummary) -> dict[str, object]:
    return {"clean": drift.is_clean, **drift.to_json()}


_STATE_ORDER: Final = ("error", "scanning", "summarizing", "idle")


def _progress(scope: _Scope) -> dict[str, object]:
    snaps = scope.snapshots
    states = [s.state for s in snaps]
    state = next((s for s in _STATE_ORDER if s in states), "idle")
    total = sum(s.total for s in snaps)
    summarized = sum(s.summarized for s in snaps)
    first_pass = any(s.fast_at is None for s in snaps)
    return {
        "state": "scanning" if first_pass and state == "idle" else state,
        "total": total,
        "summarized": summarized,
        "from_cache": sum(s.from_cache for s in snaps),
        "read": sum(s.read for s in snaps),
        "failed": sum(s.failed for s in snaps),
        "complete": not first_pass
        and summarized + sum(s.failed for s in snaps) >= total
        and not any(s.pending_budget for s in snaps),
    }


def _freshness(scope: _Scope) -> dict[str, object]:
    fast = [s.fast_at for s in scope.snapshots if s.fast_at is not None]
    summary = [s.summary_at for s in scope.snapshots]
    complete = all(t is not None for t in summary)
    return {
        "fast_pass_at": min(fast) if len(fast) == len(scope.snapshots) and fast else None,
        "summary_pass_at": min(t for t in summary if t is not None)
        if complete and summary
        else None,
        "passes": sum(s.passes for s in scope.snapshots),
    }


def _cache(scope: _Scope) -> dict[str, object]:
    states = {s.cache for s in scope.snapshots}
    state = "unavailable" if "unavailable" in states else "ok" if "ok" in states else "unknown"
    return {"state": state, "write_errors": sum(s.cache_write_errors for s in scope.snapshots)}


# -- routes ---------------------------------------------------------------------------


def _guarded(handler: Callable[[Request], dict[str, object]]) -> Callable[[Request], JSONResponse]:
    def wrapped(request: Request) -> JSONResponse:
        try:
            return JSONResponse(handler(request))
        except _Refusal as refusal:
            return refusal.response()

    wrapped.__name__ = handler.__name__
    wrapped.__doc__ = handler.__doc__
    return wrapped


@_guarded
def catalog_handler(request: Request) -> dict[str, object]:
    """Homes, totals, size-histogram buckets, sessions per day, progress, and freshness."""

    scope = _scope(request)
    homes: list[dict[str, object]] = []
    rows: list[tuple[SessionSummary, str, bool]] = []
    for snap in scope.snapshots:
        mine = scope.rows(snap)
        rows.extend(mine)
        times = [s.last_activity for s, _, _ in mine if s.last_activity is not None]
        homes.append(
            {
                "agent": snap.home.agent,
                "path": scope.relative(snap.home),
                "state": snap.state,
                "sessions": snap.total,
                "summarized": snap.summarized,
                "running": sum(1 for s, _, _ in mine if s.status == "running"),
                "size_bytes": sum(s.size_bytes for s, _, _ in mine),
                "oldest_activity": min(times) if times else None,
                "newest_activity": max(times) if times else None,
                "discover_limit_reached": snap.home.agent == "codex"
                and snap.total >= codex.DISCOVER_LIMIT,
            }
        )
    sessions = [session for session, _, _ in rows]
    counts = [0] * len(SIZE_BUCKET_LOWER_BOUNDS)
    per_day: Counter[str] = Counter()
    for session in sessions:
        index = bisect_right(SIZE_BUCKET_LOWER_BOUNDS, session.size_bytes) - 1
        counts[index] += 1
        moment = _started(session)
        if moment is not None:
            per_day[_day(moment)] += 1
    uppers: list[int | None] = [*SIZE_BUCKET_LOWER_BOUNDS[1:], None]
    drift = merge_drift([s.drift for s in scope.snapshots])
    return {
        "folder": scope.folder,
        "now": scope.now,
        "homes": homes,
        "totals": {
            "sessions": len(sessions),
            "summarized": sum(1 for _, _, done in rows if done),
            "running": sum(1 for s in sessions if s.status == "running"),
            "size_bytes": sum(s.size_bytes for s in sessions),
            "by_agent": _counts(Counter(s.agent for s in sessions), AGENTS),
            "by_origin": _counts(Counter(s.origin for s in sessions), ORIGINS),
        },
        "size_histogram": {
            "unit": "bytes",
            "buckets": [
                {"lower": lower, "upper": upper, "count": count}
                for lower, upper, count in zip(
                    SIZE_BUCKET_LOWER_BOUNDS, uppers, counts, strict=True
                )
            ],
        },
        "per_day": [
            {"day": day, "sessions": per_day[day]} for day in sorted(per_day)[-PER_DAY_MAX:]
        ],
        "progress": _progress(scope),
        "freshness": _freshness(scope),
        "cache": _cache(scope),
        "drift": _drift_json(drift),
        "engines": dict(ENGINES),
    }


def _counts(counter: Counter[str], order: Sequence[str]) -> dict[str, int]:
    """Counts in a fixed key order: the *order* given, then anything else sorted."""

    known = {key: counter[key] for key in order if counter[key]}
    known.update({key: counter[key] for key in sorted(counter) if key not in order})
    return known


_SORT_KEYS: Final[dict[str, Callable[[SessionSummary], object]]] = {
    "activity": lambda s: s.last_activity,
    "start": _started,
    "duration": _duration,
    "turns": lambda s: s.turns,
    "records": lambda s: s.records,
    "size": lambda s: s.size_bytes,
    "title": lambda s: s.title.casefold() if s.title else None,
    "agent": lambda s: s.agent,
    "origin": lambda s: s.origin,
    "project": lambda s: _project(s.cwd),
    "status": lambda s: s.status,
    "model": lambda s: s.models[0] if s.models else None,
}


def _sorted(
    rows: list[tuple[SessionSummary, str, bool]], sort: str, descending: bool
) -> list[tuple[SessionSummary, str, bool]]:
    """Rows by *sort*, with rows lacking the value last and ties broken by identity."""

    key = _SORT_KEYS[sort]
    rows = sorted(rows, key=lambda r: (r[0].agent, r[0].session_id))
    present = [r for r in rows if key(r[0]) is not None]
    absent = [r for r in rows if key(r[0]) is None]
    present.sort(key=lambda r: key(r[0]), reverse=descending)  # pyright: ignore[reportArgumentType, reportCallIssue]
    return present + absent


@_guarded
def sessions_handler(request: Request) -> dict[str, object]:
    """Filtered, sorted, paged session rows, with totals and facets over the whole folder."""

    agent = _choice(request, "agent", AGENTS)
    origins = _choices(request, "origin", ORIGINS)
    statuses = _choices(request, "status", STATUSES)
    project = _text(request, "project")
    model = _text(request, "model")
    since = _moment(request, "since")
    until = _moment(request, "until")
    sort = _choice(request, "sort", SORTS) or "activity"
    order = _choice(request, "order", ("asc", "desc")) or ("asc" if sort in _ASCENDING else "desc")
    limit = _integer(request, "limit", PAGE_DEFAULT, 1, PAGE_MAX)
    offset = _integer(request, "offset", 0, 0, 10**9)
    scope = _scope(request)
    everything = scope.sessions()

    def keep(row: tuple[SessionSummary, str, bool]) -> bool:
        session = row[0]
        moment = _started(session)
        return (
            (agent is None or session.agent == agent)
            and (not origins or session.origin in origins)
            and (not statuses or session.status in statuses)
            and (project is None or _project(session.cwd) == project)
            and (model is None or model in session.models)
            and (since is None or (moment is not None and moment >= since))
            and (until is None or (moment is not None and moment < until))
        )

    matched = _sorted([r for r in everything if keep(r)], sort, order == "desc")
    page = matched[offset : offset + limit]
    every = [r[0] for r in everything]
    projects = Counter(p for p in (_project(s.cwd) for s in every) if p is not None)
    models = Counter(name for s in every for name in s.models)
    return {
        "folder": scope.folder,
        "now": scope.now,
        "filters": {
            "agent": agent,
            "origin": list(origins),
            "status": list(statuses),
            "project": project,
            "model": model,
            "since": since,
            "until": until,
        },
        "sort": sort,
        "order": order,
        "offset": offset,
        "limit": limit,
        "next_offset": offset + limit if offset + limit < len(matched) else None,
        "total": len(matched),
        "available": len(everything),
        "totals": {
            "size_bytes": sum(r[0].size_bytes for r in matched),
            "running": sum(1 for r in matched if r[0].status == "running"),
        },
        "facets": {
            "agent": _counts(Counter(s.agent for s in every), AGENTS),
            "origin": _counts(Counter(s.origin for s in every), ORIGINS),
            "status": _counts(Counter(s.status for s in every), STATUSES),
            "project": [
                [name, count]
                for name, count in sorted(projects.items(), key=lambda kv: (-kv[1], kv[0]))[
                    :PROJECT_FACET_MAX
                ]
            ],
            "model": [
                [name, count]
                for name, count in sorted(models.items(), key=lambda kv: (-kv[1], kv[0]))[
                    :MODEL_FACET_MAX
                ]
            ],
        },
        "progress": _progress(scope),
        "freshness": _freshness(scope),
        "cache": _cache(scope),
        "sessions": [_row(s, home, done) for s, home, done in page],
    }


# What a sort ascends by default: the text columns. The others default to the largest or
# newest first, which is what a person scanning a history wants.
_ASCENDING: Final = ("title", "agent", "origin", "project", "status", "model")


@dataclass(frozen=True, slots=True)
class _Located:
    """The session a request named, with the snapshot of the home it lives in."""

    scope: _Scope
    snap: catalogs.Snapshot
    session: SessionSummary
    summarized: bool
    drift: DriftSummary
    source: Path | None = None  # the file a `path` request named

    @property
    def home(self) -> Home:
        return self.snap.home

    @property
    def relative(self) -> str:
        return self.scope.relative(self.snap.home)


def _located(scope: _Scope, snap: catalogs.Snapshot, entry: catalogs.CatalogEntry) -> _Located:
    running = any(
        h == snap.home and i.session_id == entry.summary.session_id for h, i in scope.live
    )
    session = replace(entry.summary, status="running") if running else entry.summary
    return _Located(scope, snap, session, entry.summarized, entry.drift)


def _locate(request: Request) -> _Located:
    """The session a request names, by ``path`` or by ``agent`` and ``id``."""

    path_param = _text(request, "path")
    if path_param is not None:
        try:
            target = resolve_path(path_param)
        except UnsupportedSourceCapabilityError:
            raise _Refusal(
                400, "unsupported_source", "Agent sessions are read from a served folder", "path"
            ) from None
        if target is None or not target.is_file():
            raise _Refusal(404, "not_found", "No such session file", "path")
        home = home_of(target, served_root())
        if home is None:
            raise _Refusal(404, "no_agent_homes", "This file is not inside an agent home", "path")
        scope = _scope(request, homes=[home], folder=_relative(home.path) or "")
        stem = target.name.removesuffix(".zst").removesuffix(".jsonl")
        for snap in scope.snapshots:
            for entry in snap.entries:
                if str(target) in entry.summary.source_paths:
                    return replace(_located(scope, snap, entry), source=target)
        # Two files can carry one session id, and the catalog keeps one of them; the
        # request still streams the file it named. A Codex thread's database records its
        # rollout's path as Codex wrote it, which need not spell the file the way the
        # request does (a relative path, a link, or a moved home), so a rollout is also
        # found by the thread id in its name.
        thread = codex.rollout_thread_id(target.name)
        for snap in scope.snapshots:
            for entry in snap.entries:
                if snap.home.agent == "claude" and entry.summary.session_id == stem:
                    return replace(_located(scope, snap, entry), source=target)
                if snap.home.agent == "codex" and entry.summary.session_id == thread:
                    return replace(_located(scope, snap, entry), source=target)
        raise _Refusal(404, "session_not_found", "No session in the catalog has that file", "path")
    agent = _choice(request, "agent", AGENTS)
    identifier = _text(request, "id")
    if agent is None or identifier is None:
        raise _bad("id", "name a session with path, or with agent and id")
    scope = _scope(request)
    for snap in scope.snapshots:
        if snap.home.agent != agent:
            continue
        for entry in snap.entries:
            if entry.summary.session_id == identifier:
                return _located(scope, snap, entry)
    raise _Refusal(404, "session_not_found", "No such session", "id")


@_guarded
def session_handler(request: Request) -> dict[str, object]:
    """One session's summary, its parent and children, and its drift."""

    found = _locate(request)
    session, scope = found.session, found.scope
    by_id = {s.session_id: (s, done) for s, _, done in scope.rows(found.snap)}
    children = [by_id[c] for c in session.child_ids if c in by_id]
    parent = by_id.get(session.parent_id) if session.parent_id else None
    relative = found.relative
    return {
        "folder": scope.folder,
        "now": scope.now,
        "session": _row(session, relative, found.summarized),
        "parent": _row(parent[0], relative, parent[1]) if parent else None,
        "children": [_row(c, relative, done) for c, done in children[:CHILDREN_MAX]],
        "children_total": len(session.child_ids),
        "drift": _drift_json(found.drift),
        "provider_sections": [],
        "progress": _progress(scope),
        "freshness": _freshness(scope),
    }


@_guarded
def records_handler(request: Request) -> dict[str, object]:
    """One session's normalized events, filtered by kind, tool, or locator, one page."""

    kind = _choice(request, "kind", KINDS)
    tool = _text(request, "tool")
    locator = _text(request, "locator")
    limit = _integer(request, "limit", RECORDS_DEFAULT, 1, RECORDS_MAX)
    cursor = _integer(request, "cursor", 0, 0, RECORDS_SCAN_MAX)
    found = _locate(request)
    scope, session, relative = found.scope, found.session, found.relative

    def wanted(event: Event) -> bool:
        return (
            (kind is None or event.kind == kind)
            and (tool is None or tool in (event.tool_name, event.tool_family))
            and (locator is None or event.locator == locator)
        )

    stream = _open_stream(found)
    events: list[Event] = []
    examined = 0
    exhausted = True
    try:
        # One request examines at most RECORDS_SCAN_MAX events in all, the ones before
        # the cursor included, since a stream is re-read from its start each time.
        for event in stream:
            if examined >= RECORDS_SCAN_MAX or len(events) >= limit:
                exhausted = False
                break
            examined += 1
            if examined > cursor and wanted(event):
                events.append(event)
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()
    return {
        "folder": scope.folder,
        "session": {"agent": session.agent, "session_id": session.session_id, "home": relative},
        "filters": {"kind": kind, "tool": tool, "locator": locator},
        "cursor": cursor,
        "limit": limit,
        "examined": examined,
        "next_cursor": None if exhausted else examined,
        "events": [event.to_json() for event in events],
    }


def _open_stream(found: _Located) -> Iterator[Event]:
    """The session's events from the file the catalog located, never a rescan of the home."""

    session = found.session
    if found.home.agent == "codex":
        return codex.stream_paths(found.home, session.session_id, session.source_paths)
    source = found.source
    if source is None and session.source_paths:
        source = Path(session.source_paths[0])
    if source is None:
        return iter(())
    return claude.stream_file(
        source, session.session_id, subagent=source.parent.name == "subagents"
    )


@_guarded
def live_handler(request: Request) -> dict[str, object]:
    """Sessions something vouches for now, with what the catalog knows of each."""

    scope = _scope(request, wait=False)
    known = {
        (session.agent, session.session_id, rel): session for session, rel, _ in scope.sessions()
    }
    rows: list[dict[str, object]] = []
    ordered = sorted(
        scope.live, key=lambda hi: (-(hi[1].updated_at or 0.0), hi[1].agent, hi[1].session_id)
    )
    for home, item in ordered:
        relative = scope.homes[(home.agent, str(home.path))]
        session = known.get((item.agent, item.session_id, relative))
        rows.append(
            {
                "agent": item.agent,
                "session_id": item.session_id,
                "home": relative,
                "source": item.source,
                "status": item.status,
                "project": _clipped(_project(item.cwd)),
                "name": _clipped(item.name),
                "title": session.title if session else None,
                "models": list(session.models) if session else [],
                "started_at": session.started_at if session else None,
                "source_paths": _source_files(session.source_paths) if session else [],
                "pid": item.pid,
                "updated_at": item.updated_at,
            }
        )
    return {
        "folder": scope.folder,
        "now": scope.now,
        "total": len(rows),
        "sessions": rows[:LIVE_MAX],
    }
