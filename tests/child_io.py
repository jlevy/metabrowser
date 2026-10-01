"""Read from a child process a test started, without waiting on it forever."""

from __future__ import annotations

import subprocess
import threading

import pytest

# How long a child gets to write a line it writes at once when it works. Not a budget:
# only a child that hangs or dies silently uses it up.
CHILD_LINE_TIMEOUT_S = 30.0


def read_line(process: subprocess.Popen[str], *, timeout: float = CHILD_LINE_TIMEOUT_S) -> str:
    """The next line of the child's stdout, as ``readline`` returns it.

    A bare ``readline`` on a child that never writes waits until the suite's own
    timeout stops the whole run. Here the child is killed and the one test fails,
    with what the child wrote to stderr.
    """

    stdout = process.stdout
    assert stdout is not None, "the child's stdout is not a pipe"
    lines: list[str] = []
    reader = threading.Thread(target=lambda: lines.append(stdout.readline()), daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        # Killing the child closes its end of the pipe, which ends the read.
        process.kill()
        reader.join(timeout)
        errors = process.stderr.read() if process.stderr is not None else ""
        pytest.fail(f"the child wrote no line within {timeout:g}s; its stderr: {errors!r}")
    return lines[0]
