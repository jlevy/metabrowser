"""Provisional Python helpers for installed Metabrowser plugin sidekicks.

Plugin data hooks run inside the Metabrowser server process. They need the
same served-root containment, transparent artifact reads, log-adapter
detection, and cache lifecycle as built-in handlers. This module exposes that
small 0.x contract without requiring plugins to import private implementation
names. Names can evolve before 1.0, with release notes documenting changes.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)
from metabrowser.jsonl_view import JsonlParseLimitError
from metabrowser.logutil.parsing import LogEvent, LogParser, detect_adapter, register_log_adapter
from metabrowser.paths_safe import (
    _relativize,
    _safe_path,
    _safe_subdir,
    register_root_callback,
)
from metabrowser.projections import extract_agent_charts_cached


def resolve_path(requested: str) -> Path | None:
    """Resolve a served-root-relative path without allowing traversal.

    An empty string returns the served root. A successful result may be a file
    or directory; use :func:`resolve_directory` when a directory is required.
    """
    return _safe_path(requested)


def resolve_directory(requested: str) -> Path | None:
    """Resolve a served-root-relative directory without allowing traversal."""
    return _safe_subdir(requested)


def relativize_path(raw: str | None) -> str | None:
    """Convert an absolute path under the served root to its client path."""
    return _relativize(raw)


__all__ = [
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "detect_adapter",
    "extract_agent_charts_cached",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
]
