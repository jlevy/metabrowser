"""The Codex provider: threads from ``~/.codex`` SQLite stores and rollouts.

What it reads, and nothing else, every database read-only and by index:

- ``state_<N>.sqlite``: ``threads`` (the catalog) and ``thread_spawn_edges`` (children).
  The store's generation ``N`` is the highest on disk, since a store is recreated, not
  migrated, when it moves.
- ``thread_history_<N>.sqlite``: ``thread_turns`` and ``thread_items``, the stream. Rows
  are keyed by *history id*: the thread id for its first segment and the id after the
  underscore in ``rollout-<ts>-<thread>_<history>.jsonl*`` for each later segment, so a
  stream reads every segment or a busy thread looks idle. A compressed ``.jsonl.zst``
  rollout needs no zstd, since the history store is the readable copy.
- ``sqlite/codex.db``: ``active_chat_turns``, the one source of "running now".
- Plain ``.jsonl`` and ``.jsonl.gz`` rollouts, only when the history store has no rows
  for a thread. They carry metering and turn context the history lacks.

An ``inProgress`` turn proves nothing: most are orphans from a crash. Only
``active_chat_turns`` (seen recently) and a very recent ``threads.updated_at_ms`` make a
thread live.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import re
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final

from .kinds import CODEX_RULES, classify, mcp_label, tool_family
from .model import (
    DriftCollector,
    DriftSummary,
    Event,
    Home,
    LiveSession,
    SessionSummary,
    merge_drift,
    parse_timestamp,
)
from .readers import (
    JsonlReader,
    as_dict,
    as_int,
    as_list,
    as_str,
    check_table,
    clip,
    open_readonly,
)

AGENT: Final = "codex"

# The measure families a Codex summary holds, each with its schema version.
FAMILY_VERSIONS: Final = {"session": 1, "drift": 1}

# The most threads one discovery reads, newest first, by an indexed read that never scans.
# Measured on the maintainer's machine (see `catalog.py`, "Measurements"): one real store
# holds 22,302 threads, and reading all of them took 23.8 s under heavy load (about 1 ms
# a thread; the newest 5,000 took 2 s), in the catalog's background worker, never on a
# request. The limit is 30,000: every thread of that store with 1.3 times its size to grow
# into. A store over it lists its newest threads, and `catalog` says so
# (`discover_limit_reached`).
DISCOVER_LIMIT: Final = 30_000

# The most characters of a thread's title or name one discovery reads. A thread with no
# name keeps its first prompt as its title: of 22,302 real threads the median title was 15
# characters, the 99th percentile 245,541 and the longest 647,106, and reading them whole
# took the discovery to 618 MB of memory. The cut is in SQL.
TITLE_READ_CHARS: Final = 4000

# The most spawn edges one discovery reads.
EDGE_LIMIT: Final = 200_000

# The most history items one stream reads from a thread, across all its segments. The
# largest of 16,125 real threads holds 27,682 items (2,021,343 in all), so this is 3.6
# times the largest.
MAX_ITEMS: Final = 100_000

# The most characters of one item's JSON a stream reads. SQLite counts a TEXT value's
# characters, not bytes, so this is at most four times as many bytes. An item over it
# decodes to nothing and keeps its kind from `item_type`.
MAX_ITEM_CHARS: Final = 1024 * 1024

# The most characters of item JSON one stream reads from a thread, across its segments.
MAX_THREAD_CHARS: Final = 256 * 1024 * 1024

# `active_chat_turns` is refreshed about every minute (research brief), so a row not
# observed within three refreshes is stale.
ACTIVE_TURN_MAX_AGE_SECONDS: Final = 180.0

# A thread updated this recently counts as live even with no active turn row.
RECENT_UPDATE_SECONDS: Final = 120.0

# How many of the newest threads `live` looks at for recent updates.
LIVE_THREAD_LIMIT: Final = 50

_FETCH: Final = 500

# How many unmatched messages a rollout read remembers to catch a message written twice,
# and how much of each it compares.
_ECHO_WINDOW: Final = 64
_ECHO_TEXT_CHARS: Final = 2000

# The schemas this provider was written against, from the research brief's survey. A
# column outside `expected` is drift; a missing column in `required` is drift too.
THREADS_EXPECTED: Final = frozenset(
    [
        "id",
        "rollout_path",
        "created_at",
        "updated_at",
        "source",
        "model_provider",
        "cwd",
        "title",
        "sandbox_policy",
        "approval_mode",
        "tokens_used",
        "has_user_event",
        "archived",
        "archived_at",
        "git_sha",
        "git_branch",
        "git_origin_url",
        "cli_version",
        "first_user_message",
        "agent_nickname",
        "agent_role",
        "memory_mode",
        "model",
        "reasoning_effort",
        "agent_path",
        "created_at_ms",
        "updated_at_ms",
        "thread_source",
        "preview",
        "recency_at",
        "recency_at_ms",
        "history_mode",
        "name",
        "is_pinned",
        "thread_section_id",
        "section_position",
        "section_entered_at_ms",
        "project_id",
        "originator",
        "daybreak_enabled",
        "creator_user_id",
        "creator_account_id",
        "attached_thread_parent_id",
    ]
)
THREADS_REQUIRED: Final = frozenset(
    [
        "id",
        "rollout_path",
        "created_at",
        "updated_at",
        "cwd",
        "title",
        "git_branch",
        "model",
        "thread_source",
    ]
)
EDGES_EXPECTED: Final = frozenset({"parent_thread_id", "child_thread_id", "status"})
EDGES_REQUIRED: Final = frozenset({"parent_thread_id", "child_thread_id"})
TURNS_EXPECTED: Final = frozenset(
    [
        "thread_id",
        "turn_id",
        "rollout_ordinal",
        "status",
        "error_json",
        "started_at",
        "completed_at",
        "duration_ms",
        "first_user_item_id",
        "final_agent_item_id",
        "rollout_byte_offset",
        "rollout_end_ordinal",
        "rollout_end_byte_offset",
        "root_turn_id",
    ]
)
TURNS_REQUIRED: Final = frozenset(
    {"thread_id", "turn_id", "rollout_ordinal", "status", "error_json"}
)
ITEMS_EXPECTED: Final = frozenset(
    [
        "thread_id",
        "turn_id",
        "item_id",
        "rollout_ordinal",
        "created_at_ms",
        "item_json",
        "item_type",
        "updated_at_ordinal",
        "started_at_ms",
        "completed_at_ms",
    ]
)
ITEMS_REQUIRED: Final = frozenset(
    {"thread_id", "rollout_ordinal", "created_at_ms", "item_json", "item_type"}
)
ACTIVE_EXPECTED: Final = frozenset(
    {"profile", "account_id", "user_id", "thread_id", "launch_id", "observed_at_ms"}
)
ACTIVE_REQUIRED: Final = frozenset({"thread_id", "observed_at_ms"})

_THREAD_COLUMNS: Final = (
    "id",
    "rollout_path",
    "created_at",
    "updated_at",
    "created_at_ms",
    "updated_at_ms",
    "cwd",
    "title",
    "name",
    "git_branch",
    "model",
    "thread_source",
)

# The `threads` columns that hold free text, which `_select_list` cuts in SQL.
_FREE_TEXT_COLUMNS: Final = frozenset({"title", "name"})

_ROLLOUT_NAME: Final = re.compile(
    r"^rollout-.+-(?P<tid>[0-9a-fA-F]{8}-[0-9a-fA-F-]{27})(?:_(?P<hid>[0-9A-Za-z-]+))?"
    r"\.jsonl(?:\.zst|\.gz)?$"
)


def rollout_thread_id(name: str) -> str | None:
    """The thread a rollout file belongs to, from its name, or ``None`` for any other file."""

    match = _ROLLOUT_NAME.match(name)
    return match["tid"] if match else None


def _generation(home: Home, prefix: str) -> Path | None:
    """The newest ``<prefix>_<N>.sqlite`` in the home, by its generation number."""

    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)\.sqlite$")
    best: tuple[int, Path] | None = None
    try:
        for entry in home.path.iterdir():
            match = pattern.match(entry.name)
            if match and (best is None or int(match.group(1)) > best[0]):
                best = (int(match.group(1)), entry)
    except OSError:
        return None
    return best[1] if best else None


def _state_db(home: Home) -> Path | None:
    return _generation(home, "state")


def _history_db(home: Home) -> Path | None:
    return _generation(home, "thread_history")


def _query(
    conn: sqlite3.Connection,
    sql: str,
    args: tuple[object, ...] = (),
    drift: DriftCollector | None = None,
    label: str = "",
) -> list[tuple[object, ...]]:
    """Rows of a query; a failed query is a read error in *drift*, never silence."""

    try:
        return [tuple(row) for row in conn.execute(sql, args).fetchall()]  # pyright: ignore[reportAny]
    except sqlite3.Error:
        if drift is not None:
            drift.read_error(label or "query")
        return []


def _rollout_files(
    rollout_path: str | None, thread_id: str, cache: dict[Path, list[Path]]
) -> list[Path]:
    """The rollout segment files of a thread: its own file and any ``_<history>`` ones."""

    if not rollout_path:
        return []
    named = Path(rollout_path)
    directory = named.parent
    if directory not in cache:
        try:
            cache[directory] = sorted(directory.iterdir())
        except OSError:
            cache[directory] = []
    files: list[Path] = []
    for entry in cache[directory]:
        match = _ROLLOUT_NAME.match(entry.name)
        if match and match.group("tid") == thread_id and entry.is_file():
            files.append(entry)
    return files


def _history_ids(session_id: str, paths: tuple[str, ...]) -> list[str]:
    """The history ids of a thread's segments: the thread id first, then later ones."""

    ids = [session_id]
    for name in sorted(Path(p).name for p in paths):
        match = _ROLLOUT_NAME.match(name)
        hid = match.group("hid") if match else None
        if hid and hid not in ids:
            ids.append(hid)
    return ids


def _seconds(ms: object, seconds: object) -> float | None:
    value = as_int(ms)
    if value is not None:
        return value / 1000.0
    return parse_timestamp(seconds)


def discover(
    home: Home, limit: int = DISCOVER_LIMIT, drift: DriftCollector | None = None
) -> list[SessionSummary]:
    """The fast pass: the newest *limit* threads by indexed read, with sizes by ``stat``.

    Children come from ``thread_spawn_edges``. Records and turns are ``None`` and status
    is ``unknown`` until :func:`summarize`. A caller that passes *drift* learns about a
    store that failed to open or a query that failed, which would otherwise read as an
    empty catalog.
    """

    drift = drift if drift is not None else DriftCollector()
    path = _state_db(home)
    conn = open_readonly(path, drift) if path else None
    if conn is None:
        return []
    try:
        actual = check_table(conn, "state", "threads", THREADS_EXPECTED, THREADS_REQUIRED, drift)
        if actual is None:
            return []
        wanted = [c for c in _THREAD_COLUMNS if c in actual]
        order = next((c for c in ("updated_at_ms", "updated_at") if c in actual), "rowid")
        rows = _query(
            conn,
            f"SELECT {_select_list(wanted)} FROM threads ORDER BY {order} DESC LIMIT ?",
            (limit,),
            drift,
            "state.threads",
        )
        parents: dict[str, str] = {}
        children: dict[str, list[str]] = {}
        edge_cols = check_table(
            conn, "state", "thread_spawn_edges", EDGES_EXPECTED, EDGES_REQUIRED, drift
        )
        if edge_cols is not None and edge_cols >= EDGES_REQUIRED:
            for parent, child in _query(
                conn,
                "SELECT parent_thread_id, child_thread_id FROM thread_spawn_edges LIMIT ?",
                (EDGE_LIMIT,),
                drift,
                "state.thread_spawn_edges",
            ):
                if isinstance(parent, str) and isinstance(child, str):
                    parents[child] = parent
                    children.setdefault(parent, []).append(child)
    finally:
        conn.close()
    cache: dict[Path, list[Path]] = {}
    sessions: list[SessionSummary] = []
    for row in rows:
        record = dict(zip(wanted, row, strict=True))
        thread_id = as_str(record.get("id"))
        if thread_id is None:
            continue
        files = _rollout_files(as_str(record.get("rollout_path")), thread_id, cache)
        size = 0
        for file in files:
            with contextlib.suppress(OSError):
                size += file.stat().st_size
        source = as_str(record.get("thread_source"))
        origin = (
            "subagent"
            if thread_id in parents
            else "review"
            if source == "guardian_review"
            else "human"
        )
        model = as_str(record.get("model"))
        sessions.append(
            SessionSummary(
                agent=AGENT,
                session_id=thread_id,
                title=as_str(record.get("name")) or as_str(record.get("title")),
                parent_id=parents.get(thread_id),
                child_ids=tuple(sorted(children.get(thread_id, ()))),
                origin=origin,
                cwd=as_str(record.get("cwd")),
                git_branch=as_str(record.get("git_branch")),
                started_at=_seconds(record.get("created_at_ms"), record.get("created_at")),
                last_activity=_seconds(record.get("updated_at_ms"), record.get("updated_at")),
                size_bytes=size,
                models=(model,) if model else (),
                status="unknown",
                source_paths=tuple(str(f) for f in files),
            )
        )
    sessions.sort(key=lambda s: (-(s.last_activity or 0.0), s.session_id))
    return sessions


def schema_drift(home: Home) -> DriftSummary:
    """Columns outside or missing from the schemas this provider was written against."""

    drift = DriftCollector()
    state = _state_db(home)
    conn = open_readonly(state) if state else None
    if conn is not None:
        try:
            check_table(conn, "state", "threads", THREADS_EXPECTED, THREADS_REQUIRED, drift)
            check_table(conn, "state", "thread_spawn_edges", EDGES_EXPECTED, EDGES_REQUIRED, drift)
        finally:
            conn.close()
    history = _history_db(home)
    conn = open_readonly(history) if history else None
    if conn is not None:
        try:
            check_table(conn, "history", "thread_turns", TURNS_EXPECTED, TURNS_REQUIRED, drift)
            check_table(conn, "history", "thread_items", ITEMS_EXPECTED, ITEMS_REQUIRED, drift)
        finally:
            conn.close()
    return drift.freeze()


def _item_event(
    session_id: str,
    segment: str,
    ordinal: int,
    stamp: float | None,
    item_type: str,
    item: dict[str, object],
    drift: DriftCollector | None,
) -> Event:
    tool: str | None = None
    label: str | None = None
    family: str | None = None
    summary = ""
    if item_type == "commandExecution":
        command = item.get("command")
        text = (
            " ".join(str(p) for p in as_list(command))
            if isinstance(command, list)
            else str(command or "")
        )
        code = as_int(item.get("exitCode"))
        summary = f"{text} (exit {code})" if code is not None else text
        tool = item_type
    elif item_type == "mcpToolCall":
        label = mcp_label(as_str(item.get("server")) or "?", as_str(item.get("tool")) or "?")
        family = "mcp"
        summary = label
    elif item_type == "dynamicToolCall":
        tool = as_str(item.get("tool")) or item_type
        summary = tool
    elif item_type in ("fileChange", "webSearch", "collabAgentToolCall", "imageView"):
        tool = item_type
        summary = str(item.get("query") or item.get("tool") or item_type)
    elif item_type == "imageGeneration":
        tool = item_type
    elif item_type == "userMessage":
        parts = [as_dict(p) or {} for p in as_list(item.get("content"))]
        summary = " ".join(str(p.get("text", "")) for p in parts)
    elif item_type == "agentMessage":
        summary = str(item.get("text") or "")
    elif item_type == "reasoning":
        summary = " ".join(str(s) for s in as_list(item.get("summary")))
    if tool is not None:
        family, label = tool_family(AGENT, tool)
    kind = classify(CODEX_RULES, "thread_item", item_type)
    if kind == "unknown" and drift is not None:
        drift.unknown(f"thread_item/{item_type}")
    return Event(
        session_id=session_id,
        ordinal=ordinal,
        locator=f"{segment}:{ordinal}",
        timestamp=stamp,
        kind=kind,
        raw_type="thread_item",
        raw_subtype=item_type,
        tool_name=label,
        tool_family=family,
        summary=clip(summary),
    )


def _history_events(
    conn: sqlite3.Connection, session_id: str, segments: list[str], drift: DriftCollector | None
) -> Iterator[Event]:
    """Items of every segment in ordinal order, with turn errors merged in by ordinal."""

    scratch = DriftCollector()
    item_cols = check_table(
        conn, "history", "thread_items", ITEMS_EXPECTED, ITEMS_REQUIRED, scratch
    )
    if item_cols is None or not item_cols >= ITEMS_REQUIRED:
        return
    turn_cols = check_table(
        conn, "history", "thread_turns", TURNS_EXPECTED, TURNS_REQUIRED, scratch
    )
    thread_items = 0
    thread_chars = 0
    stopped = False
    for segment in segments:
        errors: list[tuple[int, float | None, str]] = []
        if turn_cols is not None and turn_cols >= TURNS_REQUIRED:
            completed = "completed_at" if "completed_at" in turn_cols else "NULL"
            for ordinal, stamp, raw in _query(
                conn,
                f"SELECT rollout_ordinal, {completed}, error_json FROM thread_turns "
                "WHERE thread_id = ? AND error_json IS NOT NULL AND error_json != '' "
                "ORDER BY rollout_ordinal",
                (segment,),
                drift,
                "history.thread_turns",
            ):
                errors.append((as_int(ordinal) or 0, parse_timestamp(stamp), str(raw)))
        pending = iter(errors)
        next_error = next(pending, None)
        try:
            cursor = conn.execute(
                "SELECT rollout_ordinal, created_at_ms, substr(item_json, 1, ?), item_type, "
                "length(item_json) FROM thread_items WHERE thread_id = ? "
                "ORDER BY rollout_ordinal LIMIT ?",
                (MAX_ITEM_CHARS, segment, MAX_ITEMS - thread_items + 1),
            )
            while not stopped:
                rows = cursor.fetchmany(_FETCH)  # pyright: ignore[reportAny]
                if not rows:
                    break
                for ordinal_raw, created, raw_json, item_type, length in rows:  # pyright: ignore[reportAny]
                    thread_items += 1
                    thread_chars += min(as_int(length) or 0, MAX_ITEM_CHARS)
                    if thread_items > MAX_ITEMS or thread_chars > MAX_THREAD_CHARS:
                        if drift is not None:
                            drift.truncated = True
                        stopped = True
                        break
                    ordinal = as_int(ordinal_raw) or 0
                    while next_error is not None and next_error[0] <= ordinal:
                        yield _error_event(session_id, segment, next_error)
                        next_error = next(pending, None)
                    item = _decode_item(raw_json)
                    kind_name = as_str(item_type) or as_str(item.get("type")) or "?"
                    yield _item_event(
                        session_id,
                        segment,
                        ordinal,
                        parse_timestamp(created),
                        kind_name,
                        item,
                        drift,
                    )
        except sqlite3.Error:
            if drift is not None:
                drift.read_error("history.thread_items")
            stopped = True
        while next_error is not None:
            yield _error_event(session_id, segment, next_error)
            next_error = next(pending, None)
        if stopped:
            return


def _decode_item(raw: object) -> dict[str, object]:
    if isinstance(raw, (str, bytes)):
        try:
            return as_dict(json.loads(raw)) or {}
        except (ValueError, RecursionError):
            return {}
    return {}


def _error_event(session_id: str, segment: str, error: tuple[int, float | None, str]) -> Event:
    ordinal, stamp, raw = error
    return Event(
        session_id=session_id,
        ordinal=ordinal,
        locator=f"{segment}:{ordinal}:error",
        timestamp=stamp,
        kind=classify(CODEX_RULES, "thread_turn", "error"),
        raw_type="thread_turn",
        raw_subtype="error",
        summary=clip(raw),
    )


def _rollout_events(path: Path, session_id: str, drift: DriftCollector | None) -> Iterator[Event]:
    """Events of a plain or gzip rollout, one per line."""

    reader = JsonlReader(path)
    call_names: dict[str, str] = {}
    echoes: dict[tuple[str, str], str] = {}
    for number, record in reader:
        if record is None:
            if drift is not None:
                drift.unknown("<invalid-json>")
            continue
        raw = as_str(record.get("type")) or "?"
        payload = as_dict(record.get("payload")) or {}
        subtype = as_str(payload.get("type"))
        if _is_echo(echoes, raw, subtype, payload):
            continue
        block: str | None = None
        tool: str | None = None
        label: str | None = None
        family: str | None = None
        summary = ""
        if raw == "response_item":
            if subtype == "message":
                block = as_str(payload.get("role"))
            name = as_str(payload.get("name"))
            call_id = as_str(payload.get("call_id"))
            if subtype and subtype.endswith("_call") and subtype != "web_search_call":
                tool = name or ("local_shell" if subtype == "local_shell_call" else subtype)
                if call_id:
                    call_names[call_id] = tool
                summary = tool
            elif subtype == "web_search_call":
                tool = "web_search"
            elif subtype and subtype.endswith("_call_output") and call_id:
                tool = call_names.get(call_id)
        elif raw == "event_msg":
            if subtype == "item_completed":
                item = as_dict(payload.get("item")) or {}
                block = as_str(item.get("type"))
                if block == "mcpToolCall":
                    label = mcp_label(
                        as_str(item.get("server")) or "?", as_str(item.get("tool")) or "?"
                    )
                    family = "mcp"
                elif block in (
                    "commandExecution",
                    "fileChange",
                    "webSearch",
                    "collabAgentToolCall",
                ):
                    tool = block
            elif subtype in ("exec_command_begin", "exec_command_end"):
                tool = "exec_command"
            elif subtype in ("patch_apply_begin", "patch_apply_end"):
                tool = "apply_patch"
            elif subtype in ("mcp_tool_call_begin", "mcp_tool_call_end"):
                invocation = as_dict(payload.get("invocation")) or {}
                label = mcp_label(
                    as_str(invocation.get("server")) or "?", as_str(invocation.get("tool")) or "?"
                )
                family = "mcp"
        if tool is not None:
            family, label = tool_family(AGENT, tool)
        kind = classify(CODEX_RULES, raw, subtype, block)
        if kind == "unknown" and drift is not None:
            drift.unknown(raw + (f"/{subtype}" if subtype else ""))
        yield Event(
            session_id=session_id,
            ordinal=_ordinal(record, number),
            locator=str(number),
            timestamp=parse_timestamp(record.get("timestamp")),
            kind=kind,
            raw_type=raw,
            raw_subtype=subtype,
            tool_name=label,
            tool_family=family,
            summary=clip(summary),
        )
    if drift is not None and reader.truncated:
        drift.truncated = True


def _message_key(
    raw: str, subtype: str | None, payload: dict[str, object]
) -> tuple[str, str, str] | None:
    """(role, text, source) of a message that a rollout writes twice, else ``None``.

    A rollout carries a message both as ``response_item/message`` and as
    ``event_msg/user_message`` or ``agent_message``; the second must not be counted.
    """

    if raw == "response_item" and subtype == "message":
        role = as_str(payload.get("role"))
        parts = [as_dict(p) or {} for p in as_list(payload.get("content"))]
        text = " ".join(str(p.get("text", "")) for p in parts).strip()
        source = "response_item"
    elif raw == "event_msg" and subtype in ("user_message", "agent_message"):
        role = "user" if subtype == "user_message" else "assistant"
        text = str(payload.get("message") or "").strip()
        source = "event_msg"
    else:
        return None
    if role not in ("user", "assistant") or not text:
        return None
    return role, text[:_ECHO_TEXT_CHARS], source


def _is_echo(
    echoes: dict[tuple[str, str], str], raw: str, subtype: str | None, payload: dict[str, object]
) -> bool:
    """True when this message repeats the other source's message seen just before it."""

    key = _message_key(raw, subtype, payload)
    if key is None:
        return False
    role, text, source = key
    seen = echoes.get((role, text))
    if seen is not None and seen != source:
        del echoes[(role, text)]
        return True
    if len(echoes) >= _ECHO_WINDOW:
        del echoes[next(iter(echoes))]
    echoes[(role, text)] = source
    return False


def _ordinal(record: dict[str, object], line: int) -> int:
    value = as_int(record.get("ordinal"))
    return line if value is None else value


def _plain_rollouts(paths: tuple[str, ...]) -> list[Path]:
    return [Path(p) for p in sorted(paths) if not p.endswith(".zst") and Path(p).is_file()]


def _events(
    home: Home,
    session_id: str,
    paths: tuple[str, ...],
    drift: DriftCollector | None,
) -> Iterator[Event]:
    emitted = False
    history = _history_db(home)
    conn = open_readonly(history, drift) if history else None
    if conn is not None:
        try:
            for event in _history_events(conn, session_id, _history_ids(session_id, paths), drift):
                emitted = True
                yield event
        finally:
            conn.close()
    if not emitted:
        for rollout in _plain_rollouts(paths):
            yield from _rollout_events(rollout, session_id, drift)


def summarize(home: Home, session: SessionSummary) -> tuple[SessionSummary, DriftSummary]:
    """Stream the thread's events and its turns, and fill in what discovery left out.

    Status comes from the last turn: ``failed`` when it has an error, ``unknown`` while
    it is ``inProgress`` (an orphan until :func:`live` says otherwise), else ``finished``.
    """

    drift = DriftCollector()
    records = 0
    for event in _events(home, session.session_id, session.source_paths, drift):
        if event.raw_type != "thread_turn":
            records += 1
    turns, status = _turns(home, session, drift)
    updated = dataclasses.replace(
        session,
        ended_at=session.last_activity if status in ("finished", "failed") else None,
        records=records,
        turns=turns,
        status=status,
        family_versions=dict(FAMILY_VERSIONS),
    )
    return updated, merge_drift([drift.freeze(), schema_drift(home)])


def _turns(home: Home, session: SessionSummary, drift: DriftCollector) -> tuple[int, str]:
    """(turn count, status) from the thread's turns, segment by segment.

    Ordinals are not assumed to continue across segments, so turns are read per segment
    in history-id order and each segment by ordinal; the last turn is the last segment's.
    """

    history = _history_db(home)
    conn = open_readonly(history, drift) if history else None
    if conn is None:
        return 0, "unknown"
    rows: list[tuple[object, ...]] = []
    try:
        scratch = DriftCollector()
        cols = check_table(conn, "history", "thread_turns", TURNS_EXPECTED, TURNS_REQUIRED, scratch)
        if cols is None or not cols >= TURNS_REQUIRED:
            return 0, "unknown"
        for segment in _history_ids(session.session_id, session.source_paths):
            rows.extend(
                _query(
                    conn,
                    "SELECT status, error_json FROM thread_turns WHERE thread_id = ? "
                    "ORDER BY rollout_ordinal",
                    (segment,),
                    drift,
                    "history.thread_turns",
                )
            )
    finally:
        conn.close()
    if not rows:
        return 0, "unknown"
    last_status, last_error = rows[-1]
    if last_error:
        return len(rows), "failed"
    if last_status == "inProgress":
        return len(rows), "unknown"
    return len(rows), "failed" if last_status == "failed" else "finished"


def stream(home: Home, session_id: str) -> Iterator[Event]:
    """Yield a thread's events: history rows by segment, else its plain rollouts."""

    state = _state_db(home)
    conn = open_readonly(state) if state else None
    paths: tuple[str, ...] = ()
    if conn is not None:
        try:
            rows = _query(conn, "SELECT rollout_path FROM threads WHERE id = ?", (session_id,))
        finally:
            conn.close()
        if rows:
            files = _rollout_files(as_str(rows[0][0]), session_id, {})
            paths = tuple(str(f) for f in files)
    yield from stream_paths(home, session_id, paths)


def stream_paths(home: Home, session_id: str, paths: tuple[str, ...]) -> Iterator[Event]:
    """Yield a thread's events given its rollout files, as the catalog already holds them."""

    yield from _events(home, session_id, paths, None)


def _select_list(columns: Iterable[str]) -> str:
    """*columns* as a ``SELECT`` list, with the free-text ones cut to TITLE_READ_CHARS.

    A thread with no name keeps its first prompt as its title, so a title can be hundreds
    of kilobytes. The cut is in SQL, so the rest is never read into memory.
    """

    return ", ".join(
        f"substr({c}, 1, {TITLE_READ_CHARS})" if c in _FREE_TEXT_COLUMNS else c for c in columns
    )


def _thread_select(actual: frozenset[str]) -> str:
    """The columns `live` reads from `threads`, with NULL for any this schema lacks."""

    return _select_list(
        c if c in actual else "NULL"
        for c in ("id", "cwd", "name", "title", "updated_at_ms", "updated_at")
    )


def live(home: Home, now: float, drift: DriftCollector | None = None) -> list[LiveSession]:
    """Threads the desktop store or a very recent update vouches for.

    ``active_chat_turns`` rows observed within :data:`ACTIVE_TURN_MAX_AGE_SECONDS` of
    *now* come first; then threads updated within :data:`RECENT_UPDATE_SECONDS`. A turn
    row marked ``inProgress`` in the history store is never consulted. A time after
    *now* vouches for nothing.
    """

    collector = drift if drift is not None else DriftCollector()
    state = _state_db(home)
    state_conn = open_readonly(state, collector) if state else None
    found: dict[str, LiveSession] = {}
    actual = (
        check_table(state_conn, "state", "threads", THREADS_EXPECTED, frozenset(), collector)
        if state_conn is not None
        else None
    )
    select = _thread_select(actual) if actual is not None else ""
    order = "updated_at_ms" if actual and "updated_at_ms" in actual else "updated_at"

    def thread_row(row: tuple[object, ...]) -> tuple[str | None, str | None, float | None]:
        _, cwd, name, title, ms, sec = row
        return as_str(cwd), as_str(name) or as_str(title), _seconds(ms, sec)

    def detail(thread_id: str) -> tuple[str | None, str | None]:
        if state_conn is None or actual is None:
            return None, None
        rows = _query(
            state_conn,
            f"SELECT {select} FROM threads WHERE id = ?",
            (thread_id,),
            collector,
            "state.threads",
        )
        if not rows:
            return None, None
        cwd, name, _ = thread_row(rows[0])
        return cwd, name

    try:
        desktop = open_readonly(home.path / "sqlite" / "codex.db", collector)
        if desktop is not None:
            try:
                columns = check_table(
                    desktop,
                    "desktop",
                    "active_chat_turns",
                    ACTIVE_EXPECTED,
                    ACTIVE_REQUIRED,
                    collector,
                )
                active = (
                    _query(
                        desktop,
                        "SELECT thread_id, observed_at_ms FROM active_chat_turns "
                        "ORDER BY observed_at_ms DESC LIMIT 200",
                        (),
                        collector,
                        "desktop.active_chat_turns",
                    )
                    if columns is not None and columns >= ACTIVE_REQUIRED
                    else []
                )
                for thread_id, observed in active:
                    seen = _seconds(observed, None)
                    if (
                        isinstance(thread_id, str)
                        and seen is not None
                        and 0 <= now - seen <= ACTIVE_TURN_MAX_AGE_SECONDS
                        and thread_id not in found
                    ):
                        cwd, name = detail(thread_id)
                        found[thread_id] = LiveSession(
                            agent=AGENT,
                            session_id=thread_id,
                            source="active-chat-turn",
                            status="busy",
                            cwd=cwd,
                            name=name,
                            updated_at=seen,
                        )
            finally:
                desktop.close()
        if state_conn is not None and actual is not None and "id" in actual:
            for row in _query(
                state_conn,
                f"SELECT {select} FROM threads ORDER BY {order} DESC LIMIT ?",
                (LIVE_THREAD_LIMIT,),
                collector,
                "state.threads",
            ):
                thread_id = row[0]
                cwd, name, stamp = thread_row(row)
                if (
                    isinstance(thread_id, str)
                    and stamp is not None
                    and 0 <= now - stamp <= RECENT_UPDATE_SECONDS
                    and thread_id not in found
                ):
                    found[thread_id] = LiveSession(
                        agent=AGENT,
                        session_id=thread_id,
                        source="recent-update",
                        status="idle",
                        cwd=cwd,
                        name=name,
                        updated_at=stamp,
                    )
    finally:
        if state_conn is not None:
            state_conn.close()
    return sorted(found.values(), key=lambda s: (s.source, s.session_id))
