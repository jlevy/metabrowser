"""The ``--show`` mode: the four layers for one selection.

A selection travels route, kind, model, view. Three of those are data and need
no screen, so one command can answer "what would the browser do with this
path" -- which route it resolves to, what kind it classifies as, which views it
offers, and a summary of the model behind them.

This is the report for ``/api/file``, the route that decides the tabs a reader
sees for every selection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import typer

from metabrowser.cli.asgi_client import INDEX_READY_TIMEOUT_S, ApiResponse, InProcessClient
from metabrowser.cli.common import apply_log_level
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.normalize import NormalizeContext, normalize_payload
from metabrowser.view_routes import format_view_href

LOG = logging.getLogger(__name__)

# Model fields worth reporting per envelope type. Absent keys are skipped, so a
# type that grows a field reports it only once this list names it -- which
# keeps the summary a stated contract rather than whatever the envelope holds.
_MODEL_FIELDS: dict[str, tuple[str, ...]] = {
    "text": ("size", "content_bytes", "content_truncated"),
    "binary": ("size",),
    "folder": ("readme_path",),
}
_DEFAULT_MODEL_FIELDS: tuple[str, ...] = ("size",)


async def _fetch(app: Any, path: str, *, index_timeout_s: float) -> ApiResponse:
    from metabrowser.cli.asgi_client import wait_for_index

    async with InProcessClient(app, label="show", logger=LOG) as client:
        await wait_for_index(client, timeout_s=index_timeout_s)
        return await client.get("/api/file", params={"path": path})


def _describe_views(views: Any) -> str:
    if not isinstance(views, list) or not views:
        return "none"
    rendered: list[str] = []
    for view in views:
        if not isinstance(view, dict):
            continue
        label = str(view.get("id", "?"))
        if view.get("default"):
            label += " (default)"
        rendered.append(label)
    return ", ".join(rendered) if rendered else "none"


def _describe_model(payload: dict[str, Any]) -> str:
    envelope_type = str(payload.get("type", "unknown"))
    fields = _MODEL_FIELDS.get(envelope_type, _DEFAULT_MODEL_FIELDS)
    parts = [f"{name}={payload[name]}" for name in fields if name in payload]
    detail = " ".join(parts) if parts else "no summary fields"
    return f"{envelope_type} envelope; {detail}"


def run_show(
    root: Path,
    *,
    path: str,
    fmt: str = "text",
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> None:
    """Report route, kind, views, and model summary for one selection."""

    load_dotenv_chain()
    apply_log_level(log_level)
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    from metabrowser import server

    server._set_root_dir(resolved)
    response = asyncio.run(_fetch(server.app, path, index_timeout_s=index_timeout_s))

    if response.status_code != 200:
        raise CLIError(
            f"{path} is not a selection the browser can open (HTTP {response.status_code})"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CLIError(f"{path} returned a non-JSON envelope") from exc
    if not isinstance(payload, dict):
        raise CLIError(f"{path} returned an unexpected envelope")

    ctx = NormalizeContext(root=resolved)
    payload = normalize_payload(payload, ctx)

    logical = str(payload.get("path", path))
    route = format_view_href(logical) if logical not in ("", ".") else "/view/"
    kind = str(payload.get("kind", "unknown"))
    views = payload.get("views")

    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "show": path,
                    "route": route,
                    "kind": kind,
                    "views": views,
                    "model": _describe_model(payload),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    typer.echo(f"show: {path}")
    typer.echo(f"route: {route}")
    typer.echo(f"kind: {kind}")
    typer.echo(f"views: {_describe_views(views)}")
    typer.echo(f"model: {_describe_model(payload)}")
