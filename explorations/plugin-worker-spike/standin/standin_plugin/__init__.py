"""A stand-in for a packaged plugin: an entry point, data hooks, and two log adapters.

It imports only the documented ``metabrowser`` names and has no other dependency, so the
probes can install it offline (``probes.py`` writes its metadata by hand) and run it in a
worker whose only ``metabrowser`` is the runtime the host injects. It stands in for the
downstream plugins the research measured, which are not public; nothing here says what
those cost.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metabrowser import LogEvent, register_log_adapter, register_root_callback

ROOT_BINDINGS: list[str] = []
register_root_callback(lambda: ROOT_BINDINGS.append("bound"))


class LineParser:
    """One event per line, which is enough to price the transport around a parse."""

    def __init__(self, name: str) -> None:
        self.adapter_name = name

    def parse_line(self, line: str) -> list[LogEvent]:
        return [LogEvent(kind="line", summary=line[:40], adapter=self.adapter_name, raw=line)]

    def flush(self) -> list[LogEvent]:
        return []


def _is_pool(event: dict[str, Any]) -> bool:
    return event.get("event") == "pool_start"


def _is_process(event: dict[str, Any]) -> bool:
    return event.get("event") in ("run_start", "step_start")


register_log_adapter("pool", detector=_is_pool, parser_factory=lambda: LineParser("pool"))
register_log_adapter("process", detector=_is_process, parser_factory=lambda: LineParser("process"))


def plugin_dir() -> str:
    return str(Path(__file__).parent / "plugin")
