"""Spike: the plugin-side runtime the host injects into a worker, importable as ``metabrowser``.

``host_runtime.py`` installs this file as ``metabrowser/__init__.py`` in a runtime folder,
beside verbatim copies of the host's ``gz_io.py`` and ``content_errors.py``, and puts
that folder first on the worker's ``sys.path``. Plugin code then imports the documented
sidekick names (``from metabrowser import resolve_path``) and gets this runtime, whatever
Metabrowser version the plugin environment itself holds, or none.

Standard library only. Spike-level: path containment here is a plain ``resolve`` and
``relative_to``; the plan moves the host's real identity codec into the runtime.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from metabrowser.content_errors import ContentReadError
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)

__version__ = "spike-runtime"

HostCall = Callable[[str, dict[str, Any]], Any]
_root: Path | None = None
_host_call: HostCall | None = None
_root_callbacks: list[Callable[[], None]] = []


def _bind(root: Path, host_call: HostCall) -> None:  # pyright: ignore[reportUnusedFunction]
    """Called by the worker at ``hello``: the session's root and the host channel."""
    global _root, _host_call
    _root = root.resolve()
    _host_call = host_call
    for callback in _root_callbacks:
        callback()


def _call_host(op: str, **args: Any) -> Any:
    if _host_call is None:
        raise RuntimeError("the plugin runtime is not bound to a host")
    return _host_call(op, args)


class CLIError(Exception):
    """The error type plugins catch around Metabrowser helpers."""


def served_root() -> Path:
    if _root is None:
        raise RuntimeError("no served root is bound")
    return _root


def resolve_path(requested: str) -> Path | None:
    root = served_root()
    candidate = (root / requested).resolve() if requested else root
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def resolve_directory(requested: str) -> Path | None:
    target = resolve_path(requested)
    return target if target is not None and target.is_dir() else None


def relativize_path(raw: str | None) -> str | None:
    if not raw:
        return raw
    try:
        return Path(raw).resolve().relative_to(served_root()).as_posix()
    except ValueError:
        return raw


def register_root_callback(callback: Callable[[], None]) -> None:
    _root_callbacks.append(callback)


@dataclass
class LogEvent:
    """The normalized event shape, field for field as the host defines it."""

    kind: str
    summary: str
    adapter: str = "unknown"
    provider: str | None = None
    timestamp: str | None = None
    is_error: bool = False
    is_done: bool = False
    cost_usd: float | None = None
    duration_s: float | None = None
    raw: dict[str, Any] | str = field(default_factory=lambda: {})
    summary_parts: list[dict[str, Any]] | None = None


AdapterDetector = Callable[[dict[str, Any]], bool]
_adapters: dict[str, tuple[AdapterDetector, Callable[[], Any]]] = {}


def register_log_adapter(
    name: str, *, detector: AdapterDetector, parser_factory: Callable[[], Any]
) -> None:
    normalized = name.strip().lower()
    existing = _adapters.get(normalized)
    if existing is not None and existing != (detector, parser_factory):
        raise ValueError(f"adapter already registered: {normalized}")
    _adapters[normalized] = (detector, parser_factory)


def adapter_names() -> list[str]:
    return sorted(_adapters)


def create_plugin_parser(name: str) -> Any:
    return _adapters[name][1]()


def detect_adapter(lines: list[str]) -> str:
    """Plugin detectors here first, as the host orders them; built-ins from the host."""
    import json

    for line in lines[:20]:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        for name, (detector, _factory) in _adapters.items():
            if detector(event):  # pyright: ignore[reportUnknownArgumentType]
                return name
    return str(_call_host("detect_builtin", lines=lines[:20]))


def extract_agent_charts_cached(path: Path) -> dict[str, Any] | None:
    """A host computation: the worker sends the path, the host checks and computes."""
    relative = relativize_path(str(path))
    result = _call_host("agent_charts", path=relative)
    return cast(dict[str, Any], result) if isinstance(result, dict) else None


__all__ = [
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "CLIError",
    "ContentReadError",
    "LogEvent",
    "detect_adapter",
    "extract_agent_charts_cached",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
    "served_root",
]
