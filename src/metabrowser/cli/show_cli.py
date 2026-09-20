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
from metabrowser.inventory_engine.contract import (
    canonical_inventory_path,
)
from metabrowser.normalize import NormalizeContext, normalize_payload
from metabrowser.view_routes import (
    COMMIT_ROUTE_PREFIX,
    VIEW_ROUTE_PREFIX,
    decode_safe_commit_route,
    decode_safe_view_path,
    format_commit_href,
    format_inventory_view_href,
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


def _display_selection(path: str) -> str:
    """Return a terminal-safe spelling for one native or route selection."""

    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        # Command-line arguments on POSIX preserve undecodable bytes as
        # surrogates. The inventory spelling is printable ASCII at exactly
        # those positions and remains distinct from a literal percent name.
        return canonical_inventory_path(path)
    return path


def _encoded_route(path: str, display_path: str) -> bytes:
    """Encode a URL-shaped CLI selection or report its printable spelling."""

    try:
        return path.encode()
    except UnicodeEncodeError as exc:
        raise CLIError(f"{display_path} is not a route this grammar accepts") from exc


def _prepare_plugins(plugins_dir: list[Path] | None) -> None:
    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )


def _emit_show(
    *,
    display_path: str,
    shown_route: str,
    kind: str,
    views: Any,
    model: str,
    fmt: str,
) -> None:
    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "show": display_path,
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
    typer.echo(f"show: {display_path}")
    typer.echo(f"route: {shown_route}")
    typer.echo(f"kind: {kind}")
    typer.echo(f"views: {_describe_views(views)}")
    typer.echo(f"model: {model}")


async def ashow_active(
    *,
    path: str,
    fmt: str = "text",
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    normalize_root: Path,
    filesystem_root: Path | None,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Report one selection against the already-attached subject."""

    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )
    apply_log_level(log_level)
    display_path = _display_selection(path)
    _prepare_plugins(plugins_dir)

    from metabrowser import server

    commit = None
    native_selection: str | None = None
    git_wire: str | None = None
    if path.startswith(COMMIT_ROUTE_PREFIX):
        commit = decode_safe_commit_route(_encoded_route(path, display_path))
        if commit is None:
            raise CLIError(f"{display_path} is not a route this grammar accepts")

    if commit is not None:
        revision, inner = commit
        params = {"revision": revision}
        if inner:
            params["file"] = inner
        route = "/api/plugin/diff/comparison"
        needs_index = False
    elif filesystem_root is None:
        from metabrowser.git.content_routes import decode_git_view_path, split_git_container_wire
        from metabrowser.git.tree_source import GitPath, GitPathError

        selection = path
        if path.startswith(VIEW_ROUTE_PREFIX):
            decoded = decode_git_view_path(_encoded_route(path, display_path))
            if decoded is None:
                raise CLIError(f"{display_path} is not a route this grammar accepts")
            selection = decoded
        try:
            if selection.startswith("g1-"):
                git_path, inner = split_git_container_wire(selection)
                git_wire = f"{git_path.to_wire()}/{inner}" if inner else git_path.to_wire()
            else:
                git_wire = GitPath.from_display(selection).to_wire()
        except GitPathError as exc:
            raise CLIError(f"{display_path} is not a GitPath this pin accepts") from exc
        route, params = "/api/file", {"path": git_wire}
        needs_index = True
    else:
        native_selection = path
        if path.startswith(VIEW_ROUTE_PREFIX):
            decoded = decode_safe_view_path(_encoded_route(path, display_path))
            if decoded is None:
                raise CLIError(f"{display_path} is not a route this grammar accepts")
            native_selection = decoded
        # Command-line paths and decoded browser routes are native filesystem
        # spellings. `/api/file` speaks the canonical identity published by the
        # inventory, where a literal `%` is escaped as `%25` so percent-looking
        # siblings cannot alias each other.
        route, params = "/api/file", {"path": canonical_inventory_path(native_selection)}
        needs_index = (filesystem_root / native_selection).is_dir()

    response = await _fetch(
        server.app,
        route,
        params,
        index_timeout_s=index_timeout_s,
        needs_index=needs_index,
    )

    if response.incomplete:
        raise CLIError(f"{display_path} failed mid-response; the model below would be truncated")
    if response.status_code != 200:
        raise CLIError(
            f"{display_path} is not a selection the browser can open (HTTP {response.status_code})"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CLIError(f"{display_path} returned a non-JSON envelope") from exc
    if not isinstance(payload, dict):
        raise CLIError(f"{display_path} returned an unexpected envelope")

    ctx = NormalizeContext(root=normalize_root)
    payload = normalize_payload(payload, ctx)

    if commit is not None:
        revision, inner = commit
        shown_route = format_commit_href(revision, inner)
        kind = "comparison"
        # The same registry /api/file reads, so the views reported are the real
        # registered ones rather than a second list that could drift from them.
        views: Any = server._views_for_kind("diff")
        model = _describe_comparison(payload, inner)
    elif git_wire is not None:
        identity = payload.get("path", git_wire)
        if not isinstance(identity, str):
            raise CLIError(f"{display_path} returned an unexpected path identity")
        shown_route = f"{VIEW_ROUTE_PREFIX}{identity}" if identity else "/view/"
        kind = str(payload.get("kind", "unknown"))
        views = payload.get("views")
        model = _describe_model(payload)
    else:
        identity = payload.get("path", params["path"])
        if not isinstance(identity, str):
            raise CLIError(f"{display_path} returned an unexpected path identity")
        try:
            shown_route = (
                format_inventory_view_href(identity) if identity not in ("", ".") else "/view/"
            )
        except (UnicodeEncodeError, ValueError) as exc:
            raise CLIError(f"{display_path} returned a non-canonical path identity") from exc
        kind = str(payload.get("kind", "unknown"))
        views = payload.get("views")
        model = _describe_model(payload)

    _emit_show(
        display_path=display_path,
        shown_route=shown_route,
        kind=kind,
        views=views,
        model=model,
        fmt=fmt,
    )


def run_show_active(
    *,
    path: str,
    fmt: str = "text",
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    normalize_root: Path,
    filesystem_root: Path | None,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    asyncio.run(
        ashow_active(
            path=path,
            fmt=fmt,
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout_s,
            normalize_root=normalize_root,
            filesystem_root=filesystem_root,
            untrusted=untrusted,
            no_active_content=no_active_content,
            allow_edits=allow_edits,
        )
    )


def run_show(
    root: Path,
    *,
    path: str,
    fmt: str = "text",
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Report route, kind, views, and model summary for one filesystem selection."""

    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")
    from metabrowser import server

    server._set_root_dir(resolved)
    run_show_active(
        path=path,
        fmt=fmt,
        plugins_dir=plugins_dir,
        log_level=log_level,
        index_timeout_s=index_timeout_s,
        normalize_root=resolved,
        filesystem_root=resolved,
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )
