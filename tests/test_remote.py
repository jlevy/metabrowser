"""Tests for `metab remote` — SSH command construction."""

from __future__ import annotations

from metabrowser.cli.ssh_utils import (
    build_ssh_command,
    build_ssh_tunnel_command,
    wrap_with_stdin_watchdog,
)


class TestBuildSshTunnelCommand:
    """Tests for build_ssh_tunnel_command."""

    def test_plain_ssh_basic(self) -> None:
        cmd = build_ssh_tunnel_command(
            "user@myhost",
            remote_cmd="metab serve /mnt/filestore/runs --port 8411 --host 127.0.0.1 --no-open",
            local_port=8411,
            remote_port=8411,
        )
        assert cmd[0] == "ssh"
        assert "-L" in cmd
        tunnel_idx = cmd.index("-L")
        assert cmd[tunnel_idx + 1] == "8411:localhost:8411"
        assert "user@myhost" in cmd
        assert "metab serve" in cmd[-1]

    def test_plain_ssh_with_options(self) -> None:
        cmd = build_ssh_tunnel_command(
            "devbox",
            remote_cmd="metab serve /data/runs --port 8500 --host 127.0.0.1 --no-open",
            local_port=9000,
            remote_port=8500,
            ssh_options="-i ~/.ssh/mykey -o StrictHostKeyChecking=no",
        )
        assert cmd[0] == "ssh"
        assert "-i" in cmd
        assert "~/.ssh/mykey" in cmd
        assert "-o" in cmd
        tunnel_idx = cmd.index("-L")
        assert cmd[tunnel_idx + 1] == "9000:localhost:8500"

    def test_plain_ssh_different_ports(self) -> None:
        cmd = build_ssh_tunnel_command(
            "user@host",
            remote_cmd="metab serve /data --port 8080 --host 127.0.0.1 --no-open",
            local_port=9090,
            remote_port=8080,
        )
        tunnel_idx = cmd.index("-L")
        assert cmd[tunnel_idx + 1] == "9090:localhost:8080"

    def test_gcp_mode_basic(self) -> None:
        cmd = build_ssh_tunnel_command(
            "my-browser-vm",
            remote_cmd="metab serve /mnt/filestore/runs --port 8411 --host 127.0.0.1 --no-open",
            local_port=8411,
            remote_port=8411,
            gcp=True,
            zone="us-central1-b",
            project="aitradearena",
        )
        assert cmd[0] == "gcloud"
        assert cmd[1] == "compute"
        assert cmd[2] == "ssh"
        assert "my-browser-vm" in cmd
        zone_idx = cmd.index("--zone")
        assert cmd[zone_idx + 1] == "us-central1-b"
        proj_idx = cmd.index("--project")
        assert cmd[proj_idx + 1] == "aitradearena"
        separator_idx = cmd.index("--")
        assert cmd[separator_idx + 1] == "-L"
        assert cmd[separator_idx + 2] == "8411:localhost:8411"
        assert "metab serve" in cmd[-1]

    def test_gcp_mode_no_project(self) -> None:
        cmd = build_ssh_tunnel_command(
            "my-vm",
            remote_cmd="metab serve /data/runs --port 8411 --host 127.0.0.1 --no-open",
            local_port=8411,
            remote_port=8411,
            gcp=True,
            zone="us-east1-b",
        )
        assert "--project" not in cmd
        assert "--zone" in cmd


class TestStdinWatchdog:
    """Tests for wrap_with_stdin_watchdog — orphan prevention on SSH disconnect."""

    def test_wrapper_structure(self) -> None:
        wrapped = wrap_with_stdin_watchdog("metab serve /data/runs --port 8411")
        # Must run via bash -c with a single quoted script argument.
        assert wrapped.startswith("bash -c ")
        # Inner command must be backgrounded with stdin from /dev/null.
        assert "</dev/null &" in wrapped
        # Must capture PID and block on stdin via cat.
        assert "PID=$!" in wrapped
        assert "cat >/dev/null" in wrapped
        # Must kill the backgrounded process after stdin closes (explicit kill,
        # not just trap — bash would otherwise block in `wait`).
        assert "kill $PID" in wrapped
        # Trap must cover channel-close signals.
        for sig in ("INT", "TERM", "HUP", "EXIT"):
            assert sig in wrapped

    def test_wrapper_preserves_inner_command(self) -> None:
        inner = 'export PATH="$HOME/.local/bin:$PATH" && metab serve /data --port 8411'
        wrapped = wrap_with_stdin_watchdog(inner)
        # Inner command is wrapped in a subshell so compound commands
        # (with &&) work under the background + redirect.
        assert "( " + inner + " )" in wrapped


class TestBuildSshCommand:
    """Tests for build_ssh_command (no tunnel)."""

    def test_plain_ssh(self) -> None:
        cmd = build_ssh_command(
            "user@host",
            remote_cmd="example-tool --help",
        )
        assert cmd == ["ssh", "user@host", "example-tool --help"]

    def test_gcp_mode(self) -> None:
        cmd = build_ssh_command(
            "my-vm",
            remote_cmd="example-tool --help",
            gcp=True,
            zone="us-central1-b",
            project="myproject",
        )
        assert cmd[0] == "gcloud"
        assert "my-vm" in cmd
        assert "--zone" in cmd
        assert "--project" in cmd
        assert cmd[-1] == "example-tool --help"

    def test_gcp_mode_with_iap(self) -> None:
        cmd = build_ssh_command(
            "my-vm",
            remote_cmd="ls /mnt/filestore",
            gcp=True,
            zone="us-central1-b",
            project="myproject",
            iap=True,
        )
        assert "--tunnel-through-iap" in cmd
        separator_idx = cmd.index("--")
        # IAP flag should be before the -- separator
        iap_idx = cmd.index("--tunnel-through-iap")
        assert iap_idx < separator_idx
        assert cmd[-1] == "ls /mnt/filestore"

    def test_gcp_mode_with_interactive(self) -> None:
        cmd = build_ssh_command(
            "my-vm",
            remote_cmd="tmux attach -t mysession",
            gcp=True,
            zone="us-central1-b",
            project="myproject",
            iap=True,
            interactive=True,
        )
        assert "--tunnel-through-iap" in cmd
        separator_idx = cmd.index("--")
        # -t should be after -- but before the remote command
        assert cmd[separator_idx + 1] == "-t"
        assert cmd[-1] == "tmux attach -t mysession"

    def test_plain_ssh_with_interactive(self) -> None:
        cmd = build_ssh_command(
            "user@host",
            remote_cmd="tmux attach",
            interactive=True,
        )
        assert cmd[0] == "ssh"
        assert "-t" in cmd
        assert cmd[-1] == "tmux attach"

    def test_gcp_tunnel_with_iap(self) -> None:
        cmd = build_ssh_tunnel_command(
            "my-vm",
            remote_cmd="metab serve /data/runs --port 8411 --host 127.0.0.1 --no-open",
            local_port=8411,
            remote_port=8411,
            gcp=True,
            zone="us-central1-b",
            project="myproject",
            iap=True,
        )
        assert "--tunnel-through-iap" in cmd
        separator_idx = cmd.index("--")
        iap_idx = cmd.index("--tunnel-through-iap")
        assert iap_idx < separator_idx
