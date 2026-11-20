"""Contracts for plugin-owned JSONL adapter registration."""

from __future__ import annotations

import json
from typing import Any

import pytest

from metabrowser.logutil import parsing
from metabrowser.logutil.parsing import (
    LogEvent,
    create_parser,
    detect_adapter,
    register_log_adapter,
    registered_log_adapters,
)


@pytest.fixture(autouse=True)
def _registered_adapters_stay_in_one_test(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Register into a copy of the adapter table, dropped when the test ends.

    The table is a process global with no way to take a registration back. An adapter
    left in it is asked about every JSONL file read afterwards, and the one whose
    detector raises logged a traceback each time.
    """

    monkeypatch.setattr(parsing, "_ADAPTERS", dict(parsing._ADAPTERS))


class _FixtureParser:
    adapter_name = "fixture"

    def parse_line(self, line: str) -> list[LogEvent]:
        return [LogEvent(kind="system", summary=line, adapter=self.adapter_name)]

    def flush(self) -> list[LogEvent]:
        return []


def _is_fixture(event: dict[str, Any]) -> bool:
    return event.get("fixture_event") is True


def test_plugin_adapter_detection_and_parser_factory() -> None:
    register_log_adapter(
        "fixture",
        detector=_is_fixture,
        parser_factory=_FixtureParser,
    )

    assert detect_adapter([json.dumps({"fixture_event": True})]) == "fixture"
    parser = create_parser("fixture")
    assert parser.adapter_name == "fixture"
    assert parser.parse_line("payload")[0].summary == "payload"


def test_core_adapters_register_through_the_same_registry() -> None:
    """Core holds no reserved names: its adapters are ordinary registrations."""
    assert registered_log_adapters()[:5] == ("claude", "codex-rollout", "codex", "pi", "gemini")


def test_a_registered_name_cannot_be_claimed_again() -> None:
    with pytest.raises(ValueError, match="adapter already registered: claude"):
        register_log_adapter(
            "claude",
            detector=_is_fixture,
            parser_factory=_FixtureParser,
        )


def test_plugin_adapter_registration_is_idempotent_but_rejects_collisions() -> None:
    register_log_adapter(
        "fixture",
        detector=_is_fixture,
        parser_factory=_FixtureParser,
    )

    with pytest.raises(ValueError, match="adapter already registered"):
        register_log_adapter(
            "fixture",
            detector=lambda _event: False,
            parser_factory=_FixtureParser,
        )


def test_failing_plugin_detector_does_not_break_other_jsonl_detection() -> None:
    def detector_raises(_event: dict[str, Any]) -> bool:
        raise RuntimeError("detector failed")

    register_log_adapter(
        "failing-fixture",
        detector=detector_raises,
        parser_factory=_FixtureParser,
    )

    assert detect_adapter([json.dumps({"unrecognized": True})]) == "unknown"


def test_a_line_detector_recognizes_a_plain_text_preamble() -> None:
    register_log_adapter(
        "fixture",
        detector=_is_fixture,
        parser_factory=_FixtureParser,
        line_detector=lambda line: line.startswith("FIXTURE BANNER"),
    )

    assert detect_adapter(["FIXTURE BANNER v1", json.dumps({"other": 1})]) == "fixture"
    assert detect_adapter(["some other banner"]) == "unknown"


def test_core_detectors_run_before_a_plugin_registered_later() -> None:
    """Detection order is registration order, and core registers at import."""
    register_log_adapter(
        "greedy-fixture",
        detector=lambda _event: True,
        parser_factory=_FixtureParser,
    )
    codex_exec = json.dumps({"type": "thread.started", "thread_id": "t"})

    assert detect_adapter([codex_exec]) == "codex"
    assert detect_adapter([json.dumps({"unrecognized": True})]) == "greedy-fixture"
