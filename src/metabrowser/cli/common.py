"""Helpers shared by the metab CLI modes (serve, walk, remote, plugins).

Log-level plumbing, served-path containment checks, and broken-pipe
handling live here so :mod:`metabrowser.cli.main` and the per-mode
implementation modules can share them without import cycles.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TextIO

import typer

from metabrowser.errors import CLIError

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def validate_log_level(value: str | None) -> str:
    """Click callback: normalize ``--log-level`` to upper case or reject it."""
    if not value:
        return ""
    upper = value.upper()
    if upper not in VALID_LOG_LEVELS:
        raise typer.BadParameter(f"must be one of {', '.join(VALID_LOG_LEVELS)}")
    return upper


def apply_log_level(level: str | None) -> None:
    """Export ``METABROWSER_LOG_LEVEL`` so the logging setup at server
    import (``server._setup_perf_logging``) and the walk mode pick
    up the requested verbosity. ``--log-level debug`` is the general
    knob for tracing the walker — e.g. every ``rewalk_subtree`` target
    and its resolved path — without a feature-specific flag.
    """

    # ``isinstance str`` guard: when a mode implementation is invoked as a
    # plain function (some tests do this) rather than through Typer, unpassed
    # options can arrive as sentinels instead of resolved strings. Treat
    # anything non-string / empty as "no level set".
    if not isinstance(level, str) or not level:
        return
    upper = level.upper()
    if upper not in VALID_LOG_LEVELS:
        raise CLIError(
            f"invalid --log-level {level!r}; expected one of {', '.join(VALID_LOG_LEVELS)}"
        )
    os.environ["METABROWSER_LOG_LEVEL"] = upper


def validate_contained_path(root: Path, requested: str) -> Path:
    """Require a requested path to exist within the resolved root."""
    target = (root / requested).resolve()
    if not target.is_relative_to(root):
        raise CLIError(f"--path target is outside the served root: {requested}")
    if not target.exists():
        raise CLIError(f"--path target does not exist: {target}")
    return target


class PipeTrackingStream:
    """Delegate a text stream while recording downstream pipe closure."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.broken_pipe = False

    def write(self, data: str) -> int:
        try:
            return self.stream.write(data)
        except BrokenPipeError:
            self.broken_pipe = True
            raise

    def flush(self) -> None:
        try:
            self.stream.flush()
        except BrokenPipeError:
            self.broken_pipe = True
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


def silence_broken_pipe(stream: TextIO) -> None:
    """Redirect a closed standard stream before interpreter finalization."""
    try:
        stream_fd = stream.fileno()
        null_fd = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError):
        return
    try:
        os.dup2(null_fd, stream_fd)
    finally:
        os.close(null_fd)
