"""A timed-out or cancelled acquisition Git kills its helpers, not only itself (mb-lp89).

Fetch and clone fork helpers (``upload-pack``, ``index-pack``, ``remote-https``). Killing
only the ``git`` process orphans them, still holding the staging directory and the
network. A shell alias stands in for a helper: ``git`` forks ``sh``, which forks
``sleep`` and records its pid.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path

import pytest

from metabrowser.git.process import (
    ACQUISITION_POLICY,
    READ_POLICY,
    GitTimeoutError,
    run_git,
)

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


def _alias_args(pid_file: Path) -> list[str]:
    script = f"!sleep 60 & echo $! > '{pid_file}'; wait"
    return ["-c", f"alias.hang={script}", "hang"]


def _wait_for_pid(pid_file: Path) -> int:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        text = pid_file.read_text() if pid_file.exists() else ""
        if text.strip():
            return int(text)
        time.sleep(0.02)
    raise AssertionError("the helper never started")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _gone_within(pid: int, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.02)
    return False


def _kill_leftover(pid: int) -> None:
    if _alive(pid):
        os.kill(pid, 9)


def test_acquisition_timeout_kills_the_helper_git_forked(tmp_path: Path) -> None:
    pid_file = tmp_path / "helper.pid"
    with pytest.raises(GitTimeoutError):
        asyncio.run(
            run_git(_alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY, timeout_s=1)
        )
    helper = _wait_for_pid(pid_file)
    try:
        assert _gone_within(helper), "the forked helper outlived the timed-out git"
    finally:
        _kill_leftover(helper)


def test_acquisition_cancellation_kills_the_helper_git_forked(tmp_path: Path) -> None:
    pid_file = tmp_path / "helper.pid"

    async def cancel_while_running() -> None:
        task = asyncio.ensure_future(
            run_git(_alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY)
        )
        await asyncio.to_thread(_wait_for_pid, pid_file)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(asyncio.wait_for(cancel_while_running(), timeout=30))
    helper = _wait_for_pid(pid_file)
    try:
        assert _gone_within(helper), "the forked helper outlived the cancelled git"
    finally:
        _kill_leftover(helper)


def test_read_policy_keeps_git_in_the_callers_process_group(tmp_path: Path) -> None:
    """Request-path reads stay in the foreground group so terminal Ctrl-C still reaches them."""

    assert not READ_POLICY.own_process_group
    assert ACQUISITION_POLICY.own_process_group
    pid_file = tmp_path / "helper.pid"
    script = f"!echo $(ps -o pgid= -p $$) > '{pid_file}'"
    asyncio.run(run_git(["-c", f"alias.pg={script}", "pg"], cwd=tmp_path, policy=READ_POLICY))
    assert int(pid_file.read_text()) == os.getpgid(0)
