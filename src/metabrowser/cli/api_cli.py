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

# Routes whose answer changes once the inventory scan finishes. Measured by
# requesting each one with and without the wait and comparing: /api/recent grew
# from 6 KB to 853 KB on this repository, while /api/routes, /api/file, and the
# Git and plugin routes were byte-identical.
#
# Waiting is therefore opt-in rather than universal. A full scan costs about
# 0.7s on a three-thousand-file tree and grows with it, so making every route
# pay for it made the cheap ones -- route discovery, one file's kind, a Git log
# -- several times slower than the work they do.
_INDEX_DEPENDENT: tuple[str, ...] = (
    "/api/tree",
    "/api/rollup",
    "/api/recent",
    "/api/catalog",
    "/api/capabilities",
    "/api/index/meta",
    # A folder envelope carries inventory aggregates, so /api/file is
    # index-dependent for a directory even though it is not for a file. The
    # sweep that built this list only ever requested a file, and the folder
    # branch returned state "pending" with nulls, HTTP 200, exit 0.
    "/api/file",
    # POST-only, so the GET probe that measured the others could not see it;
    # its whole payload is inventory state, and it reported status "scanning"
    # instead of "done" the moment the wait was skipped.
    "/api/diagnostics/pending-tallies",
    # Same reason, and the GET probe did see it -- it just could not tell a
    # race from an answer. Its whole payload is inventory state, so without the
    # wait what it reports is whichever moment the request happened to land in:
    # its transcript recorded a mid-scan `scanning` on a four-file fixture,
    # which held on one machine and flipped to `done` on a faster one.
    #
    # This does not blind the route. Progress is read live from the browser
    # while a scan runs, which is where it means something; through `--api` the
    # scan is already over by the time anyone reads the output, so the settled
    # answer is both the honest one and the reproducible one.
    "/api/index/progress",
)


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
) -> tuple[ApiResponse, str]:
    """Return the response and the index state it was produced under."""

    index_detail = "skipped"
    async with InProcessClient(app, label="api", logger=LOG) as client:
        if route.startswith(_INDEX_DEPENDENT):
            result = await _wait_for_index(client, timeout_s=index_timeout_s)
            index_detail = result.detail if result.completed else f"incomplete: {result.detail}"
        if body:
            return await client.post(route, body=body), index_detail
        return await client.get(route), index_detail


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
        if not body:
            # An empty body would fall through to the GET path, so --data would
            # look accepted while changing nothing about the request.
            raise CLIError(f"request body from {data} is empty; --data needs content")

    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    from metabrowser import server

    server._set_root_dir(resolved)
    response, index_detail = asyncio.run(
        _issue(server.app, route, body=body, index_timeout_s=index_timeout_s)
    )

    ctx = NormalizeContext(root=resolved)
    typer.echo(f"api: {route}")
    typer.echo(f"status: {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        typer.echo(normalize_text(response.text(), ctx))
    else:
        typer.echo(_render(normalize_payload(payload, ctx), fmt))

    # An envelope built from an index that never finished is not the envelope
    # the browser would have drawn, so say so rather than letting it read clean.
    if index_detail.startswith("incomplete"):
        typer.echo(f"index: {index_detail}", err=True)
    if response.incomplete:
        raise CLIError(
            f"{route} answered HTTP {response.status_code} and then failed mid-response; "
            "the body above is truncated"
        )
    if not 200 <= response.status_code < 300:
        raise CLIError(f"{route} returned HTTP {response.status_code}")
