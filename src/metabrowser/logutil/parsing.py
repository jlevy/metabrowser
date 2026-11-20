"""Core log-event model and the JSONL adapter registry.

Provides:
  LogEvent         — normalized event dataclass
  LogParser        — per-adapter parser protocol
  register_log_adapter, registered_log_adapters — the adapter registry
  detect_adapter   — auto-detect an adapter from the first JSON lines
  create_parser    — a fresh parser for a registered adapter name

Core registers no adapter. The coding-agent adapters (Claude Code, Codex, Pi, Gemini)
belong to the built-in ``agents`` plugin, which registers them when it is loaded; a
log no registered adapter recognizes gets :class:`GenericLogParser`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast, runtime_checkable

log = logging.getLogger(__name__)


# ── Normalized event ─────────────────────────────────────────────


@dataclass
class LogEvent:
    """A normalized log event from any adapter."""

    kind: str  # "init", "tool_call", "tool_result", "text", "thinking", "rate_limit", "result", "system", "raw"
    summary: str  # compact one-liner for display
    adapter: str = "unknown"  # "claude", "codex", "codex-rollout", "gemini", "pi", "unknown"
    provider: str | None = (
        None  # "anthropic", "vertex-maas", "openai", etc. — set on rate_limit events
    )
    timestamp: str | None = None
    is_error: bool = False
    is_done: bool = False  # True for result events (DONE or FAIL)
    cost_usd: float | None = None
    duration_s: float | None = None
    raw: dict[str, Any] | str = field(default_factory=dict)
    summary_parts: list[dict[str, Any]] | None = (
        None  # structured [{type, text}] for rich rendering
    )


# ── Parser protocol ──────────────────────────────────────────────


@runtime_checkable
class LogParser(Protocol):
    adapter_name: str

    def parse_line(self, line: str) -> list[LogEvent]:
        """Parse a raw line, return zero or more LogEvents."""
        ...

    def flush(self) -> list[LogEvent]:
        """Flush any buffered state (e.g. pending Gemini deltas)."""
        ...


AdapterDetector = Callable[[dict[str, Any]], bool]
LineDetector = Callable[[str], bool]
LogParserFactory = Callable[[], LogParser]


@dataclass(frozen=True)
class _AdapterRegistration:
    detector: AdapterDetector
    parser_factory: LogParserFactory
    line_detector: LineDetector | None = None


# Every JSONL adapter, core and plugin alike, in registration order. Detection asks
# each line's detectors in this order, so core's adapters, registered at import, are
# asked before a plugin's; each detector recognizes only its own format.
_ADAPTERS: dict[str, _AdapterRegistration] = {}


def register_log_adapter(
    name: str,
    *,
    detector: AdapterDetector,
    parser_factory: LogParserFactory,
    line_detector: LineDetector | None = None,
) -> None:
    """Register a JSONL adapter.

    The detector receives a parsed JSON object from the first non-empty lines, and
    the optional line detector receives each of those lines that is not a JSON
    object, for a format whose stream opens with plain text. The parser factory must
    return a fresh ``LogParser`` for each stream. Registering the same callables
    again is a no-op; claiming a name already registered raises ``ValueError``.
    """
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("adapter name must not be empty")
    registration = _AdapterRegistration(detector, parser_factory, line_detector)
    existing = _ADAPTERS.get(normalized)
    if existing == registration:
        return
    if existing is not None:
        raise ValueError(f"adapter already registered: {normalized}")
    _ADAPTERS[normalized] = registration


def registered_log_adapters() -> tuple[str, ...]:
    """Return the registered adapter names, in detection order."""
    return tuple(_ADAPTERS)


# ── Helpers ──────────────────────────────────────────────────────


def _parse_json(line: str) -> dict[str, Any] | None:
    """Try to parse a line as JSON. Returns None on failure."""
    try:
        obj: Any = json.loads(line)
        if isinstance(obj, dict):
            return cast(dict[str, Any], obj)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def detect_adapter(lines: list[str]) -> str:
    """Detect adapter type from the first few lines of a JSONL file.

    Returns a registered adapter's name, or ``"unknown"``.
    """
    for line in lines[:20]:
        event = _parse_json(line)
        for name, registration in _ADAPTERS.items():
            try:
                if event is None:
                    matched = registration.line_detector is not None and registration.line_detector(
                        line
                    )
                else:
                    matched = registration.detector(event)
            except Exception:
                log.exception("log adapter detector %r failed", name)
                continue
            if matched:
                return name
    return "unknown"


class GenericLogParser:
    """The parser for a log no registered adapter recognizes (adapter ``unknown``).

    Each JSON object becomes one event: its kind is its ``type`` (``unknown`` when it has
    none), its summary the type and the object, and its raw payload the object itself.
    A line that is not a JSON object becomes a ``raw`` event.
    """

    adapter_name: str = "unknown"

    def parse_line(self, line: str) -> list[LogEvent]:
        event = _parse_json(line)
        if event is None:
            return [
                LogEvent(
                    kind="raw",
                    summary=f"[raw] {line.strip()}",
                    adapter=self.adapter_name,
                    raw=line,
                )
            ]
        etype = str(event.get("type", "unknown"))
        return [
            LogEvent(
                kind=etype,
                adapter=self.adapter_name,
                timestamp=event.get("timestamp") or event.get("uuid"),
                summary=f"[{etype}] {event!s}",
                raw=event,
            )
        ]

    def flush(self) -> list[LogEvent]:
        return []


def create_parser(adapter: str) -> LogParser:
    """Create a parser for a registered adapter; any other name gets the generic parser."""
    registered = _ADAPTERS.get(adapter)
    if registered is not None:
        return registered.parser_factory()
    return GenericLogParser()
