"""The Codex provider against the synthetic home, with hand-computed expectations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.agents import codex
from metabrowser.builtin_plugins.agents.model import (
    DriftCollector,
    Home,
    SessionSummary,
    apply_live,
)
from tests import agents_synthetic_home as syn


@pytest.fixture
def home(tmp_path: Path) -> Home:
    return syn.build(tmp_path).codex


def _by_id(home: Home) -> dict[str, SessionSummary]:
    return {s.session_id: s for s in codex.discover(home)}


def test_discover_lists_threads_newest_first_with_origin(home: Home) -> None:
    sessions = codex.discover(home)
    assert [s.session_id for s in sessions] == [
        syn.T5,
        syn.T6,
        syn.T4,
        syn.T3,
        syn.T2,
        syn.T1,
        syn.T8,
        syn.T7,
    ]
    origins = {s.session_id: s.origin for s in sessions}
    assert origins[syn.T2] == "subagent"  # a spawn edge makes it a child
    assert origins[syn.T3] == "review"
    assert origins[syn.T1] == "human"


def test_discover_tree_title_time_and_size(home: Home) -> None:
    found = _by_id(home)
    t1, t2 = found[syn.T1], found[syn.T2]
    assert t2.parent_id == syn.T1
    assert t1.child_ids == (syn.T2,)
    assert t1.title == "Gamma thread"  # the name wins over the title
    assert found[syn.T4].title == "title 4"
    assert t1.last_activity == syn.NOW - 3600
    assert t1.started_at == syn.NOW - 3600 - 600
    assert (t1.cwd, t1.git_branch, t1.models) == ("/work/gamma", "main", ("gpt-test-1",))
    assert t1.size_bytes == 40
    assert found[syn.T4].size_bytes == 50 + 70  # both segments
    assert found[syn.T2].size_bytes == 0
    assert all(s.status == "unknown" and s.records is None for s in found.values())


def test_summarize_failed_thread(home: Home) -> None:
    summary, drift = codex.summarize(home, _by_id(home)[syn.T1])
    assert summary.records == 11
    assert summary.turns == 2
    assert summary.status == "failed"  # the last turn carries an error
    assert summary.family_versions == {"drift": 1, "session": 1}
    assert drift.unknown_types == {"thread_item/holographicThing": 1}


def test_drift_names_the_unexpected_columns(home: Home) -> None:
    _, drift = codex.summarize(home, _by_id(home)[syn.T1])
    assert drift.unexpected_columns == {
        "state.threads.zz_future": 1,
        "history.thread_items.zz_new_col": 1,
    }
    assert drift.missing_columns == {}
    assert codex.schema_drift(home).unexpected_columns == drift.unexpected_columns


def test_drift_names_a_missing_column(tmp_path: Path) -> None:
    built = syn.build(tmp_path, omit_thread_columns=("git_branch",))
    assert codex.schema_drift(built.codex).missing_columns == {"state.threads.git_branch": 1}
    # Discovery still works; the branch is just absent.
    assert {s.git_branch for s in codex.discover(built.codex)} == {None}


def test_stream_history_covers_items_and_merges_the_turn_error(home: Home) -> None:
    events = list(codex.stream(home, syn.T1))
    assert [e.ordinal for e in events] == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    assert Counter(e.kind for e in events) == {
        "prompt": 1,
        "thinking": 1,
        "text": 1,
        "tool-call": 5,
        "context": 1,
        "unknown": 1,
        "error": 2,
    }
    error = events[6]
    assert (error.raw_type, error.raw_subtype, error.kind) == ("thread_turn", "error", "error")
    tools = [(e.tool_name, e.tool_family) for e in events if e.kind == "tool-call"]
    assert tools == [
        ("commandExecution", "shell"),
        ("mcp:srv.lookup", "mcp"),
        ("fileChange", "edit"),
        ("webSearch", "web"),
        ("collabAgentToolCall", "subagent"),
    ]
    assert events[3].summary == "ls -l (exit 0)"
    assert events[0].summary == "hello codex"
    assert events[0].timestamp == syn.T0 + 102


def test_a_second_segment_is_read_under_its_history_id(home: Home) -> None:
    t4 = _by_id(home)[syn.T4]
    assert codex._history_ids(syn.T4, t4.source_paths) == [syn.T4, syn.H4]  # pyright: ignore[reportPrivateUsage]
    events = list(codex.stream(home, syn.T4))
    assert [(e.ordinal, e.kind) for e in events] == [
        (1, "prompt"),
        (2, "text"),
        (3, "text"),
        (4, "tool-call"),
    ]
    assert events[3].summary == "echo hi (exit 1)"
    summary, _ = codex.summarize(home, t4)
    assert (summary.records, summary.turns, summary.status) == (4, 2, "finished")


def test_orphaned_in_progress_turn_is_not_running(home: Home) -> None:
    summary, _ = codex.summarize(home, _by_id(home)[syn.T7])
    assert (summary.turns, summary.status) == (1, "unknown")
    assert syn.T7 not in {s.session_id for s in codex.live(home, syn.NOW)}


def test_plain_rollout_is_read_when_history_has_no_rows(home: Home) -> None:
    t8 = _by_id(home)[syn.T8]
    events = list(codex.stream(home, syn.T8))
    assert len(events) == 21  # the `event_msg` copy of line 22 is not counted
    assert Counter(e.kind for e in events) == {
        "context": 6,
        "prompt": 2,
        "thinking": 1,
        "tool-call": 2,
        "tool-result": 2,
        "text": 1,
        "metering": 2,
        "control": 1,
        "error": 2,
        "unknown": 2,
    }
    by_ordinal = {e.ordinal: e for e in events}
    assert (by_ordinal[8].tool_name, by_ordinal[8].tool_family) == ("exec_command", "shell")
    assert (by_ordinal[13].tool_name, by_ordinal[13].tool_family) == ("mcp:srv.lookup", "mcp")
    assert (by_ordinal[19].tool_name, by_ordinal[19].tool_family) == ("apply_patch", "edit")
    summary, drift = codex.summarize(home, t8)
    assert (summary.records, summary.turns, summary.status) == (21, 0, "unknown")
    assert drift.unknown_types == {
        "<invalid-json>": 1,
        "event_msg/novel_event": 1,
        "novel_record": 1,
    }


def test_live_comes_from_active_turns_and_recent_updates_only(home: Home) -> None:
    result = codex.live(home, syn.NOW)
    assert [(s.session_id, s.source, s.status) for s in result] == [
        (syn.T6, "active-chat-turn", "busy"),
        (syn.T5, "recent-update", "idle"),
    ]
    assert result[0].name == "title 6"
    assert result[0].cwd == "/work/gamma"
    assert result[0].updated_at == syn.NOW - 20
    # Time passes: the active row goes stale and nothing is recent.
    assert codex.live(home, syn.NOW + 600) == []


def test_apply_live_leaves_orphans_unmarked(home: Home) -> None:
    marked = {
        s.session_id: s.status for s in apply_live(codex.discover(home), codex.live(home, syn.NOW))
    }
    assert marked[syn.T6] == marked[syn.T5] == "running"
    assert marked[syn.T7] == "unknown"


def test_databases_are_opened_read_only(home: Home) -> None:
    def digest() -> dict[str, str]:
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(home.path.rglob("*"))
            if p.is_file() and p.suffix in (".sqlite", ".db")
        }

    before = digest()
    names = {p.name for p in home.path.rglob("*")}
    codex.discover(home)
    codex.summarize(home, _by_id(home)[syn.T1])
    list(codex.stream(home, syn.T4))
    codex.live(home, syn.NOW)
    assert digest() == before
    assert {p.name for p in home.path.rglob("*")} == names  # no journal or wal appeared


def test_empty_home_has_nothing(tmp_path: Path) -> None:
    empty = Home("codex", tmp_path / "missing")
    assert codex.discover(empty) == []
    assert codex.live(empty, syn.NOW) == []
    assert list(codex.stream(empty, syn.T1)) == []
    assert codex.schema_drift(empty).is_clean


def test_to_json_is_plain_and_ordered(home: Home) -> None:
    summary, drift = codex.summarize(home, _by_id(home)[syn.T1])
    for value in (summary.to_json(), drift.to_json(), codex.live(home, syn.NOW)[0].to_json()):
        assert json.loads(json.dumps(value)) == value
    assert list(summary.to_json())[-3:] == ["status", "source_paths", "family_versions"]


def _names(home: Home) -> set[str]:
    return {p.name for p in home.path.rglob("*")}


def test_the_synthetic_databases_are_wal_like_the_real_ones(home: Home) -> None:
    for name in ("state_5.sqlite", "thread_history_1.sqlite", "sqlite/codex.db"):
        header = (home.path / name).read_bytes()[:20]
        assert header[18:20] == b"\x02\x02", name  # file format write/read version 2 = WAL


def test_reading_an_idle_wal_database_creates_no_file(home: Home) -> None:
    before = _names(home)
    assert not any(n.endswith(("-wal", "-shm")) for n in before)
    codex.discover(home)
    list(codex.stream(home, syn.T4))
    codex.live(home, syn.NOW)
    assert _names(home) == before


def test_reading_beside_a_live_writer_sees_its_commits_and_adds_nothing(home: Home) -> None:
    writer = sqlite3.connect(home.path / "thread_history_1.sqlite")
    try:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute(
            "INSERT INTO thread_items (thread_id, rollout_ordinal, created_at_ms, item_json, "
            "item_type) VALUES (?, 2, 1, '{\"text\": \"live\"}', 'agentMessage')",
            (syn.T2,),
        )
        writer.commit()
        before = _names(home)
        assert "thread_history_1.sqlite-wal" in before  # the writer's, not ours
        events = list(codex.stream(home, syn.T2))
        assert [e.summary for e in events] == ["child reply", "live"]
        assert _names(home) == before
    finally:
        writer.close()


def test_an_undecodable_text_value_does_not_fail_the_stream(home: Home) -> None:
    with closing(sqlite3.connect(home.path / "thread_history_1.sqlite")) as conn:
        conn.execute(
            "INSERT INTO thread_items (thread_id, rollout_ordinal, created_at_ms, item_json, "
            "item_type) VALUES (?, 2, 1, CAST(x'ff7b7d' AS TEXT), 'agentMessage')",
            (syn.T2,),
        )
        conn.commit()
    events = list(codex.stream(home, syn.T2))
    assert [e.kind for e in events] == ["text", "text"]
    assert events[1].summary == ""


def test_a_failed_catalog_read_is_drift_not_an_empty_catalog(tmp_path: Path) -> None:
    root = tmp_path / "home"
    root.mkdir()
    (root / "state_5.sqlite").write_bytes(b"this is not a database" * 100)
    drift = DriftCollector()
    assert codex.discover(Home("codex", root), drift=drift) == []
    frozen = drift.freeze()
    assert frozen.read_errors == {"state.threads": 1}
    assert frozen.truncated


class _FailingItems:
    """A connection whose `thread_items` read fails after the schema checks."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        if "FROM thread_items" in sql:
            raise sqlite3.OperationalError("database is locked")
        return self._conn.execute(sql, *args)  # pyright: ignore[reportArgumentType]

    def close(self) -> None:
        self._conn.close()


def test_a_failing_item_read_is_drift_and_truncates_instead_of_raising(
    home: Home, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = codex.open_readonly
    monkeypatch.setattr(
        codex,
        "open_readonly",
        lambda path, drift=None: (
            _FailingItems(c) if (c := real(path, drift)) is not None else None  # pyright: ignore[reportReturnType]
        ),
    )
    # No item is read; only the turn error, which a separate query supplies, survives.
    assert [e.raw_type for e in codex.stream(home, syn.T1)] == ["thread_turn"]
    summary, drift = codex.summarize(home, _by_id(home)[syn.T1])
    assert summary.records == 0
    assert drift.read_errors["history.thread_items"] >= 1
    assert drift.truncated


def test_the_item_cap_is_per_thread_not_per_segment(
    home: Home, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codex, "MAX_ITEMS", 3)
    t4 = _by_id(home)[syn.T4]  # two items in each of two segments
    assert [e.ordinal for e in codex.stream(home, syn.T4)] == [1, 2, 3]
    summary, drift = codex.summarize(home, t4)
    assert summary.records == 3
    assert drift.truncated


def test_the_character_cap_stops_a_thread_by_size(
    home: Home, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codex, "MAX_THREAD_CHARS", 1)
    assert len(list(codex.stream(home, syn.T1))) < 11


def test_an_oversize_item_keeps_its_kind_but_not_its_body(
    home: Home, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(codex, "MAX_ITEM_CHARS", 10)
    events = list(codex.stream(home, syn.T1))
    assert events[0].kind == "prompt"
    assert events[0].summary == ""


def test_turns_are_ordered_by_segment_not_by_a_global_ordinal(home: Home) -> None:
    with closing(sqlite3.connect(home.path / "thread_history_1.sqlite")) as conn:
        # A first-segment turn whose ordinal is higher than the second segment's.
        conn.execute(
            "INSERT INTO thread_turns (thread_id, turn_id, rollout_ordinal, status) "
            "VALUES (?, 'late', 99, 'failed')",
            (syn.T4,),
        )
        conn.commit()
    summary, _ = codex.summarize(home, _by_id(home)[syn.T4])
    assert (summary.turns, summary.status) == (3, "finished")  # the last segment's turn wins


def test_live_ignores_an_active_row_from_the_future(home: Home) -> None:
    with closing(sqlite3.connect(home.path / "sqlite" / "codex.db")) as conn:
        conn.execute(
            "INSERT INTO active_chat_turns (thread_id, observed_at_ms) VALUES (?, ?)",
            (syn.T3, int((syn.NOW + 500) * 1000)),
        )
        conn.commit()
    assert syn.T3 not in {s.session_id for s in codex.live(home, syn.NOW)}


def test_live_reports_a_drifted_active_table(home: Home) -> None:
    with closing(sqlite3.connect(home.path / "sqlite" / "codex.db")) as conn:
        conn.execute("ALTER TABLE active_chat_turns ADD COLUMN zz_extra TEXT")
        conn.commit()
    drift = DriftCollector()
    assert codex.live(home, syn.NOW, drift)
    assert drift.freeze().unexpected_columns["desktop.active_chat_turns.zz_extra"] == 1


def test_live_works_without_the_millisecond_and_name_columns(tmp_path: Path) -> None:
    built = syn.build(tmp_path, omit_thread_columns=("updated_at_ms", "name"))
    assert [(s.session_id, s.source) for s in codex.live(built.codex, syn.NOW)] == [
        (syn.T6, "active-chat-turn"),
        (syn.T5, "recent-update"),
    ]


def test_a_message_written_twice_is_counted_once(home: Home) -> None:
    events = [e for e in codex.stream(home, syn.T8) if e.ordinal in (22, 23)]
    assert [(e.ordinal, e.raw_type, e.kind) for e in events] == [(22, "response_item", "prompt")]


def test_a_repeated_message_from_one_source_is_not_an_echo() -> None:
    echoes: dict[tuple[str, str], str] = {}
    payload: dict[str, object] = {"type": "user_message", "message": "ok"}
    assert not codex._is_echo(echoes, "event_msg", "user_message", payload)  # pyright: ignore[reportPrivateUsage]
    assert not codex._is_echo(echoes, "event_msg", "user_message", payload)  # pyright: ignore[reportPrivateUsage]
    other: dict[str, object] = {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "ok"}],
    }
    assert codex._is_echo(echoes, "response_item", "message", other)  # pyright: ignore[reportPrivateUsage]
