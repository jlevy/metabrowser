"""A run in its own process group leaves nothing running, however it ends.

The Chrome tests (``test_folder_overview_alignment.py``, ``test_transitions_instrument.py``,
``test_github_pull_header_chrome.py``, ``test_staged_fonts_chrome.py``) run a Node script
that starts Chrome and its helpers. Here a Node parent starts a
long-lived child that stands in for Chrome, naming the profile on its command line as
Chrome does, so the cleanup in ``tests/process_group.py`` is held without a browser: a
run stopped at its deadline, a run whose parent exits and leaves its child behind, and a
child that left the group, which ``owned_profile`` kills and reports.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.process_group import owned_profile, run_in_own_group
from tests.required_tools import require_node

# The stand-in for Chrome: it runs until it is killed, and names the profile it was given.
CHILD = "setInterval(() => {}, 1000);"
# The parent starts the child, writes the child's pid, and then hangs or exits.
PARENT = """
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const [child, profile, pidFile, mode] = process.argv.slice(1);
const started = spawn(process.execPath, ["-e", child, profile], {
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
# stopped here only in the hanging case.
DEADLINE_S = 5.0


def _gone(pid: int, within_s: float = 2.0) -> bool:
    """Whether *pid* has exited, given a moment for a killed process to be reaped."""

    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _run(profile: Path, pid_file: Path, mode: str) -> tuple[bool, int]:
    run = run_in_own_group(
        [require_node(), "-e", PARENT, CHILD, str(profile), str(pid_file), mode],
        timeout_s=DEADLINE_S,
        env=os.environ,
    )
    assert pid_file.exists(), f"the parent never started its child: {run.stderr}"
    return run.timed_out, int(pid_file.read_text(encoding="utf-8"))


def test_a_run_stopped_at_its_deadline_stops_its_whole_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    with owned_profile("metab-test-group-") as profile:
        timed_out, child = _run(profile, pid_file, "hang")
        assert timed_out
        assert _gone(child), "the child outlived the run that was stopped at its deadline"
    assert not profile.exists()


def test_a_run_whose_parent_exits_still_stops_the_child_it_left(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    with owned_profile("metab-test-group-") as profile:
        timed_out, child = _run(profile, pid_file, "exit")
        assert not timed_out
        assert _gone(child), "the child its parent left behind is still running"
    assert not profile.exists()


def test_a_process_that_left_the_group_is_killed_and_reported(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    profiles: list[Path] = []
    with (
        pytest.raises(AssertionError, match="processes outlived their group"),
        owned_profile("metab-test-group-") as profile,
    ):
        profiles.append(profile)
        timed_out, child = _run(profile, pid_file, "leave-group")
        assert not timed_out
        # In a session of its own, the child is out of the group's reach.
        assert not _gone(child, within_s=0.5)
    assert _gone(int(pid_file.read_text(encoding="utf-8")))
    assert not profiles[0].exists()
