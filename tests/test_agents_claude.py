"""The Claude Code provider against the synthetic home, with hand-computed expectations."""

from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.agents import claude
from metabrowser.builtin_plugins.agents.model import (
    Home,
    SessionSummary,
    apply_live,
    default_pid_probe,
)
from tests import agents_synthetic_home as syn


@pytest.fixture
def home(tmp_path: Path) -> Home:
    return syn.build(tmp_path).claude


def _by_id(home: Home) -> dict[str, SessionSummary]:
    return {s.session_id: s for s in claude.discover(home)}


def test_discover_lists_every_transcript_newest_first(home: Home) -> None:
    sessions = claude.discover(home)
    assert [s.session_id for s in sessions] == [
        syn.S2,
        syn.S1,
        syn.AGENT_B,
        syn.AGENT_A,
        syn.S3,
    ]
    assert all(s.status == "unknown" and s.records is None for s in sessions)


def test_discover_fast_pass_reads_edges_only(home: Home) -> None:
    s1 = _by_id(home)[syn.S1]
    assert s1.title == "Synthetic session"
    assert (s1.cwd, s1.git_branch) == ("/work/alpha", "main")
    # Lines 1 and 2 are resumed history, so the session starts at line 3.
    assert s1.started_at == syn.T0
    assert s1.ended_at == syn.T0 + 31
    assert s1.last_activity == syn.T0 + 40
    assert s1.size_bytes == (home.path / "projects/-work-alpha" / f"{syn.S1}.jsonl").stat().st_size
    assert s1.child_ids == (syn.AGENT_A,)
    assert s1.parent_id is None


def test_subagents_are_children_and_nested_spawns_link_by_parent_agent(home: Home) -> None:
    found = _by_id(home)
    a, b = found[syn.AGENT_A], found[syn.AGENT_B]
    assert (a.parent_id, a.origin, a.title, a.models) == (
        syn.S1,
        "subagent",
        "Explore code",
        ("claude-sub-1",),
    )
    assert a.child_ids == (syn.AGENT_B,)
    assert b.parent_id == syn.AGENT_A


def test_compressed_transcript_is_listed_from_stat_only(home: Home) -> None:
    s3 = _by_id(home)[syn.S3]
    assert s3.size_bytes == 100
    assert (s3.cwd, s3.started_at, s3.title) == (None, None, None)
    assert claude.summarize(home, s3) == (s3, claude.summarize(home, s3)[1])
    assert list(claude.stream(home, syn.S3)) == []


def test_summarize_main_session(home: Home) -> None:
    summary, drift = claude.summarize(home, _by_id(home)[syn.S1])
    assert summary.records == 17
    assert summary.replayed_records == 2
    assert summary.turns == 2  # lines 5 and 16; the tool result is not a prompt
    assert summary.models == ("claude-test-1", "claude-test-2")
    assert (summary.started_at, summary.ended_at) == (syn.T0, syn.T0 + 31)
    assert summary.status == "finished"
    assert summary.origin == "human"
    assert summary.family_versions == {"drift": 1, "session": 1}
    assert drift.unknown_types == {"never-seen-type": 1, "assistant/hologram": 1}
    assert not drift.truncated


def test_summarize_scheduled_session_that_ends_in_an_error(home: Home) -> None:
    summary, _ = claude.summarize(home, _by_id(home)[syn.S2])
    assert (summary.origin, summary.status, summary.turns) == ("scheduled", "failed", 1)
    assert (summary.cwd, summary.git_branch) == ("/work/beta", "dev")
    assert summary.models == ()  # the only model is `<synthetic>`


def test_summarize_subagent_is_exempt_from_replay(home: Home) -> None:
    summary, _ = claude.summarize(home, _by_id(home)[syn.AGENT_A])
    # Its records carry the parent's sessionId by design.
    assert (summary.records, summary.replayed_records, summary.turns) == (2, 0, 1)
    assert summary.origin == "subagent"
    assert summary.status == "finished"


def test_stream_covers_every_kind_and_marks_replays(home: Home) -> None:
    events = list(claude.stream(home, syn.S1))
    assert len(events) == 24
    assert sum(e.replay for e in events) == 3
    own = Counter(e.kind for e in events if not e.replay)
    assert own == {
        "prompt": 3,
        "text": 1,
        "thinking": 1,
        "tool-call": 3,
        "tool-result": 1,
        "metering": 3,
        "control": 2,
        "context": 4,
        "error": 1,
        "unknown": 2,
    }
    assert len({e.locator for e in events}) == 24
    assert [e.ordinal for e in events][:3] == [1, 2, 2]


def test_stream_names_tools_and_families(home: Home) -> None:
    calls = [e for e in claude.stream(home, syn.S1) if e.kind in ("tool-call", "tool-result")]
    assert [(e.kind, e.tool_name, e.tool_family) for e in calls] == [
        ("tool-call", "Bash", "shell"),
        ("tool-result", "Bash", "shell"),
        ("tool-call", "Task", "subagent"),
        ("tool-call", "mcp:srv.lookup", "mcp"),
    ]
    assert calls[0].summary == "Bash: ls"


def test_stream_of_unknown_session_is_empty(home: Home) -> None:
    assert list(claude.stream(home, "nope")) == []


def test_live_believes_only_a_pid_the_probe_vouches_for(home: Home) -> None:
    seen: list[int] = []

    def probe(pid: int, proc_start: str | None) -> bool:
        seen.append(pid)
        return pid == syn.PID_LIVE

    result = claude.live(home, syn.NOW, probe)
    assert [(s.session_id, s.pid, s.status, s.source) for s in result] == [
        (syn.S1, syn.PID_LIVE, "busy", "pid-file")
    ]
    assert sorted(seen) == [syn.PID_LIVE, syn.PID_STALE]  # the garbage file is skipped
    assert result[0].updated_at == syn.NOW - 5
    assert claude.live(home, syn.NOW, lambda pid, start: False) == []


def test_apply_live_marks_only_vouched_sessions(home: Home) -> None:
    live = claude.live(home, syn.NOW, lambda pid, start: pid == syn.PID_LIVE)
    marked = {s.session_id: s.status for s in apply_live(claude.discover(home), live)}
    assert marked[syn.S1] == "running"
    assert marked[syn.S2] == "unknown"  # a stale pid file is not proof


def _own_proc_start() -> str:
    result = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(os.getpid())],
        capture_output=True,
        text=True,
        env={**os.environ, "TZ": "UTC"},
        check=True,
    )
    return result.stdout.strip()


def test_default_probe_needs_a_matching_process_start() -> None:
    assert default_pid_probe(os.getpid(), _own_proc_start())
    assert not default_pid_probe(os.getpid(), "Mon Jan  1 00:00:00 1990")
    assert not default_pid_probe(0, "x")
    assert not default_pid_probe(2**22 + 12345, _own_proc_start())


def test_default_probe_never_proves_liveness_without_a_start_time() -> None:
    assert not default_pid_probe(os.getpid(), None)
    assert not default_pid_probe(os.getpid(), "")


def test_default_probe_rejects_out_of_range_pids() -> None:
    for pid in (2**31, 2**63, 10**30):
        assert not default_pid_probe(pid, "x")


def test_default_probe_is_false_when_ps_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    start = _own_proc_start()

    def broken(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("ps")

    monkeypatch.setattr(subprocess, "run", broken)
    assert not default_pid_probe(os.getpid(), start)

    def nonzero(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, stdout=start, stderr="")

    monkeypatch.setattr(subprocess, "run", nonzero)
    assert not default_pid_probe(os.getpid(), start)

    def empty(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", empty)
    assert not default_pid_probe(os.getpid(), start)


def test_live_with_the_default_probe_ignores_a_pid_file_without_a_start_time(
    tmp_path: Path,
) -> None:
    home = Home("claude", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "1.json").write_text(
        json.dumps({"pid": os.getpid(), "sessionId": "s"}), encoding="utf-8"
    )
    assert claude.live(home, syn.NOW) == []


def test_a_replayed_title_does_not_override_the_sessions_own(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "-p"
    project.mkdir(parents=True)
    lines = [
        {"type": "custom-title", "sessionId": "own", "customTitle": "Mine"},
        {"type": "custom-title", "sessionId": "other", "customTitle": "Copied"},
        {"type": "user", "sessionId": "own", "message": {"content": "hi"}},
    ]
    (project / "own.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8"
    )
    home = Home("claude", tmp_path)
    summary, _ = claude.summarize(home, claude.discover(home)[0])
    assert (summary.title, summary.replayed_records) == ("Mine", 1)


def test_empty_home_has_nothing(tmp_path: Path) -> None:
    empty = Home("claude", tmp_path / "missing")
    assert claude.discover(empty) == []
    assert claude.live(empty, syn.NOW) == []


def test_to_json_is_plain_and_ordered(home: Home) -> None:
    summary, drift = claude.summarize(home, _by_id(home)[syn.S1])
    data = summary.to_json()
    assert list(data)[:4] == ["agent", "session_id", "title", "parent_id"]
    assert json.loads(json.dumps(data)) == data
    assert json.loads(json.dumps(drift.to_json())) == drift.to_json()
    event = next(iter(claude.stream(home, syn.S1)))
    assert list(event.to_json())[:3] == ["session_id", "ordinal", "locator"]
