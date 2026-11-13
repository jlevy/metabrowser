"""The Folder Overview's labels share one left edge at every width, in a real Chrome.

A served folder with a README and a few kinds of file shows both Overview panels and
File Overview's Details toggle. ``tests/dom/folder-overview-alignment-chrome.mjs`` then
measures where each label's text starts at window widths that put the preview pane in
each KPress document band, and checks that every label starts on the Overview tab's
label. The rule is in ``docs/design-system.md``, "Folder Overview Is a Panel Stack".

Where text starts is computed layout, so this needs a browser; it skips without Chrome,
as ``docs/e2e-testing.md`` lists, and CI runs it.

The test owns everything it starts. The server stops when its stdin closes. The
measuring Node process leads a process group of its own, which Chrome and its helpers
join when Node spawns them, so a run stopped at its deadline or by an interrupt stops
all of them, not Node alone. The browser profile is a directory this module creates and
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
from dataclasses import dataclass
from pathlib import Path

import pytest

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from tests.child_io import CHILD_LINE_TIMEOUT_S, read_line
from tests.required_tools import require_chrome, require_node

DOM = Path(__file__).parent / "dom"
_METAB = Path(sys.executable).with_name("metab")
# The first line a server prints, naming the address it took, which is not always the
# one asked for: a port in use sends the search to the next one. It is printed before the
# server accepts connections, so it says where to wait, not that the wait is over.
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/")
# Starting the server and measuring take about 4 s on a 10-core Mac. Both must finish
# within this many seconds of the test's start; stopping the measurement's process group
# (at most _TERM_GRACE_S + _KILL_GRACE_S) and the server (at most twice _SERVER_STOP_S)
# then keeps a run that hangs under the suite's 60 s per-test timeout.
_DEADLINE_S = 40.0
_TERM_GRACE_S = 3.0
_KILL_GRACE_S = 2.0
_SERVER_STOP_S = 5.0

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


def _wait_until_serving(server: subprocess.Popen[str], port: int, timeout_s: float) -> None:
    """Return once the server answers HTTP OK; fail at once if it exits first."""

    url = f"http://127.0.0.1:{port}/view/"
    outcome: list[str] = []
    wait_for_http_ok_then(
        "127.0.0.1",
        port,
        url,
        on_ready=lambda: outcome.append("ready"),
        on_error=outcome.append,
        is_cancelled=lambda: server.poll() is not None,
        timeout_s=timeout_s,
    )
    if outcome == ["ready"]:
        return
    if server.poll() is not None:
        pytest.fail(f"the server exited with status {server.returncode} before serving {url}")
    pytest.fail(outcome[0] if outcome else f"{url} was not served within {timeout_s:.1f}s")


def _stop_server(server: subprocess.Popen[str]) -> None:
    assert server.stdin is not None
    server.stdin.close()
    # Closed here, so ``communicate`` must not flush it: Python 3.12 and 3.13 raise
    # ``ValueError`` for a flush of a closed stdin, which 3.14 ignores.
    server.stdin = None
    try:
        server.communicate(timeout=_SERVER_STOP_S)
    except subprocess.TimeoutExpired:
        server.kill()
        server.communicate(timeout=_SERVER_STOP_S)


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
    deadline = time.monotonic() + _DEADLINE_S

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    root = tmp_path / "served"
    _served_folder(root)
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CACHE_DIR"] = str(tmp_path / "cache")
    env["METABROWSER_CONFIG_DIR"] = str(tmp_path / "config")
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    # --exit-on-eof: closing stdin stops the server however this test ends.
    server = subprocess.Popen(
        [str(_METAB), str(root), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        banner = read_line(server, timeout=min(CHILD_LINE_TIMEOUT_S, remaining()))
        match = _SERVING_LINE.match(banner)
        assert match is not None, f"not a banner: {banner!r}"
        port = int(match.group(1))
        _wait_until_serving(server, port, remaining())
        run = _run_in_own_group(
            [
                node,
                str(DOM / "folder-overview-alignment-chrome.mjs"),
                f"http://127.0.0.1:{port}",
                str(chrome_profile),
            ],
            timeout_s=remaining(),
            env={**os.environ, "CHROME_BIN": chrome},
        )
    finally:
        _stop_server(server)
    assert not run.timed_out, (
        f"the measurement was stopped {_DEADLINE_S:g}s after the test started; "
        f"its stderr: {run.stderr!r}"
    )
    assert run.returncode == 0, run.stderr or run.stdout
    assert run.stdout == "folder overview alignment: 30 checks passed\n"
