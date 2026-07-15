"""Plugin-static and data-hook Starlette routes.

Routes are mounted by the server at startup based on the discovered
plugins:

- ``GET /plugin-static/<plugin>/<resource>`` — serves files from the
  plugin's directory. Path-traversal-guarded; ETag matches the existing
  /api/file helper.
- ``GET|POST /api/plugin/<plugin>/<route>`` — dispatches to the Python
  sidekick callable declared in the manifest's ``[[data_hook]]`` block.

Both routes are namespaced by the plugin's ``[plugin].name`` field; two
plugins cannot collide.
"""

from __future__ import annotations

import importlib
import json
import logging
import mimetypes
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from pathlib import Path
from typing import Any, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from strif import file_mtime_hash

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


def _make_plugin_static_handler(
    plugins: dict[str, LoadedPlugin],
) -> Callable[[Request], Awaitable[Response]]:
    """Build the /plugin-static/{plugin}/{path:path} handler."""

    async def handler(request: Request) -> Response:
        plugin_name = request.path_params["plugin"]
        rel = request.path_params["path"]
        plugin = plugins.get(plugin_name)
        if plugin is None:
            return PlainTextResponse(f"unknown plugin '{plugin_name}'", status_code=404)
        resolved = _safe_join(plugin.static_root, rel)
        if resolved is None:
            return PlainTextResponse(f"not found: {rel}", status_code=404)

        # ETag: same shape as the rest of the app uses for /api/file.
        etag = f'"mb-{file_mtime_hash(resolved)}"'
        if_none_match = request.headers.get("if-none-match", "")
        if if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})

        media_type, _ = mimetypes.guess_type(str(resolved))
        body = resolved.read_bytes()
        headers = {
            "ETag": etag,
            "Cache-Control": "no-cache",  # let revalidation happen via ETag
        }
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
            result: Response | Any = sidekick(request)
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


def build_plugin_routes(plugins: list[LoadedPlugin]) -> list[Route]:
    """Return the full list of plugin-static + data-hook Starlette routes.

    Order: one global static route (handles every plugin via path params)
    plus one route per declared data hook. The static route uses path
    params so a single Starlette Route handles the whole namespace; data
    hooks get one route each so their HTTP methods can vary per hook.
    """
    plugins_by_name = {p.name: p for p in plugins}
    routes: list[Route] = [
        Route(
            "/plugin-static/{plugin}/{path:path}",
            endpoint=_make_plugin_static_handler(plugins_by_name),
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
