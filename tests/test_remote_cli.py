"""Tests for the `metab remote` subcommand's remote command construction.

The SSH inner command must use the
explicit ``metab serve <path>`` form. The bare ``metab
<path>`` rewrite works too (see test_cli_serve.py), but ``serve`` is
explicit and insulates this command from any future routing change.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from unittest.mock import patch

import pytest
import typer
from click import unstyle
from typer.testing import CliRunner

from metabrowser.cli import remote
from metabrowser.cli.serve import _app
from metabrowser.cli.ssh_utils import build_ssh_tunnel_command
from metabrowser.errors import CLIError
from metabrowser.server_utils import MAX_TCP_PORT


class _FakeProcess:
    """Minimal ``Popen`` stand-in for remote CLI process-lifecycle tests."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.forwarded_signals: list[int] = []
        self.on_wait: object | None = None

    def poll(self) -> int | None:
        return None

    def wait(self) -> int:
        if callable(self.on_wait):
            self.on_wait()
        return self.returncode

    def send_signal(self, signum: int) -> None:
        self.forwarded_signals.append(signum)


def _invoke_remote(monkeypatch, process: _FakeProcess) -> None:
    monkeypatch.setattr(remote, "_probe_remote_free_port", lambda *a, **kw: 8412)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *a, **kw: 8411)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    remote.remote(
        host="user@vm",
        path="/runs",
        base_port=8411,
        no_open=True,
        ssh_options="",
        gcp=False,
        zone="",
        project="",
    )


@pytest.mark.parametrize("base_port", ["0", str(MAX_TCP_PORT + 1)])
def test_remote_rejects_out_of_range_base_port(base_port: str) -> None:
    result = CliRunner().invoke(
        _app,
        ["remote", "user@vm", "--path", "/runs", "--base-port", base_port],
    )

    assert result.exit_code == 2
    assert "--base-port" in unstyle(result.output)


def test_remote_inner_command_uses_explicit_serve_subcommand(monkeypatch) -> None:
    """The remote command piped into SSH must call ``metab serve …``."""
    captured: dict[str, list[str]] = {}

    def _fake_popen(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)

        class _FakeProc:
            returncode = 0

            def poll(self):
                return 0

            def wait(self):
                return 0

            def send_signal(self, sig):
                pass

        return _FakeProc()

    def _fake_probe(*args, **kwargs):
        return 8412

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(remote, "_probe_remote_free_port", _fake_probe)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *a, **kw: 8411)
    # Skip auto-open + signal forwarding; the test only cares about the cmd.
    with (
        patch.object(remote, "webbrowser", create=True),
        patch.object(remote, "signal", create=True),
        contextlib.suppress(Exception),
    ):
        remote.remote(
            host="user@vm",
            path="/runs",
            base_port=8411,
            no_open=True,
            ssh_options="",
            gcp=False,
            zone="",
            project="",
        )

    cmd = captured["cmd"]
    assert cmd[0] == "ssh"
    inner = cmd[-1]
    assert "metab serve" in inner, f"remote command should call 'metab serve …', got: {inner!r}"
    assert "metab /runs" not in inner.split("&&", 1)[1] or "serve" in inner


def test_ssh_tunnel_helper_unchanged() -> None:
    """The lower-level SSH-tunnel builder still constructs the right shape."""
    cmd = build_ssh_tunnel_command(
        "user@vm",
        remote_cmd="metab serve /runs --port 8412 --host 127.0.0.1 --no-open",
        local_port=8411,
        remote_port=8412,
    )
    assert cmd[0] == "ssh"
    assert "-L" in cmd
    tunnel_idx = cmd.index("-L")
    assert cmd[tunnel_idx + 1] == "8411:localhost:8412"
    assert "metab serve" in cmd[-1]


def test_remote_auto_open_uses_portable_webbrowser(monkeypatch) -> None:
    """Auto-open must not depend on the macOS-only ``open`` executable."""
    popen_calls: list[list[str]] = []

    class _FakeProc:
        returncode = 0

        def poll(self):
            return None

        def wait(self):
            return 0

        def send_signal(self, sig):
            pass

    def _fake_popen(cmd, *args, **kwargs):
        popen_calls.append(list(cmd))
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(remote, "_probe_remote_free_port", lambda *a, **kw: 8412)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *a, **kw: 8411)

    with (
        patch.object(remote, "webbrowser", create=True) as browser,
        patch.object(remote, "wait_for_http_ok_then", create=True) as wait_for_ready,
        patch.object(remote.signal, "signal"),
    ):
        wait_for_ready.side_effect = lambda *args, **kwargs: kwargs["on_ready"]()
        remote.remote(
            host="user@vm",
            path="/runs",
            base_port=8411,
            no_open=False,
            ssh_options="",
            gcp=False,
            zone="",
            project="",
        )

    wait_for_ready.assert_called_once()
    assert wait_for_ready.call_args.args == (
        "127.0.0.1",
        8411,
        "http://localhost:8411",
    )
    browser.open.assert_called_once_with("http://localhost:8411", new=2)
    assert len(popen_calls) == 1


def test_remote_loads_dotenv_before_resolving_gcp_project(monkeypatch) -> None:
    observed: dict[str, str] = {}

    class _FakeProc:
        returncode = 0

        def poll(self):
            return 0

        def wait(self):
            return 0

        def send_signal(self, sig):
            pass

    def _fake_load_dotenv_chain():
        os.environ["METABROWSER_GCP_PROJECT"] = "dotenv-project"

    def _fake_probe(*args, **kwargs):
        observed["probe_project"] = kwargs["project"]
        return 8412

    def _fake_tunnel(*args, **kwargs):
        observed["tunnel_project"] = kwargs["project"]
        return ["ssh"]

    monkeypatch.delenv("METABROWSER_GCP_PROJECT", raising=False)
    monkeypatch.setattr(remote, "_load_dotenv_chain", _fake_load_dotenv_chain)
    monkeypatch.setattr(remote, "_probe_remote_free_port", _fake_probe)
    monkeypatch.setattr(remote, "build_ssh_tunnel_command", _fake_tunnel)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *a, **kw: 8411)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _FakeProc())

    with patch.object(remote.signal, "signal"):
        remote.remote(
            host="my-vm",
            path="/runs",
            base_port=8411,
            no_open=True,
            ssh_options="",
            gcp=True,
            zone="us-central1-b",
            project="",
        )

    assert observed == {
        "probe_project": "dotenv-project",
        "tunnel_project": "dotenv-project",
    }


def test_remote_port_probe_reports_command_launch_failure(monkeypatch) -> None:
    error = FileNotFoundError(2, "No such file or directory", "ssh")

    def _fail_to_launch(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", _fail_to_launch)

    with pytest.raises(CLIError, match=r"ssh.*probing.*user@vm.*PATH") as caught:
        remote._probe_remote_free_port(
            "user@vm",
            8411,
            gcp=False,
            zone="",
            project="",
            ssh_options="",
        )

    assert caught.value.__cause__ is error


def test_remote_reports_tunnel_command_launch_failure(monkeypatch) -> None:
    error = FileNotFoundError(2, "No such file or directory", "ssh")

    def _fail_to_launch(*args, **kwargs):
        raise error

    monkeypatch.setattr(remote, "_probe_remote_free_port", lambda *a, **kw: 8412)
    monkeypatch.setattr(remote, "find_available_local_port", lambda *a, **kw: 8411)
    monkeypatch.setattr(subprocess, "Popen", _fail_to_launch)

    with pytest.raises(CLIError, match=r"ssh.*connecting.*user@vm.*PATH") as caught:
        remote.remote(
            host="user@vm",
            path="/runs",
            base_port=8411,
            no_open=True,
            ssh_options="",
            gcp=False,
            zone="",
            project="",
        )

    assert caught.value.__cause__ is error


@pytest.mark.parametrize(
    ("signum", "expected_exit_code"),
    [(signal.SIGINT, 130), (signal.SIGTERM, 143)],
)
def test_remote_forwards_signals_restores_handlers_and_normalizes_exit(
    monkeypatch, signum: int, expected_exit_code: int
) -> None:
    process = _FakeProcess(returncode=-signum)
    original_handlers: dict[int, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    installed_handlers: dict[int, object] = {}
    signal_calls: list[tuple[int, object]] = []

    def _fake_signal(current_signum: int, handler: object) -> object:
        signal_calls.append((current_signum, handler))
        if handler is not original_handlers[current_signum]:
            installed_handlers[current_signum] = handler
        return original_handlers[current_signum]

    monkeypatch.setattr(remote.signal, "signal", _fake_signal)

    def _signal_while_waiting() -> None:
        handler = installed_handlers[signum]
        assert callable(handler)
        handler(signum, None)

    process.on_wait = _signal_while_waiting

    with pytest.raises(typer.Exit) as caught:
        _invoke_remote(monkeypatch, process)

    assert caught.value.exit_code == expected_exit_code
    assert process.forwarded_signals == [signum]
    assert signal_calls[-2:] == [
        (signal.SIGTERM, original_handlers[signal.SIGTERM]),
        (signal.SIGINT, original_handlers[signal.SIGINT]),
    ]


def test_remote_preserves_non_signal_exit_code_and_restores_handlers(monkeypatch) -> None:
    process = _FakeProcess(returncode=23)
    original_handlers: dict[int, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    signal_calls: list[tuple[int, object]] = []

    def _fake_signal(signum: int, handler: object) -> object:
        signal_calls.append((signum, handler))
        return original_handlers[signum]

    monkeypatch.setattr(remote.signal, "signal", _fake_signal)

    with pytest.raises(typer.Exit) as caught:
        _invoke_remote(monkeypatch, process)

    assert caught.value.exit_code == 23
    assert signal_calls[-2:] == [
        (signal.SIGTERM, original_handlers[signal.SIGTERM]),
        (signal.SIGINT, original_handlers[signal.SIGINT]),
    ]


def test_remote_ignores_signal_forwarding_race_when_child_has_exited(monkeypatch) -> None:
    process = _FakeProcess(returncode=-signal.SIGTERM)
    installed_handlers: dict[int, object] = {}

    def _fake_signal(signum: int, handler: object) -> object:
        installed_handlers[signum] = handler
        return signal.SIG_DFL

    def _child_exited_before_signal(_signum: int) -> None:
        raise ProcessLookupError("child exited")

    def _signal_while_waiting() -> None:
        handler = installed_handlers[signal.SIGTERM]
        assert callable(handler)
        handler(signal.SIGTERM, None)

    process.on_wait = _signal_while_waiting
    monkeypatch.setattr(process, "send_signal", _child_exited_before_signal)
    monkeypatch.setattr(remote.signal, "signal", _fake_signal)

    with pytest.raises(typer.Exit) as caught:
        _invoke_remote(monkeypatch, process)

    assert caught.value.exit_code == 143


def test_remote_restores_handlers_when_wait_fails(monkeypatch) -> None:
    process = _FakeProcess()
    original_handlers: dict[int, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    signal_calls: list[tuple[int, object]] = []

    def _fake_signal(signum: int, handler: object) -> object:
        signal_calls.append((signum, handler))
        return original_handlers[signum]

    def _fail_while_waiting() -> None:
        raise RuntimeError("wait failed")

    process.on_wait = _fail_while_waiting
    monkeypatch.setattr(remote.signal, "signal", _fake_signal)

    with pytest.raises(RuntimeError, match="wait failed"):
        _invoke_remote(monkeypatch, process)

    assert signal_calls[-2:] == [
        (signal.SIGTERM, original_handlers[signal.SIGTERM]),
        (signal.SIGINT, original_handlers[signal.SIGINT]),
    ]
