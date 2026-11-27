"""A run in its own process group leaves nothing running, however it ends.

The Chrome tests (``CHROME_TESTS`` below, every module that uses ``chrome_profile``)
run a Node script that starts Chrome and its helpers. Stopping that script's process group is what stops
them, so this holds:

- that Chrome keeps every process it starts for a session in the group, both ways the
  tests launch it (``tests/dom/chrome-group-probe.mjs``);
- with Node stand-ins for Chrome, that a run stopped at its deadline, a parent that exits
  and leaves its child or an orphaned helper behind, and a child that ignores SIGTERM all
  end with nothing of the group running, even when the process table cannot be read or
  the run fails while starting its readers;
- that every signal to the group is sent while its leader is unreaped, so the group ID is
  still the run's, and that a group with no live member, or only zombies, gets none;
- that a process still naming the profile after the run is reported and not signalled,
  wherever its path has spaces, and that the profile is removed even when the look fails;
- that each teardown keeps to the time its callers reserve for it, on its slow paths
  too, and that each Chrome test's whole lifecycle fits under its timeout.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

import tests.process_group as pg
from tests.process_group import owned_profile, run_in_own_group, stop_group
from tests.required_tools import require_chrome, require_node

# The serial tier (tests/suite_tiers.py): every stop and teardown here is timed against
# the time its callers reserve, past it by SLACK_S at most, so beside other workers it
# would time the machine. Its one Chrome test is in the Chrome tier, which is serial too.
# Beside three busy-looping processes on a 4-processor machine its six timing tests
# still passed, in 48 s against 49 s alone (2026-11-17), so the slack holds against
# processor load alone; workers start Node, Git, and ps processes too, which no run has
# measured beside it.
pytestmark = pytest.mark.serial(
    reason="times each stop and teardown to within SLACK_S of its reserved time"
)

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "dom" / "chrome-group-probe.mjs"
# The stand-in for a browser process: it runs until it is killed. Started with
# `-- --user-data-dir=…`, its command line names the profile as Chrome's does.
CHILD = "setInterval(() => {}, 1000);"
# One that stays up through SIGTERM, which only SIGKILL stops.
STUBBORN = "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);"
# The parent starts the child and writes its pid, then hangs or exits. "orphan" starts it
# through a shell that exits at once, so the child is reparented, names no profile, and
# is in the group only.
PARENT = """
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const [child, profile, pidFile, mode] = process.argv.slice(1);
if (mode === "orphan") {
  spawnSync("/bin/sh", ["-c", '"$0" -e "$1" & echo $! > "$2"', process.execPath, child, pidFile], {
    stdio: "ignore",
  });
} else {
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
}
"""
# A parent whose child leaves the group but keeps the output pipes open.
HOLDING = """
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const [child, pidFile] = process.argv.slice(1);
const started = spawn(process.execPath, ["-e", child], { stdio: "inherit", detached: true });
fs.writeFileSync(pidFile, String(started.pid));
setInterval(() => {}, 1000);
"""
# Long enough for Node to start and write the pid file on a loaded machine; the run is
# stopped here only in the hanging cases.
DEADLINE_S = 5.0
# How far past its reserved time a teardown may run: a thread switch and a last ``ps``.
SLACK_S = 0.5
# Every module that uses ``chrome_profile``, which a check below holds, but this one and
# tests/test_suite_tiers.py, whose Chrome tests are probes of the harness with their own
# bounds.
CHROME_TESTS = (
    "tests.test_agents_views_chrome",
    "tests.test_changed_file_rows_chrome",
    "tests.test_checkout_ref_selector_chrome",
    "tests.test_chrome_starts",
    "tests.test_control_chords_chrome",
    "tests.test_diff_current_chrome",
    "tests.test_diff_file_bar_chrome",
    "tests.test_diff_hunk_gap_chrome",
    "tests.test_diff_markdown_fold_chrome",
    "tests.test_diff_markdown_spacing_chrome",
    "tests.test_diff_structured_chrome",
    "tests.test_document_print_chrome",
    "tests.test_event_log_details_chrome",
    "tests.test_event_log_view_chrome",
    "tests.test_table_view_chrome",
    "tests.test_files_tab_chrome",
    "tests.test_files_totals_stable_chrome",
    "tests.test_folder_home_chrome",
    "tests.test_folder_overview_alignment",
    "tests.test_git_commit_summary_chrome",
    "tests.test_github_guided_review_chrome",
    "tests.test_github_pull_core_markdown_chrome",
    "tests.test_github_pull_header_chrome",
    "tests.test_github_pull_text_chrome",
    "tests.test_github_pull_timeline_chrome",
    "tests.test_github_pulls_readiness_chrome",
    "tests.test_github_pulls_row_lines_chrome",
    "tests.test_github_pulls_stack_lines_chrome",
    "tests.test_github_pulls_stacks_chrome",
    "tests.test_github_stack_page_chrome",
    "tests.test_inert_render_refusal_chrome",
    "tests.test_link_card_chrome",
    "tests.test_markdown_badges_chrome",
    "tests.test_markdown_diagrams_chrome",
    "tests.test_markdown_github_layout_chrome",
    "tests.test_menu_dismissal_chrome",
    "tests.test_nav_collapse_chrome",
    "tests.test_nav_metadata_chrome",
    "tests.test_nav_reveal_chrome",
    "tests.test_overview_label_column_chrome",
    "tests.test_overview_legend_hover_chrome",
    "tests.test_overview_readme_toc_chrome",
    "tests.test_page_header_chrome",
    "tests.test_pdf_preview_chrome",
    "tests.test_prose_faces_chrome",
    "tests.test_raw_profile_cache_chrome",
    "tests.test_reading_column_chrome",
    "tests.test_ref_selector_long_list_chrome",
    "tests.test_ref_selector_pulls_chrome",
    "tests.test_root_kind_mark_chrome",
    "tests.test_shortcut_strip_chrome",
    "tests.test_staged_fonts_chrome",
    "tests.test_title_prefix_chrome",
    "tests.test_transitions_instrument",
    "tests.test_treemap_containment_chrome",
    "tests.test_treemap_legend_hover_chrome",
    "tests.test_type_scale_chrome",
    "tests.test_view_header_chrome",
)
CHROME_TESTS_EXEMPT = ("tests.test_process_group", "tests.test_suite_tiers")
# Creating the profile and the test's own setup, before its bounds start.
SETUP_ALLOWANCE_S = 3.0


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


def _wait_for(path: Path) -> int:
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        with suppress(ValueError, FileNotFoundError):
            return int(path.read_text(encoding="utf-8"))
        time.sleep(0.02)
    raise AssertionError(f"no pid in {path}")


def _parent(child: str, profile: Path, pid_file: Path, mode: str) -> list[str]:
    return [require_node(), "-e", PARENT, child, str(profile), str(pid_file), mode]


def _run(profile: Path, pid_file: Path, mode: str, child: str = CHILD) -> tuple[bool, int]:
    run = run_in_own_group(
        _parent(child, profile, pid_file, mode), timeout_s=DEADLINE_S, env=os.environ
    )
    assert pid_file.exists(), f"the parent never started its child: {run.stderr}"
    return run.timed_out, _wait_for(pid_file)


SignalCall = tuple[int, int, bool]


def _record_group_signals(monkeypatch: pytest.MonkeyPatch) -> list[SignalCall]:
    """Each ``killpg`` the module sends: the group, the signal, and whether the group's
    leader was, at that moment, a child of this process still unreaped."""

    calls: list[SignalCall] = []
    real = os.killpg

    def recording(group: int, signum: int) -> None:
        # Signal 0 only asks whether the group has a member.
        if signum != 0:
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


def _capture_leaders(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[str]]:
    """Every process ``run_in_own_group`` starts, kept for the test to inspect."""

    started: list[subprocess.Popen[str]] = []
    real = subprocess.Popen

    def popen(*args: Any, **kwargs: Any) -> subprocess.Popen[str]:
        process: subprocess.Popen[str] = real(*args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(pg.subprocess, "Popen", popen)
    return started


# ── The group ─────────────────────────────────────────────────────────────


def test_a_run_stopped_at_its_deadline_stops_its_whole_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    with owned_profile("metab-test-group-") as profile:
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
    with owned_profile("metab-test-group-") as profile:
        timed_out, child = _run(profile, tmp_path / "child.pid", "exit")
        assert not timed_out
        assert _gone(child), "the child its parent left behind is still running"
    # The parent had exited: its unreaped entry still held the group's ID.
    assert signals and all(unreaped for _, _, unreaped in signals), signals


def test_an_orphaned_helper_that_names_no_profile_is_stopped(tmp_path: Path) -> None:
    """A helper whose parent exited is reparented, and found by no ancestry and no
    profile argument; it is still in the group, which is what stops it."""

    with owned_profile("metab-test-group-") as profile:
        _, helper = _run(profile, tmp_path / "helper.pid", "orphan")
        assert _gone(helper), "the orphaned helper outlived its group's stop"


def test_a_child_that_ignores_sigterm_is_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signals = _record_group_signals(monkeypatch)
    with owned_profile("metab-test-group-") as profile:
        timed_out, child = _run(profile, tmp_path / "child.pid", "hang", STUBBORN)
        assert timed_out
        assert _gone(child), "the child that ignores SIGTERM outlived the stop"
    assert [signum for _, signum, _ in signals] == [signal.SIGTERM, signal.SIGKILL]


def _read_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop groups as Linux does, by the process table: macOS stops need none (below), so
    the tests of a slow or failed look make it the way to tell live from zombie."""

    monkeypatch.setattr(pg, "_ZOMBIE_GROUP_REFUSES_SIGNALS", False)


def _no_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading the process table fails the test: a ``ps`` of every process took 1.3 to
    2.7 s beside 250 busy loops, and a stop of a group with nothing live in it must not
    wait on one. Only macOS answers signal 0 to a group of zombies with an error; elsewhere
    the table tells them from live processes, so it is read."""

    if sys.platform != "darwin":
        return

    def unread(deadline: float) -> list[pg._Process]:
        raise AssertionError("the process table was read for a group with no live member")

    monkeypatch.setattr(pg, "_processes", unread)


@pytest.mark.macos_tier
@pytest.mark.skipif(sys.platform != "darwin", reason="Linux answers a zombie like a live process")
def test_a_live_group_is_stopped_without_reading_the_process_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stop's looks at the table were what failed a Chrome test at 3 s beside heavy
    load; on macOS signal 0 answers whether the group has a live member."""

    _no_table(monkeypatch)
    pid_file = tmp_path / "child.pid"
    run = run_in_own_group(
        _parent(STUBBORN, tmp_path, pid_file, "hang"), timeout_s=1.0, env=os.environ
    )
    assert run.timed_out
    assert _gone(_wait_for(pid_file))


def test_a_group_that_already_ended_gets_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    signals = _record_group_signals(monkeypatch)
    _no_table(monkeypatch)
    run = run_in_own_group([require_node(), "-e", "0"], timeout_s=DEADLINE_S, env=os.environ)
    assert (run.returncode, run.timed_out) == (0, False)
    assert signals == []


def test_a_group_of_only_zombies_gets_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The leader has exited and is not reaped: its group has no live member. macOS
    answers a signal to such a group with EPERM."""

    signals = _record_group_signals(monkeypatch)
    process = subprocess.Popen(
        [require_node(), "-e", "0"], start_new_session=True, stdout=subprocess.DEVNULL, text=True
    )
    try:
        deadline = time.monotonic() + DEADLINE_S
        while _running(process.pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _running(process.pid), "the leader did not exit"
        _no_table(monkeypatch)
        stop_group(process)
    finally:
        process.wait(timeout=5)
    assert signals == []


def test_a_reaped_leader_s_group_is_not_signalled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the leader is reaped, its ID can be given to another process that leads a
    group of its own; a stop must refuse rather than signal whatever has the number."""

    signals = _record_group_signals(monkeypatch)
    process = subprocess.Popen([require_node(), "-e", "0"], start_new_session=True, text=True)
    process.wait(timeout=5)
    with pytest.raises(AssertionError, match="was reaped before its group was stopped"):
        stop_group(process)
    assert signals == []


def test_a_failed_look_still_kills_the_whole_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The process table cannot be read: the group is still the run's, and is killed
    outright, child that ignores SIGTERM and all; the error is kept."""

    leaders = _capture_leaders(monkeypatch)

    def unreadable(deadline: float) -> list[pg._Process]:
        raise subprocess.TimeoutExpired(["ps"], 5)

    monkeypatch.setattr(pg, "_processes", unreadable)
    _read_the_table(monkeypatch)
    pid_file = tmp_path / "child.pid"
    with pytest.raises(subprocess.TimeoutExpired):
        run_in_own_group(
            _parent(STUBBORN, tmp_path, pid_file, "hang"), timeout_s=DEADLINE_S, env=os.environ
        )
    assert _gone(_wait_for(pid_file)), "a child of the group outlived a stop that could not look"
    assert leaders[0].returncode is not None, "the leader was not reaped"


def test_a_failure_while_its_readers_start_still_stops_and_reaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaders = _capture_leaders(monkeypatch)
    pid_file = tmp_path / "child.pid"
    real = threading.Thread
    starts: list[int] = []

    class FailingSecondStart(real):  # type: ignore[misc, valid-type]
        def start(self) -> None:
            starts.append(1)
            if len(starts) == 2:
                # Once the group has its child, so that there is a descendant to stop.
                _wait_for(pid_file)
                raise RuntimeError("the second reader could not start")
            super().start()

    monkeypatch.setattr(pg.threading, "Thread", FailingSecondStart)
    with pytest.raises(RuntimeError, match="the second reader could not start"):
        run_in_own_group(
            _parent(CHILD, tmp_path, pid_file, "hang"), timeout_s=DEADLINE_S, env=os.environ
        )
    assert _gone(_wait_for(pid_file)), "the group's child outlived a failed start"
    assert leaders[0].returncode is not None, "the leader was not reaped"


# ── The time a teardown takes ─────────────────────────────────────────────


def _slow_looks(monkeypatch: pytest.MonkeyPatch, hang: bool) -> None:
    """Each look at the process table takes 0.3 s, or, with *hang*, the whole time it is
    given and then fails."""

    real = pg._processes
    _read_the_table(monkeypatch)

    def slow(deadline: float) -> list[pg._Process]:
        if hang:
            time.sleep(max(pg.SCAN_FLOOR_S, deadline - time.monotonic()))
            raise subprocess.TimeoutExpired(["ps"], 0)
        time.sleep(0.3)
        return real(deadline)

    monkeypatch.setattr(pg, "_processes", slow)


@pytest.mark.parametrize("hang", [False, True], ids=["slow looks", "hanging looks"])
def test_a_stop_keeps_to_its_reserved_time(
    hang: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _slow_looks(monkeypatch, hang)
    pid_file = tmp_path / "child.pid"
    started = time.monotonic()
    with suppress(subprocess.TimeoutExpired):
        run_in_own_group(
            _parent(STUBBORN, tmp_path, pid_file, "hang"), timeout_s=DEADLINE_S, env=os.environ
        )
    teardown = time.monotonic() - started - DEADLINE_S
    assert teardown <= pg.GROUP_STOP_S + SLACK_S, f"the stop took {teardown:.1f} s"
    assert _gone(_wait_for(pid_file))


def test_a_stop_keeps_to_its_reserved_time_with_a_pipe_held_outside_the_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The looks hang, and a process outside the group holds the output pipes open, so
    neither the stop nor the readers end on their own: one deadline still ends both."""

    _slow_looks(monkeypatch, hang=True)
    pid_file = tmp_path / "child.pid"
    started = time.monotonic()
    try:
        with suppress(subprocess.TimeoutExpired):
            run_in_own_group(
                [require_node(), "-e", HOLDING, CHILD, str(pid_file)],
                timeout_s=DEADLINE_S,
                env=os.environ,
            )
        teardown = time.monotonic() - started - DEADLINE_S
        assert teardown <= pg.GROUP_STOP_S + SLACK_S, f"the stop took {teardown:.1f} s"
    finally:
        _kill(_wait_for(pid_file))


def test_a_profile_teardown_keeps_to_its_reserved_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_looks(monkeypatch, hang=True)
    started = 0.0
    profiles: list[Path] = []
    with (
        pytest.raises(AssertionError, match="the look for processes on the profile failed"),
        owned_profile("metab-test-group-") as profile,
    ):
        profiles.append(profile)
        started = time.monotonic()
    teardown = time.monotonic() - started
    assert teardown <= pg.PROFILE_TEARDOWN_S + SLACK_S, f"the teardown took {teardown:.1f} s"
    assert not profiles[0].exists()


# ── What still names the profile ──────────────────────────────────────────


def test_a_process_still_naming_the_profile_is_reported_and_left_running(
    tmp_path: Path,
) -> None:
    """A browser that left the group is not signalled: it fails the test, by name, and
    stays for someone to look at; the profile is removed all the same."""

    pid_file = tmp_path / "child.pid"
    profiles: list[Path] = []
    try:
        with (
            pytest.raises(AssertionError, match="still name its profile, left running"),
            owned_profile("metab-test-group-") as profile,
        ):
            profiles.append(profile)
            timed_out, _ = _run(profile, pid_file, "leave-group")
            assert not timed_out
        child = _wait_for(pid_file)
        assert _running(child), "a process outside the group was signalled"
        assert not profiles[0].exists()
    finally:
        _kill(_wait_for(pid_file))


def test_a_profile_under_a_path_with_spaces_is_still_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spaced = tmp_path / "browser profiles"
    spaced.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spaced))
    pid_file = tmp_path / "child.pid"
    try:
        with (
            pytest.raises(AssertionError, match="still name its profile"),
            owned_profile("metab test group ") as profile,
        ):
            assert " " in str(profile)
            _run(profile, pid_file, "leave-group")
    finally:
        _kill(_wait_for(pid_file))


def test_a_failed_look_still_removes_the_profile_and_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(deadline: float) -> list[pg._Process]:
        raise subprocess.TimeoutExpired(["ps"], 5)

    monkeypatch.setattr(pg, "_processes", failing)
    profiles: list[Path] = []
    with (
        pytest.raises(
            AssertionError, match="the look for processes on the profile failed"
        ) as raised,
        owned_profile("metab-test-group-") as profile,
    ):
        profiles.append(profile)
        (profile / "Default").mkdir()
    assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)
    assert not profiles[0].exists()


def test_a_failure_in_the_block_keeps_its_own_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(deadline: float) -> list[pg._Process]:
        raise subprocess.TimeoutExpired(["ps"], 5)

    monkeypatch.setattr(pg, "_processes", failing)
    profiles: list[Path] = []
    with (
        pytest.raises(ValueError, match="the measurement failed") as raised,
        owned_profile("metab-test-group-") as profile,
    ):
        profiles.append(profile)
        raise ValueError("the measurement failed")
    assert any("the look for processes on the profile failed" in n for n in raised.value.__notes__)
    assert not profiles[0].exists()


# ── Where Chrome's processes live ─────────────────────────────────────────


def _outside_the_group(snapshot: list[dict[str, Any]], node: int, profile: Path) -> list[str]:
    """The processes Node started, followed by parent, that are not in its group; and any
    live process outside it whose command line names a profile under *profile*."""

    children: dict[int, list[dict[str, Any]]] = {}
    for row in snapshot:
        children.setdefault(int(row["ppid"]), []).append(row)
    outside: list[str] = []
    pending = [node]
    while pending:
        for row in children.get(pending.pop(), []):
            pending.append(int(row["pid"]))
            if row["pgid"] != node:
                outside.append(f"{row['pid']} (group {row['pgid']}): {str(row['args'])[:160]}")
    outside.extend(
        f"{row['pid']} (group {row['pgid']}) names the profile: {str(row['args'])[:160]}"
        for row in snapshot
        if row["pgid"] != node and str(profile) in str(row["args"])
    )
    return outside


# The probe's bound, above its two Chrome starts' bounds and its two closes' waits
# together, 76 s: each start may take 30 s (START_BOUND_MS in tests/dom/chrome-session.mjs,
# endpointTimeoutMs in launchBrowser), and each close waits for a Chrome that on a Mac does
# not leave promptly (stopChrome 5 s after SIGTERM and 5 s after SIGKILL; launchBrowser
# 3 s for Browser.close and 3 s more). Measured on a 10-core Mac on 2026-11-23, three
# probes at once at a load average near 180 took 17.6 to 18.1 s, 8.5 s of it those closes'
# waits; six at once, the load rising from 200 to 300, took 26.3 to 27.4 s, their Chrome
# starts 6.4 to 9.1 s and 4.7 to 5.1 s. The former 40 s was under those bounds, and the
# probe printed nothing until it ended, so a run stopped there failed with an empty
# message (mb-hsul). The probe writes each step's end to stderr, which a failure shows.
PROBE_BUDGET_S = 90


@pytest.mark.timeout(PROBE_BUDGET_S + pg.GROUP_STOP_S + pg.PROFILE_TEARDOWN_S + 10)
def test_chrome_keeps_its_processes_in_the_launched_group(chrome_profile: Path) -> None:
    """Stopping the group stops Chrome only if Chrome stays in it. Chrome's crash reporter
    leaves: it is reparented and leads a group of its own, but it names no test profile
    and exits with the browser it watches, so it is not looked for here."""

    run = run_in_own_group(
        [require_node(), str(PROBE)],
        timeout_s=PROBE_BUDGET_S,
        env={**os.environ, "CHROME_BIN": require_chrome(), "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not run.timed_out, f"the probe ran past its {PROBE_BUDGET_S} s:\n{run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    probe = json.loads(run.stdout)
    for launcher, snapshot in probe["snapshots"].items():
        outside = _outside_the_group(snapshot, probe["node"], chrome_profile)
        assert not outside, f"{launcher}: {outside}"


STOP_CHROME = """
import { spawn } from "node:child_process";
import { stopChrome } from %s;
// A browser that ignores SIGTERM, and a helper in its group that inherits its stderr
// pipe and outlives it, as Chrome's helpers do: only destroying the pipe at the close
// lets this process exit while the helper still holds the other end.
const helper = "setTimeout(() => {}, 30000);";
const stubborn = `process.on('SIGTERM', () => {});
require('node:child_process').spawn(process.execPath, ['-e', ${JSON.stringify(helper)}],
  { stdio: ['ignore', 'ignore', 'inherit'] });
setInterval(() => {}, 1000);`;
const chrome = spawn(process.execPath, ["-e", stubborn], { stdio: ["ignore", "ignore", "pipe"] });
chrome.stderr.on("data", () => {});
const exited = new Promise((resolve) => chrome.once("exit", resolve));
await new Promise((resolve) => setTimeout(resolve, 500));
const began = Date.now();
await stopChrome(chrome, exited, 700);
console.log(JSON.stringify({ ms: Date.now() - began, signal: chrome.signalCode }));
"""


def test_a_chrome_that_ignores_sigterm_is_killed_at_its_close_and_does_not_hold_the_session(
    tmp_path: Path,
) -> None:
    """The close SIGKILLs a browser still up after its wait, and the session's process then
    exits: waiting only held it until the test's bound while Chrome took 5 to 35 s to leave
    after SIGTERM at a load average of 110 to 230."""

    session = (ROOT / "tests" / "dom" / "chrome-session.mjs").as_uri()
    script = tmp_path / "stop-chrome.mjs"
    script.write_text(STOP_CHROME % json.dumps(session), encoding="utf-8")
    started = time.monotonic()
    run = run_in_own_group([require_node(), str(script)], timeout_s=DEADLINE_S, env=os.environ)
    assert not run.timed_out and run.returncode == 0, run.stderr or run.stdout
    stopped = json.loads(run.stdout)
    assert stopped["signal"] == "SIGKILL", stopped
    assert time.monotonic() - started < DEADLINE_S, "the session's process outlived its close"


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


def test_every_module_that_drives_chrome_has_its_lifecycle_checked() -> None:
    """A module left out of CHROME_TESTS has no check that its bounds fit its timeout;
    five were, until this check."""

    using = {
        f"tests.{path.stem}"
        for path in (ROOT / "tests").glob("test_*.py")
        if "chrome_profile" in path.read_text(encoding="utf-8")
    }
    assert sorted(using - set(CHROME_TESTS) - set(CHROME_TESTS_EXEMPT)) == []
    assert sorted(set(CHROME_TESTS) - using) == []


@pytest.mark.parametrize("name", CHROME_TESTS)
def test_a_chrome_test_s_whole_lifecycle_fits_its_timeout(name: str) -> None:
    """Its bounds, the group's stop, its server's stop, and the profile's teardown: the
    timeout ends the whole run when it fires, before any of that cleanup. The stop and
    the teardown keep to these figures on their slow paths (above)."""

    module = importlib.import_module(name)
    lifecycle = float(module.LIFECYCLE_S)
    assert lifecycle + SETUP_ALLOWANCE_S <= _timeout_of(module), (
        f"{name} can take {lifecycle:g} s, over its {_timeout_of(module):g} s timeout"
    )
