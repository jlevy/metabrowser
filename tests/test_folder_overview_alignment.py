"""The Folder Overview's labels share one left edge at every width, in a real Chrome.

A served folder with a README and a few kinds of file shows both Overview panels and
File Overview's Details toggle. ``tests/dom/folder-overview-alignment-chrome.mjs`` then
measures where each label's text starts at window widths that put the preview pane in
each KPress document band, and checks that every label starts on the Overview tab's
label. The rule is in ``docs/design-system.md``, "Folder Overview Is a Panel Stack".

Where text starts is computed layout, so this needs a browser; it skips without Chrome,
as ``docs/e2e-testing.md`` lists, and CI runs it.

The run is a sequence of phases, each with its own budget: the server prints its
banner, then serves HTTP, then the measurement launches Chrome, loads the Overview,
waits for each panel, and measures each width. This module sets every budget and hands
the measurement its own; the measurement enforces them, reports each phase on stderr as
it ends, and fails naming the phase that ran out. A measurement that stops reporting
altogether is stopped at the sum of its budgets, named by the phase after the last one
it reported. Either way the failure lists how long every earlier phase took.

The test owns everything it starts. The server stops when its stdin closes. The
measuring Node process leads a process group of its own, which Chrome and its helpers
join when Node spawns them, so a run stopped at its budget or by an interrupt stops all
of them, not Node alone. The browser profile is a directory this module creates and
removes once those processes are gone.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from tests.required_tools import require_chrome, require_node

DOM = Path(__file__).parent / "dom"
_METAB = Path(sys.executable).with_name("metab")
# The first line a server prints, naming the address it took, which is not always the
# one asked for: a port in use sends the search to the next one. It is printed before the
# server accepts connections, so it says where to wait, not that the wait is over.
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/", re.MULTILINE)
# The phases the measurement reports, in the order it reports them, as
# ``phase <name> <milliseconds since Node started>`` lines on stderr.
_WIDTHS = (900, 1200, 1440, 1920, 2560)
_MEASUREMENT_PHASES = (
    "imported",
    "chrome",
    "navigated",
    "panels",
    "readme",
    "rollup",
    *(f"width {width}" for width in _WIDTHS),
    "closed",
)
_PHASE_LINE = re.compile(r"^phase (.+) (\d+)$", re.MULTILINE)

# Each phase's budget in seconds, from what it took, with room for a loaded machine.
#
# The first Chrome launch of a CI test session is the slow one, because it reads Chrome
# from a cold disk. On ubuntu-latest runners, about four minutes into the suite, reading
# the 474 MB under /opt/google/chrome took 9.5 to 10.8 s, after which launching Chrome
# took 0.2 to 0.8 s and the whole measurement 1.4 s. Without that read, the launch took
# 13.8 s in one run and 0.2 s in each launch after it, every other phase took under
# 0.5 s, and a run whose budget was 40 s for the whole test ran out of it. On a 10-core
# Mac a run takes about 1.5 s to print the banner, 0.1 s more to serve, and 1.5 s to
# measure; with ten busy loops beside a load average of 14 to 97, the whole test took at
# most 9.5 s in twenty runs.
_BANNER_BUDGET_S = 30.0
_SERVING_BUDGET_S = 15.0
# The measurement enforces these itself and names the phase that runs out; "width" is
# each width's budget. Chrome's is also how long it may take to publish its endpoint,
# and is over six times the slowest launch measured and twice the 40 s the failed run
# had for everything. The others are at least five times the longest their phase took,
# here or in CI.
_PHASE_BUDGETS_S: dict[str, float] = {
    "chrome": 90.0,
    "navigated": 10.0,
    "panels": 20.0,
    "readme": 15.0,
    "rollup": 15.0,
    "width": 5.0,
    "closed": 15.0,
}
# Node's own start and exit, outside every phase: under 0.1 s on a 10-core Mac.
_NODE_START_EXIT_S = 10.0
# The measurement's own budget: every phase's, and Node's start and exit. It only fires
# when the measurement stops reporting, as when a DevTools call never answers.
_MEASUREMENT_BUDGET_S = (
    sum(_PHASE_BUDGETS_S.values())
    + _PHASE_BUDGETS_S["width"] * (len(_WIDTHS) - 1)
    + _NODE_START_EXIT_S
)
# Stopping what the run started: the measurement's process group gets SIGTERM, then
# SIGKILL, and the server its closed stdin, then SIGKILL.
_TERM_GRACE_S = 3.0
_KILL_GRACE_S = 2.0
_SERVER_STOP_S = 5.0
# The longest a run can take: every budget, then every stop. This module's own limit,
# over the suite's 60 s default (tests/test_suite_gates.py), adds the fixture's setup and
# teardown, which list processes once and remove one directory.
_LONGEST_RUN_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + _TERM_GRACE_S
    + 2 * _KILL_GRACE_S
    + 2 * _SERVER_STOP_S
)
pytestmark = pytest.mark.timeout(_LONGEST_RUN_S + 30)

README = """# Sample Project

This folder exists so the Overview has both of its panels: a README long enough to wrap
at a narrow width, and files of several kinds for File Overview to break down.

## Usage

Run the tool and read the output.
"""


@dataclass(frozen=True, slots=True)
class _Run:
    """How a run in its own process group ended."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


@dataclass(slots=True)
class _Phases:
    """When each phase of the run ended, in seconds since the run started."""

    started: float = field(default_factory=time.monotonic)
    ended: list[tuple[str, float]] = field(default_factory=list)

    def end(self, name: str) -> None:
        self.ended.append((name, time.monotonic() - self.started))

    def add_measurement(self, stderr: str, node_started: float) -> None:
        """Record the phases the measurement reported, against when Node started."""

        offset = node_started - self.started
        for name, milliseconds in _PHASE_LINE.findall(stderr):
            self.ended.append((name, offset + int(milliseconds) / 1000))

    def next_measurement_phase(self) -> str:
        reached = {name for name, _ in self.ended}
        return next((name for name in _MEASUREMENT_PHASES if name not in reached), "exit")

    def report(self) -> str:
        """Each phase that ended, with how long it took."""

        parts: list[str] = []
        previous = 0.0
        for name, at in self.ended:
            parts.append(f"{name} {at - previous:.1f} s")
            previous = at
        return ", ".join(parts) or "none"


def _served_folder(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text(README, encoding="utf-8")
    for n in range(1, 4):
        (root / "src" / f"module{n}.py").write_text(f"VALUE = {n}\n", encoding="utf-8")
        (root / "docs" / f"note{n}.md").write_text(f"# Note {n}\n", encoding="utf-8")
        (root / f"data{n}.json").write_text(f'{{"n": {n}}}\n', encoding="utf-8")
    (root / "src" / "app.js").write_text("export const ready = true;\n", encoding="utf-8")


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _stop_group(process: subprocess.Popen[str]) -> None:
    """Stop every process in the group *process* leads: SIGTERM, then SIGKILL, each bounded.

    A group that is already empty, as after a run that closed its own browser, gets no
    signal at all.
    """

    group = process.pid
    for signum, grace in ((signal.SIGTERM, _TERM_GRACE_S), (signal.SIGKILL, _KILL_GRACE_S)):
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
    raise AssertionError(f"process group {group} outlived SIGKILL by {_KILL_GRACE_S:g}s")


def _run_in_own_group(argv: list[str], *, timeout_s: float, env: Mapping[str, str]) -> _Run:
    """Run *argv* as the leader of a new process group, and stop the whole group after.

    The group is stopped however this returns: at the deadline, on an error, or on an
    interrupt. Killing Node alone would leave the Chrome it started running.
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
            _stop_group(process)
            # Every process that could hold the pipes open was in the group.
            stdout, stderr = process.communicate(timeout=_KILL_GRACE_S)
    finally:
        _stop_group(process)
    return _Run(process.returncode, stdout, stderr, timed_out)


def _last_lines(stderr: str) -> str:
    """What the measurement wrote besides its phase lines: its failure, when it failed."""

    return "\n".join(line for line in stderr.splitlines() if not _PHASE_LINE.match(line))


def _log_tail(log: Path) -> str:
    return log.read_text(encoding="utf-8", errors="replace")[-2000:]


def _read_port(server: subprocess.Popen[str], log: Path, phases: _Phases) -> int:
    """The port the server's banner names, read from its log within the banner budget."""

    deadline = time.monotonic() + _BANNER_BUDGET_S
    while time.monotonic() < deadline:
        if match := _SERVING_LINE.search(log.read_text(encoding="utf-8", errors="replace")):
            phases.end("banner")
            return int(match.group(1))
        if server.poll() is not None:
            pytest.fail(
                f"the server exited with status {server.returncode} before its banner; "
                f"its output: {_log_tail(log)!r}"
            )
        time.sleep(0.05)
    pytest.fail(
        f"the server printed no banner within {_BANNER_BUDGET_S:g} s; "
        f"its output: {_log_tail(log)!r}"
    )


def _wait_until_serving(
    server: subprocess.Popen[str], port: int, log: Path, phases: _Phases
) -> None:
    """Return once the server answers HTTP OK within its budget; fail if it exits first."""

    url = f"http://127.0.0.1:{port}/view/"
    outcome: list[str] = []
    wait_for_http_ok_then(
        "127.0.0.1",
        port,
        url,
        on_ready=lambda: outcome.append("ready"),
        on_error=outcome.append,
        is_cancelled=lambda: server.poll() is not None,
        timeout_s=_SERVING_BUDGET_S,
    )
    if outcome == ["ready"]:
        phases.end("serving")
        return
    if server.poll() is not None:
        pytest.fail(
            f"the server exited with status {server.returncode} before serving {url}; "
            f"its output: {_log_tail(log)!r}"
        )
    pytest.fail(
        f"phase serving ran out of its {_SERVING_BUDGET_S:g} s budget: "
        f"{outcome[0] if outcome else url}"
    )


def _stop_server(server: subprocess.Popen[str]) -> None:
    assert server.stdin is not None
    server.stdin.close()
    try:
        server.wait(timeout=_SERVER_STOP_S)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=_SERVER_STOP_S)


def _kill_processes_naming(profile: Path) -> list[str]:
    """Kill any process whose command line still names *profile*; return what was found."""

    listed = subprocess.run(
        ["ps", "-A", "-ww", "-o", "pid=,args="],
        capture_output=True,
        check=True,
        text=True,
        timeout=5,
    ).stdout
    found = [line.strip() for line in listed.splitlines() if str(profile) in line]
    for line in found:
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(line.split()[0]), signal.SIGKILL)
    return found


@pytest.fixture
def chrome_profile() -> Iterator[Path]:
    """A profile directory the test owns, removed after the processes that used it stop.

    The teardown also fails the test if any process naming the profile is still running,
    which would mean it escaped the process group, and kills it so it does not leak.
    """

    profile = Path(tempfile.mkdtemp(prefix="overview-alignment-chrome-"))
    try:
        yield profile
    finally:
        survivors = _kill_processes_naming(profile)
        shutil.rmtree(profile, ignore_errors=True)
        assert not profile.exists(), f"the browser profile {profile} was not removed"
        assert not survivors, f"processes outlived their group: {survivors}"


def test_overview_labels_start_on_the_tab_label_at_every_width(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    root = tmp_path / "served"
    _served_folder(root)
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CACHE_DIR"] = str(tmp_path / "cache")
    env["METABROWSER_CONFIG_DIR"] = str(tmp_path / "config")
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    # The server's output goes to a file, which never fills as an unread pipe can, and
    # which a failure quotes.
    log = tmp_path / "server.log"
    phases = _Phases()
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [str(_METAB), str(root), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
    try:
        port = _read_port(server, log, phases)
        _wait_until_serving(server, port, log, phases)
        node_started = time.monotonic()
        run = _run_in_own_group(
            [
                node,
                str(DOM / "folder-overview-alignment-chrome.mjs"),
                f"http://127.0.0.1:{port}",
                str(chrome_profile),
                json.dumps({"widths": _WIDTHS, "budgets": _PHASE_BUDGETS_S}),
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome},
        )
        phases.add_measurement(run.stderr, node_started)
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(
            f"the measurement stopped reporting during phase "
            f"{phases.next_measurement_phase()} and ran out of its "
            f"{_MEASUREMENT_BUDGET_S:g} s budget; phases that ended: {phases.report()}"
        )
    # A phase that runs out of its own budget fails the measurement, which names it.
    assert run.returncode == 0, (
        f"{_last_lines(run.stderr) or run.stdout}\nphases that ended: {phases.report()}"
    )
    assert run.stdout == "folder overview alignment: 30 checks passed\n"
