"""Contracts for plugin-owned JSONL adapter registration."""

from __future__ import annotations

import json
from typing import Any

import pytest

from metabrowser.logutil.parsing import (
    LogEvent,
    create_parser,
    detect_adapter,
    register_log_adapter,
)


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


def test_plugin_cannot_replace_builtin_adapter() -> None:
    with pytest.raises(ValueError, match="cannot replace built-in adapter"):
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
