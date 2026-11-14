"""Run a child that starts other processes, and leave none of them running afterwards.

A Node script that drives a headless Chrome starts Chrome and its helpers as its own
children. Killing Node alone, as ``subprocess.run`` does at its timeout, leaves them
running with their profile on disk. Here the child leads a process group of its own,
which the processes it spawns join, and the whole group is stopped however the run
ends: at its deadline, on an error, or on an interrupt.

Two rules keep the signals on what the run started:

- The leader is not reaped until its group has been signalled for the last time. An
  exited but unreaped leader keeps its process ID, and with it the group ID, from being
  given to anyone else, so ``killpg`` cannot reach another group that took the number
  (as ``src/metabrowser/git/process.py`` guards its Git groups).
- Outside the group, only a verified browser process is killed: one running the browser
  the test launched, with a ``--user-data-dir`` argument inside the test's profile, and
  that browser's helpers. Its identity is read again just before the signal. Any other
  process that merely mentions the profile is left alone.

The profile is the caller's: ``owned_profile`` creates it, and afterwards stops any
browser that escaped the group, waits for those processes to exit, and removes the
directory whatever else failed. ``tests/test_process_group.py`` holds all of this on
stand-ins for Chrome, which need no browser.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO

# Stopping a group: SIGTERM and this long for its live members to exit, then SIGKILL and
# this long. Chrome and Node exit on SIGTERM well inside the first.
TERM_GRACE_S = 3.0
KILL_GRACE_S = 2.0
# Once the group is down: reaping its leader, and its pipes reaching their end.
REAP_S = 2.0
# The longest a stopped run takes after its own bound: the group's stop and the reap.
GROUP_STOP_S = TERM_GRACE_S + KILL_GRACE_S + REAP_S
# The longest ``owned_profile`` takes after its block: the scans for escaped browser
# processes, the wait for any it kills (ESCAPEE_EXIT_S of it), and the removal.
PROFILE_TEARDOWN_S = 8.0
ESCAPEE_EXIT_S = 2.0
# How often a wait looks again. Each look is one ``ps`` of every process, 20 to 40 ms on
# a 10-core Mac.
_POLL_S = 0.05


@dataclass(frozen=True, slots=True)
class GroupRun:
    """How a run in its own process group ended."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


@dataclass(frozen=True, slots=True)
class _Process:
    pid: int
    ppid: int
    pgid: int
    state: str
    started: str
    args: str

    @property
    def zombie(self) -> bool:
        return self.state.startswith("Z")

    @property
    def identity(self) -> tuple[int, str, str]:
        """The process, as opposed to its ID: a reused ID starts later, running another
        command."""

        return (self.pid, self.started, self.args)


def _processes(deadline: float) -> list[_Process]:
    """Every process, read with one ``ps`` bounded by *deadline*."""

    listed = subprocess.run(
        ["ps", "-A", "-ww", "-o", "pid=,ppid=,pgid=,stat=,lstart=,args="],
        capture_output=True,
        check=True,
        text=True,
        timeout=max(0.5, deadline - time.monotonic()),
    ).stdout
    found: list[_Process] = []
    for line in listed.splitlines():
        # The start time is five fields: weekday, month, day, time, year.
        fields = line.split(None, 9)
        if len(fields) < 9:
            continue
        pid, ppid, pgid, state, *started = fields[:9]
        args = fields[9] if len(fields) > 9 else ""
        found.append(_Process(int(pid), int(ppid), int(pgid), state, " ".join(started), args))
    return found


def _live_members(group: int, deadline: float) -> list[_Process]:
    """The members of *group* still running: a zombie has stopped, whoever reaps it."""

    return [p for p in _processes(deadline) if p.pgid == group and not p.zombie]


def stop_group(process: subprocess.Popen[str]) -> None:
    """Stop every live process in the group *process* leads: SIGTERM, then SIGKILL.

    *process* must not have been reaped yet: its entry is what keeps the group ID its
    own. A group with no live member, as after a run whose browser closed, or one whose
    only members are zombies, gets no signal at all; macOS answers a signal to such a
    group with EPERM.
    """

    if process.returncode is not None:
        raise AssertionError(
            f"the leader of process group {process.pid} was reaped before its group was "
            "stopped, so the group ID may name someone else's group by now"
        )
    group = process.pid
    for signum, grace in ((signal.SIGTERM, TERM_GRACE_S), (signal.SIGKILL, KILL_GRACE_S)):
        deadline = time.monotonic() + grace
        if not _live_members(group, deadline):
            return
        try:
            os.killpg(group, signum)
        except ProcessLookupError:
            return
        except PermissionError:
            # Only a group of zombies, whose last live member exited since the look.
            if not _live_members(group, deadline):
                return
            raise
        while time.monotonic() < deadline:
            if not _live_members(group, deadline):
                return
            time.sleep(_POLL_S)
    live = _live_members(group, time.monotonic() + REAP_S)
    if live:
        raise AssertionError(
            f"process group {group} still runs after SIGKILL: {[p.args[:100] for p in live]}"
        )


def _drain(stream: IO[str], into: list[str]) -> None:
    into.append(stream.read())


def _reap(process: subprocess.Popen[str]) -> None:
    """Reap the leader once its group is down; kill it first if it is somehow still up."""

    try:
        process.wait(timeout=REAP_S)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=REAP_S)


def run_in_own_group(argv: list[str], *, timeout_s: float, env: Mapping[str, str]) -> GroupRun:
    """Run *argv* as the leader of a new process group, and stop the whole group after.

    The group is stopped exactly once, however this returns: at the deadline, on an
    error, or on an interrupt. Its output is read on threads rather than by waiting for
    the leader, so the leader is reaped only after that stop.
    """

    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(env),
        start_new_session=True,
    )
    assert process.stdout is not None and process.stderr is not None
    stdout: list[str] = []
    stderr: list[str] = []
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_s
    timed_out = True
    try:
        for reader in readers:
            reader.join(max(0.0, deadline - time.monotonic()))
        # Both pipes end when the leader exits; one still open means it has not.
        timed_out = any(reader.is_alive() for reader in readers)
    finally:
        try:
            stop_group(process)
        finally:
            _reap(process)
            for reader in readers:
                reader.join(REAP_S)
    return GroupRun(process.returncode, "".join(stdout), "".join(stderr), timed_out)


def _browser_root(browser: Path) -> str:
    """Where the browser's program and its helpers live: a Mac app bundle, or the
    directory of the program it resolves to."""

    real = os.path.realpath(browser)
    bundle = real.find(".app/")
    return real[: bundle + len(".app/")] if bundle >= 0 else os.path.dirname(real) + os.sep


def _names_profile(args: str, profile: str) -> bool:
    """Whether *args* carries a ``--user-data-dir`` that is *profile* or inside it."""

    for token in args.split():
        if token.startswith("--user-data-dir="):
            value = os.path.realpath(token.removeprefix("--user-data-dir="))
            if value == profile or value.startswith(profile + os.sep):
                return True
    return False


def _escapees(processes: list[_Process], profile: str, root: str) -> list[_Process]:
    """The browser processes on *profile*, and their helpers, that are still running."""

    live = [p for p in processes if not p.zombie and p.args.startswith(root)]
    found = [p for p in live if _names_profile(p.args, profile)]
    pids = {p.pid for p in found}
    while helpers := [p for p in live if p.ppid in pids and p.pid not in pids]:
        found.extend(helpers)
        pids.update(p.pid for p in helpers)
    return found


def _stop_escapees(profile: Path, root: str, deadline: float) -> tuple[list[str], list[str]]:
    """Kill the browser processes still on *profile* and wait for them to exit.

    Returns what was killed, and what still runs at the deadline. Each process is read
    again just before its signal and signalled only if it is the same process.
    """

    real = os.path.realpath(profile)
    first = _escapees(_processes(deadline), real, root)
    if not first:
        return [], []
    wanted = {p.identity for p in first}
    current = [p for p in _escapees(_processes(deadline), real, root) if p.identity in wanted]
    for escapee in current:
        with suppress(ProcessLookupError):
            os.kill(escapee.pid, signal.SIGKILL)
    killed = {p.identity for p in current}
    wait_until = min(deadline, time.monotonic() + ESCAPEE_EXIT_S)
    remaining = killed
    while remaining and time.monotonic() < wait_until:
        time.sleep(_POLL_S)
        running = {p.identity for p in _processes(deadline) if not p.zombie}
        remaining = killed & running
    return [p.args[:100] for p in current], [args[:100] for _, _, args in remaining]


@contextmanager
def owned_profile(prefix: str, *, browser: Path) -> Generator[Path]:
    """A browser profile directory the caller owns, removed once the run has stopped.

    On the way out, every *browser* process still on the profile, and its helpers, has
    escaped the run's process group: they are killed, and waited for, before the
    directory is removed. The removal happens whatever else fails. Leaving normally,
    the block then fails on an escapee, a failed sweep, or a directory left behind;
    leaving on an exception, it adds those to that exception's notes and lets it stand.
    """

    profile = Path(tempfile.mkdtemp(prefix=prefix))
    root = _browser_root(browser)
    failure: BaseException | None = None
    try:
        yield profile
    except BaseException as error:
        failure = error
        raise
    finally:
        problems: list[str] = []
        sweep_error: Exception | None = None
        try:
            killed, running = _stop_escapees(profile, root, time.monotonic() + PROFILE_TEARDOWN_S)
            if killed:
                problems.append(f"browser processes outlived their group: {killed}")
            if running:
                problems.append(f"browser processes still run after SIGKILL: {running}")
        except Exception as error:
            sweep_error = error
            problems.append(f"the sweep for browser processes failed: {error!r}")
        finally:
            shutil.rmtree(profile, ignore_errors=True)
            if profile.exists():
                problems.append(f"the browser profile {profile} was not removed")
        if failure is not None:
            for problem in problems:
                failure.add_note(problem)
        elif problems:
            raise AssertionError("; ".join(problems)) from sweep_error
