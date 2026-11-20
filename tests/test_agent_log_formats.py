"""Claude Code session transcripts and Codex rollouts are recognized and parsed.

The fixtures in ``tests/fixtures/agent-logs`` are synthetic, built from the record shapes
the agent-home research brief surveyed; real agent homes hold private data. The golden
``cli-api-agent-logs.tryscript.md`` pins their kind, views, and chart counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metabrowser.file_kinds import classify_file_kind
from metabrowser.logutil.parsing import LogEvent, create_parser, detect_adapter

FIXTURES = Path(__file__).parent / "fixtures" / "agent-logs"


def _lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text().splitlines()


def _parse(adapter: str, records: list[dict[str, Any]]) -> list[LogEvent]:
    parser = create_parser(adapter)
    events: list[LogEvent] = []
    for record in records:
        events.extend(parser.parse_line(json.dumps(record)))
    return events


def _summaries(events: list[LogEvent]) -> list[str]:
    return [event.summary for event in events]


def test_a_transcript_whose_first_assistant_record_is_past_line_20_is_claude() -> None:
    lines = _lines("claude-transcript.jsonl")
    first_types = [json.loads(line)["type"] for line in lines[:20]]
    assert "assistant" not in first_types, "the fixture must reproduce the late assistant record"

    assert detect_adapter(lines[:20]) == "claude"


def test_one_transcript_record_of_any_listed_type_is_enough() -> None:
    sid = "5e551011-0000-4000-8000-000000000001"
    assert detect_adapter([json.dumps({"type": "custom-title", "sessionId": sid})]) == "claude"
    conversation = {"type": "attachment", "sessionId": sid, "uuid": "u1", "parentUuid": None}
    assert detect_adapter([json.dumps(conversation)]) == "claude"


def test_records_without_the_transcript_envelope_are_not_claude() -> None:
    # The snake_case ``session_id`` of the stream-json format and of other agents does
    # not make a transcript, and a conversation type needs its uuid envelope.
    assert detect_adapter([json.dumps({"type": "custom-title", "session_id": "s"})]) == "unknown"
    assert detect_adapter([json.dumps({"type": "user", "sessionId": "s"})]) == "unknown"
    assert detect_adapter([json.dumps({"type": "queue-operation"})]) == "unknown"


def test_transcript_records_without_conversation_are_one_compact_line() -> None:
    sid = "s"
    envelope = {"sessionId": sid, "uuid": "u", "parentUuid": None}
    events = _parse(
        "claude",
        [
            {"type": "queue-operation", "operation": "enqueue", "sessionId": sid},
            {"type": "attachment", **envelope, "attachment": {"type": "hook_success"}},
            {"type": "api-request-blob", "sessionId": sid, "message": {"system": "x" * 5000}},
            {"type": "system", "subtype": "api_error", **envelope, "content": "overloaded"},
            {
                "type": "user",
                **envelope,
                "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            },
        ],
    )

    assert _summaries(events) == [
        "[queue:enqueue]",
        "[attachment:hook_success]",
        "[api-request-blob]",
        "[system:api_error] overloaded",
        "[user] Hello",
    ]
    assert [event.kind for event in events] == ["system"] * 4 + ["text"]
    assert [event.is_error for event in events] == [False, False, False, True, False]


def test_a_typed_rollout_is_codex_rollout_and_the_exec_stream_stays_codex() -> None:
    assert detect_adapter(_lines("codex-rollout.jsonl")[:20]) == "codex-rollout"
    # The envelope needs a payload mapping, so a bare event of the same name is not one.
    assert detect_adapter([json.dumps({"type": "event_msg"})]) == "unknown"
    stream = json.dumps({"type": "thread.started", "thread_id": "abc"})
    assert detect_adapter([stream]) == "codex"


def test_rollout_fixture_parses_to_the_conversation_without_repeats() -> None:
    lines = _lines("codex-rollout.jsonl")
    parser = create_parser("codex-rollout")
    events = [event for line in lines for event in parser.parse_line(line)]

    assert [(event.kind, event.summary) for event in events] == [
        ("init", "[init] thread=019e0000 cli=0.166.0 originator=codex_cli_rs"),
        ("system", "[world_state]"),
        ("system", "[turn.started]"),
        ("system", "[turn_context] model=gpt-demo effort=medium"),
        ("system", "[developer]"),
        ("text", "[user] Count the files"),
        ("thinking", "[thinking] List the folder."),
        ("tool_call", "[call:exec] const r = await run('ls'); return r;"),
        ("tool_call", "[call:command] ls exit=0"),
        ("tool_call", "[call:command] cat missing exit=1"),
        ("tool_result", "[result] a b c"),
        ("tool_call", "[call:spawn_agent] prompt=Check the count"),
        ("tool_result", "[result] agent started"),
        ("tool_call", "[call:file_change] /work/demo/notes.md"),
        ("tool_call", "[call:mcp:docs.search]"),
        ("system", "[subagent:started]"),
        ("usage", "[usage] input=1200 output=80 cached=1000 reasoning=30"),
        ("text", "[text] There are 3 files."),
        ("result", "[result] DONE duration=8s first_token=900ms"),
        ("system", "[turn.started]"),
        ("result", "[result] ABORTED interrupted"),
    ]
    failed = [event.summary for event in events if event.is_error]
    assert failed == ["[call:command] cat missing exit=1", "[result] ABORTED interrupted"]
    assert all(event.is_done for event in events if event.kind == "result")
    assert events[8].duration_s == 0.25


def test_a_rollout_without_usage_records_shows_token_count_usage() -> None:
    # Rollouts written before ``token_usage_record`` meter only through ``token_count``.
    usage = {"input_tokens": 5, "output_tokens": 6, "cached_input_tokens": 1}
    record = {
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"last_token_usage": usage}},
    }
    events = _parse("codex-rollout", [record, record])

    assert _summaries(events) == ["[usage] input=5 output=6 cached=1 reasoning=0"] * 2


def test_both_codex_adapters_classify_as_agent_logs(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    for adapter in ("codex", "codex-rollout"):
        assert classify_file_kind(path, ".jsonl", adapter) == "agent-log"
