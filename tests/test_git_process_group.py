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
from typing import Any

import pytest

from metabrowser.git.process import (
    ACQUISITION_POLICY,
    READ_POLICY,
    GitTimeoutError,
    kill_live_process_groups,
    run_git,
    spawn_git_process,
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


def test_an_unexpected_failure_while_waiting_kills_the_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only a timeout or a cancellation: any exception out of the wait reaps the group."""

    import metabrowser.git.process as process_module

    pid_file = tmp_path / "helper.pid"
    real_read = process_module._read_capped

    async def failing_read(stream: Any, limit: int) -> tuple[bytes, bool]:
        await asyncio.to_thread(_wait_for_pid, pid_file)
        raise RuntimeError("the reader broke")

    registered: list[asyncio.subprocess.Process] = []
    real_register = process_module._register_group

    def recording_register(proc: asyncio.subprocess.Process) -> None:
        registered.append(proc)
        real_register(proc)

    monkeypatch.setattr(process_module, "_register_group", recording_register)
    monkeypatch.setattr(process_module, "_read_capped", failing_read)
    with pytest.raises(RuntimeError, match="the reader broke"):
        asyncio.run(
            asyncio.wait_for(
                run_git(_alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY), 30
            )
        )
    monkeypatch.setattr(process_module, "_read_capped", real_read)
    helper = _wait_for_pid(pid_file)
    try:
        assert _gone_within(helper), "the forked helper outlived the failed wait"
    finally:
        _kill_leftover(helper)
    # Reaped, so the exit path no longer knows it.
    assert [proc.pid in process_module._LIVE_PROCESS_GROUPS for proc in registered] == [False]


def test_the_exit_path_kills_live_groups_and_skips_reaped_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``kill_live_process_groups`` signals only children not yet reaped.

    A reaped child's group ID may already belong to an unrelated process.
    """

    import metabrowser.git.process as process_module

    pid_file = tmp_path / "helper.pid"

    async def scenario() -> list[int]:
        finished = await spawn_git_process(["--version"], cwd=tmp_path, policy=ACQUISITION_POLICY)
        await finished.wait()
        hanging = await spawn_git_process(
            _alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY
        )
        await asyncio.to_thread(_wait_for_pid, pid_file)
        signalled: list[int] = []
        real_killpg = os.killpg

        def recording_killpg(pgid: int, signum: int) -> None:
            signalled.append(pgid)
            real_killpg(pgid, signum)

        monkeypatch.setattr(process_module.os, "killpg", recording_killpg)
        kill_live_process_groups()
        monkeypatch.setattr(process_module.os, "killpg", real_killpg)
        await hanging.wait()
        assert finished.pid not in signalled
        return signalled

    signalled = asyncio.run(asyncio.wait_for(scenario(), timeout=30))
    helper = _wait_for_pid(pid_file)
    try:
        assert _gone_within(helper), "the forked helper outlived the exit path"
    finally:
        _kill_leftover(helper)
    assert len(signalled) == 1
