"""Run a child that starts other processes, and leave none of them running afterwards.

A Node script that drives a headless Chrome starts Chrome and its helpers as its own
children. Killing Node alone, as ``subprocess.run`` does at its timeout, leaves them
running with their profile on disk. Here the child leads a process group of its own,
which the processes it spawns join, and the whole group is stopped however the run
ends: at its deadline, on an error, or on an interrupt.

The profile is the caller's: ``owned_profile`` creates it, and after the run removes it
and kills anything still naming it, which would be a process that left the group.
``tests/test_process_group.py`` holds both on stand-ins for Chrome, which need no
browser.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from pathlib import Path

# Stopping a group: SIGTERM and this long to exit, then SIGKILL and this long. Chrome
# and Node exit on SIGTERM well inside the first.
TERM_GRACE_S = 3.0
KILL_GRACE_S = 2.0


@dataclass(frozen=True, slots=True)
class GroupRun:
    """How a run in its own process group ended."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


def stop_group(process: subprocess.Popen[str]) -> None:
    """Stop every process in the group *process* leads: SIGTERM, then SIGKILL, each bounded.

    A group that is already empty, as after a run that closed its own browser, gets no
    signal at all.
    """

    group = process.pid
    for signum, grace in ((signal.SIGTERM, TERM_GRACE_S), (signal.SIGKILL, KILL_GRACE_S)):
        try:
            os.killpg(group, signum)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            # Reap the leader: until it is reaped its exit leaves it in the group.
            process.poll()
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
    raise AssertionError(f"process group {group} outlived SIGKILL by {KILL_GRACE_S:g}s")


def run_in_own_group(argv: list[str], *, timeout_s: float, env: Mapping[str, str]) -> GroupRun:
    """Run *argv* as the leader of a new process group, and stop the whole group after.

    The group is stopped however this returns: at the deadline, on an error, or on an
    interrupt.
    """

    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(env),
        start_new_session=True,
    )
    timed_out = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_group(process)
            # Every process that could hold the pipes open was in the group.
            stdout, stderr = process.communicate(timeout=KILL_GRACE_S)
    finally:
        stop_group(process)
    return GroupRun(process.returncode, stdout, stderr, timed_out)


def kill_processes_naming(path: Path) -> list[str]:
    """Kill any process whose command line still names *path*; return what was found."""

    listed = subprocess.run(
        ["ps", "-A", "-ww", "-o", "pid=,args="],
        capture_output=True,
        check=True,
        text=True,
        timeout=5,
    ).stdout
    found = [line.strip() for line in listed.splitlines() if str(path) in line]
    for line in found:
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(line.split()[0]), signal.SIGKILL)
    return found


@contextlib.contextmanager
def owned_profile(prefix: str) -> Generator[Path]:
    """A browser profile directory the caller owns, removed once the run has stopped.

    On the way out it kills any process whose command line still names the profile, and
    removes the profile. Leaving normally, it then fails if there was such a process,
    which escaped the run's process group, so it neither leaks nor passes unseen; leaving
    on an exception, it lets that exception stand.
    """

    profile = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield profile
    finally:
        survivors = kill_processes_naming(profile)
        shutil.rmtree(profile, ignore_errors=True)
    assert not profile.exists(), f"the browser profile {profile} was not removed"
    assert not survivors, f"processes outlived their group: {survivors}"
