"""A synthetic ``~/.claude`` and ``~/.codex`` for the ``agents`` provider tests.

Real homes hold private data, so they are never fixtures. :func:`build` writes both homes
under a directory, SQLite databases included, from schemas pinned here. Every id, time,
and count is a constant below, so a test states its expectation from the construction:

Claude Code (``projects/-work-alpha/``):

- ``S1``: 17 records. Lines 1 and 2 are resumed history, naming another ``sessionId``.
  The 15 own records yield 21 events covering every kind; 2 are ``unknown``.
- ``agent-aaa`` and ``agent-bbb``, subagents of ``S1`` (``bbb`` is a child of ``aaa``).
- ``S2``: a scheduled session that ends in an API error stub.
- ``S3``: a ``.jsonl.zst`` transcript, listed from ``stat`` only.
- ``sessions/4242.json`` names ``S1`` (alive in tests); ``sessions/4343.json`` names ``S2``
  and is a stale pid file.

Codex:

- ``T1`` (parent) has 11 history items and a failed turn; ``T2`` is its child by a spawn
  edge; ``T3`` is an automatic review; ``T4`` has a second segment under history id
  ``H4``; ``T5`` was updated seconds ago; ``T6`` has a fresh ``active_chat_turns`` row;
  ``T7`` has an orphaned ``inProgress`` turn and a stale ``active_chat_turns`` row; ``T8``
  has no history rows, only a plain rollout of 20 events and one invalid line.
- ``state_5.sqlite`` carries one unexpected column, ``threads.zz_future``, and
  ``thread_history_1.sqlite`` one, ``thread_items.zz_new_col``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from metabrowser.builtin_plugins.agents.model import Home

NOW: Final = 1_800_000_000.0
T0: Final = NOW - 86_400.0

S1: Final = "11111111-1111-4111-8111-111111111111"
S2: Final = "22222222-2222-4222-8222-222222222222"
S3: Final = "33333333-3333-4333-8333-333333333333"
OTHER: Final = "99999999-9999-4999-8999-999999999999"
AGENT_A: Final = "agent-aaa"
AGENT_B: Final = "agent-bbb"
PID_LIVE: Final = 4242
PID_STALE: Final = 4343

T1: Final = "00000000-0000-4000-8000-000000000001"
T2: Final = "00000000-0000-4000-8000-000000000002"
T3: Final = "00000000-0000-4000-8000-000000000003"
T4: Final = "00000000-0000-4000-8000-000000000004"
T5: Final = "00000000-0000-4000-8000-000000000005"
T6: Final = "00000000-0000-4000-8000-000000000006"
T7: Final = "00000000-0000-4000-8000-000000000007"
T8: Final = "00000000-0000-4000-8000-000000000008"
H4: Final = "00000000-0000-4000-8000-0000000000a4"

# The columns of `threads` as the research survey saw them, in order.
THREADS_SCHEMA: Final = (
    ("id", "TEXT PRIMARY KEY"),
    ("rollout_path", "TEXT"),
    ("created_at", "INTEGER"),
    ("updated_at", "INTEGER"),
    ("source", "TEXT"),
    ("model_provider", "TEXT"),
    ("cwd", "TEXT"),
    ("title", "TEXT"),
    ("sandbox_policy", "TEXT"),
    ("approval_mode", "TEXT"),
    ("tokens_used", "INTEGER"),
    ("has_user_event", "INTEGER"),
    ("archived", "INTEGER"),
    ("archived_at", "INTEGER"),
    ("git_sha", "TEXT"),
    ("git_branch", "TEXT"),
    ("git_origin_url", "TEXT"),
    ("cli_version", "TEXT"),
    ("first_user_message", "TEXT"),
    ("agent_nickname", "TEXT"),
    ("agent_role", "TEXT"),
    ("memory_mode", "TEXT"),
    ("model", "TEXT"),
    ("reasoning_effort", "TEXT"),
    ("agent_path", "TEXT"),
    ("created_at_ms", "INTEGER"),
    ("updated_at_ms", "INTEGER"),
    ("thread_source", "TEXT"),
    ("preview", "TEXT"),
    ("recency_at", "INTEGER"),
    ("recency_at_ms", "INTEGER"),
    ("history_mode", "TEXT"),
    ("name", "TEXT"),
    ("is_pinned", "INTEGER"),
    ("project_id", "TEXT"),
    ("originator", "TEXT"),
)
EDGES_SCHEMA: Final = (
    ("parent_thread_id", "TEXT"),
    ("child_thread_id", "TEXT"),
    ("status", "TEXT"),
)
TURNS_SCHEMA: Final = (
    ("thread_id", "TEXT"),
    ("turn_id", "TEXT"),
    ("rollout_ordinal", "INTEGER"),
    ("status", "TEXT"),
    ("error_json", "TEXT"),
    ("started_at", "INTEGER"),
    ("completed_at", "INTEGER"),
    ("duration_ms", "INTEGER"),
)
ITEMS_SCHEMA: Final = (
    ("thread_id", "TEXT"),
    ("turn_id", "TEXT"),
    ("item_id", "TEXT"),
    ("rollout_ordinal", "INTEGER"),
    ("created_at_ms", "INTEGER"),
    ("item_json", "TEXT"),
    ("item_type", "TEXT"),
    ("started_at_ms", "INTEGER"),
    ("completed_at_ms", "INTEGER"),
)
ACTIVE_SCHEMA: Final = (
    ("profile", "TEXT"),
    ("account_id", "TEXT"),
    ("user_id", "TEXT"),
    ("thread_id", "TEXT"),
    ("launch_id", "TEXT"),
    ("observed_at_ms", "INTEGER"),
)

# The Codex history items of T1, as (ordinal, item type, item body). Ordinal 8 is the
# failed turn's error event, which the stream merges in by ordinal.
T1_ITEMS: Final[tuple[tuple[int, str, Mapping[str, object]], ...]] = (
    (2, "userMessage", {"content": [{"type": "text", "text": "hello codex"}]}),
    (3, "reasoning", {"summary": ["thinking it over"]}),
    (4, "agentMessage", {"text": "hello human"}),
    (5, "commandExecution", {"command": "ls -l", "exitCode": 0, "durationMs": 12}),
    (6, "mcpToolCall", {"server": "srv", "tool": "lookup"}),
    (7, "fileChange", {"changes": [{"path": "a.txt"}]}),
    (9, "webSearch", {"query": "synthetic query"}),
    (10, "collabAgentToolCall", {"tool": "spawn_agent"}),
    (11, "contextCompaction", {}),
    (12, "holographicThing", {"x": 1}),
    (13, "error", {"message": "item failed"}),
)


def iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class SyntheticHomes:
    root: Path
    claude: Home
    codex: Home


def _write_jsonl(path: Path, lines: Iterable[object], *, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _usage(inp: int, out: int) -> dict[str, int]:
    return {"input_tokens": inp, "output_tokens": out}


def _env(session: str, offset: float, **extra: object) -> dict[str, object]:
    return {"sessionId": session, "timestamp": iso(T0 + offset), **extra}


def claude_s1_records() -> list[object]:
    """The 17 lines of S1; lines 1 and 2 are resumed history from ``OTHER``."""

    return [
        {
            "type": "user",
            **_env(OTHER, -1000, cwd="/work/other"),
            "message": {"role": "user", "content": "old prompt"},
        },
        {
            "type": "assistant",
            **_env(OTHER, -990),
            "message": {
                "id": "msg_old",
                "model": "claude-old",
                "content": [{"type": "text", "text": "old reply"}],
                "usage": _usage(1, 1),
            },
        },
        {"type": "queue-operation", **_env(S1, 0), "operation": "enqueue"},
        {"type": "custom-title", "sessionId": S1, "customTitle": "Synthetic session"},
        {
            "type": "user",
            **_env(S1, 10, cwd="/work/alpha", gitBranch="main", turnOrigin="human"),
            "message": {"role": "user", "content": "Please list files"},
        },
        {
            "type": "assistant",
            **_env(S1, 12, cwd="/work/alpha"),
            "message": {
                "id": "msg_1",
                "model": "claude-test-1",
                "content": [
                    {"type": "thinking", "thinking": "plan"},
                    {"type": "text", "text": "Listing."},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    },
                ],
                "usage": _usage(10, 5),
            },
        },
        {
            "type": "user",
            **_env(S1, 14),
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "a b"}],
            },
            "permissionDecision": {"decision": "allow"},
        },
        {"type": "attachment", **_env(S1, 15), "attachment": {"type": "hook_success"}},
        {"type": "system", **_env(S1, 16), "subtype": "compact_boundary"},
        {"type": "system", **_env(S1, 17), "subtype": "api_error"},
        {
            "type": "assistant",
            **_env(S1, 20),
            "message": {
                "id": "msg_2",
                "model": "claude-test-2",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_task",
                        "name": "Task",
                        "input": {"description": "Explore"},
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_mcp",
                        "name": "mcp__srv__lookup",
                        "input": {},
                    },
                ],
                "usage": _usage(20, 8),
            },
        },
        {"type": "attachment", **_env(S1, 22), "attachment": {"type": "brand_new_attachment"}},
        {"type": "never-seen-type", **_env(S1, 24)},
        {"type": "cost-state", "sessionId": S1, "totalCostUsd": 0.5},
        {"type": "file-history-snapshot", "sessionId": S1, "snapshot": {}},
        {
            "type": "user",
            **_env(S1, 30, turnOrigin="human"),
            "message": {"role": "user", "content": [{"type": "text", "text": "second prompt"}]},
        },
        {
            "type": "assistant",
            **_env(S1, 31),
            "message": {"id": "msg_3", "model": "claude-test-2", "content": [{"type": "hologram"}]},
        },
    ]


def _build_claude(home: Path) -> None:
    project = home / "projects" / "-work-alpha"
    _write_jsonl(project / f"{S1}.jsonl", claude_s1_records(), mtime=T0 + 40)
    subs = project / S1 / "subagents"
    sub_envelope = {"sessionId": S1, "isSidechain": True}
    _write_jsonl(
        subs / "agent-aaa.jsonl",
        [
            {
                "type": "user",
                **sub_envelope,
                "timestamp": iso(T0 + 21),
                "message": {"role": "user", "content": "Explore"},
            },
            {
                "type": "assistant",
                **sub_envelope,
                "timestamp": iso(T0 + 25),
                "message": {
                    "id": "msg_a1",
                    "model": "claude-sub-1",
                    "content": [{"type": "text", "text": "found it"}],
                    "usage": _usage(3, 2),
                },
            },
        ],
        mtime=T0 + 26,
    )
    _write_json(
        subs / "agent-aaa.meta.json",
        {
            "agentType": "Explore",
            "description": "Explore code",
            "toolUseId": "toolu_task",
            "spawnDepth": 1,
            "model": "claude-sub-1",
            "finished": True,
        },
    )
    _write_jsonl(
        subs / "agent-bbb.jsonl",
        [
            {
                "type": "assistant",
                **sub_envelope,
                "timestamp": iso(T0 + 26),
                "message": {
                    "id": "msg_b1",
                    "model": "claude-sub-2",
                    "content": [{"type": "text", "text": "nested"}],
                },
            }
        ],
        mtime=T0 + 27,
    )
    _write_json(
        subs / "agent-bbb.meta.json",
        {
            "agentType": "Explore",
            "description": "Nested",
            "parentAgentId": "aaa",
            "model": "claude-sub-2",
        },
    )
    _write_jsonl(
        project / f"{S2}.jsonl",
        [
            {
                "type": "user",
                **_env(S2, 3600, cwd="/work/beta", gitBranch="dev", turnOrigin="scheduled"),
                "message": {"role": "user", "content": "nightly"},
            },
            {
                "type": "assistant",
                **_env(S2, 3601),
                "isApiErrorMessage": True,
                "message": {
                    "id": "msg_err",
                    "model": "<synthetic>",
                    "content": [{"type": "text", "text": "API Error"}],
                },
            },
        ],
        mtime=T0 + 3601,
    )
    zst = project / f"{S3}.jsonl.zst"
    zst.write_bytes(b"\x28\xb5\x2f\xfd" + b"x" * 96)
    os.utime(zst, (T0 + 10, T0 + 10))
    (project / "memory").mkdir()
    (project / "memory" / "note.md").write_text("not a transcript\n", encoding="utf-8")
    (project / S1 / "tool-results").mkdir()
    _write_json(
        home / "sessions" / f"{PID_LIVE}.json",
        {
            "pid": PID_LIVE,
            "sessionId": S1,
            "cwd": "/work/alpha",
            "procStart": "Thu Nov 19 01:28:41 2026",
            "name": "alpha work",
            "status": "busy",
            "updatedAt": int((NOW - 5) * 1000),
        },
    )
    _write_json(
        home / "sessions" / f"{PID_STALE}.json",
        {"pid": PID_STALE, "sessionId": S2, "cwd": "/work/beta", "status": "idle", "updatedAt": 1},
    )
    (home / "sessions" / "garbage.json").write_text("{not json", encoding="utf-8")


@contextmanager
def _db(path: Path) -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    try:
        # Codex's databases are WAL, so the synthetic ones are too.
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _create(
    conn: sqlite3.Connection,
    table: str,
    schema: tuple[tuple[str, str], ...],
    extra: tuple[str, ...] = (),
) -> None:
    cols = ", ".join(f"{name} {kind}" for name, kind in (*schema, *((c, "TEXT") for c in extra)))
    conn.execute(f"CREATE TABLE {table} ({cols})")


def _insert(conn: sqlite3.Connection, table: str, row: Mapping[str, object]) -> None:
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO {table} ({names}) VALUES ({marks})", tuple(row.values()))


def _t8_rollout() -> list[object]:
    def line(n: int, kind: str, payload: Mapping[str, object] | None = None) -> dict[str, object]:
        record: dict[str, object] = {"timestamp": iso(T0 + 7000 + n), "ordinal": n, "type": kind}
        if payload is not None:
            record["payload"] = dict(payload)
        return record

    return [
        line(1, "session_meta", {"id": T8}),
        line(2, "turn_context", {"model": "gpt-test-1"}),
        line(3, "world_state", {}),
        line(4, "event_msg", {"type": "task_started", "turn_id": "t"}),
        line(5, "response_item", {"type": "message", "role": "user", "content": []}),
        line(6, "response_item", {"type": "reasoning", "summary": []}),
        line(
            7,
            "response_item",
            {"type": "function_call", "name": "exec_command", "call_id": "c1", "arguments": "{}"},
        ),
        line(8, "response_item", {"type": "function_call_output", "call_id": "c1", "output": "ok"}),
        line(9, "response_item", {"type": "message", "role": "assistant", "content": []}),
        line(10, "event_msg", {"type": "token_count", "info": {}}),
        line(11, "token_usage_record", {"total": 1}),
        line(12, "event_msg", {"type": "exec_approval_request"}),
        line(
            13,
            "event_msg",
            {
                "type": "item_completed",
                "item": {"type": "mcpToolCall", "server": "srv", "tool": "lookup"},
            },
        ),
        line(14, "event_msg", {"type": "turn_aborted"}),
        line(15, "event_msg", {"type": "novel_event"}),
        line(16, "novel_record", {}),
        line(17, "compacted", {}),
        line(18, "event_msg", {"type": "task_complete"}),
        line(
            19,
            "response_item",
            {"type": "custom_tool_call", "name": "apply_patch", "call_id": "c2"},
        ),
        "{{{ not json",
        line(21, "event_msg", {"type": "error"}),
        # One message written twice, as `response_item` and as `event_msg`: counted once.
        line(
            22,
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "dup"}]},
        ),
        line(23, "event_msg", {"type": "user_message", "message": "dup"}),
    ]


def _build_codex(home: Path, omit_thread_columns: tuple[str, ...]) -> None:
    day = home / "sessions" / "2026" / "11" / "18"
    day.mkdir(parents=True)

    def rollout(
        thread: str,
        hour: int,
        *,
        history: str | None = None,
        suffix: str = ".jsonl.zst",
        size: int = 0,
    ) -> Path:
        tail = f"_{history}" if history else ""
        path = day / f"rollout-2026-11-18T{hour:02d}-00-00-{thread}{tail}{suffix}"
        path.write_bytes(b"z" * size)
        return path

    rollout(T1, 0, size=40)
    rollout(T3, 1, size=30)
    rollout(T4, 2, size=50)
    rollout(T4, 3, history=H4, size=70)
    t8_path = day / f"rollout-2026-11-18T04-00-00-{T8}.jsonl"
    _write_jsonl(t8_path, _t8_rollout())

    def uncompressed(thread: str, hour: int) -> str:
        return str(day / f"rollout-2026-11-18T{hour:02d}-00-00-{thread}.jsonl")

    threads: list[Mapping[str, object]] = []

    def thread(tid: str, hour: int, updated: float, **fields: object) -> None:
        row: dict[str, object] = {
            "id": tid,
            "rollout_path": uncompressed(tid, hour),
            "created_at": int(updated) - 600,
            "updated_at": int(updated),
            "created_at_ms": (int(updated) - 600) * 1000,
            "updated_at_ms": int(updated) * 1000,
            "cwd": "/work/gamma",
            "git_branch": "main",
            "model": "gpt-test-1",
            "thread_source": "vscode",
            "title": f"title {tid[-1]}",
            "zz_future": "x",
        }
        row.update(fields)
        threads.append({k: v for k, v in row.items() if k not in omit_thread_columns})

    thread(T1, 0, NOW - 3600, name="Gamma thread")
    thread(T2, 5, NOW - 3500)
    thread(T3, 1, NOW - 3000, thread_source="guardian_review")
    thread(T4, 2, NOW - 1800, model="gpt-test-2")
    thread(T5, 6, NOW - 30)
    thread(T6, 7, NOW - 600)
    thread(T7, 8, NOW - 90_000)
    thread(T8, 4, NOW - 5000)
    with _db(home / "state_5.sqlite") as conn:
        schema = tuple(c for c in THREADS_SCHEMA if c[0] not in omit_thread_columns)
        _create(conn, "threads", schema, ("zz_future",))
        for row in threads:
            _insert(conn, "threads", row)
        _create(conn, "thread_spawn_edges", EDGES_SCHEMA)
        _insert(
            conn,
            "thread_spawn_edges",
            {"parent_thread_id": T1, "child_thread_id": T2, "status": "closed"},
        )
        conn.commit()

    def item(
        thread_id: str, ordinal: int, kind: str, body: Mapping[str, object]
    ) -> dict[str, object]:
        return {
            "thread_id": thread_id,
            "turn_id": f"turn-{ordinal}",
            "item_id": f"item-{thread_id[-2:]}-{ordinal}",
            "rollout_ordinal": ordinal,
            "created_at_ms": int((T0 + 100 + ordinal) * 1000),
            "item_json": json.dumps({"type": kind, **body}),
            "item_type": kind,
            "zz_new_col": "x",
        }

    def turn(
        thread_id: str, ordinal: int, status: str, error: str | None = None
    ) -> dict[str, object]:
        return {
            "thread_id": thread_id,
            "turn_id": f"turn-{ordinal}",
            "rollout_ordinal": ordinal,
            "status": status,
            "error_json": error,
            "completed_at": None if status == "inProgress" else int(T0 + 200 + ordinal),
        }

    with _db(home / "thread_history_1.sqlite") as conn:
        _create(conn, "thread_turns", TURNS_SCHEMA)
        _create(conn, "thread_items", ITEMS_SCHEMA, ("zz_new_col",))
        _insert(conn, "thread_turns", turn(T1, 1, "completed"))
        _insert(conn, "thread_turns", turn(T1, 8, "failed", json.dumps({"message": "boom"})))
        for ordinal, kind, body in T1_ITEMS:
            _insert(conn, "thread_items", item(T1, ordinal, kind, body))
        _insert(conn, "thread_items", item(T2, 1, "agentMessage", {"text": "child reply"}))
        _insert(conn, "thread_turns", turn(T4, 1, "completed"))
        _insert(
            conn,
            "thread_items",
            item(T4, 1, "userMessage", {"content": [{"type": "text", "text": "seg one"}]}),
        )
        _insert(conn, "thread_items", item(T4, 2, "agentMessage", {"text": "seg one reply"}))
        _insert(conn, "thread_turns", turn(H4, 3, "completed"))
        _insert(conn, "thread_items", item(H4, 3, "agentMessage", {"text": "seg two"}))
        _insert(
            conn,
            "thread_items",
            item(H4, 4, "commandExecution", {"command": ["echo", "hi"], "exitCode": 1}),
        )
        _insert(conn, "thread_turns", turn(T7, 1, "inProgress"))
        conn.commit()

    (home / "sqlite").mkdir()
    with _db(home / "sqlite" / "codex.db") as conn:
        _create(conn, "active_chat_turns", ACTIVE_SCHEMA)
        _insert(
            conn, "active_chat_turns", {"thread_id": T6, "observed_at_ms": int((NOW - 20) * 1000)}
        )
        _insert(
            conn, "active_chat_turns", {"thread_id": T7, "observed_at_ms": int((NOW - 5000) * 1000)}
        )
        conn.commit()


def build(root: Path, *, omit_thread_columns: tuple[str, ...] = ()) -> SyntheticHomes:
    """Write both homes under *root* and return them.

    *omit_thread_columns* leaves columns out of ``threads``, to test missing-column drift.
    """

    claude = root / ".claude"
    codex = root / ".codex"
    claude.mkdir(parents=True)
    codex.mkdir(parents=True)
    _build_claude(claude)
    _build_codex(codex, omit_thread_columns)
    return SyntheticHomes(root, Home("claude", claude), Home("codex", codex))


if __name__ == "__main__":
    # `python tests/agents_synthetic_home.py DIR` writes both homes under DIR; the goldens'
    # `before` step uses it, so a golden serves the same homes the unit tests read.
    import sys

    build(Path(sys.argv[1]))
