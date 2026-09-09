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
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.jsonl_view import JsonlParseLimitError
from metabrowser.logutil.parsing import LogEvent, LogParser, detect_adapter, register_log_adapter
from metabrowser.paths_safe import (
    _relativize,
    _safe_path,
    _safe_path_from_identity,
    register_root_callback,
)
from metabrowser.projections import extract_agent_charts_cached


def resolve_path(requested: str) -> Path | None:
    """Resolve a canonical inventory path without allowing traversal.

    An empty string returns the served root. A successful result may be a file
    or directory; use :func:`resolve_directory` when a directory is required.
    """
    return _safe_path_from_identity(requested)


def resolve_directory(requested: str) -> Path | None:
    """Resolve a served-root-relative directory without allowing traversal."""
    target = resolve_path(requested)
    return target if target is not None and target.is_dir() else None


def relativize_path(raw: str | None) -> str | None:
    """Convert an absolute path under the served root to its client path."""
    relative = _relativize(raw)
    return canonical_inventory_path(relative) if relative else relative


# The deepest inner path a container may expose beneath its own file,
# counted from the container, not from the served root. One value for
# the server's ancestor walk and every plugin's, so the two
# implementations of this security-relevant rule cannot drift.
MAX_CONTAINER_INNER_DEPTH = 16


def served_root() -> Path:
    """The folder this server is serving.

    Hooks that reason about the tree as a whole — a repository, an
    archive — need the root itself, which ``resolve_path("")`` also
    returns; this name says why the caller wants it.
    """
    root = _safe_path("")
    if root is None:  # pragma: no cover - the served root always resolves
        raise RuntimeError("served root is unavailable")
    return root


__all__ = [
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "MAX_CONTAINER_INNER_DEPTH",
    "detect_adapter",
    "extract_agent_charts_cached",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
    "served_root",
]
