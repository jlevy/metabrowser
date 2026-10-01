"""Read from a child process a test started, without waiting on it forever."""

from __future__ import annotations

import contextlib
import subprocess
import threading
from collections.abc import Callable
from typing import IO

import pytest

# How long a child gets to write a line it writes at once when it works. Not a budget:
# only a child that hangs or dies silently uses it up. Twenty seconds, so that a caller
# which then waits 30 s for the child to exit stays within 50 s, under the suite's
# 60 s per-test timeout.
CHILD_LINE_TIMEOUT_S = 20.0
# What giving up may then cost, twice: ending the child, and reading its stderr.
_GIVE_UP_STEP_S = 5.0


def read_line(process: subprocess.Popen[str], *, timeout: float = CHILD_LINE_TIMEOUT_S) -> str:
    """The next line of the child's stdout, as ``readline`` returns it.

    A bare ``readline`` on a child that never writes waits until the suite's own
    timeout stops the whole run. Here the child is killed and the one test fails,
    with what the child wrote to stderr.
    """

    stdout = process.stdout
    assert stdout is not None, "the child's stdout is not a pipe"
    line = _read_within(stdout.readline, timeout)
    if line is None:
        # Killing the child closes its end of the pipe, which ends the read, unless
        # a process it started still holds that end open; so no wait here is unbounded.
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=_GIVE_UP_STEP_S)
        errors = _stderr_within(process.stderr)
        pytest.fail(f"the child wrote no line within {timeout:g}s; its stderr: {errors!r}")
    return line


def _stderr_within(stderr: IO[str] | None) -> str:
    if stderr is None:
        return ""
    errors = _read_within(stderr.read, _GIVE_UP_STEP_S)
    return "(still held open by another process)" if errors is None else errors


def _read_within(read: Callable[[], str], timeout: float) -> str | None:
    """What *read* returns, or ``None`` when it has not returned within *timeout*."""

    chunks: list[str] = []
    reader = threading.Thread(target=lambda: chunks.append(read()), daemon=True)
    reader.start()
    reader.join(timeout)
    return chunks[0] if chunks else None
