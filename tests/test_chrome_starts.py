"""A Chrome start that fails is abandoned and reported, and one whose Chrome exited is made
once more; the run warms Chrome up first and summarizes every start.

``tests/dom/chrome-session.mjs`` starts every Chrome the tests drive, in at most
``START_ATTEMPTS`` tries. ``tests/dom/chrome-start-retry.mjs`` drives it against a
stand-in for Chrome's binary that exits, dies of a signal, hangs, publishes a port that
never answers, lists a page whose socket never answers, or is not there. Each failed
start's browser and helpers are gone and its profile removed once the launch returns or
throws, the error names every start's reason and the end of the last one's stderr, and
only a start whose Chrome exited is made again. With a real Chrome behind the stand-in's
second start, the retried launch is a working session.

``tests/chrome_starts.py`` holds the run's warm-up and the summary of starts. Nested
pytest sessions of this module's ``probe_*`` functions hold the warm-up's wiring in
``tests/conftest.py``: it runs before a run with a Chrome test, and not under
``--collect-only`` or without one, its outcome is on the terminal before the tests', and
each test's starts reach the summary.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests import chrome_starts
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, GroupRun, run_in_own_group
from tests.required_tools import require_chrome, require_node

THIS = Path(__file__).resolve()
ROOT = THIS.parents[1]
DRIVER = THIS.parent / "dom" / "chrome-start-retry.mjs"
SESSION_SCRIPT = THIS.parent / "dom" / "chrome-session.mjs"
# The longest case, a Chrome session held DEFAULT_APPS_HOLD_MS (below) after it starts:
# 8.78 s in a CI job, and 18.6 s on a 10-core Mac at a load average near 400, on
# 2026-11-24. Then a nested session: pytest's start and collection, the warm-up and the
# probe's two starts of a stand-in that exits, 3.7 s on a 10-core Mac at a load average
# near 17. The driver's cases each wait at most two of their own bounds (BOUNDS_MS in the
# driver) and the session's close.
SESSION_TIMEOUT_S = 40
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py); tests/test_process_group.py holds the sum under the limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# A stand-in for Chrome's binary that writes a line to stderr and exits 3.
EXITS = "#!/bin/sh\necho 'stand-in chrome: exits' >&2\nexit 3\n"
# One launch through the session, for the probe; it fails against EXITS.
ONE_LAUNCH = f"""
import {{ launchChrome }} from {json.dumps(SESSION_SCRIPT.as_uri())};
try {{
  await launchChrome(process.env.CHROME_BIN, {{ profiles: process.env.CHROME_PROFILES }});
}} catch (error) {{
  console.error(error.message);
}}
"""


# A new profile installs Google Chrome's default apps from two CRX files that it first
# copies into its temporary directory, and leaves there however it is stopped. The copies
# came 1.5 to 4.2 s after Chrome wrote its DevTools port, in five starts on a 10-core Mac
# at a load average of 360 to 430 on 2026-11-24, so a session that holds its page twice
# the longest of those would see them made. On macOS Chrome takes that directory from
# MAC_CHROMIUM_TMPDIR (base/files/file_util_mac.mm in Chromium), elsewhere from TMPDIR.
DEFAULT_APPS_HOLD_MS = 8400
MAC_TEMPORARY = "MAC_CHROMIUM_TMPDIR"
HELD_LAUNCH = f"""
import {{ launchChrome }} from {json.dumps(SESSION_SCRIPT.as_uri())};
const session = await launchChrome(process.env.CHROME_BIN, {{
  profiles: process.env.CHROME_PROFILES,
}});
await new Promise((resolve) => setTimeout(resolve, {DEFAULT_APPS_HOLD_MS}));
await session.close();
"""


def _stand_in(directory: Path, script: str) -> Path:
    binary = directory / "chrome"
    binary.write_text(script, encoding="utf-8")
    binary.chmod(0o755)
    return binary


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


def _case(tmp_path: Path, case: str) -> Any:
    (tmp_path / "profiles").mkdir()
    return _launch(case, tmp_path / "profiles", tmp_path / "stand", tmp_path / "s.jsonl")


def _left_nothing(result: Any) -> None:
    assert result["processesLeft"] == [], "a failed start left processes on its profile"
    assert result["profilesLeft"] == [], "a start's profile was left behind"


def test_a_start_that_never_writes_a_port_is_not_made_again(tmp_path: Path) -> None:
    result = _case(tmp_path, "hang")
    assert not result["ok"]
    assert result["starts"] == 1
    _left_nothing(result)
    reason = "wrote no DevTools port in 1.5 s, still running"
    assert result["error"].startswith(f"Chrome did not start in 1 try: start 1 {reason}\n")
    assert "stand-in chrome: start 1 hangs" in result["error"]
    assert "starting Chrome again" not in result["stderr"]
    assert [(n["attempt"], n["ok"], n["failure"]) for n in result["noted"]] == [(1, False, reason)]


def test_a_start_that_exits_is_made_again_and_says_how_it_exited(tmp_path: Path) -> None:
    result = _case(tmp_path, "exit")
    assert not result["ok"]
    assert result["starts"] == 2
    _left_nothing(result)
    assert result["error"].startswith("Chrome did not start in 2 tries: start 1 wrote no")
    assert "start 1 wrote no DevTools port: exited (3) after" in result["error"]
    assert "start 2 wrote no DevTools port: exited (3) after" in result["error"]
    assert "stand-in chrome: start 2 exits" in result["error"]
    assert "launchChrome: start 1 of 2 wrote no DevTools port: exited (3)" in result["stderr"]
    assert "stand-in chrome: start 1 exits" in result["stderr"]
    assert [(n["attempt"], n["ok"]) for n in result["noted"]] == [(1, False), (2, False)]


def test_a_start_killed_by_a_signal_says_so_at_once(tmp_path: Path) -> None:
    """The check before this change read only an exit code, so a start that died of a
    signal ran to the start's bound and was reported as one that wrote no port."""

    result = _case(tmp_path, "signal")
    assert not result["ok"]
    assert result["starts"] == 2
    _left_nothing(result)
    assert "start 1 wrote no DevTools port: exited (SIGSEGV) after" in result["error"]
    assert "stand-in chrome: start 2 crashes" in result["error"]


def test_a_port_that_never_answers_ends_at_the_start_s_bound(tmp_path: Path) -> None:
    result = _case(tmp_path, "silent")
    assert not result["ok"]
    assert result["starts"] == 1
    _left_nothing(result)
    assert re.search(
        r"start 1 wrote DevTools port \d+ but gave no page to drive \(TimeoutError: .*\): "
        r"still running at 3\.0 s",
        result["error"],
    ), result["error"]


def test_a_page_socket_that_never_opens_ends_at_the_start_s_bound(tmp_path: Path) -> None:
    result = _case(tmp_path, "socket")
    assert not result["ok"]
    assert result["starts"] == 1
    _left_nothing(result)
    assert re.search(
        r"start 1 opened no socket to its page on DevTools port \d+: still running at 3\.0 s",
        result["error"],
    ), result["error"]


def test_a_binary_that_cannot_be_spawned_is_not_tried_again(tmp_path: Path) -> None:
    result = _case(tmp_path, "missing")
    assert not result["ok"]
    _left_nothing(result)
    assert result["error"].startswith("Chrome did not start in 1 try: start 1 could not be")
    assert "starting Chrome again" not in result["stderr"]
    assert len(result["noted"]) == 1


def test_a_retried_start_is_a_working_session_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    result = _launch(
        "exit-once", chrome_profile, tmp_path / "stand", tmp_path / "s.jsonl", require_chrome()
    )
    assert result["ok"], result["error"]
    assert result["value"] == 42
    assert result["starts"] == 2
    _left_nothing(result)
    assert "launchChrome: start 1 of 2 wrote no DevTools port: exited (3)" in result["stderr"]
    assert [(n["attempt"], n["ok"]) for n in result["noted"]] == [(1, False), (2, True)]


def test_a_session_leaves_no_file_in_chrome_s_temporary_directory(chrome_profile: Path) -> None:
    """A new profile's default apps are not installed (``--disable-default-apps`` in
    ``tests/dom/chrome-session.mjs``), so nothing is copied there to be left behind."""

    # Short, under the system's own, as the path of Chrome's singleton socket in it must
    # be: not tmp_path.
    with tempfile.TemporaryDirectory(prefix="mb-chrome-tmp-") as temporary:
        run = run_in_own_group(
            [require_node(), "--input-type=module", "-e", HELD_LAUNCH],
            timeout_s=SESSION_TIMEOUT_S,
            env={
                **os.environ,
                "CHROME_BIN": require_chrome(),
                "CHROME_PROFILES": str(chrome_profile),
                "TMPDIR": temporary,
                MAC_TEMPORARY: temporary,
            },
        )
        # A Chrome stopped by SIGKILL leaves its singleton's directory, which holds a
        # socket and a link and no file.
        left = [p for p in Path(temporary).rglob("*") if p.is_file() and not p.is_symlink()]
    assert not run.timed_out, f"ran past {SESSION_TIMEOUT_S} s:\n{run.stderr}"
    assert run.returncode == 0, run.stderr or run.stdout
    assert left == [], f"Chrome left files in its temporary directory: {left}"


def _warm_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[Any]]:
    # A short bound, so a regression that hangs fails this test before its timeout.
    monkeypatch.setattr(chrome_starts, "WARM_UP_BOUND_S", 5.0)
    monkeypatch.setenv("CHROME_BIN", str(_stand_in(tmp_path, EXITS)))
    told = chrome_starts.warm_up(tmp_path)
    log = chrome_starts.log_path(tmp_path)
    return told, [json.loads(line) for line in log.read_text().splitlines()]


def test_a_warm_up_that_fails_is_noted_and_told(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    told, noted = _warm_up(tmp_path, monkeypatch)
    assert [(n["test"], n["attempt"], n["ok"]) for n in noted] == [
        (chrome_starts.WARM_UP_LABEL, 1, False)
    ]
    assert noted[0]["failure"].startswith("wrote no DevTools port: exited (3) after")
    assert told[0].startswith(f"{chrome_starts.WARM_UP_LABEL}: start 1 wrote no DevTools")
    assert told[1].endswith("stand-in chrome: exits")
    summary = chrome_starts.summary(tmp_path)
    assert summary[0] == "chrome starts: 1, 1 failed"
    assert summary[1:] == [f"  {line}" for line in told]


def test_a_warm_up_that_exits_without_a_record_is_noted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "warm-up.mjs"
    script.write_text("console.error('no module here'); process.exit(4);\n", encoding="utf-8")
    monkeypatch.setattr(chrome_starts, "WARM_UP", script)
    told, noted = _warm_up(tmp_path, monkeypatch)
    assert [n["failure"] for n in noted] == ["exited (4) without noting a start"]
    assert told == [
        f"{chrome_starts.WARM_UP_LABEL}: start 1 exited (4) without noting a start",
        "  no module here",
    ]


def test_a_warm_up_stopped_at_its_bound_is_noted_with_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "warm-up.mjs"
    script.write_text(
        "console.error('starting, slowly'); setInterval(() => {}, 1000);\n", encoding="utf-8"
    )
    monkeypatch.setattr(chrome_starts, "WARM_UP", script)
    monkeypatch.setattr(chrome_starts, "WARM_UP_CLOSE_S", 1.0)
    monkeypatch.setattr(chrome_starts, "WARM_UP_BOUND_S", 1.0)
    monkeypatch.setenv("CHROME_BIN", str(_stand_in(tmp_path, EXITS)))
    told = chrome_starts.warm_up(tmp_path)
    limit = 2.0 + GROUP_STOP_S
    assert told == [
        f"{chrome_starts.WARM_UP_LABEL}: start 1 ran past {limit:g} s and was stopped",
        "  starting, slowly",
    ]


def test_a_warm_up_that_cannot_run_is_noted_and_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object, **__: object) -> GroupRun:
        raise OSError("no processes left")

    monkeypatch.setattr(chrome_starts, "run_in_own_group", refuse)
    told, noted = _warm_up(tmp_path, monkeypatch)
    assert [n["failure"] for n in noted] == ["could not be run: OSError('no processes left')"]
    assert told == [
        f"{chrome_starts.WARM_UP_LABEL}: start 1 could not be run: OSError('no processes left')"
    ]


def test_the_warm_up_s_close_covers_an_abandoned_start() -> None:
    """WARM_UP_CLOSE_S, beside its definition, names the session's constants it covers."""

    source = SESSION_SCRIPT.read_text(encoding="utf-8")

    def constant(name: str) -> int:
        found = re.search(rf"^const {name} = (\d+);$", source, re.MULTILINE)
        assert found is not None, name
        return int(found.group(1))

    removal = re.findall(r"maxRetries: (\d+), retryDelay: (\d+)", source)
    assert removal and len(set(removal)) == 1, removal
    retries, delay = (int(value) for value in removal[0])
    abandoned_s = (constant("EXIT_WAIT_MS") + constant("LOOK_MS") + retries * delay) / 1000
    assert abandoned_s + 1 <= chrome_starts.WARM_UP_CLOSE_S


def test_the_summary_counts_every_worker_s_starts_and_shows_each_failure(
    tmp_path: Path,
) -> None:
    tail = "".join(f"[+{n}.0 s] line {n}\n" for n in range(20))
    records = [
        {"test": "tests/test_a.py::test_one (call)", "attempt": 1, "ok": True, "ms": 1200},
        {"test": "tests/test_a.py::test_two (call)", "attempt": 1, "ok": False, "ms": 300,
         "failure": "wrote no DevTools port: exited (3) after 0.3 s", "tail": tail},
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
        "  tests/test_a.py::test_two: start 1 wrote no DevTools port: exited (3) after 0.3 s",
        *(f"    [+{n}.0 s] line {n}" for n in range(8, 20)),
    ]
    assert chrome_starts.summary(tmp_path / "popen-gw1" / "none") == []


# ── The warm-up's wiring, in nested sessions ──────────────────────────────────


def probe_a_test_that_starts_chrome(chrome_profile: Path) -> None:
    """Collected only by the nested sessions below: one launch, as a Chrome test makes."""

    run = run_in_own_group(
        [require_node(), "--input-type=module", "-e", ONE_LAUNCH],
        timeout_s=20,
        env={**os.environ, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert "Chrome did not start in 2 tries" in run.stderr, run.stderr


def probe_a_test_without_chrome() -> None:
    """Collected only by the nested sessions below."""


def _session(tmp_path: Path, *arguments: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    basetemp = tmp_path / f"nested-{len(list(tmp_path.glob('nested-*')))}"
    env = {key: value for key, value in os.environ.items() if key != chrome_starts.STARTS_ENV}
    env["CHROME_BIN"] = str(_stand_in(tmp_path, EXITS))
    pytest_run = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    probes = ["-o", "python_functions=probe_*", f"--basetemp={basetemp}"]
    run = subprocess.run(
        [*pytest_run, *probes, *arguments, str(THIS)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=SESSION_TIMEOUT_S,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return run, chrome_starts.log_path(basetemp)


def test_a_run_with_a_chrome_test_warms_up_first_and_records_each_start(
    tmp_path: Path,
) -> None:
    run, log = _session(tmp_path)
    noted = [json.loads(line) for line in log.read_text().splitlines()]
    probe = f"{THIS.relative_to(ROOT)}::probe_a_test_that_starts_chrome (call)"
    assert [(n["test"], n["attempt"]) for n in noted] == [
        (chrome_starts.WARM_UP_LABEL, 1),
        (probe, 1),
        (probe, 2),
    ]
    lines = run.stdout.splitlines()
    told = f"{chrome_starts.WARM_UP_LABEL}: start 1 wrote no DevTools port: exited (3)"
    at_once = next(n for n, line in enumerate(lines) if line.startswith(told))
    summary = lines.index("chrome starts: 3, 3 failed")
    progress = next(
        n for n, line in enumerate(lines) if line.startswith(str(THIS.relative_to(ROOT)))
    )
    assert at_once < progress < summary, run.stdout


@pytest.mark.parametrize("arguments", [("--collect-only",), ("-m", "not chrome")])
def test_a_run_without_a_chrome_test_to_run_does_not_warm_up(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    run, log = _session(tmp_path, *arguments)
    assert not log.exists()
    assert "chrome starts" not in run.stdout
