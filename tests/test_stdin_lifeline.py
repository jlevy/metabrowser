"""``--exit-on-eof``: a server that stops when the process that started it is gone.

A parent that holds the server's stdin open, as the macOS app does, gives the server a
lifeline the kernel cuts however the parent ends: a crash or a force quit closes the
pipe, the server reads EOF, and it stops by itself. Nothing has to find it later by its
pid, which the kernel may have given to another process by then.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.main import _app
from metabrowser.cli.stdin_lifeline import (
    STDIN_CLOSED_NOTICE,
    require_open_stdin,
    watch_for_eof,
)
from metabrowser.errors import CLIError

runner = CliRunner()

# A child that works stops within a second of its stdin closing; this bounds only a
# child that does not, so the test fails instead of hanging the suite.
_EXIT_TIMEOUT_S = 15.0


def test_the_watcher_reads_everything_and_calls_back_once_at_eof() -> None:
    read_end, write_end = os.pipe()
    calls: list[int] = []
    done = threading.Event()

    def on_eof() -> None:
        calls.append(1)
        done.set()

    watcher = watch_for_eof(on_eof, fd=read_end)
    # More than a pipe holds, so the write returns only once the watcher has drained it:
    # data is read and dropped, and never mistaken for the end.
    os.write(write_end, b"x" * (1 << 20))
    assert not done.is_set()
    os.close(write_end)
    assert done.wait(_EXIT_TIMEOUT_S)
    watcher.join(_EXIT_TIMEOUT_S)
    assert calls == [1]
    assert watcher.daemon
    os.close(read_end)


def test_a_stdin_that_is_not_open_is_refused_before_serving() -> None:
    read_end, write_end = os.pipe()
    os.close(read_end)
    os.close(write_end)
    with pytest.raises(CLIError, match="--exit-on-eof needs an open stdin"):
        require_open_stdin(fd=read_end)


@pytest.mark.parametrize("flag", [False, True])
def test_serving_watches_stdin_only_when_asked(flag: bool, tmp_path: Path) -> None:
    previous = signal.getsignal(signal.SIGINT)
    try:
        with (
            patch("metabrowser.cli.serve._QuietForceExitServer"),
            patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
            patch("metabrowser.cli.serve.watch_for_eof") as watch,
            patch("metabrowser.cli.serve.require_open_stdin") as require,
        ):
            args = [str(tmp_path), "--no-open"] + (["--exit-on-eof"] if flag else [])
            result = runner.invoke(_app, args)
    finally:
        signal.signal(signal.SIGINT, previous)
    assert result.exit_code == 0, result.output
    assert watch.call_count == int(flag)
    assert require.call_count == int(flag)


def test_the_flag_is_a_serve_option() -> None:
    result = runner.invoke(_app, [".", "--walk", "--exit-on-eof"])
    assert result.exit_code == 2
    assert "--exit-on-eof not valid with --walk" in result.output


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipes and process groups")
def test_a_server_whose_stdin_closes_stops_and_frees_its_port(tmp_path: Path) -> None:
    root = tmp_path / "served"
    root.mkdir()
    (root / "a.txt").write_text("a")
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    console_script = Path(sys.executable).with_name("metab")
    process = subprocess.Popen(
        [str(console_script), str(root), "--no-open", "--port", str(port), "--exit-on-eof"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        ready: list[bool] = []
        wait_for_http_ok_then(
            "127.0.0.1",
            port,
            f"http://127.0.0.1:{port}/view/",
            on_ready=lambda: ready.append(True),
            on_error=lambda message: None,
            is_cancelled=lambda: process.poll() is not None,
            timeout_s=20.0,
        )
        assert ready, f"the server never served (exit={process.poll()})"
        assert process.stdin is not None
        process.stdin.close()  # what the kernel does when the parent dies
        stdout, stderr = process.communicate(timeout=_EXIT_TIMEOUT_S)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    assert process.returncode == 0, stderr
    assert STDIN_CLOSED_NOTICE in stderr
    assert b"Serving " in stdout
    with socket.socket() as again, pytest.raises(ConnectionRefusedError):
        again.connect(("127.0.0.1", port))
