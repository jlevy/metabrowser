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
waits for each panel, and measures each width. The measurement reports each of its
phases on stderr as it ends, so a run stopped at a budget names the phase it was in and
how long every earlier one took.

The test owns everything it starts. The server stops when its stdin closes. The
measuring Node process leads a process group of its own, which Chrome and its helpers
join when Node spawns them, so a run stopped at its budget or by an interrupt stops all
of them, not Node alone. The browser profile is a directory this module creates and
removes once those processes are gone.
"""

from __future__ import annotations

import contextlib
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

# Each phase's budget, from what it took. A run on a 10-core Mac takes about 1.5 s to
# print the banner, 0.1 s more to serve, and 1.5 s to measure; with twelve busy loops
# beside a load average of 17, 3.1 s, 0.3 s, and 2.5 s. In CI the whole test took from
# 5.5 to 40 s (ubuntu-latest).
_BANNER_BUDGET_S = 30.0
_SERVING_BUDGET_S = 15.0
_MEASUREMENT_BUDGET_S = 90.0
# Stopping what the run started: the measurement's process group gets SIGTERM, then
# SIGKILL, and the server its closed stdin, then SIGKILL.
_TERM_GRACE_S = 3.0
_KILL_GRACE_S = 2.0
_SERVER_STOP_S = 5.0
# The budgets and every stop, with a third again to spare, raise this module's own limit
# over the suite's 60 s default (see tests/test_suite_gates.py).
pytestmark = pytest.mark.timeout(200)

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
    # Closed here, so ``wait`` must not flush it: Python 3.12 and 3.13 raise
    # ``ValueError`` for a flush of a closed stdin, which 3.14 ignores.
    server.stdin = None
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


# DIAGNOSTIC, not for merge: what the machine looks like before the first Chrome launch,
# reported as warnings so that every matrix job finishes and shows them.
def _cache_state() -> str:
    parts = []
    for directory in (Path.home() / ".cache" / "fontconfig", Path("/var/cache/fontconfig")):
        files = [p for p in directory.glob("*") if p.is_file()] if directory.is_dir() else []
        parts.append(
            f"{directory}: {len(files)} files {sum(p.stat().st_size for p in files)} bytes"
        )
    return "; ".join(parts)


def test_aa_diagnostic_machine_state() -> None:
    import warnings

    chrome = require_chrome()
    real = Path(os.path.realpath(chrome))
    load = Path("/proc/loadavg").read_text() if Path("/proc/loadavg").exists() else "n/a"
    top = subprocess.run(
        ["ps", "-eo", "pcpu,etime,args", "--sort=-pcpu"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()[:8]
    before = _cache_state()
    started = time.monotonic()
    total = 0
    for path in real.parent.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as handle:
                while chunk := handle.read(1 << 20):
                    total += len(chunk)
    read_s = time.monotonic() - started
    warnings.warn(
        f"DIAGNOSTIC machine: chrome {chrome} -> {real}; loadavg {load.strip()}; "
        f"read {total} bytes of {real.parent} in {read_s:.1f} s; caches before: {before}; "
        f"top: {' | '.join(line.strip()[:120] for line in top)}",
        stacklevel=1,
    )


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
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome},
        )
        phases.add_measurement(run.stderr, node_started)
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(
            f"phase {phases.next_measurement_phase()} ran out of the measurement's "
            f"{_MEASUREMENT_BUDGET_S:g} s budget; phases that ended: {phases.report()}"
        )
    assert run.returncode == 0, f"{run.stderr or run.stdout}\nphases that ended: {phases.report()}"
    assert run.stdout == "folder overview alignment: 30 checks passed\n"
    import warnings

    warnings.warn("DIAGNOSTIC first run phases: " + phases.report(), stacklevel=1)


def test_zz_diagnostic_warm_runs(tmp_path: Path) -> None:
    import warnings

    reports = [f"caches after the first run: {_cache_state()}"]
    made: list[_Phases] = []
    real_phases = globals()["_Phases"]

    for attempt in (1, 2):
        profile = Path(tempfile.mkdtemp(prefix="overview-alignment-chrome-"))
        started = time.monotonic()
        try:
            globals()["_Phases"] = lambda: made.append(real_phases()) or made[-1]
            test_overview_labels_start_on_the_tab_label_at_every_width(
                tmp_path / f"run{attempt}", profile
            )
            reports.append(
                f"warm run {attempt} ok in {time.monotonic() - started:.1f} s: {made[-1].report()}"
            )
        except BaseException as error:  # noqa: BLE001
            reports.append(f"warm run {attempt} failed: {error}")
        finally:
            globals()["_Phases"] = real_phases
            _kill_processes_naming(profile)
            shutil.rmtree(profile, ignore_errors=True)
    warnings.warn("DIAGNOSTIC " + " || ".join(reports), stacklevel=1)
