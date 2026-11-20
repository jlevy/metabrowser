"""The Claude Code provider: sessions from ``~/.claude`` transcripts.

What it reads, and nothing else:

- ``projects/<enc-cwd>/<sid>.jsonl``: a main session (``.jsonl.zst`` is listed from
  ``stat`` only; this provider has no zstd reader).
- ``projects/<enc-cwd>/<sid>/subagents/agent-<aid>.jsonl`` and its ``.meta.json``: a
  child session of ``<sid>``, or of the agent its ``parentAgentId`` names. A subagent's
  session id is its file stem, ``agent-<aid>``.
- ``sessions/<pid>.json``: the live registry, believed only after a liveness probe.

``discover`` is the fast pass (``stat`` plus the first and last records). ``summarize``
reads one transcript within a byte budget. ``stream`` yields normalized events.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .kinds import CLAUDE_RULES, classify, tool_family
from .model import (
    DriftCollector,
    DriftSummary,
    Event,
    Home,
    LiveSession,
    PidProbe,
    SessionSummary,
    default_pid_probe,
    parse_timestamp,
)
from .readers import (
    JsonlReader,
    as_dict,
    as_int,
    as_list,
    as_str,
    clip,
    edge_records,
    read_small_json,
)

AGENT: Final = "claude"

# The measure families a Claude summary holds, each with its schema version.
FAMILY_VERSIONS: Final = {"session": 1, "drift": 1}

# The subagent id prefix, which is also the file stem prefix.
_AGENT_PREFIX: Final = "agent-"

# The most pid files `live` reads. A real home held 16 (a pid file is removed when its
# session ends, so stale ones are few), and each read costs a `ps` probe, so this is 12
# times the measured count.
MAX_PID_FILES: Final = 200

# `input` keys whose value best says what a tool call did, in order of preference.
_TOOL_ARGUMENT_KEYS: Final = ("command", "file_path", "pattern", "url", "description", "prompt")

# Message models that are not a real model.
_SYNTHETIC_MODEL: Final = "<synthetic>"


@dataclass(frozen=True, slots=True)
class _Found:
    session_id: str
    path: Path
    parent_sid: str | None  # the main session a subagent lives under
    meta: dict[str, object] | None


def _scan(home: Home) -> list[_Found]:
    """Every transcript under ``projects/``, by ``stat`` and directory listing only."""

    found: list[_Found] = []
    projects = home.path / "projects"
    try:
        project_dirs = sorted(p for p in projects.iterdir() if p.is_dir())
    except OSError:
        return found
    for project in project_dirs:
        try:
            entries = sorted(project.iterdir())
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if entry.is_file():
                for suffix in (".jsonl", ".jsonl.zst"):
                    if name.endswith(suffix):
                        found.append(_Found(name[: -len(suffix)], entry, None, None))
                        break
            elif entry.is_dir():
                subagents = entry / "subagents"
                if not subagents.is_dir():
                    continue
                for transcript in sorted(subagents.glob(f"{_AGENT_PREFIX}*.jsonl")):
                    stem = transcript.name[: -len(".jsonl")]
                    meta = read_small_json(subagents / f"{stem}.meta.json")
                    found.append(_Found(stem, transcript, entry.name, meta))
    return found


def _find(home: Home, session_id: str) -> _Found | None:
    for item in _scan(home):
        if item.session_id == session_id:
            return item
    return None


def _stat(path: Path) -> tuple[int, float | None]:
    try:
        info = path.stat()
    except OSError:
        return 0, None
    return info.st_size, info.st_mtime


def _meta_parent(item: _Found) -> str | None:
    if item.parent_sid is None:
        return None
    parent_agent = as_str(item.meta.get("parentAgentId")) if item.meta else None
    return f"{_AGENT_PREFIX}{parent_agent}" if parent_agent else item.parent_sid


def _title_of(record: dict[str, object]) -> str | None:
    kind = record.get("type")
    if kind == "custom-title":
        return as_str(record.get("customTitle"))
    if kind == "agent-name":
        return as_str(record.get("agentName"))
    return None


def _is_replay(record: dict[str, object], own: str, subagent: bool) -> bool:
    other = as_str(record.get("sessionId"))
    return not subagent and other is not None and other != own


def discover(home: Home) -> list[SessionSummary]:
    """The fast pass: every session with size, times, place, title, and its children.

    Reads ``stat`` for every transcript and the first and last 64 KiB of each plain one.
    Records and turns are left ``None`` and status ``unknown``; a summary pass fills them.
    Newest first by last activity, then by id.
    """

    items = _scan(home)
    children: dict[str, list[str]] = {}
    for item in items:
        parent = _meta_parent(item)
        if parent is not None:
            children.setdefault(parent, []).append(item.session_id)
    sessions = [_fast(item, children.get(item.session_id, ())) for item in items]
    sessions.sort(key=lambda s: (-(s.last_activity or 0.0), s.session_id))
    return sessions


def _fast(item: _Found, child_ids: list[str] | tuple[str, ...]) -> SessionSummary:
    size, mtime = _stat(item.path)
    subagent = item.parent_sid is not None
    title: str | None = None
    cwd: str | None = None
    branch: str | None = None
    first: float | None = None
    last: float | None = None
    models: tuple[str, ...] = ()
    if subagent and item.meta:
        title = as_str(item.meta.get("description"))
        model = as_str(item.meta.get("model"))
        models = (model,) if model else ()
    if not item.path.name.endswith(".zst"):
        head, tail = edge_records(item.path)
        for record in head:
            if _is_replay(record, item.session_id, subagent):
                continue
            first = first if first is not None else parse_timestamp(record.get("timestamp"))
            cwd = cwd or as_str(record.get("cwd"))
            branch = branch or as_str(record.get("gitBranch"))
        for record in tail:
            if _is_replay(record, item.session_id, subagent):
                continue
            stamp = parse_timestamp(record.get("timestamp"))
            last = stamp if stamp is not None else last
            title = _title_of(record) or title
        for record in head:
            if not subagent:
                title = title or _title_of(record)
    return SessionSummary(
        agent=AGENT,
        session_id=item.session_id,
        title=title,
        parent_id=_meta_parent(item),
        child_ids=tuple(sorted(child_ids)),
        origin="subagent" if subagent else "human",
        cwd=cwd,
        git_branch=branch,
        started_at=first,
        ended_at=last,
        last_activity=mtime,
        size_bytes=size,
        models=models,
        status="unknown",
        source_paths=(str(item.path),),
        family_versions={},
    )


def _record_events(
    record: dict[str, object],
    *,
    session_id: str,
    ordinal: int,
    replay: bool,
    tool_names: dict[str, str],
) -> list[Event]:
    """The events one transcript record yields, in order."""

    raw = as_str(record.get("type")) or "?"
    stamp = parse_timestamp(record.get("timestamp"))
    events: list[Event] = []

    def emit(
        subtype: str | None,
        block: str | None,
        *,
        tool: str | None = None,
        summary: str = "",
    ) -> None:
        family, label = (None, None)
        if tool is not None:
            family, label = tool_family(AGENT, tool)
        events.append(
            Event(
                session_id=session_id,
                ordinal=ordinal,
                locator=f"{ordinal}.{len(events)}",
                timestamp=stamp,
                kind=classify(CLAUDE_RULES, raw, subtype, block),
                raw_type=raw,
                raw_subtype=subtype
                if subtype
                else (block if raw in ("assistant", "user") else None),
                tool_name=label,
                tool_family=family,
                summary=clip(summary),
                replay=replay,
            )
        )

    if raw in ("assistant", "user"):
        message = as_dict(record.get("message")) or {}
        content = message.get("content")
        blocks: list[object] = (
            [{"type": "text", "text": content}] if isinstance(content, str) else as_list(content)
        )
        stub = raw == "assistant" and record.get("isApiErrorMessage") is True
        for entry in blocks:
            block = as_dict(entry)
            if block is None:
                emit(None, "?")
                continue
            btype = as_str(block.get("type")) or "?"
            if stub and btype == "text":
                emit(None, "api_error", summary=str(block.get("text", "")))
            elif btype == "tool_use":
                name = as_str(block.get("name")) or "?"
                tool_id = as_str(block.get("id"))
                if tool_id:
                    tool_names[tool_id] = name
                emit(None, btype, tool=name, summary=_tool_summary(name, block.get("input")))
            elif btype in ("tool_result", "server_tool_result"):
                tool_id = as_str(block.get("tool_use_id"))
                name = tool_names.get(tool_id) if tool_id else None
                failed = block.get("is_error") is True
                emit(None, btype, tool=name, summary="error" if failed else "result")
            else:
                emit(None, btype, summary=str(block.get("text") or block.get("thinking") or ""))
        usage = as_dict(message.get("usage"))
        if raw == "assistant" and usage is not None:
            out = as_int(usage.get("output_tokens")) or 0
            emit(None, "usage", summary=f"{as_int(usage.get('input_tokens')) or 0} in, {out} out")
        if raw == "user" and as_dict(record.get("permissionDecision")) is not None:
            emit(None, "permission_decision", summary="permission decision")
    elif raw == "attachment":
        attachment = as_dict(record.get("attachment")) or {}
        emit(as_str(attachment.get("type")) or "?", None)
    elif raw == "system":
        emit(as_str(record.get("subtype")) or "?", None, summary=str(record.get("content") or ""))
    else:
        emit(None, None)
    return events


def _tool_summary(name: str, arguments: object) -> str:
    args = as_dict(arguments) or {}
    for key in _TOOL_ARGUMENT_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            return f"{name}: {value}"
    return name


def _drift_key(event: Event) -> str:
    return event.raw_type + (f"/{event.raw_subtype}" if event.raw_subtype else "")


def _walk(
    path: Path, session_id: str, *, subagent: bool, drift: DriftCollector | None
) -> Iterator[tuple[dict[str, object], list[Event], bool]]:
    """Each record of a transcript with its events and whether it is a replay."""

    reader = JsonlReader(path)
    tool_names: dict[str, str] = {}
    for number, record in reader:
        if record is None:
            if drift is not None:
                drift.unknown("<invalid-json>")
            continue
        replay = _is_replay(record, session_id, subagent)
        events = _record_events(
            record, session_id=session_id, ordinal=number, replay=replay, tool_names=tool_names
        )
        if drift is not None:
            for event in events:
                if event.kind == "unknown":
                    drift.unknown(_drift_key(event))
        yield record, events, replay
    if drift is not None and reader.truncated:
        drift.truncated = True


def summarize(home: Home, session: SessionSummary) -> tuple[SessionSummary, DriftSummary]:
    """Read the whole transcript, bounded, and fill in what the fast pass left out.

    A compressed transcript comes back unchanged. Status is ``failed`` when the last
    conversation event is an error and ``finished`` otherwise; never ``running``, which
    only :func:`live` can say.
    """

    del home
    drift = DriftCollector()
    path = Path(session.source_paths[0]) if session.source_paths else None
    if path is None or path.name.endswith(".zst") or not path.is_file():
        return session, drift.freeze()
    subagent = session.origin == "subagent"
    records = replayed = turns = 0
    models: dict[str, None] = {}
    cwd = branch = title = None
    first = last = None
    last_kind: str | None = None
    for record, events, replay in _walk(path, session.session_id, subagent=subagent, drift=drift):
        records += 1
        if replay:
            replayed += 1
            continue
        title = _title_of(record) or title
        cwd = cwd or as_str(record.get("cwd"))
        branch = branch or as_str(record.get("gitBranch"))
        stamp = parse_timestamp(record.get("timestamp"))
        if stamp is not None:
            first = first if first is not None else stamp
            last = stamp
        if record.get("type") == "assistant":
            model = as_str((as_dict(record.get("message")) or {}).get("model"))
            if model and model != _SYNTHETIC_MODEL:
                models[model] = None
        if record.get("type") == "user" and record.get("isMeta") is not True:
            turns += any(e.kind == "prompt" for e in events)
        for event in events:
            if event.kind not in ("context", "metering"):
                last_kind = event.kind
    origin = session.origin
    if not subagent and origin == "human":
        origin = _origin_of(path, session.session_id)
    updated = dataclasses.replace(
        session,
        title=title or session.title,
        origin=origin,
        cwd=cwd or session.cwd,
        git_branch=branch or session.git_branch,
        started_at=first if first is not None else session.started_at,
        ended_at=last if last is not None else session.ended_at,
        records=records,
        replayed_records=replayed,
        turns=turns,
        models=tuple(models) or session.models,
        status="failed" if last_kind == "error" else "finished",
        family_versions=dict(FAMILY_VERSIONS),
    )
    return updated, drift.freeze()


def _origin_of(path: Path, session_id: str) -> str:
    """``scheduled`` when the first own prompt's ``turnOrigin`` says so, else ``human``."""

    for _, record in JsonlReader(path, budget=2 * 1024 * 1024):
        if record is None or _is_replay(record, session_id, False):
            continue
        origin = as_str(record.get("turnOrigin"))
        if record.get("type") == "user" and origin:
            return "scheduled" if origin == "scheduled" else "human"
    return "human"


def stream(home: Home, session_id: str) -> Iterator[Event]:
    """Yield a session's normalized events in file order; none for a compressed one.

    This finds the transcript by walking ``projects/``; a caller that already knows the
    file uses :func:`stream_file`.
    """

    item = _find(home, session_id)
    if item is None:
        return
    yield from stream_file(item.path, session_id, subagent=item.parent_sid is not None)


def stream_file(path: Path, session_id: str, *, subagent: bool) -> Iterator[Event]:
    """Yield the normalized events of one transcript file; none for a compressed one."""

    if path.name.endswith(".zst"):
        return
    for _, events, _ in _walk(path, session_id, subagent=subagent, drift=None):
        yield from events


def live(home: Home, now: float, probe: PidProbe = default_pid_probe) -> list[LiveSession]:
    """Sessions whose ``sessions/<pid>.json`` names a pid the probe says is alive.

    A pid file alone proves nothing: it can outlive its process. *now* is accepted so
    callers pass one clock to every provider; liveness here is the probe's, not an age.
    """

    del now
    registry = home.path / "sessions"
    result: list[LiveSession] = []
    try:
        names = sorted(n for n in os.listdir(registry) if n.endswith(".json"))[:MAX_PID_FILES]
    except OSError:
        return result
    for name in names:
        data = read_small_json(registry / name)
        if data is None:
            continue
        pid = as_int(data.get("pid"))
        session_id = as_str(data.get("sessionId"))
        if pid is None or session_id is None:
            continue
        if not probe(pid, as_str(data.get("procStart"))):
            continue
        result.append(
            LiveSession(
                agent=AGENT,
                session_id=session_id,
                source="pid-file",
                status=as_str(data.get("status")),
                cwd=as_str(data.get("cwd")),
                name=as_str(data.get("name")),
                pid=pid,
                updated_at=parse_timestamp(data.get("updatedAt")),
            )
        )
    return result
