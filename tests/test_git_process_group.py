"""A timed-out or cancelled acquisition Git kills its helpers, not only itself (mb-lp89).

Fetch and clone fork helpers (``upload-pack``, ``index-pack``, ``remote-https``). Killing
only the ``git`` process orphans them, still holding the staging directory and the
network. A shell alias stands in for a helper: ``git`` forks ``sh``, which forks
``sleep`` and records its pid.

A stop that exits without unwinding (Ctrl-C, a hangup, a closed stdin under
``--exit-on-eof``) kills the groups first, including one whose spawn is still under way.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import metabrowser.git.process as process_module
from metabrowser.cli import stdin_lifeline
from metabrowser.cli.serve import _stop_now
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    READ_POLICY,
    GitError,
    GitTimeoutError,
    GitUnavailableError,
    kill_live_process_groups,
    run_git,
    spawn_git_process,
)
from tests.child_io import read_line
from tests.required_tools import needs_git

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only"),
    needs_git,
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


def test_a_cancellation_while_git_is_starting_kills_its_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cancellation lands after the child exists but before the spawn returns it.

    asyncio's own cleanup for an interrupted ``create_subprocess_exec`` kills only the
    ``git`` process, which leaves the helpers it already forked running. The spawn is
    held open here, after the real process started, until the cancellation has been
    sent, which is the window a terminal hangup hit about one run in four. Held on an
    event, not for a fixed time: a pause can end before the cancellation is sent, and
    the test then passes on the ordinary path.
    """

    pid_file = tmp_path / "helper.pid"
    real_spawn = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    cancellation_sent = asyncio.Event()

    async def slow_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        proc = await real_spawn(*args, **kwargs)
        spawned.set()
        await asyncio.to_thread(_wait_for_pid, pid_file)
        await cancellation_sent.wait()
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_spawn)

    async def cancel_while_spawning() -> None:
        task = asyncio.ensure_future(
            run_git(_alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY)
        )
        await spawned.wait()
        await asyncio.to_thread(_wait_for_pid, pid_file)
        task.cancel()
        cancellation_sent.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(asyncio.wait_for(cancel_while_spawning(), timeout=30))
    helper = _wait_for_pid(pid_file)
    try:
        assert _gone_within(helper), "a helper outlived a cancellation during spawn"
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


# ── A stop while a group is starting ──────────────────────────────────────

# A stop's own bound on waiting is a couple of seconds; this bounds only a process that
# does not stop at all, so the test fails instead of hanging the suite.
_STOP_TIMEOUT_S = 15.0


@pytest.fixture
def fresh_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop is for good and process-wide, so each test that stops gets its own."""

    monkeypatch.setattr(process_module, "_GROUP_STOP", process_module._GroupStop())


class _HeldSpawn:
    """A spawn held after the child exists and before it returns, until ``release``.

    That is the window a stop used to miss: the group's ID is known only once the spawn
    returns, a few event-loop turns after the fork, and the registry learns it then.
    Held on events, not for a time, so the stop always lands inside the window.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, reap_first: bool = False) -> None:
        self.started = threading.Event()
        self.reaped = threading.Event()
        self.release = threading.Event()
        real_spawn = asyncio.create_subprocess_exec

        async def held_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            proc = await real_spawn(*args, **kwargs)
            self.started.set()
            if reap_first:
                # The child ends and is reaped before the spawn returns to its caller.
                await proc.wait()
                self.reaped.set()
            await asyncio.to_thread(self.release.wait, 30)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", held_spawn)


def _held_lock(path: Path) -> int:
    """A descriptor holding an exclusive ``flock`` on *path*, as a fetch lock is held."""

    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _lock_free_within(path: Path, seconds: float = 5.0) -> bool:
    fd = os.open(path, os.O_RDWR)
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(0.02)
                continue
            fcntl.flock(fd, fcntl.LOCK_UN)
            return True
        return False
    finally:
        os.close(fd)


def _release_once_the_stop_kills(held: _HeldSpawn, monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the held spawn go only once the stop has begun: its first kill of the groups."""

    real_kill = process_module._kill_owned_groups

    def kill_then_release(stop: process_module._GroupStop) -> None:
        real_kill(stop)
        held.release.set()

    monkeypatch.setattr(process_module, "_kill_owned_groups", kill_then_release)


async def _end(task: asyncio.Future[bytes]) -> None:
    """End a ``run_git`` task, killed by the stop or cancelled here, without waiting long."""

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, GitError, TimeoutError):
        await asyncio.wait_for(task, 20)


@pytest.mark.usefixtures("fresh_stop")
def test_a_closed_stdin_kills_a_group_still_starting_and_frees_its_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stop begins after the child exists and before its group is registered.

    The group must still be killed, with the helper it forked and the fetch lock it
    inherited (cache locks are ``flock`` on a descriptor the child holds), and the stop
    exits once the spawn has ended. Before, the stop killed what the registry held at
    that moment, which did not include this group, and exited, leaving the helper
    running and the lock held.
    """

    pid_file = tmp_path / "helper.pid"
    lock_path = tmp_path / "fetch.lock"
    lock_fd = _held_lock(lock_path)
    held = _HeldSpawn(monkeypatch)
    exits: list[int] = []
    monkeypatch.setattr(os, "_exit", exits.append)

    _release_once_the_stop_kills(held, monkeypatch)

    async def scenario() -> tuple[int, bool, bool]:
        task = asyncio.ensure_future(
            run_git(
                _alias_args(pid_file),
                cwd=tmp_path,
                policy=ACQUISITION_POLICY,
                pass_fds=(lock_fd,),
            )
        )
        await asyncio.to_thread(held.started.wait, 30)
        os.close(lock_fd)  # From here only Git and its helpers hold the lock.
        helper = await asyncio.to_thread(_wait_for_pid, pid_file)
        stopper = threading.Thread(target=stdin_lifeline.stop_for_closed_stdin, daemon=True)
        stopper.start()
        await asyncio.to_thread(stopper.join, 20)
        gone = await asyncio.to_thread(_gone_within, helper)
        lock_free = await asyncio.to_thread(_lock_free_within, lock_path)
        await _end(task)
        return helper, gone, lock_free

    helper, gone, lock_free = asyncio.run(asyncio.wait_for(scenario(), timeout=50))
    try:
        assert gone, "the helper of a group still starting outlived the stop"
        assert lock_free, "the fetch lock outlived the stop"
        assert exits[:1] == [0]
    finally:
        _kill_leftover(helper)


@pytest.mark.usefixtures("fresh_stop")
def test_an_interrupt_while_a_group_is_starting_kills_it_and_exits_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl-C lands on the event loop's own thread, between the fork and the registry.

    The handler cannot wait for the spawn on the thread that has to finish it, and need
    not: the kernel lists the child, so the handler kills its group and exits with the
    interrupt's status there and then. Before the stop counted spawns, the handler
    exited and the group was never killed.
    """

    pid_file = tmp_path / "helper.pid"
    held = _HeldSpawn(monkeypatch)
    exits: list[int] = []
    monkeypatch.setattr(os, "_exit", exits.append)
    previous = signal.signal(signal.SIGINT, _stop_now)

    async def scenario() -> tuple[int, list[int], bool]:
        task = asyncio.ensure_future(
            run_git(_alias_args(pid_file), cwd=tmp_path, policy=ACQUISITION_POLICY)
        )
        await asyncio.to_thread(held.started.wait, 30)
        helper = await asyncio.to_thread(_wait_for_pid, pid_file)
        # The handler runs here, on this thread, while the spawn is held.
        signal.raise_signal(signal.SIGINT)
        during = list(exits)
        held.release.set()
        with contextlib.suppress(GitError, TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 20)
        gone = await asyncio.to_thread(_gone_within, helper)
        await _end(task)
        return helper, during, gone

    try:
        helper, during, gone = asyncio.run(asyncio.wait_for(scenario(), timeout=50))
    finally:
        signal.signal(signal.SIGINT, previous)
    try:
        assert during == [130], "one interrupt did not stop the process"
        assert gone, "the helper of a group still starting outlived the interrupt"
        assert exits[:1] == [130]
    finally:
        _kill_leftover(helper)


@pytest.mark.usefixtures("fresh_stop")
def test_no_group_is_started_once_a_stop_has_begun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exits: list[int] = []
    monkeypatch.setattr(os, "_exit", exits.append)
    stdin_lifeline.stop_for_closed_stdin()
    assert exits[:1] == [0]
    started: list[asyncio.subprocess.Process] = []
    real_spawn = asyncio.create_subprocess_exec

    async def recording_spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        proc = await real_spawn(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_spawn)
    with pytest.raises(GitUnavailableError, match="stopping"):
        asyncio.run(spawn_git_process(["--version"], cwd=tmp_path, policy=ACQUISITION_POLICY))
    assert started == []


@pytest.mark.usefixtures("fresh_stop")
def test_a_group_reaped_before_its_spawn_returns_is_never_signalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child that exits and is reaped while its spawn is held has given up its ID.

    The kernel may hand that ID to an unrelated process group at once, so the stop that
    was waiting for the spawn must finish without ever passing it to ``killpg``.
    """

    held = _HeldSpawn(monkeypatch, reap_first=True)
    exits: list[int] = []
    monkeypatch.setattr(os, "_exit", exits.append)
    signalled: list[int] = []
    real_killpg = os.killpg

    def recording_killpg(pgid: int, signum: int) -> None:
        signalled.append(pgid)
        real_killpg(pgid, signum)

    monkeypatch.setattr(os, "killpg", recording_killpg)
    _release_once_the_stop_kills(held, monkeypatch)

    async def scenario() -> int:
        task = asyncio.ensure_future(
            spawn_git_process(["--version"], cwd=tmp_path, policy=ACQUISITION_POLICY)
        )
        await asyncio.to_thread(held.started.wait, 30)
        await asyncio.to_thread(held.reaped.wait, 30)
        stopper = threading.Thread(target=stdin_lifeline.stop_for_closed_stdin, daemon=True)
        stopper.start()
        await asyncio.to_thread(held.release.wait, 30)
        proc = await asyncio.wait_for(task, 20)
        await asyncio.to_thread(stopper.join, 20)
        assert not stopper.is_alive(), "the stop never finished"
        return proc.pid

    pid = asyncio.run(asyncio.wait_for(scenario(), timeout=50))
    assert pid not in signalled
    assert exits[:1] == [0]


# A process that runs a real acquisition Git, with a helper and a fetch lock it inherits,
# whose spawn is held after the fork for good: its event loop's thread stuck, its
# set-up failing once a stop has begun, or the loop running and the spawn never returning.
# It stops by its own --exit-on-eof and Ctrl-C paths, with a real os._exit.
_HELD_SPAWN_DRIVER = """
import asyncio, fcntl, os, sys, time

import metabrowser.git.process as process
from metabrowser.cli.serve import stop_on_interrupt
from metabrowser.cli.stdin_lifeline import stop_when_stdin_closes

mode, workdir, lock_path, pid_file = sys.argv[1:5]
lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(lock_fd, fcntl.LOCK_EX)
real_spawn = asyncio.create_subprocess_exec


async def held_spawn(*args, **kwargs):
    proc = await real_spawn(*args, **kwargs)
    os.close(lock_fd)  # From here only Git and its helper hold the lock.
    print("spawned", flush=True)
    if mode == "stalled":
        time.sleep(600)  # The loop's thread is stuck: nothing on it runs again.
    elif mode == "failed":
        while not process._GROUP_STOP.requested:
            await asyncio.sleep(0.01)
        raise OSError("the pipes would not connect")
    else:
        await asyncio.Event().wait()  # The loop runs; this spawn never returns.
    return proc


asyncio.create_subprocess_exec = held_spawn
stop_on_interrupt()
stop_when_stdin_closes()
script = f"!sleep 60 & echo $! > '{pid_file}'; wait"
try:
    asyncio.run(
        process.run_git(
            ["-c", f"alias.hang={script}", "hang"],
            cwd=workdir,
            policy=process.ACQUISITION_POLICY,
            pass_fds=(lock_fd,),
        )
    )
except process.GitError:
    pass  # A server goes on serving after a failed fetch; only a stop ends it.
while True:
    time.sleep(1)
"""


@pytest.mark.parametrize(
    ("mode", "stop", "status"),
    [
        ("stalled", "stdin closes", 0),
        ("failed", "stdin closes", 0),
        ("held", "interrupt", 130),
        ("stalled", "interrupt", 130),
    ],
    ids=["eof-loop-stuck", "eof-set-up-fails", "sigint-spawn-held", "sigint-loop-stuck"],
)
def test_a_stop_kills_a_group_whose_spawn_never_registers(
    mode: str, stop: str, status: int, tmp_path: Path
) -> None:
    """The group is the stop's from its fork on, whether or not its spawn ever returns.

    The registry learns a group only when its spawn returns, which needs the event
    loop. Here the spawn is held after the fork past any wait: the loop's thread stuck,
    its set-up failing once the stop has begun, or the loop running and the spawn never
    returning. Each stop must still kill the group, with the helper it forked and the
    fetch lock it inherited, and exit with its own status, in a bounded time. Before,
    the stop for a closed stdin exited after its wait and left them running, or exited
    from the failed set-up without killing them; one Ctrl-C did not exit at all.
    """

    lock_path = tmp_path / "fetch.lock"
    pid_file = tmp_path / "helper.pid"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _HELD_SPAWN_DRIVER,
            mode,
            str(tmp_path),
            str(lock_path),
            str(pid_file),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    helper: int | None = None
    try:
        assert read_line(process).strip() == "spawned"
        helper = _wait_for_pid(pid_file)
        assert process.stdin is not None
        if stop == "interrupt":
            process.send_signal(signal.SIGINT)
        else:
            process.stdin.close()
            process.stdin = None
        try:
            returncode = process.wait(timeout=_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            pytest.fail(f"{stop}: the process did not stop with its spawn held ({mode})")
        gone = _gone_within(helper)
        lock_free = _lock_free_within(lock_path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if helper is not None:
            _kill_leftover(helper)
    assert returncode == status, process.stderr.read() if process.stderr else ""
    assert gone, "the helper of a group whose spawn never registered outlived the stop"
    assert lock_free, "the fetch lock outlived the stop"


# ── What a stop may signal ────────────────────────────────────────────────


@pytest.mark.usefixtures("fresh_stop")
def test_a_spawn_that_registers_during_the_first_look_is_still_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spawn on another thread forks and registers between the stop's first look and
    its check for spawns under way, so the check finds none and nothing waits.

    The stop must still look once more before its caller exits. Before, it looked again
    only when it had waited, and the Git, its helper and its fetch lock outlived it.
    """

    pid_file = tmp_path / "helper.pid"
    lock_path = tmp_path / "fetch.lock"
    lock_fd = _held_lock(lock_path)
    fork = threading.Event()
    ended = threading.Event()
    real_spawn = asyncio.create_subprocess_exec

    async def admitted_then_forked(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        # Counted as under way from here, and forked only once the stop has looked.
        await asyncio.to_thread(fork.wait, 30)
        return await real_spawn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", admitted_then_forked)
    real_end = process_module._end_group_spawn

    def ending(*args: Any) -> None:
        real_end(*args)
        ended.set()

    monkeypatch.setattr(process_module, "_end_group_spawn", ending)
    real_look = process_module._kill_owned_groups
    looks: list[int] = []

    def look(stop: process_module._GroupStop) -> None:
        real_look(stop)
        looks.append(1)
        if len(looks) == 1:
            fork.set()
            assert ended.wait(30), "the spawn never registered"

    monkeypatch.setattr(process_module, "_kill_owned_groups", look)

    def serve() -> None:
        async def fetch() -> None:
            with contextlib.suppress(GitError):
                await run_git(
                    _alias_args(pid_file),
                    cwd=tmp_path,
                    policy=ACQUISITION_POLICY,
                    pass_fds=(lock_fd,),
                )

        with contextlib.suppress(TimeoutError):
            asyncio.run(asyncio.wait_for(fetch(), 40))

    loop = threading.Thread(target=serve, daemon=True)
    loop.start()
    deadline = time.monotonic() + 30
    while not process_module._GROUP_STOP.in_flight:
        assert time.monotonic() < deadline, "the spawn was never admitted"
        time.sleep(0.01)
    try:
        process_module.stop_process_groups()
        os.close(lock_fd)  # Forked by now: from here only Git and its helper hold it.
        lock_free = _lock_free_within(lock_path)
    finally:
        process_module.kill_live_process_groups()
        loop.join(30)
    helper = int(pid_file.read_text()) if pid_file.exists() and pid_file.read_text() else None
    if helper is not None:
        assert _gone_within(helper), "the helper outlived the stop"
    assert lock_free, "the fetch lock outlived the stop"
