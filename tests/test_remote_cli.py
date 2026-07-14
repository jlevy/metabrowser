"""Tests for the `metabrowser remote` subcommand's remote command construction.

The SSH inner command must use the
explicit ``metabrowser serve <path>`` form. The bare ``metabrowser
<path>`` rewrite works too (see test_cli_serve.py), but ``serve`` is
explicit and insulates this command from any future routing change.
"""

from __future__ import annotations

import contextlib
import subprocess
from unittest.mock import patch

from metabrowser.cli import remote
from metabrowser.cli.ssh_utils import build_ssh_tunnel_command


def test_remote_inner_command_uses_explicit_serve_subcommand(monkeypatch) -> None:
    """The remote command piped into SSH must call ``metabrowser serve …``."""
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
    assert "metabrowser serve" in inner, (
        f"remote command should call 'metabrowser serve …', got: {inner!r}"
    )
    assert "metabrowser /runs" not in inner.split("&&", 1)[1] or "serve" in inner


def test_ssh_tunnel_helper_unchanged() -> None:
    """The lower-level SSH-tunnel builder still constructs the right shape."""
    cmd = build_ssh_tunnel_command(
        "user@vm",
        remote_cmd="metabrowser serve /runs --port 8412 --host 127.0.0.1 --no-open",
        local_port=8411,
        remote_port=8412,
    )
    assert cmd[0] == "ssh"
    assert "-L" in cmd
    tunnel_idx = cmd.index("-L")
    assert cmd[tunnel_idx + 1] == "8411:localhost:8412"
    assert "metabrowser serve" in cmd[-1]


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
        patch.object(remote.signal, "signal"),
        patch.object(remote.time, "sleep"),
    ):
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

    browser.open.assert_called_once_with("http://localhost:8411", new=2)
    assert len(popen_calls) == 1
