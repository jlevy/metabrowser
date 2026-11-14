"""A run in its own process group leaves nothing running, however it ends.

The Chrome tests (``test_folder_overview_alignment.py``, ``test_transitions_instrument.py``,
``test_github_pull_header_chrome.py``, ``test_staged_fonts_chrome.py``) run a Node script
that starts Chrome and its helpers. Here a Node parent starts a long-lived Node child that
stands in for the browser, with a ``--user-data-dir`` inside the profile as Chrome has, so
``tests/process_group.py`` is held without a browser:

- a run stopped at its deadline, a parent that exits and leaves its child behind, and a
  child that ignores SIGTERM all end with nothing of the group running;
- every signal to the group is sent while its leader is unreaped, so the group ID is
  still the run's; a group with no live member, or only zombies, gets no signal;
- a browser that left the group is killed, waited for, and reported, and only a verified
  one: a process that merely mentions the profile, or whose ID now names another
  process, is not signalled;
- the profile is removed even when the sweep fails, and a failure in the block keeps
  its own exception;
- each Chrome test's whole lifecycle fits under its timeout.
"""

from __future__ import annotations

import importlib
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from contextlib import suppress
from pathlib import Path

import pytest

import tests.process_group as pg
from tests.process_group import owned_profile, run_in_own_group, stop_group
from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
# The stand-in browser: it runs until it is killed. Started with `-- --user-data-dir=…`,
# its command line carries the profile argument the sweep looks for.
CHILD = "setInterval(() => {}, 1000);"
# One that stays up through SIGTERM, which only SIGKILL stops.
STUBBORN = "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);"
# The parent starts the child, writes the child's pid, and then hangs or exits.
PARENT = """
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const [child, profile, pidFile, mode] = process.argv.slice(1);
const started = spawn(process.execPath, ["-e", child, "--", `--user-data-dir=${profile}`], {
  stdio: "ignore",
  detached: mode === "leave-group",
});
fs.writeFileSync(pidFile, String(started.pid));
if (mode === "hang") {
  setInterval(() => {}, 1000);
} else {
  started.unref();
}
"""
# Long enough for Node to start and write the pid file on a loaded machine; the run is
# stopped here only in the hanging cases.
DEADLINE_S = 5.0
CHROME_TESTS = (
    "tests.test_folder_overview_alignment",
    "tests.test_github_pull_header_chrome",
    "tests.test_staged_fonts_chrome",
    "tests.test_transitions_instrument",
)
# Creating the profile and the test's own setup, before its bounds start.
SETUP_ALLOWANCE_S = 3.0


def _node() -> Path:
    """The stand-in browser's program, as its own command line names it."""

    return Path(os.path.realpath(require_node()))


def _running(pid: int) -> bool:
    try:
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        return True
    return bool(state) and not state.startswith("Z")


def _gone(pid: int, within_s: float = 2.0) -> bool:
    """Whether *pid* has stopped running, given a moment for a killed process to exit."""

    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        if not _running(pid):
            return True
        time.sleep(0.05)
    return False


def _kill(pid: int) -> None:
    with suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


def _run(profile: Path, pid_file: Path, mode: str, child: str = CHILD) -> tuple[bool, int]:
    run = run_in_own_group(
        [str(_node()), "-e", PARENT, child, str(profile), str(pid_file), mode],
        timeout_s=DEADLINE_S,
        env=os.environ,
    )
    assert pid_file.exists(), f"the parent never started its child: {run.stderr}"
    return run.timed_out, int(pid_file.read_text(encoding="utf-8"))


SignalCall = tuple[int, int, bool]


def _record_group_signals(monkeypatch: pytest.MonkeyPatch) -> list[SignalCall]:
    """Each ``killpg`` the module sends: the group, the signal, and whether the group's
    leader was, at that moment, a child of this process still unreaped."""

    calls: list[SignalCall] = []
    real = os.killpg

    def recording(group: int, signum: int) -> None:
        calls.append((group, signum, _unreaped(group)))
        real(group, signum)

    monkeypatch.setattr(pg.os, "killpg", recording)
    return calls


def _unreaped(pid: int) -> bool:
    if hasattr(os, "waitid"):
        try:
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            return False
        return True
    from metabrowser.git.children import child_pids

    listed = child_pids()
    return listed is not None and pid in listed


# ── The group ─────────────────────────────────────────────────────────────


def test_a_run_stopped_at_its_deadline_stops_its_whole_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    with owned_profile("metab-test-group-", browser=_node()) as profile:
        timed_out, child = _run(profile, tmp_path / "child.pid", "hang")
        assert timed_out
        assert _gone(child), "the child outlived the run that was stopped at its deadline"
    # One stop, and each of its signals sent while the leader still held the group's ID.
    assert [signum for _, signum, _ in signals] == [signal.SIGTERM]
    assert all(unreaped for _, _, unreaped in signals), signals


def test_a_run_whose_parent_exits_still_stops_the_child_it_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    with owned_profile("metab-test-group-", browser=_node()) as profile:
        timed_out, child = _run(profile, tmp_path / "child.pid", "exit")
        assert not timed_out
        assert _gone(child), "the child its parent left behind is still running"
    # The parent had exited: its unreaped entry still held the group's ID.
    assert signals and all(unreaped for _, _, unreaped in signals), signals


def test_a_child_that_ignores_sigterm_is_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    with owned_profile("metab-test-group-", browser=_node()) as profile:
        timed_out, child = _run(profile, tmp_path / "child.pid", "hang", STUBBORN)
        assert timed_out
        assert _gone(child), "the child that ignores SIGTERM outlived the stop"
    assert [signum for _, signum, _ in signals] == [signal.SIGTERM, signal.SIGKILL]


def test_a_group_that_already_ended_gets_no_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    run = run_in_own_group([str(_node()), "-e", "0"], timeout_s=DEADLINE_S, env=os.environ)
    assert (run.returncode, run.timed_out) == (0, False)
    assert signals == []


def test_a_group_of_only_zombies_gets_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The leader has exited and is not reaped: its group has no live member. macOS
    answers a signal to such a group with EPERM, which stopped the run before."""

    signals = _record_group_signals(monkeypatch)
    process = subprocess.Popen(
        [str(_node()), "-e", "0"], start_new_session=True, stdout=subprocess.DEVNULL, text=True
    )
    try:
        deadline = time.monotonic() + DEADLINE_S
        while _running(process.pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _running(process.pid), "the leader did not exit"
        stop_group(process)
    finally:
        process.wait(timeout=5)
    assert signals == []


def test_a_reaped_leader_s_group_is_not_signalled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the leader is reaped, its ID can be given to another process that leads a
    group of its own; a stop must refuse rather than signal whatever has the number."""

    signals = _record_group_signals(monkeypatch)
    process = subprocess.Popen([str(_node()), "-e", "0"], start_new_session=True, text=True)
    process.wait(timeout=5)
    with pytest.raises(AssertionError, match="was reaped before its group was stopped"):
        stop_group(process)
    assert signals == []


# ── Browsers outside the group ────────────────────────────────────────────


def test_a_browser_that_left_the_group_is_killed_waited_for_and_reported(
    tmp_path: Path,
) -> None:
    pid_file = tmp_path / "child.pid"
    profiles: list[Path] = []
    with (
        pytest.raises(AssertionError, match="browser processes outlived their group"),
        owned_profile("metab-test-group-", browser=_node()) as profile,
    ):
        profiles.append(profile)
        timed_out, child = _run(profile, pid_file, "leave-group")
        assert not timed_out
        # In a session of its own, the child is out of the group's reach.
        assert _running(child)
    child = int(pid_file.read_text(encoding="utf-8"))
    assert not _running(child), "the escaped browser was not waited for"
    assert not profiles[0].exists()


def test_a_process_that_only_mentions_the_profile_is_left_alone(tmp_path: Path) -> None:
    bystander: subprocess.Popen[str] | None = None
    try:
        with owned_profile("metab-test-group-", browser=_node()) as profile:
            # The same program, naming a file in the profile, but not as its user data
            # directory: an editor or a listing could do as much.
            bystander = subprocess.Popen(
                [str(_node()), "-e", CHILD, "--", str(profile / "Default" / "Preferences")],
                start_new_session=True,
                text=True,
            )
            deadline = time.monotonic() + DEADLINE_S
            while not _running(bystander.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
        assert bystander.poll() is None, "a process that only mentions the profile was killed"
    finally:
        if bystander is not None:
            bystander.kill()
            bystander.wait(timeout=5)


def test_a_process_whose_id_was_reused_is_not_signalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Between the sweep's look and its signal the escapee exits, and its ID goes to
    another process: read again, it starts at another time, and is left alone."""

    real = pg._processes
    looks: list[int] = []

    def renamed(deadline: float) -> list[pg._Process]:
        found = real(deadline)
        looks.append(1)
        if len(looks) != 2:
            return found
        return [
            pg._Process(p.pid, p.ppid, p.pgid, p.state, "Mon Jan  1 00:00:00 2001", p.args)
            for p in found
        ]

    killed: list[int] = []
    monkeypatch.setattr(pg, "_processes", renamed)
    monkeypatch.setattr(pg.os, "kill", lambda pid, signum: killed.append(pid))
    pid_file = tmp_path / "child.pid"
    try:
        with owned_profile("metab-test-group-", browser=_node()) as profile:
            _run(profile, pid_file, "leave-group")
        assert killed == []
    finally:
        # The real os.kill again, for the escapee this test kept alive on purpose.
        monkeypatch.undo()
        _kill(int(pid_file.read_text(encoding="utf-8")))
        assert _gone(int(pid_file.read_text(encoding="utf-8")))


def test_an_escapee_is_gone_before_its_profile_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGKILL is not the exit: the escapee may still be running, and writing its
    profile, for a moment after the signal. Here that moment is 300 ms."""

    real_kill = os.kill

    def late_kill(pid: int, signum: int) -> None:
        threading.Timer(0.3, real_kill, (pid, signum)).start()

    pid_file = tmp_path / "child.pid"
    at_removal: list[bool] = []
    real_rmtree = shutil.rmtree

    def removing(path: Path, ignore_errors: bool = False) -> None:
        at_removal.append(_running(int(pid_file.read_text(encoding="utf-8"))))
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(pg.os, "kill", late_kill)
    monkeypatch.setattr(pg.shutil, "rmtree", removing)
    with (
        pytest.raises(AssertionError, match="browser processes outlived their group"),
        owned_profile("metab-test-group-", browser=_node()) as profile,
    ):
        _run(profile, pid_file, "leave-group")
    assert at_removal == [False], "the profile was removed while its browser still ran"


# ── The profile ──────────────────────────────────────────────────────────


def _failing_sweep(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(deadline: float) -> list[pg._Process]:
        raise subprocess.TimeoutExpired(["ps"], 5)

    monkeypatch.setattr(pg, "_processes", failing)


def test_a_failed_sweep_still_removes_the_profile_and_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _failing_sweep(monkeypatch)
    profiles: list[Path] = []
    with (
        pytest.raises(AssertionError, match="the sweep for browser processes failed") as raised,
        owned_profile("metab-test-group-", browser=_node()) as profile,
    ):
        profiles.append(profile)
        (profile / "Default").mkdir()
    assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)
    assert not profiles[0].exists()


def test_a_failure_in_the_block_keeps_its_own_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _failing_sweep(monkeypatch)
    profiles: list[Path] = []
    with (
        pytest.raises(ValueError, match="the measurement failed") as raised,
        owned_profile("metab-test-group-", browser=_node()) as profile,
    ):
        profiles.append(profile)
        raise ValueError("the measurement failed")
    assert any("the sweep for browser processes failed" in note for note in raised.value.__notes__)
    assert not profiles[0].exists()


# ── Each Chrome test's budget ─────────────────────────────────────────────


def _timeout_of(module: object) -> float:
    marks = getattr(module, "pytestmark", [])
    for mark in marks if isinstance(marks, list) else [marks]:
        if mark.name == "timeout":
            return float(mark.args[0])
    settings = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    suite = re.search(r"^timeout = (\d+)$", settings, re.MULTILINE)
    assert suite is not None
    return float(suite.group(1))


@pytest.mark.parametrize("name", CHROME_TESTS)
def test_a_chrome_test_s_whole_lifecycle_fits_its_timeout(name: str) -> None:
    """Its bounds, the group's stop, its server's stop, and the profile's teardown: the
    timeout ends the whole run when it fires, before any of that cleanup."""

    module = importlib.import_module(name)
    lifecycle = float(module.LIFECYCLE_S)
    assert lifecycle + SETUP_ALLOWANCE_S <= _timeout_of(module), (
        f"{name} can take {lifecycle:g} s, over its {_timeout_of(module):g} s timeout"
    )
