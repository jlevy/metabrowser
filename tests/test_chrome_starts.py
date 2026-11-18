"""A Chrome start that fails is abandoned, made once more, and reported; the run warms
Chrome up first and summarizes every start.

``tests/dom/chrome-session.mjs`` starts every Chrome the tests drive, in at most
``START_ATTEMPTS`` tries. ``tests/dom/chrome-start-retry.mjs`` drives it against a
stand-in for Chrome's binary: one that hangs without writing a DevTools port and leaves a
helper naming its profile, one that exits at once, and one that is not there. Each failed
start's browser and helpers are gone and its profile removed once the launch returns or
throws, and the error names every start's reason and the end of the last one's stderr.
With a real Chrome behind the stand-in's second start, the retried launch is a working
session. ``tests/chrome_starts.py`` holds the run's warm-up and the summary of starts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests import chrome_starts
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

DRIVER = Path(__file__).resolve().parent / "dom" / "chrome-start-retry.mjs"
# The longest case: the stand-in's 10 s hang, a warm Chrome start under the same bound,
# and the session's close, which gives Chrome 5 s to exit: 10.9 s on a 10-core Mac at a
# load average near 12.
SESSION_TIMEOUT_S = 40
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py); tests/test_process_group.py holds the sum under the limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def _launch(case: str, profiles: Path, stand_in: Path, starts: Path, chrome: str = "") -> Any:
    stand_in.mkdir()
    run = run_in_own_group(
        [require_node(), str(DRIVER), case],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(profiles),
            "STAND_IN": str(stand_in),
            # Its own record, so the stand-in's starts stay out of the run's summary.
            chrome_starts.STARTS_ENV: str(starts),
        },
    )
    assert not run.timed_out, f"ran past {SESSION_TIMEOUT_S} s:\n{run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    result = json.loads(run.stdout)
    result["stderr"] = run.stderr
    result["noted"] = [json.loads(line) for line in starts.read_text().splitlines()]
    return result


def _left_nothing(result: Any) -> None:
    assert result["processesLeft"] == [], "a failed start left processes on its profile"
    assert result["profilesLeft"] == [], "a start's profile was left behind"


def test_a_start_that_never_writes_a_port_is_tried_twice_and_says_so(tmp_path: Path) -> None:
    (tmp_path / "profiles").mkdir()
    result = _launch("hang", tmp_path / "profiles", tmp_path / "stand", tmp_path / "s.jsonl")
    assert not result["ok"]
    assert result["starts"] == 2
    _left_nothing(result)
    reason = "wrote no DevTools port in 1.5 s, still running"
    assert result["error"].startswith(
        f"Chrome did not start in 2 of 2 tries: start 1 {reason}; start 2 {reason}\n"
    ), result["error"]
    assert "stand-in chrome: start 2 hangs" in result["error"]
    assert f"launchChrome: start 1 of 2 {reason}; starting Chrome again" in result["stderr"]
    assert "stand-in chrome: start 1 hangs" in result["stderr"]
    assert [(n["attempt"], n["ok"], n["failure"]) for n in result["noted"]] == [
        (1, False, reason),
        (2, False, reason),
    ]


def test_a_start_that_exits_is_tried_twice_and_says_how_it_exited(tmp_path: Path) -> None:
    (tmp_path / "profiles").mkdir()
    result = _launch("exit", tmp_path / "profiles", tmp_path / "stand", tmp_path / "s.jsonl")
    assert not result["ok"]
    assert result["starts"] == 2
    _left_nothing(result)
    assert "start 1 wrote no DevTools port: exited (3) after" in result["error"]
    assert "start 2 wrote no DevTools port: exited (3) after" in result["error"]
    assert "stand-in chrome: start 2 exits" in result["error"]


def test_a_binary_that_cannot_be_spawned_is_not_tried_again(tmp_path: Path) -> None:
    (tmp_path / "profiles").mkdir()
    result = _launch("missing", tmp_path / "profiles", tmp_path / "stand", tmp_path / "s.jsonl")
    assert not result["ok"]
    _left_nothing(result)
    assert result["error"].startswith("Chrome did not start in 1 of 2 tries: start 1 could not")
    assert "starting Chrome again" not in result["stderr"]
    assert len(result["noted"]) == 1


def test_a_retried_start_is_a_working_session_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    result = _launch(
        "hang-once", chrome_profile, tmp_path / "stand", tmp_path / "s.jsonl", require_chrome()
    )
    assert result["ok"], result["error"]
    assert result["value"] == 42
    assert result["starts"] == 2
    _left_nothing(result)
    assert "launchChrome: start 1 of 2 wrote no DevTools port in 10.0 s" in result["stderr"]
    assert [(n["attempt"], n["ok"]) for n in result["noted"]] == [(1, False), (2, True)]


def test_a_warm_up_that_fails_is_noted_and_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exits = tmp_path / "chrome"
    exits.write_text("#!/bin/sh\necho 'stand-in chrome: exits' >&2\nexit 3\n", encoding="utf-8")
    exits.chmod(0o755)
    monkeypatch.setenv("CHROME_BIN", str(exits))
    chrome_starts.warm_up(tmp_path)
    noted = [json.loads(line) for line in chrome_starts.log_path(tmp_path).read_text().splitlines()]
    assert [(n["test"], n["attempt"], n["ok"]) for n in noted] == [
        (chrome_starts.WARM_UP_LABEL, 1, False)
    ]
    assert noted[0]["failure"].startswith("wrote no DevTools port: exited (3) after")
    summary = chrome_starts.summary(tmp_path)
    assert summary[0] == "chrome starts: 1, 1 failed"
    assert summary[1].startswith(f"  {chrome_starts.WARM_UP_LABEL}: start 1 wrote no DevTools")
    assert summary[2].endswith("stand-in chrome: exits")


def test_the_summary_counts_every_worker_s_starts_and_shows_each_failure(
    tmp_path: Path,
) -> None:
    tail = "".join(f"[+{n}.0 s] line {n}\n" for n in range(20))
    records = [
        {"test": "tests/test_a.py::test_one (call)", "attempt": 1, "ok": True, "ms": 1200},
        {"test": "tests/test_a.py::test_two (call)", "attempt": 1, "ok": False, "ms": 30000,
         "failure": "wrote no DevTools port in 30.0 s, still running", "tail": tail},
        {"test": "tests/test_a.py::test_two (call)", "attempt": 2, "ok": True, "ms": 9800},
    ]  # fmt: skip
    (tmp_path / "popen-gw1").mkdir()
    chrome_starts.log_path(tmp_path).write_text(json.dumps(records[0]) + "\n")
    chrome_starts.log_path(tmp_path / "popen-gw1").write_text(
        "".join(json.dumps(record) + "\n" for record in records[1:]) + '{"test": "cut'
    )
    assert chrome_starts.summary(tmp_path) == [
        "chrome starts: 3, 1 failed; slowest 9.8 s (tests/test_a.py::test_two, start 2); "
        "1 unreadable line(s)",
        "  tests/test_a.py::test_two: start 1 wrote no DevTools port in 30.0 s, still running",
        *(f"    [+{n}.0 s] line {n}" for n in range(8, 20)),
    ]
    assert chrome_starts.summary(tmp_path / "popen-gw1" / "none") == []
