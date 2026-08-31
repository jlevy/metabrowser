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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import typer

from metabrowser.cli.asgi_client import (
    INDEX_READY_TIMEOUT_S,
    ApiResponse,
    InProcessClient,
    wait_for_index,
)
from metabrowser.cli.common import apply_log_level
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.normalize import NormalizeContext, normalize_payload
from metabrowser.view_routes import (
    COMMIT_ROUTE_PREFIX,
    VIEW_ROUTE_PREFIX,
    decode_safe_commit_route,
    decode_safe_view_path,
    format_view_href,
)

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

# A container entry names the file it lives inside, which is the whole point of
# the /view/<container>/<inner> address, so the report says both.
_CONTAINER_FIELDS: tuple[str, ...] = ("container", "container_inner")


async def _fetch(
    app: Any,
    route: str,
    params: Mapping[str, str],
    *,
    index_timeout_s: float,
    needs_index: bool,
) -> ApiResponse:

    async with InProcessClient(app, label="show", logger=LOG) as client:
        # A file envelope answers from disk; a folder envelope carries
        # inventory aggregates and reads "pending" until the scan finishes.
        # --show knows which it is asked for, so it waits only when it must.
        if needs_index:
            index = await wait_for_index(client, timeout_s=index_timeout_s)
            if not index.completed:
                typer.echo(f"index: incomplete: {index.detail}", err=True)
        return await client.get(route, params=params)


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
    names = (*fields, *(name for name in _CONTAINER_FIELDS if name in payload))
    parts = [
        f"{'inner' if name == 'container_inner' else name}={payload[name]}"
        for name in names
        if name in payload
    ]
    detail = " ".join(parts) if parts else "no summary fields"
    return f"{envelope_type} envelope; {detail}"


def _describe_comparison(payload: dict[str, Any], inner: str) -> str:
    """Summarize a comparison envelope, which has its own shape."""

    resolved = payload.get("resolved")
    manifest = payload.get("manifest")
    parts: list[str] = []
    if isinstance(resolved, dict):
        for name in ("comparison_id", "kind", "base_policy"):
            if name in resolved:
                parts.append(f"{name}={resolved[name]}")
    if isinstance(manifest, dict):
        files = manifest.get("files")
        if isinstance(files, list):
            parts.append(f"files={len(files)}")
        if "truncated" in manifest:
            parts.append(f"truncated={manifest['truncated']}")
    if inner:
        parts.append(f"file={inner}")
    detail = " ".join(parts) if parts else "no summary fields"
    return f"comparison envelope; {detail}"


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

    commit = None
    if path.startswith(COMMIT_ROUTE_PREFIX):
        commit = decode_safe_commit_route(path.encode())
        if commit is None:
            raise CLIError(f"{path} is not a route this grammar accepts")

    if commit is not None:
        revision, inner = commit
        params = {"revision": revision}
        if inner:
            params["file"] = inner
        route = "/api/plugin/diff/comparison"
    else:
        selection = path
        if path.startswith(VIEW_ROUTE_PREFIX):
            decoded = decode_safe_view_path(path.encode())
            if decoded is None:
                raise CLIError(f"{path} is not a route this grammar accepts")
            selection = decoded
        route, params = "/api/file", {"path": selection}

    # A directory's envelope carries inventory aggregates; a file's does not.
    needs_index = commit is None and (resolved / params["path"]).is_dir()
    response = asyncio.run(
        _fetch(
            server.app,
            route,
            params,
            index_timeout_s=index_timeout_s,
            needs_index=needs_index,
        )
    )

    if response.incomplete:
        raise CLIError(f"{path} failed mid-response; the model below would be truncated")
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

    if commit is not None:
        revision, inner = commit
        shown_route = COMMIT_ROUTE_PREFIX + revision + (f"/{inner}" if inner else "")
        kind = "comparison"
        # The same registry /api/file reads, so the views reported are the real
        # registered ones rather than a second list that could drift from them.
        views: Any = server._views_for_kind("diff")
        model = _describe_comparison(payload, inner)
    else:
        logical = str(payload.get("path", path))
        shown_route = format_view_href(logical) if logical not in ("", ".") else "/view/"
        kind = str(payload.get("kind", "unknown"))
        views = payload.get("views")
        model = _describe_model(payload)

    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "show": path,
                    "route": shown_route,
                    "kind": kind,
                    "views": views,
                    "model": model,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    typer.echo(f"show: {path}")
    typer.echo(f"route: {shown_route}")
    typer.echo(f"kind: {kind}")
    typer.echo(f"views: {_describe_views(views)}")
    typer.echo(f"model: {model}")
