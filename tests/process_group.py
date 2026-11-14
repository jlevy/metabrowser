"""Run a child that starts other processes, and leave none of them running afterwards.

A Node script that drives a headless Chrome starts Chrome and its helpers as its own
children. Killing Node alone, as ``subprocess.run`` does at its timeout, leaves them
running with their profile on disk. Here the child leads a process group of its own,
which the processes it spawns join, and the whole group is stopped however the run
ends: at its deadline, on an error, or on an interrupt.

Stopping the group is the whole mechanism. Chrome keeps every process it starts for a
session in the group: ``tests/test_process_group.py`` measures that on each run, for both
ways the tests launch Chrome. (Its crash reporter leaves, but it names no profile and
exits with the browser.) So nothing outside the group is ever signalled:

- The leader is not reaped until its group has been signalled for the last time. An
  exited but unreaped leader keeps its process ID, and with it the group ID, from being
  given to anyone else, so ``killpg`` cannot reach another group that took the number
  (as ``src/metabrowser/git/process.py`` guards its Git groups).
- After the run, ``owned_profile`` looks for any process still naming the profile it
  gave the run. Such a process escaped the group; it is reported, failing the test, and
  left running for someone to look at.

The profile is the caller's: ``owned_profile`` creates it and removes it whatever else
failed. Every wait in a teardown counts against one deadline, so the teardown fits the
time its caller reserves for it (GROUP_STOP_S, PROFILE_TEARDOWN_S).
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
# The least time one look at the process table is given, even past a deadline: a ``ps``
# of every process took 20 to 40 ms on a 10-core Mac.
SCAN_FLOOR_S = 0.5
# Once the group is down: reaping its leader, and its pipes reaching their end.
REAP_S = 2.0
# The longest a stopped run takes after its own bound: one deadline covers the group's
# stop, a last look that runs past it, the reap, and the readers.
GROUP_STOP_S = TERM_GRACE_S + KILL_GRACE_S + SCAN_FLOOR_S + REAP_S
# The longest ``owned_profile`` takes after its block: one look for processes still on
# the profile, and the removal. Removing the profile a killed session left, 190 files and
# 8.8 MB, took 21 to 31 ms on a 10-core Mac.
SCAN_S = 5.0
REMOVE_S = 2.0
PROFILE_TEARDOWN_S = SCAN_S + REMOVE_S
# How often a wait looks again.
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
    pgid: int
    state: str
    args: str

    @property
    def zombie(self) -> bool:
        return self.state.startswith("Z")


def _processes(deadline: float) -> list[_Process]:
    """Every process, read with one ``ps`` bounded by *deadline* (or SCAN_FLOOR_S)."""

    listed = subprocess.run(
        ["ps", "-A", "-ww", "-o", "pid=,pgid=,stat=,args="],
        capture_output=True,
        check=True,
        text=True,
        timeout=max(SCAN_FLOOR_S, deadline - time.monotonic()),
    ).stdout
    found: list[_Process] = []
    for line in listed.splitlines():
        fields = line.split(None, 3)
        if len(fields) >= 3:
            pid, pgid, state = fields[:3]
            found.append(_Process(int(pid), int(pgid), state, fields[3] if len(fields) > 3 else ""))
    return found


def _live_members(group: int, deadline: float) -> list[_Process]:
    """The members of *group* still running: a zombie has stopped, whoever reaps it."""

    return [p for p in _processes(deadline) if p.pgid == group and not p.zombie]


def stop_group(process: subprocess.Popen[str], *, deadline: float | None = None) -> None:
    """Stop every live process in the group *process* leads: SIGTERM, then SIGKILL.

    *process* must not have been reaped yet: its entry is what keeps the group ID its
    own. A group with no live member, as after a run whose browser closed, or one whose
    only members are zombies, gets no signal at all; macOS answers a signal to such a
    group with EPERM. If the process table cannot be read, the group, still ours, is
    killed outright and the error is raised. Everything finishes by *deadline*, or by
    TERM_GRACE_S and KILL_GRACE_S from now, past it by at most one SCAN_FLOOR_S look.
    """

    if process.returncode is not None:
        raise AssertionError(
            f"the leader of process group {process.pid} was reaped before its group was "
            "stopped, so the group ID may name someone else's group by now"
        )
    group = process.pid
    now = time.monotonic()
    end = deadline if deadline is not None else now + TERM_GRACE_S + KILL_GRACE_S
    phases = ((signal.SIGTERM, min(end, now + TERM_GRACE_S)), (signal.SIGKILL, end))
    try:
        live: list[_Process] = []
        for signum, phase_end in phases:
            live = _live_members(group, phase_end)
            if not live:
                return
            try:
                os.killpg(group, signum)
            except ProcessLookupError:
                return
            except PermissionError:
                # Only zombies, whose last live member exited since the look.
                if not _live_members(group, phase_end):
                    return
                raise
            while live and time.monotonic() < phase_end:
                time.sleep(_POLL_S)
                live = _live_members(group, phase_end)
            if not live:
                return
        raise AssertionError(
            f"process group {group} still runs after SIGKILL: {[p.args[:100] for p in live]}"
        )
    except AssertionError:
        raise
    except BaseException:
        # The table could not be read, or the stop was interrupted. The leader is not
        # reaped, so the group is still the run's: kill all of it, then let the error be.
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(group, signal.SIGKILL)
        raise


def _drain(stream: IO[str], into: list[str]) -> None:
    into.append(stream.read())


def _reap(process: subprocess.Popen[str], deadline: float) -> None:
    """Reap the leader once its group is down; kill it first if it is somehow still up."""

    try:
        process.wait(timeout=max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=SCAN_FLOOR_S)


def run_in_own_group(argv: list[str], *, timeout_s: float, env: Mapping[str, str]) -> GroupRun:
    """Run *argv* as the leader of a new process group, and stop the whole group after.

    From the moment the process exists, the group is stopped exactly once, however this
    returns: at the deadline, on an error, or on an interrupt, including one while its
    output readers start. Its output is read on threads rather than by waiting for the
    leader, so the leader is reaped only after that stop. The stop, the reap, and the
    readers' end take at most GROUP_STOP_S after *timeout_s*.
    """

    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(env),
        start_new_session=True,
    )
    stdout: list[str] = []
    stderr: list[str] = []
    readers: list[threading.Thread] = []
    timed_out = True
    try:
        assert process.stdout is not None and process.stderr is not None
        for stream, into in ((process.stdout, stdout), (process.stderr, stderr)):
            reader = threading.Thread(target=_drain, args=(stream, into), daemon=True)
            reader.start()
            readers.append(reader)
        deadline = time.monotonic() + timeout_s
        for reader in readers:
            reader.join(max(0.0, deadline - time.monotonic()))
        # Both pipes end when the leader exits; one still open means it has not.
        timed_out = any(reader.is_alive() for reader in readers)
    finally:
        teardown_end = time.monotonic() + GROUP_STOP_S
        try:
            stop_group(process, deadline=teardown_end - REAP_S - SCAN_FLOOR_S)
        finally:
            _reap(process, teardown_end)
            for reader in readers:
                reader.join(max(0.0, teardown_end - time.monotonic()))
    return GroupRun(process.returncode, "".join(stdout), "".join(stderr), timed_out)


def _naming(profile: Path, deadline: float) -> list[str]:
    """The live processes whose command line holds *profile*'s path anywhere."""

    path = str(profile)
    return [
        f"{p.pid} (group {p.pgid}): {p.args[:200]}"
        for p in _processes(deadline)
        if not p.zombie and path in p.args
    ]


@contextmanager
def owned_profile(prefix: str) -> Generator[Path]:
    """A browser profile directory the caller owns, removed once the run has stopped.

    On the way out, a process whose command line still holds the profile's path escaped
    the run's process group. It is reported, not signalled. The removal happens
    whatever else fails. Leaving normally, the block then fails on such a process, on a
    failed look, or on a directory left behind; leaving on an exception, it adds those
    to that exception's notes and lets it stand. All of it takes at most
    PROFILE_TEARDOWN_S.
    """

    profile = Path(tempfile.mkdtemp(prefix=prefix))
    failure: BaseException | None = None
    try:
        yield profile
    except BaseException as error:
        failure = error
        raise
    finally:
        problems: list[str] = []
        look_error: Exception | None = None
        try:
            naming = _naming(profile, time.monotonic() + SCAN_S)
            if naming:
                problems.append(
                    "processes outside the run's stopped process group still name its "
                    f"profile, left running: {naming}"
                )
        except Exception as error:
            look_error = error
            problems.append(f"the look for processes on the profile failed: {error!r}")
        finally:
            shutil.rmtree(profile, ignore_errors=True)
            if profile.exists():
                problems.append(f"the browser profile {profile} was not removed")
        if failure is not None:
            for problem in problems:
                failure.add_note(problem)
        elif problems:
            raise AssertionError("; ".join(problems)) from look_error
