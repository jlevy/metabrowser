"""A stalled https origin is bounded, and a terminal hangup cancels acquisition (mb-rati, mb-163x).

A local TCP server that accepts and never answers stands in for a stalled origin: Git's
https helper waits in the TLS handshake, where curl's low-speed bound does not apply,
so the ``ls-remote`` deadline is what ends it. The hangup tests send ``SIGHUP`` to a
process waiting on acquisition Git and require that Git and the helpers it forked die
with it rather than keep fetching as orphans.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import FrameType

import pytest

from metabrowser.cache.acquire import RemoteAccessError, acquire_source
from metabrowser.cache.urls import GitSource
from metabrowser.cli.hangup import (
    HANGUP_EXIT_STATUS,
    TERMINATION_EXIT_STATUS,
    run_cancelling_on_hangup,
)
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from tests.admitted_git import require_admitted_git
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="signals and process groups are POSIX-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


@pytest.fixture
def stalled_port() -> Iterator[int]:
    """A server that accepts every connection and never sends a byte."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            held.append(connection)

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1]
    finally:
        stop.set()
        thread.join(timeout=5)
        for connection in held:
            connection.close()
        server.close()


def _processes_mentioning(marker: str) -> list[tuple[int, str]]:
    listing = subprocess.run(
        ["ps", "-A", "-o", "pid=,args="], capture_output=True, text=True, check=True
    ).stdout
    found: list[tuple[int, str]] = []
    for line in listing.splitlines():
        pid_text, _, args = line.strip().partition(" ")
        if marker in args and pid_text.isdigit() and int(pid_text) != os.getpid():
            found.append((int(pid_text), args))
    return found


def _wait_for(predicate: object, seconds: float = 20.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.05)
    return False


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_stalled_https_origin_fails_at_the_probe_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stalled_port: int
) -> None:
    _allow_installed_git(monkeypatch)
    monkeypatch.setattr("metabrowser.cache.acquire.REMOTE_PROBE_TIMEOUT_S", 1.0)
    url = f"https://127.0.0.1:{stalled_port}/stalled.git"
    source = GitSource(transport="https", form="url", normalized=url)
    home = tmp_path / "home"
    started = time.monotonic()
    with pytest.raises(RemoteAccessError) as refused:
        asyncio.run(acquire_source(source, home=home))
    assert time.monotonic() - started < 15
    assert refused.value.state == "timed_out"
    assert str(refused.value) == (
        f"{url} stopped answering in time (timed_out); no answer within 1 s; nothing was published"
    )
    assert _wait_for(lambda: not _processes_mentioning(f"127.0.0.1:{stalled_port}"), 5)
    staging = home / "cache" / "staging"
    assert not staging.is_dir() or list(staging.iterdir()) == []


_HANGUP_CHILD = """
import signal
import sys
from pathlib import Path
from metabrowser.cli.hangup import run_cancelling_on_hangup
from metabrowser.git.process import ACQUISITION_POLICY, run_git

pid_file = sys.argv[1]
if sys.argv[3] == "ignore-hangup":
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
script = f"!sleep 60 & echo $! > '{pid_file}'; wait"
run_cancelling_on_hangup(
    run_git(["-c", f"alias.hang={script}", "hang"], cwd=Path(sys.argv[2]), policy=ACQUISITION_POLICY)
)
"""


def _child_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}


def _start_child(tmp_path: Path, mode: str) -> tuple[subprocess.Popen[bytes], int]:
    pid_file = tmp_path / "helper.pid"
    child = subprocess.Popen(
        [sys.executable, "-c", _HANGUP_CHILD, str(pid_file), str(tmp_path), mode],
        env=_child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if not _wait_for(lambda: pid_file.is_file() and pid_file.read_text().strip() != ""):
        child.kill()
        child.wait()
        pytest.fail("the helper never started")
    return child, int(pid_file.read_text())


def _reap(child: subprocess.Popen[bytes], helper: int) -> None:
    if child.poll() is None:
        child.kill()
        child.wait()
    if helper and _alive(helper):
        os.kill(helper, signal.SIGKILL)


@pytest.mark.parametrize(
    ("sent", "status"),
    [(signal.SIGHUP, HANGUP_EXIT_STATUS), (signal.SIGTERM, TERMINATION_EXIT_STATUS)],
)
def test_hangup_or_termination_cancels_acquisition_git_and_its_helpers(
    tmp_path: Path, sent: signal.Signals, status: int
) -> None:
    """Any Git: the helper is ``sleep`` forked by a Git alias, as in the timeout test."""

    child, helper = _start_child(tmp_path, "default")
    try:
        child.send_signal(sent)
        assert child.wait(timeout=15) == status, child.stderr.read() if child.stderr else ""
        assert _wait_for(lambda: not _alive(helper), 5), f"the helper outlived {sent.name}"
    finally:
        _reap(child, helper)


def test_an_ignored_hangup_stays_ignored(tmp_path: Path) -> None:
    """``nohup metab …`` keeps acquiring after the terminal closes; SIGTERM still stops it."""

    child, helper = _start_child(tmp_path, "ignore-hangup")
    try:
        child.send_signal(signal.SIGHUP)
        assert not _wait_for(lambda: child.poll() is not None, 1.5), "SIGHUP was not ignored"
        assert _alive(helper)
        child.send_signal(signal.SIGTERM)
        assert child.wait(timeout=15) == TERMINATION_EXIT_STATUS
        assert _wait_for(lambda: not _alive(helper), 5)
    finally:
        _reap(child, helper)


def test_the_previous_handlers_are_restored() -> None:
    def hangup_handler(_number: int, _frame: FrameType | None) -> None:
        return

    def termination_handler(_number: int, _frame: FrameType | None) -> None:
        return

    before = (signal.getsignal(signal.SIGHUP), signal.getsignal(signal.SIGTERM))
    signal.signal(signal.SIGHUP, hangup_handler)
    signal.signal(signal.SIGTERM, termination_handler)
    try:
        assert run_cancelling_on_hangup(asyncio.sleep(0, result="done")) == "done"
        assert signal.getsignal(signal.SIGHUP) is hangup_handler
        assert signal.getsignal(signal.SIGTERM) is termination_handler
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        run_cancelling_on_hangup(asyncio.sleep(0))
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    finally:
        for number, handler in zip((signal.SIGHUP, signal.SIGTERM), before, strict=True):
            if handler is not None:
                signal.signal(number, handler)


def _metab() -> str:
    beside = Path(sys.executable).parent / "metab"
    found = str(beside) if beside.is_file() else shutil.which("metab")
    assert found, "the metab console script is not installed in this environment"
    return found


def test_hangup_during_a_real_https_acquire_leaves_no_git_behind(
    tmp_path: Path, stalled_port: int
) -> None:
    """The installed CLI, unpatched, on an admitted Git: ``git-remote-https`` dies too."""

    require_admitted_git()
    marker = f"127.0.0.1:{stalled_port}"
    env = _child_env()
    env.update({"METABROWSER_HOME": str(tmp_path / "home"), "METABROWSER_LOG_LEVEL": "ERROR"})
    child = subprocess.Popen(
        [_metab(), f"https://{marker}/stalled.git", "--no-serve"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert _wait_for(
            lambda: any("remote-https" in args for _pid, args in _processes_mentioning(marker))
        ), "git-remote-https never started"
        child.send_signal(signal.SIGHUP)
        assert child.wait(timeout=15) == HANGUP_EXIT_STATUS
        assert _wait_for(lambda: not _processes_mentioning(marker), 5), _processes_mentioning(
            marker
        )
        staging = tmp_path / "home" / "cache" / "staging"
        assert not staging.is_dir() or list(staging.iterdir()) == []
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        for pid, _args in _processes_mentioning(marker):
            os.kill(pid, signal.SIGKILL)
