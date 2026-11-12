"""Plugin-static and data-hook Starlette routes.

Routes are mounted by the server at startup based on the discovered
plugins:

- ``GET /plugin-static/<plugin>/<resource>`` — serves files from the
  plugin's directory. Path-traversal-guarded; ETag matches the existing
  /api/file helper. The shell addresses them as
  ``/plugin-static/<plugin>/@<digest>/<resource>``, a stamp of the whole
  directory (:mod:`metabrowser.asset_stamps`), and the answer there is
  immutable while the stamp is current; the unstamped address is revalidated.
- ``GET|POST /api/plugin/<plugin>/<route>`` — dispatches to the Python
  sidekick callable declared in the manifest's ``[[data_hook]]`` block.

Both routes are namespaced by the plugin's ``[plugin].name`` field; two
plugins cannot collide.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import mimetypes
from collections.abc import Awaitable, Callable, Mapping
from inspect import isawaitable, iscoroutinefunction
from pathlib import Path
from typing import Any, cast

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from strif import file_mtime_hash

from metabrowser.asset_stamps import StampedTree, split_stamp
from metabrowser.http_caching import (
    build_scoped_etag,
    editable_install,
    matches_if_none_match,
    stamped_asset_cache_control,
)
from metabrowser.plugin_loader.discovery import LoadedPlugin

LOG = logging.getLogger(__name__)


# ── /plugin-static/<plugin>/<resource> ─────────────────────────


def _safe_join(static_root: Path, relative: str) -> Path | None:
    """Resolve ``relative`` against ``static_root`` and reject path-traversal."""
    if not relative:
        return None
    candidate = (static_root / relative).resolve()
    try:
        candidate.relative_to(static_root.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def plugin_tree_is_live(plugin: LoadedPlugin) -> bool:
    """Whether a plugin's files can change while this process runs.

    An operator's plugin directory can, and so can a plugin of an editable install: a
    built-in one when Metabrowser itself is, an entry-point one when its distribution is.
    """
    if plugin.source.startswith("local:"):
        return True
    if plugin.source.startswith("entry-point:"):
        return editable_install(plugin.source.removeprefix("entry-point:"))
    return editable_install("metabrowser")


def plugin_asset_trees(plugins: list[LoadedPlugin]) -> dict[str, StampedTree]:
    """One :class:`StampedTree` per plugin, shared by the shell that names its assets and
    the route that serves them."""
    return {
        plugin.name: StampedTree(plugin.static_root, live=plugin_tree_is_live(plugin))
        for plugin in plugins
    }


def plugin_asset_prefix(name: str, tree: StampedTree | None) -> str:
    """The path a page addresses *name*'s files under: stamped when the tree is."""
    stamp = tree.stamp() if tree is not None else None
    if stamp is None:
        return f"/plugin-static/{name}"
    return f"/plugin-static/{name}/@{stamp.digest}"


def _make_plugin_static_handler(
    plugins: dict[str, LoadedPlugin],
    trees: Mapping[str, StampedTree],
) -> Callable[[Request], Awaitable[Response]]:
    """Build the /plugin-static/{plugin}/{path:path} handler."""

    async def handler(request: Request) -> Response:
        plugin_name = request.path_params["plugin"]
        stamp_digest, rel = split_stamp(request.path_params["path"])
        plugin = plugins.get(plugin_name)
        if plugin is None:
            return PlainTextResponse(f"unknown plugin '{plugin_name}'", status_code=404)
        resolved = _safe_join(plugin.static_root, rel)
        if resolved is None:
            return PlainTextResponse(f"not found: {rel}", status_code=404)

        # The shared validator, so this really is the shape /api/file uses.
        etag = build_scoped_etag(file_mtime_hash(resolved))
        tree = trees.get(plugin_name)
        stamp = tree.latest() if tree is not None and stamp_digest is not None else None
        current = (
            stamp is not None and stamp.digest == stamp_digest and stamp.holds(rel, resolved.stat())
        )
        headers = {"ETag": etag, "Cache-Control": stamped_asset_cache_control(current=current)}
        if matches_if_none_match(request, etag):
            return Response(status_code=304, headers=headers)

        media_type, _ = mimetypes.guess_type(str(resolved))
        # Off the event loop: the largest built-in asset is a few hundred KB, an operator's
        # plugin directory has no bound.
        body = await asyncio.to_thread(resolved.read_bytes)
        return Response(
            content=body,
            status_code=200,
            media_type=media_type or "application/octet-stream",
            headers=headers,
        )

    return handler


# ── /api/plugin/<plugin>/<route> data-hook dispatcher ──────────


def _resolve_sidekick(spec: str) -> Callable[[Request], Awaitable[Response] | Response]:
    """Import a sidekick callable from a ``module:callable`` spec."""
    module_name, _, attr = spec.partition(":")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr)
    if not callable(fn):
        raise TypeError(f"sidekick {spec} is not callable")
    return cast(Callable[[Request], Awaitable[Response] | Response], fn)


def _make_data_hook_handler(
    plugin: LoadedPlugin,
    route: str,
) -> Callable[[Request], Awaitable[Response]]:
    """Build the /api/plugin/{plugin}/{route} handler for one data hook."""
    matching = [dh for dh in plugin.manifest.data_hook if dh.route == route]
    if not matching:
        raise ValueError(f"plugin '{plugin.name}' has no data hook for route '{route}'")
    spec = matching[0]
    sidekick = _resolve_sidekick(spec.sidekick)

    def _plugin_error_response(detail: str) -> JSONResponse:
        return JSONResponse(
            {
                "type": "plugin_error",
                "plugin": plugin.name,
                "route": route,
                "error": "Plugin data hook failed",
                "detail": detail,
                "warning": (
                    "Metabrowser returned a degraded plugin warning instead "
                    "of a server 500. Check the server log for the traceback."
                ),
            }
        )

    def _response_detail(response: Response) -> str:
        body = getattr(response, "body", b"")
        if isinstance(body, bytes) and body:
            text = body.decode("utf-8", errors="replace")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return text
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("error")
                if detail:
                    return str(detail)
            return text
        return f"HTTP {response.status_code}"

    async def handler(request: Request) -> Response:
        try:
            # Synchronous sidekicks run in the threadpool: this dispatcher is
            # itself async, so calling them inline would execute their full
            # (bounded, but real) parse/read work on the event loop —
            # Starlette's own sync-endpoint path offloads the same way.
            if iscoroutinefunction(sidekick):
                result: Response | Any = await sidekick(request)
            else:
                result = await run_in_threadpool(sidekick, request)
                if isawaitable(result):
                    result = await result
        except Exception as exc:
            LOG.exception(
                "metabrowser data-hook %s/%s raised %s",
                plugin.name,
                route,
                type(exc).__name__,
            )
            return _plugin_error_response(f"{type(exc).__name__}: {exc}")
        if isinstance(result, Response):
            if result.status_code >= 500:
                LOG.warning(
                    "metabrowser data-hook %s/%s returned HTTP %s; degrading",
                    plugin.name,
                    route,
                    result.status_code,
                )
                return _plugin_error_response(_response_detail(result))
            return result
        return JSONResponse(result)

    return handler


# ── Route assembly ─────────────────────────────────────────────


def build_plugin_routes(
    plugins: list[LoadedPlugin], *, asset_trees: Mapping[str, StampedTree] | None = None
) -> list[Route]:
    """Return the full list of plugin-static + data-hook Starlette routes.

    Order: one global static route (handles every plugin via path params)
    plus one route per declared data hook. The static route uses path
    params so a single Starlette Route handles the whole namespace; data
    hooks get one route each so their HTTP methods can vary per hook.

    *asset_trees* are the stamps the shell names the plugins' assets with
    (:func:`plugin_asset_trees`); without them every answer is revalidated.
    """
    plugins_by_name = {p.name: p for p in plugins}
    routes: list[Route] = [
        Route(
            "/plugin-static/{plugin}/{path:path}",
            endpoint=_make_plugin_static_handler(plugins_by_name, asset_trees or {}),
            methods=["GET"],
            name="plugin-static",
        ),
    ]
    for plugin in plugins:
        if plugin.source.startswith("local:") and plugin.manifest.data_hook:
            LOG.warning(
                "metabrowser local plugin '%s' declares Python data hooks; "
                "operator-directory plugins are JavaScript-only, so the hooks are ignored",
                plugin.name,
            )
            continue
        for hook in plugin.manifest.data_hook:
            try:
                handler = _make_data_hook_handler(plugin, hook.route)
            except (ImportError, AttributeError, TypeError, ValueError) as exc:
                LOG.warning(
                    "metabrowser plugin '%s' data-hook %s skipped: %s",
                    plugin.name,
                    hook.route,
                    exc,
                )
                continue
            routes.append(
                Route(
                    f"/api/plugin/{plugin.name}/{hook.route}",
                    endpoint=handler,
                    methods=hook.methods,
                    name=f"plugin-data-hook-{plugin.name}-{hook.route}",
                )
            )
    return routes
