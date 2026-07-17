"""metab remote — open Metabrowser on a remote host via SSH tunnel.

Walks both local and remote ports upward from a base port so multiple
remote sessions can coexist on the same host pair. Ctrl-C tears down the
tunnel and kills the remote serve cleanly.

Registered as a subcommand on the unified ``metab`` Typer app
(see :mod:`metabrowser.cli.serve`). There's no standalone console
script — invoke as ``metab remote <host> --path <remote-root>``.
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import webbrowser
from contextlib import suppress

import typer

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.ssh_utils import (
    build_ssh_command,
    build_ssh_tunnel_command,
    wrap_with_stdin_watchdog,
)
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.server_utils import (
    MAX_TCP_PORT,
    find_available_local_port,
    port_search_range,
    remote_port_probe_script,
)
from metabrowser.settings import DEFAULT_BROWSER_PORT


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except (webbrowser.Error, OSError) as exc:
        typer.echo(f"Could not auto-open browser ({exc}); visit {url} manually.", err=True)


def _probe_remote_free_port(
    host: str,
    base_port: int,
    *,
    gcp: bool,
    zone: str,
    project: str,
    ssh_options: str,
) -> int:
    """Ask the remote host which port to use for ``metab serve``.

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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        executable = cmd[0]
        raise CLIError(
            f"Unable to start {executable} while probing remote port on {host}: {exc}. "
            f"Install {executable} and ensure it is available on PATH."
        ) from exc
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
        min=1,
        max=MAX_TCP_PORT,
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
    """SSH into a remote host, start metab serve, and tunnel it to localhost.

    Both local and remote ports are chosen by walking upward from --base-port,
    so multiple remote sessions can coexist on the same host pair. Ctrl-C
    tears down the tunnel and kills the remote serve cleanly.
    """
    _load_dotenv_chain()

    # The environment default is consulted only when --gcp is set.
    effective_project = project or os.environ.get("METABROWSER_GCP_PROJECT", "")

    try:
        local_port = find_available_local_port(
            "127.0.0.1",
            port_search_range(base_port),
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
    # rewrite in metabrowser.cli.serve.main() also accepts ``metab
    # <path>``, but being explicit here insulates this command from any
    # future change in subcommand routing.
    inner_cmd = (
        'export PATH="$HOME/.local/bin:$PATH" && '
        f"metab serve {shlex.quote(path)}"
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
    typer.echo(f"Connecting to {host} and starting metab serve...")
    typer.echo(f"Tunnel: localhost:{local_port} → {host}:{remote_port}")
    typer.echo(f"Browser URL: {url}")
    typer.echo("Press Ctrl-C to stop.\n")

    try:
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    except OSError as exc:
        executable = cmd[0]
        raise CLIError(
            f"Unable to start {executable} while connecting to {host}: {exc}. "
            f"Install {executable} and ensure it is available on PATH."
        ) from exc

    def _forward_signal(signum: int, _frame: object) -> None:
        if proc.poll() is None:
            # The child can exit between the liveness check and delivery.
            with suppress(ProcessLookupError):
                proc.send_signal(signum)

    previous_handlers = []
    try:
        previous_handlers.append((signal.SIGINT, signal.signal(signal.SIGINT, _forward_signal)))
        previous_handlers.append((signal.SIGTERM, signal.signal(signal.SIGTERM, _forward_signal)))

        if not no_open:
            wait_for_http_ok_then(
                "127.0.0.1",
                local_port,
                url,
                on_ready=lambda: _open_browser(url) if proc.poll() is None else None,
                on_error=lambda message: typer.echo(message, err=True),
                is_cancelled=lambda: proc.poll() is not None,
            )

        returncode = proc.wait()
    finally:
        for signum, previous_handler in reversed(previous_handlers):
            signal.signal(signum, previous_handler)

    if returncode == 127:
        typer.echo(
            f"\nThe metab command is not available on {host}.\n"
            "Install the metabrowser package on the remote host "
            "(e.g. via your team's bootstrap script).",
            err=True,
        )

    if returncode != 0:
        exit_code = 128 + abs(returncode) if returncode < 0 else returncode
        raise typer.Exit(code=exit_code)
