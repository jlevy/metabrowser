"""metabrowser remote — open metabrowser on a remote host via SSH tunnel.

Walks both local and remote ports upward from a base port so multiple
remote sessions can coexist on the same host pair. Ctrl-C tears down the
tunnel and kills the remote serve cleanly.

Registered as a subcommand on the unified ``metabrowser`` Typer app
(see :mod:`metabrowser.cli.serve`). There's no standalone console
script — invoke as ``metabrowser remote <host> --path <remote-root>``.
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import time
import webbrowser

import typer

from metabrowser.cli.ssh_utils import (
    build_ssh_command,
    build_ssh_tunnel_command,
    wrap_with_stdin_watchdog,
)
from metabrowser.errors import CLIError
from metabrowser.server_utils import (
    DEFAULT_PORT_SEARCH_COUNT,
    find_available_local_port,
    remote_port_probe_script,
)
from metabrowser.settings import DEFAULT_BROWSER_PORT


def _probe_remote_free_port(
    host: str,
    base_port: int,
    *,
    gcp: bool,
    zone: str,
    project: str,
    ssh_options: str,
) -> int:
    """Ask the remote host which port to use for ``metabrowser serve``.

    Walks from *base_port* upward so multiple remote sessions on the same
    target host coexist. Coordinating the port choice before opening the
    tunnel is what prevents the local tunnel from landing on the wrong
    remote process (the original bug that made the remote view show a
    stale path).
    """
    probe_cmd = remote_port_probe_script(base_port)
    cmd = build_ssh_command(
        host,
        remote_cmd=probe_cmd,
        ssh_options=ssh_options,
        gcp=gcp,
        zone=zone,
        project=project,
    )
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CLIError(
            f"Failed to probe remote port on {host} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    port_str = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    try:
        return int(port_str)
    except ValueError as exc:
        raise CLIError(
            f"Remote port probe on {host} returned unparsable output: {result.stdout!r}"
        ) from exc


def remote(
    host: str = typer.Argument(..., help="SSH target (e.g. user@hostname, my-vm)"),
    path: str = typer.Option(..., "--path", help="Remote directory to serve"),
    base_port: int = typer.Option(
        DEFAULT_BROWSER_PORT,
        "--base-port",
        help="Starting port for local + remote port search (walks upward)",
    ),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open local browser"),
    ssh_options: str = typer.Option(
        "", "--ssh-options", help="Extra SSH flags (e.g. '-i ~/.ssh/mykey')"
    ),
    gcp: bool = typer.Option(False, "--gcp", help="Use gcloud compute ssh instead of plain ssh"),
    zone: str = typer.Option("us-central1-b", "--zone", help="GCP zone (only with --gcp)"),
    project: str = typer.Option("", "--project", help="GCP project (only with --gcp)"),
) -> None:
    """SSH into a remote host, start metabrowser serve, and tunnel it to localhost.

    Both local and remote ports are chosen by walking upward from --base-port,
    so multiple remote sessions can coexist on the same host pair. Ctrl-C
    tears down the tunnel and kills the remote serve cleanly.
    """
    # The environment default is consulted only when --gcp is set.
    effective_project = project or os.environ.get("METABROWSER_GCP_PROJECT", "")

    try:
        local_port = find_available_local_port(
            "127.0.0.1", range(base_port, base_port + DEFAULT_PORT_SEARCH_COUNT)
        )
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    typer.echo(f"Probing {host} for a free remote port...")
    remote_port = _probe_remote_free_port(
        host,
        base_port,
        gcp=gcp,
        zone=zone,
        project=effective_project,
        ssh_options=ssh_options,
    )

    # Use the explicit ``serve`` subcommand on the remote: the bare-form
    # rewrite in metabrowser.cli.serve.main() also accepts ``metabrowser
    # <path>``, but being explicit here insulates this command from any
    # future change in subcommand routing.
    inner_cmd = (
        'export PATH="$HOME/.local/bin:$PATH" && '
        f"metabrowser serve {shlex.quote(path)}"
        f" --port {remote_port} --host 127.0.0.1 --no-open"
    )
    # Wrap so remote serve dies when the SSH channel closes — prevents orphan
    # servers from accumulating on the remote host across sessions.
    remote_cmd = wrap_with_stdin_watchdog(inner_cmd)

    cmd = build_ssh_tunnel_command(
        host,
        remote_cmd=remote_cmd,
        local_port=local_port,
        remote_port=remote_port,
        ssh_options=ssh_options,
        gcp=gcp,
        zone=zone,
        project=effective_project,
    )

    url = f"http://localhost:{local_port}"
    typer.echo(f"Connecting to {host} and starting metabrowser serve...")
    typer.echo(f"Tunnel: localhost:{local_port} → {host}:{remote_port}")
    typer.echo(f"Browser URL: {url}")
    typer.echo("Press Ctrl-C to stop.\n")

    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    def _forward_signal(signum: int, _frame: object) -> None:
        if proc.poll() is None:
            proc.send_signal(signum)

    signal.signal(signal.SIGINT, _forward_signal)  # type: ignore[arg-type]
    signal.signal(signal.SIGTERM, _forward_signal)  # type: ignore[arg-type]

    if not no_open:
        time.sleep(3)
        if proc.poll() is None:
            try:
                webbrowser.open(url, new=2)
            except (webbrowser.Error, OSError) as exc:
                typer.echo(
                    f"Could not auto-open browser ({exc}); visit {url} manually.",
                    err=True,
                )

    proc.wait()

    if proc.returncode == 127:
        typer.echo(
            f"\nmetabrowser is not available on {host}.\n"
            "Install it on the remote host (e.g. via your team's bootstrap script).",
            err=True,
        )

    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)
