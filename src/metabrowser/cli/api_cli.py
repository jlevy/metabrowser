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

from metabrowser.cli.asgi_client import (
    INDEX_READY_TIMEOUT_S,
    ApiResponse,
    InProcessClient,
)
from metabrowser.cli.asgi_client import wait_for_index as _wait_for_index
from metabrowser.cli.common import apply_log_level
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.mirror_refresh import drain_refreshes
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


# A one-shot refresh reports how the refresh it asked for ended, after it has, and exits
# non-zero unless the fetch ran or another process's refresh is running.
_REFRESH_ROUTE = "/api/source/refresh"
_STATUS_ROUTE = "/api/source/status"
_REFRESH_ENDED_WELL = frozenset({"succeeded", "default_branch_unknown", "refreshing_elsewhere"})
# Any other POST that answers 202 may name, as ``status_route``, the GET that reports
# how the work it started ended, as a plugin's refresh does; it is followed the same way.
_STATUS_ROUTE_FIELD = "status_route"
# How long a one-shot command waits for that refresh: one Git deadline. A refresh that
# prunes and fetches again can run longer; the command then says it did not finish, and
# leaving stops it, as a server's shutdown does.
_REFRESH_DRAIN_S = GIT_ACQUISITION_TIMEOUT_S


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
) -> tuple[ApiResponse, str, tuple[str, ApiResponse] | None]:
    """Return the response, the index state it was produced under, and any follow-up.

    The follow-up is the status after a refresh this request started has ended.
    """

    index_detail = "skipped"
    async with InProcessClient(app, label="api", logger=LOG) as client:
        if route.startswith(_INDEX_DEPENDENT):
            result = await _wait_for_index(client, timeout_s=index_timeout_s)
            index_detail = result.detail if result.completed else f"incomplete: {result.detail}"
        if body:
            response = await client.post(route, body=body)
        else:
            response = await client.get(route)
        # Leaving the client shuts the application down, which cancels background work.
        # The only background work a one-shot command has is a refresh its own request
        # asked for, and that is the work the command exists to do, so let it finish.
        await drain_refreshes(app, timeout_s=_REFRESH_DRAIN_S)
        after: tuple[str, ApiResponse] | None = None
        follow = _follow_route(route, response) if body else None
        if follow is not None:
            after = (follow, await client.get(follow))
        return response, index_detail, after


def _follow_route(route: str, response: ApiResponse) -> str | None:
    """The status route that reports how the work a 202 answer started ended, if any."""

    if response.status_code != 202:
        return None
    if route.split("?", 1)[0] == _REFRESH_ROUTE:
        return _STATUS_ROUTE
    try:
        declared = response.json()
    except ValueError:
        return None
    named = declared.get(_STATUS_ROUTE_FIELD) if isinstance(declared, dict) else None
    if isinstance(named, str) and named.startswith("/api/") and "?" not in named:
        return named
    return None


def _request_body(data: Path | None) -> bytes:
    if data is None:
        return b""
    try:
        body = data.expanduser().resolve().read_bytes()
    except OSError as exc:
        raise CLIError(f"cannot read request body from {data}: {exc}") from exc
    if not body:
        # An empty body would fall through to the GET path, so --data would
        # look accepted while changing nothing about the request.
        raise CLIError(f"request body from {data} is empty; --data needs content")
    return body


def _echo_envelope(
    label: str, route: str, response: ApiResponse, ctx: NormalizeContext, fmt: str
) -> None:
    typer.echo(f"{label}: {route}")
    typer.echo(f"status: {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        typer.echo(normalize_text(response.text(), ctx))
    else:
        typer.echo(_render(normalize_payload(payload, ctx), fmt))


def _refresh_outcome(after: ApiResponse) -> tuple[bool, str | None]:
    """Whether the refresh a one-shot command waited for is still running, and its outcome.

    The outcome is ``None`` when it ended well: for the mirror, a fetch that ran or
    another process's refresh still running; for a plugin's refresh (``last_refresh``),
    only ``succeeded``, since one that found the store busy did not refresh anything.
    """

    try:
        status = after.json()
    except ValueError:
        return False, None
    if not isinstance(status, dict):
        return False, None
    running = status.get("refreshing") is True
    outcome = status.get("last_outcome")
    if isinstance(outcome, dict) and outcome.get("operation") == "refresh":
        value = outcome.get("outcome")
        if not isinstance(value, str) or value in _REFRESH_ENDED_WELL:
            return running, None
        return running, value
    refresh = status.get("last_refresh")
    if isinstance(refresh, dict):
        value = refresh.get("outcome")
        if not isinstance(value, str) or value == "succeeded":
            return running, None
        return running, value
    return running, None


def _emit_api_response(
    route: str,
    response: ApiResponse,
    index_detail: str,
    *,
    fmt: str,
    normalize_root: Path,
    after: tuple[str, ApiResponse] | None = None,
) -> None:
    ctx = NormalizeContext(root=normalize_root)
    _echo_envelope("api", route, response, ctx, fmt)

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
    if after is not None:
        follow, followed = after
        _echo_envelope("after", follow, followed, ctx, fmt)
        running, outcome = _refresh_outcome(followed)
        if running:
            raise CLIError(
                f"the refresh did not finish within {_REFRESH_DRAIN_S:g}s and was stopped"
            )
        if outcome is not None:
            raise CLIError(f"the refresh ended with {outcome}")


async def aissue_on_active_session(
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    normalize_root: Path,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Issue one request against the already-attached subject. No ``_set_root_dir``."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")

    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )
    apply_log_level(log_level)
    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )
    from metabrowser import server

    response, index_detail, after = await _issue(
        server.app, route, body=_request_body(data), index_timeout_s=index_timeout_s
    )
    _emit_api_response(
        route, response, index_detail, fmt=fmt, normalize_root=normalize_root, after=after
    )


def run_api_on_active_session(
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    normalize_root: Path,
) -> None:
    asyncio.run(
        aissue_on_active_session(
            route=route,
            fmt=fmt,
            data=data,
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout_s,
            normalize_root=normalize_root,
        )
    )


def run_api(
    root: Path,
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> None:
    """Issue one request through the in-process ASGI stack and print it."""

    if not route.startswith("/api/"):
        raise CLIError(f"route must begin with /api/; got {route}")

    load_dotenv_chain()
    from metabrowser.capabilities import apply_capabilities

    apply_capabilities(
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )
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
    response, index_detail, after = asyncio.run(
        _issue(server.app, route, body=_request_body(data), index_timeout_s=index_timeout_s)
    )
    _emit_api_response(route, response, index_detail, fmt=fmt, normalize_root=resolved, after=after)
