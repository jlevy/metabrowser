"""The ``--api`` mode: any data route through the real request stack.

``--walk`` and ``--diff`` reach their models through the library, so they prove
the model and not the wire. A route can accept a parameter the library never
sees, or drop an envelope key, with those transcripts still green. This mode
issues the request the browser would issue, through the same middleware,
routing, and serialization, and prints the normalized envelope.

One mode covers every route that exists now and every route added later, which
is why the parity rule prefers adding a route to adding a CLI mode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import typer
import yaml

from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S, ApiResponse, InProcessClient
from metabrowser.cli.asgi_client import wait_for_index as _wait_for_index
from metabrowser.cli.common import apply_log_level
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.normalize import NormalizeContext, normalize_payload, normalize_text

LOG = logging.getLogger(__name__)

# The progress route is how the index wait itself reports, so waiting on it
# before requesting it would never terminate.
_INDEX_PROGRESS_ROUTE = "/api/index/progress"


def _render(payload: Any, fmt: str) -> str:
    if fmt == "yaml":
        return yaml.safe_dump(
            payload,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ).rstrip("\n")
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)


async def _issue(
    app: Any,
    route: str,
    *,
    body: bytes,
    index_timeout_s: float,
) -> ApiResponse:
    async with InProcessClient(app, label="api", logger=LOG) as client:
        if not route.startswith(_INDEX_PROGRESS_ROUTE):
            await _wait_for_index(client, timeout_s=index_timeout_s)
        if body:
            return await client.post(route, body=body)
        return await client.get(route)


def run_api(
    root: Path,
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> None:
    """Issue one request through the in-process ASGI stack and print it."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")

    load_dotenv_chain()
    apply_log_level(log_level)
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    body = b""
    if data is not None:
        try:
            body = data.expanduser().resolve().read_bytes()
        except OSError as exc:
            raise CLIError(f"cannot read request body from {data}: {exc}") from exc

    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    from metabrowser import server

    server._set_root_dir(resolved)
    response = asyncio.run(_issue(server.app, route, body=body, index_timeout_s=index_timeout_s))

    ctx = NormalizeContext(root=resolved)
    typer.echo(f"api: {route}")
    typer.echo(f"status: {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        typer.echo(normalize_text(response.text(), ctx))
    else:
        typer.echo(_render(normalize_payload(payload, ctx), fmt))

    if not 200 <= response.status_code < 300:
        raise CLIError(f"{route} returned HTTP {response.status_code}")
