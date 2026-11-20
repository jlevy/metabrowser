"""The shared model every provider maps its files onto.

A :class:`SessionSummary` carries the same fields for Claude Code and Codex, an
:class:`Event` is the unit every tally counts, a :class:`DriftSummary` says what a
provider did not recognize, and a :class:`LiveSession` is one session a liveness check
vouched for. Each has a ``to_json`` that returns plain JSON types in a fixed key order.

Times are Unix seconds as floats, ``None`` where the source does not say.
"""

from __future__ import annotations

import dataclasses
import math
import os
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

Agent = Literal["claude", "codex"]
Status = Literal["running", "finished", "failed", "unknown"]

# The origins a session can have; a provider picks the one its files support.
ORIGINS: Final = ("human", "scheduled", "subagent", "review", "automation")

# How long a `ps` probe may take before the pid is judged by `kill(pid, 0)` alone.
_PS_TIMEOUT_SECONDS: Final = 2.0

# The largest pid `os.kill` accepts; a larger one is not a process.
_MAX_PID: Final = 2**31 - 1


@dataclass(frozen=True, slots=True)
class Home:
    """An agent's home directory: ``~/.claude`` or ``~/.codex``."""

    agent: Agent
    path: Path

    def to_json(self) -> dict[str, object]:
        return {"agent": self.agent, "path": str(self.path)}


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One session (a Claude Code transcript or a Codex thread) in the shared shape.

    ``records`` and ``turns`` are ``None`` until the summary pass has read the session;
    the fast pass leaves them out. ``replayed_records`` counts records copied in from
    another session on resume or fork. ``family_versions`` names the measure families
    this summary holds (see the plan's "Engines and the Catalog").
    """

    agent: Agent
    session_id: str
    title: str | None = None
    parent_id: str | None = None
    child_ids: tuple[str, ...] = ()
    origin: str = "human"
    cwd: str | None = None
    git_branch: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    last_activity: float | None = None
    size_bytes: int = 0
    records: int | None = None
    replayed_records: int = 0
    turns: int | None = None
    models: tuple[str, ...] = ()
    status: Status = "unknown"
    source_paths: tuple[str, ...] = ()
    family_versions: Mapping[str, int] = field(default_factory=lambda: {})

    def to_json(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "session_id": self.session_id,
            "title": self.title,
            "parent_id": self.parent_id,
            "child_ids": list(self.child_ids),
            "origin": self.origin,
            "cwd": self.cwd,
            "git_branch": self.git_branch,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "last_activity": self.last_activity,
            "size_bytes": self.size_bytes,
            "records": self.records,
            "replayed_records": self.replayed_records,
            "turns": self.turns,
            "models": list(self.models),
            "status": self.status,
            "source_paths": list(self.source_paths),
            "family_versions": dict(sorted(self.family_versions.items())),
        }


@dataclass(frozen=True, slots=True)
class DriftSummary:
    """What a provider read but did not recognize.

    ``unknown_types`` counts events no mapping rule matched, keyed by raw type (and
    subtype). ``unexpected_columns`` and ``missing_columns`` count SQLite columns outside
    or absent from the schema the provider was written against, keyed ``db.table.column``.
    ``read_errors`` counts reads that failed (a locked or malformed database, an
    unreadable file), keyed by what was being read. ``truncated`` is true when a read
    stopped early, at its byte budget or at an error.
    """

    unknown_types: Mapping[str, int] = field(default_factory=lambda: {})
    unexpected_columns: Mapping[str, int] = field(default_factory=lambda: {})
    missing_columns: Mapping[str, int] = field(default_factory=lambda: {})
    read_errors: Mapping[str, int] = field(default_factory=lambda: {})
    truncated: bool = False

    @property
    def is_clean(self) -> bool:
        return not (
            self.unknown_types or self.unexpected_columns or self.missing_columns or self.truncated
        )

    def to_json(self) -> dict[str, object]:
        return {
            "unknown_types": dict(sorted(self.unknown_types.items())),
            "unexpected_columns": dict(sorted(self.unexpected_columns.items())),
            "missing_columns": dict(sorted(self.missing_columns.items())),
            "read_errors": dict(sorted(self.read_errors.items())),
            "truncated": self.truncated,
        }


class DriftCollector:
    """A mutable accumulator that freezes into a :class:`DriftSummary`."""

    def __init__(self) -> None:
        self.unknown_types: dict[str, int] = {}
        self.unexpected_columns: dict[str, int] = {}
        self.missing_columns: dict[str, int] = {}
        self.read_errors: dict[str, int] = {}
        self.truncated = False

    def unknown(self, key: str) -> None:
        self.unknown_types[key] = self.unknown_types.get(key, 0) + 1

    def unexpected(self, key: str) -> None:
        self.unexpected_columns[key] = self.unexpected_columns.get(key, 0) + 1

    def missing(self, key: str) -> None:
        self.missing_columns[key] = self.missing_columns.get(key, 0) + 1

    def read_error(self, key: str) -> None:
        self.read_errors[key] = self.read_errors.get(key, 0) + 1
        self.truncated = True

    def freeze(self) -> DriftSummary:
        return DriftSummary(
            unknown_types=dict(self.unknown_types),
            unexpected_columns=dict(self.unexpected_columns),
            missing_columns=dict(self.missing_columns),
            read_errors=dict(self.read_errors),
            truncated=self.truncated,
        )


def merge_drift(parts: Iterable[DriftSummary]) -> DriftSummary:
    """Add drift summaries together, counts summed."""

    collector = DriftCollector()
    for part in parts:
        for key, count in part.unknown_types.items():
            collector.unknown_types[key] = collector.unknown_types.get(key, 0) + count
        for key, count in part.unexpected_columns.items():
            collector.unexpected_columns[key] = collector.unexpected_columns.get(key, 0) + count
        for key, count in part.missing_columns.items():
            collector.missing_columns[key] = collector.missing_columns.get(key, 0) + count
        for key, count in part.read_errors.items():
            collector.read_errors[key] = collector.read_errors.get(key, 0) + count
        collector.truncated = collector.truncated or part.truncated
    return collector.freeze()


@dataclass(frozen=True, slots=True)
class Event:
    """One normalized event: the unit every tally, color, and latency report counts.

    ``tool_name`` is the raw tool name, or ``mcp:<server>.<tool>`` for an MCP tool, and
    ``tool_family`` is its family from :mod:`.kinds`. ``ordinal`` and ``locator`` find
    the event in its source: a line number or item ordinal, and a string that is unique
    within the session. ``replay`` marks an event copied in from another session.
    """

    session_id: str
    ordinal: int
    locator: str
    timestamp: float | None
    kind: str
    raw_type: str
    raw_subtype: str | None = None
    tool_name: str | None = None
    tool_family: str | None = None
    summary: str = ""
    replay: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "ordinal": self.ordinal,
            "locator": self.locator,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "raw_type": self.raw_type,
            "raw_subtype": self.raw_subtype,
            "tool_name": self.tool_name,
            "tool_family": self.tool_family,
            "summary": self.summary,
            "replay": self.replay,
        }


@dataclass(frozen=True, slots=True)
class LiveSession:
    """A session something currently vouches for, and what vouched.

    ``source`` is ``pid-file`` (Claude Code, pid alive), ``active-chat-turn`` (Codex
    desktop store, observed recently), or ``recent-update`` (Codex thread updated within
    the recent window).
    """

    agent: Agent
    session_id: str
    source: str
    status: str | None = None
    cwd: str | None = None
    name: str | None = None
    pid: int | None = None
    updated_at: float | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "session_id": self.session_id,
            "source": self.source,
            "status": self.status,
            "cwd": self.cwd,
            "name": self.name,
            "pid": self.pid,
            "updated_at": self.updated_at,
        }


def apply_live(
    sessions: Iterable[SessionSummary], live: Iterable[LiveSession]
) -> list[SessionSummary]:
    """Mark the sessions a liveness check vouched for as running; touch no others."""

    running = {(item.agent, item.session_id) for item in live}
    return [
        dataclasses.replace(session, status="running")
        if (session.agent, session.session_id) in running
        else session
        for session in sessions
    ]


# A liveness probe takes a pid and the process start time a pid file recorded, if any.
PidProbe = Callable[[int, str | None], bool]


def default_pid_probe(pid: int, proc_start: str | None) -> bool:
    """True only when *pid* is provably the process a pid file recorded.

    ``kill(pid, 0)`` finds a live process but not a reused pid, so the recorded start
    time (UTC, in ``ps -o lstart`` format) must match what ``ps`` reports. A missing
    *proc_start*, or a ``ps`` that fails, cannot prove it, so the answer is False: a
    session is never shown as running on weaker evidence.
    """

    if pid <= 0 or pid > _MAX_PID or not proc_start:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        pass
    except (OSError, OverflowError, ValueError):
        return False
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=_PS_TIMEOUT_SECONDS,
            env={**os.environ, "TZ": "UTC"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    started = result.stdout.split()
    return result.returncode == 0 and bool(started) and started == proc_start.split()


def parse_timestamp(value: object) -> float | None:
    """Unix seconds from an ISO 8601 string or a number (seconds or milliseconds)."""

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except OverflowError:
            return None
        if not math.isfinite(number):
            return None
        return number / 1000.0 if number > 1e11 else number
    if isinstance(value, str) and value:
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.timestamp()
    return None
