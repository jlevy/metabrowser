"""``--exit-on-eof``: a server that stops when the process that started it is gone.

A parent that holds the server's stdin open, as the macOS app does, gives the server a
lifeline the kernel cuts however the parent ends: a crash or a force quit closes the
pipe, the server reads EOF, and it stops by itself. Nothing has to find it later by its
pid, which the kernel may have given to another process by then.
"""

from __future__ import annotations

import contextlib
import os
import re
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from metabrowser.cli.common import write_notice_now_or_never
from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.main import _app
from metabrowser.cli.stdin_lifeline import (
    STDIN_CLOSED_NOTICE,
    require_open_stdin,
    watch_for_eof,
)
from metabrowser.errors import CLIError
from tests.child_io import read_line
from tests.test_cli_main import _plain_output

runner = CliRunner()

# A child that works stops within a second of its stdin closing; this bounds only a
# child that does not, so the test fails instead of hanging the suite.
_EXIT_TIMEOUT_S = 15.0
# The first line a server prints, naming the address it took, which is not always the
# one asked for: a port in use sends the search to the next one.
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/")


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


def test_a_nonblocking_stdin_that_is_empty_for_now_has_not_ended() -> None:
    """A stdin inherited with ``O_NONBLOCK`` reads ``EAGAIN`` while its writer is alive.

    That is a pipe with nothing in it yet, not an end, so the watcher waits for it to be
    readable and goes on reading; only the writer's close stops the server.
    """

    read_end, write_end = os.pipe()
    # Only the read end: the test's own writes below block, as a parent's would.
    os.set_blocking(read_end, False)
    calls: list[int] = []
    done = threading.Event()

    def on_eof() -> None:
        calls.append(1)
        done.set()

    watcher = watch_for_eof(on_eof, fd=read_end)
    try:
        # A watcher that takes EAGAIN for the end calls back at once; this one waits.
        assert not done.wait(0.3)
        os.write(write_end, b"x" * (1 << 20))
        assert not done.is_set()
    finally:
        os.close(write_end)
    assert done.wait(_EXIT_TIMEOUT_S)
    watcher.join(_EXIT_TIMEOUT_S)
    assert calls == [1]
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
    assert "--exit-on-eof not valid with --walk" in _plain_output(result)


@contextlib.contextmanager
def _port_in_use() -> Generator[int]:
    """A loopback port something else is listening on, for as long as the block runs."""

    with socket.socket() as occupant:
        occupant.bind(("127.0.0.1", 0))
        occupant.listen()
        yield occupant.getsockname()[1]


def _served_port(process: subprocess.Popen[str]) -> int:
    """The port the child's banner names, read within a bound."""

    line = read_line(process)
    match = _SERVING_LINE.match(line)
    assert match is not None, f"not a banner: {line!r}"
    return int(match.group(1))


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipes and process groups")
def test_a_server_whose_stdin_closes_stops_and_frees_its_port(tmp_path: Path) -> None:
    root = tmp_path / "served"
    root.mkdir()
    (root / "a.txt").write_text("a")
    console_script = Path(sys.executable).with_name("metab")
    # The port asked for is taken for the whole run, so the server always moves on and
    # the test always reads where it went, rather than assuming the port asked for.
    with _port_in_use() as taken:
        process = subprocess.Popen(
            [str(console_script), str(root), "--no-open", "--port", str(taken), "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            port = _served_port(process)
            assert port != taken
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
            if not ready:
                process.kill()
                _, errors = process.communicate(timeout=5)
                pytest.fail(f"the server never served (exit={process.returncode}): {errors!r}")
            assert process.stdin is not None
            process.stdin.close()  # what the kernel does when the parent dies
            # Closed here, so ``communicate`` must not flush it: Python 3.12 and 3.13
            # raise ``ValueError`` for a flush of a closed stdin, which 3.14 ignores.
            process.stdin = None
            _, stderr = process.communicate(timeout=_EXIT_TIMEOUT_S)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert process.returncode == 0, stderr
    assert STDIN_CLOSED_NOTICE.decode() in stderr
    with socket.socket() as again, pytest.raises(ConnectionRefusedError):
        again.connect(("127.0.0.1", port))


def _full_pipe() -> tuple[int, int]:
    """A pipe whose buffer is full, with both ends blocking, as a reader that stopped
    reading leaves it."""

    read_end, write_end = os.pipe()
    os.set_blocking(write_end, False)
    # Large writes first, then single bytes, until not even one more fits.
    for size in (1 << 16, 1):
        with contextlib.suppress(BlockingIOError):
            while True:
                os.write(write_end, b"x" * size)
    os.set_blocking(write_end, True)
    return read_end, write_end


def _drain(fd: int) -> bytes:
    os.set_blocking(fd, False)
    chunks: list[bytes] = []
    with contextlib.suppress(BlockingIOError):
        while chunk := os.read(fd, 1 << 16):
            chunks.append(chunk)
    return b"".join(chunks)


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipes")
def test_a_notice_is_written_when_it_fits_and_dropped_when_it_does_not() -> None:
    read_end, write_end = _full_pipe()
    try:
        finished = threading.Event()

        def write() -> None:
            write_notice_now_or_never(write_end, b"notice\n")
            finished.set()

        # On a thread, so a write that waits fails the test instead of hanging the suite.
        threading.Thread(target=write, daemon=True).start()
        assert finished.wait(_EXIT_TIMEOUT_S)
        assert b"notice" not in _drain(read_end)
        # The open file is as blocking as it was before, for whoever else shares it.
        assert os.get_blocking(write_end)
        write_notice_now_or_never(write_end, b"notice\n")
        assert _drain(read_end) == b"notice\n"
        assert os.get_blocking(write_end)
    finally:
        os.close(read_end)
        os.close(write_end)


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipes and signals")
@pytest.mark.parametrize(
    ("stop", "status"), [("stdin closes", 0), ("interrupt", 130)], ids=["eof", "sigint"]
)
def test_a_stop_is_not_held_up_by_a_full_stderr(stop: str, status: int, tmp_path: Path) -> None:
    """The stop notice is skipped, not waited on, when stderr cannot take it now.

    A supervisor that holds the server's stderr and has stopped reading it leaves the
    pipe full. A blocking write of the notice would then wait for good, before any Git
    is killed or the process exits, for a stdin that closed and for a Ctrl-C alike.
    """

    root = tmp_path / "served"
    root.mkdir()
    console_script = Path(sys.executable).with_name("metab")
    stderr_read, stderr_write = _full_pipe()
    try:
        process = subprocess.Popen(
            [str(console_script), str(root), "--no-open", "--exit-on-eof"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_write,
            text=True,
            start_new_session=True,
        )
        os.close(stderr_write)
        try:
            _served_port(process)
            assert process.stdin is not None
            if stop == "interrupt":
                process.send_signal(signal.SIGINT)
            else:
                process.stdin.close()
                process.stdin = None
            assert process.wait(timeout=_EXIT_TIMEOUT_S) == status
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    finally:
        os.close(stderr_read)
