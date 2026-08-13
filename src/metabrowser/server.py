"""Metabrowser: an extensible, web-based file browser.

Serves a single-page application with:
  - File/folder tree browser (left pane)
  - Detail view (right pane) with interpreted and raw tabs
  - JSONL log parsing for Claude Code, Gemini, Pi
  - Markdown rendering, YAML/JSON syntax highlighting (server-side structure
    + client-side highlight.js)

This module is intentionally thin: it owns the Starlette routes and the
``main()`` entry point. The heavy lifting lives in dedicated modules:

* ``file_kinds``  — file kind taxonomy + view registry
* ``paths_safe``  — ROOT_DIR + path-safety helpers
* ``tree``        — directory walk with scandir + caches
* ``activity``    — file activity tracking (scoped to .logs/.state)
* ``jsonl_view``  — single-pass JSONL parser
* ``charts``      — chart-data extractors

Names that tests/serve.py used to import from this module are re-exported
below so external callers don't break.

Usage::

    uv --config-file uv.toml run --frozen metab ROOT_DIR [--port PORT]
"""

from __future__ import annotations

# ``python -m metabrowser.server`` is a compatibility spelling for the
# canonical CLI. Delegate before this module performs logging or plugin
# discovery so both entry points use the same dotenv, path, and readiness
# bootstrap.
if __name__ == "__main__":
    from metabrowser.cli.main import main as _cli_main

    _cli_main()
    raise SystemExit

import asyncio
import datetime as _dt
import json as _json
import logging
import os
import sys
import time
from html import escape as html_escape
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, cast
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.responses import (
    JSONResponse as _StarletteJSONResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from strif import file_mtime_hash

from metabrowser import kpress_adapter
from metabrowser.activity import (
    ACTIVITY_POLL_INTERVAL_MS,
    TRACKABLE_DISCOVERY_TTL_SECONDS,
    TRACKABLE_FILE_MAX_SIZE,
    _activity_snapshot,
    _collect_trackable_files,
    _collect_trackable_files_cached,
    _discover_trackable_files,
    activity_tracker,
)
from metabrowser.activity import FileActivityTracker as _FileActivityTracker

# Cache invalidator: clear_charts_cache is invoked by the root-change
# handler so chart memos don't stick across served-root swaps.
from metabrowser.charts import clear_charts_cache
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.file_kinds import (
    FILE_KIND_DETECTORS,
    VIEW_REGISTRY,
    FileContext,
    classify_by_ext,
    classify_file_kind,
    register_file_kind_detector,
)
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.git.routes import GIT_ROUTES
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactPath,
)
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.jsonl_view import _parse_jsonl_file

# Document rendering is delegated through the KPress adapter and built-in plugin route.
# KPress is the sole Markdown-to-HTML renderer; raw source remains a separate view.
from metabrowser.paths_safe import (
    _cached_root_prefix,
    _rel_path,
    _relativize,
    _resolved_root_dir,
    _safe_path,
    _safe_subdir,
    _set_root_dir,
)
from metabrowser.plugin_paths import normalize_plugin_dirs
from metabrowser.recent import DEFAULT_LIMIT, MAX_LIMIT, collect_recent_entries
from metabrowser.settings import (
    RECENT_WINDOW_SECONDS,
    SLOW_OPERATION_LOG_SECONDS,
    client_settings_dict,
)
from metabrowser.sse import api_stream
from metabrowser.tree import (
    _IGNORE_CACHE,
    DEFAULT_TREE_DEPTH,
    MAX_TREE_DEPTH,
    SENTINEL_SUMMARY_DEPTH,
    _build_inventory_tree,
    _dir_tree,
    _find_git_root,
    _has_any_leaf,
    _has_any_nongitignored,
    _has_visible_children,
    _subtree_is_all_gitignored,
    _subtree_is_empty,
    _subtree_summary,
    _tree_depth_from_query,
    build_gitignore_check,
    inventory_has_data,
    inventory_status,
)

if TYPE_CHECKING:
    from starlette.requests import Request


# Direct ASGI imports bypass the CLI bootstrap. Load trusted working-tree
# configuration before logging flags and one-shot plugin discovery are read.
load_dotenv_chain()

LOG = logging.getLogger(__name__)
# Bounded startup grace for route-level test calls or direct imports
# where the lifespan hook has not pre-warmed the inventory yet. Keep
# this below the first-paint budget: large trees return partial inventory
# state instead of blocking on a filesystem walk.
_TREE_COLD_START_WAIT_S = 0.10


# ── Performance logging setup ───────────────────────────────────
#
# The browser runs as a long-lived tool against potentially huge trees. Route
# its diagnostics to stderr without mixing them into machine-readable stdout.
# Routine lifecycle and request details stay at DEBUG; INFO is reserved for
# infrequent, useful summaries, while slow requests and failures use WARNING or
# ERROR. A dynamic stream proxy avoids retaining a closed test or embedding
# stream. Setup is idempotent so repeated imports do not double-attach handlers.

_PERF_LOG_HANDLER_TAG = "metabrowser-perf"


class _CurrentStderr:
    """Resolve stderr at write time instead of retaining an import-time stream."""

    def write(self, message: str) -> int:
        return sys.stderr.write(message)

    def flush(self) -> None:
        sys.stderr.flush()


def _setup_perf_logging() -> None:
    """Attach an INFO-level stderr handler to the loggers we emit timing
    info from. Idempotent; safe to call multiple times. Format keeps
    each line short and grep-friendly: ``HH:MM:SS name | message``.
    """
    handler = logging.StreamHandler(cast(TextIO, _CurrentStderr()))
    handler.set_name(_PERF_LOG_HANDLER_TAG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    # Attach to ``metabrowser`` so every child logger (server, tree,
    # activity, charts, sse, …) propagates up to this handler.
    # ``METABROWSER_LOG_LEVEL`` (DEBUG/INFO/WARNING/ERROR) overrides; default INFO.
    level_name = os.environ.get("METABROWSER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    for logger_name in ("metabrowser",):
        lg = logging.getLogger(logger_name)
        lg.setLevel(level)
        already_attached = any(
            getattr(h, "name", None) == _PERF_LOG_HANDLER_TAG for h in lg.handlers
        )
        if not already_attached:
            lg.addHandler(handler)
        # Don't double-emit through the root logger (uvicorn root has
        # its own formatter and would print every line twice).
        lg.propagate = False


_setup_perf_logging()


# ── Async timing decorator ──────────────────────────────────────
#
# ``funlog.log_calls`` wraps sync functions and isn't async-aware (a
# decorated ``async def`` would return a coroutine that Starlette
# never awaits — observed: ``TypeError: 'coroutine' object is not
# callable``). This is the equivalent for ``async def`` handlers:
# same INFO-level emission, routed through this module's logger so
# the perf-log setup above sends it to stderr.

import functools

from funlog import format_duration as _format_duration


def log_async_calls(*, if_slower_than: float = 0.0) -> Any:
    """Async equivalent of ``@log_calls(show_timing_only=True)``.

    *if_slower_than* is in seconds; a value of 0 traces every call. Request
    timings are DEBUG diagnostics. The request middleware separately reports
    genuinely slow end-to-end requests at WARNING.
    """

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.monotonic() - started
                if elapsed >= if_slower_than:
                    LOG.debug("⏱ %s took %s", func.__name__, _format_duration(elapsed))

        return wrapper

    return decorator


# ── Explicit re-exports ─────────────────────────────────────────
#
# Tests + ``serve.py`` import a number of internal names from this
# module dating back to the pre-split monolith. We forward them here so
# the refactor stays non-breaking; ``__all__`` declares the contract so
# basedpyright doesn't flag every leg of the bridge as a private-import
# usage.

__all__ = [
    "ACTIVITY_POLL_INTERVAL_MS",
    "DEFAULT_TREE_DEPTH",
    "FILE_KIND_DETECTORS",
    "FileActivityTracker",
    "FileContext",
    "MAX_TREE_DEPTH",
    "SENTINEL_SUMMARY_DEPTH",
    "STATIC_DIR",
    "TRACKABLE_DISCOVERY_TTL_SECONDS",
    "TRACKABLE_FILE_MAX_SIZE",
    "VIEW_REGISTRY",
    "_IGNORE_CACHE",
    "_activity_snapshot",
    "_cached_root_prefix",
    "_classify_file_kind",
    "_clear_browser_caches",
    "_collect_trackable_files",
    "_collect_trackable_files_cached",
    "_dir_tree",
    "_discover_trackable_files",
    "_find_git_root",
    "_has_any_leaf",
    "_has_any_nongitignored",
    "_has_visible_children",
    "_parse_jsonl_file",
    "_rel_path",
    "_relativize",
    "_resolved_root_dir",
    "_safe_path",
    "_safe_subdir",
    "_set_root_dir",
    "_subtree_is_all_gitignored",
    "_subtree_is_empty",
    "_subtree_summary",
    "_tree_depth_from_query",
    "activity_tracker",
    "api_activity",
    "api_file",
    "api_kpress_export",
    "api_kpress_render",
    "api_stream",
    "api_tree",
    "app",
    "build_gitignore_check",
    "classify_by_ext",
    "classify_file_kind",
    "index",
    "raw_file",
    "register_file_kind_detector",
    "routes",
]


# ── ROOT_DIR shim ───────────────────────────────────────────────
#
# Several existing call sites (and tests) read or write ``proc_browser.ROOT_DIR``
# directly. The canonical value lives in ``paths_safe``; expose it here as a
# property-style attribute backed by the module-level lookup.

import metabrowser.paths_safe as _paths_safe

# Re-export of the activity tracker class under the legacy proc_browser
# namespace so existing tests/imports keep working. The numeric constants
# (TRACKABLE_FILE_MAX_SIZE, TRACKABLE_DISCOVERY_TTL_SECONDS) used to be
# duplicated here; they live exclusively in ``activity.py`` now to avoid
# silent drift.
FileActivityTracker = _FileActivityTracker


# ROOT_DIR proxy: tests (and old serve.py code) read/write
# ``proc_browser.ROOT_DIR`` directly. The canonical value now lives in
# ``paths_safe``; bridge both directions via a module class so reads and
# writes always go through ``_set_root_dir`` (which fires every
# registered cache-invalidation callback).

import sys as _sys
import types as _types


class _ProcBrowserModule(_types.ModuleType):
    @property
    def ROOT_DIR(self) -> Path:  # type: ignore[override]
        return _paths_safe.ROOT_DIR

    @ROOT_DIR.setter
    def ROOT_DIR(self, value: Path) -> None:
        _set_root_dir(value)

    @property
    def _ROOT_PREFIX_CACHE(self) -> dict[Path, str]:  # type: ignore[override]
        return _paths_safe._ROOT_PREFIX_CACHE


_sys.modules[__name__].__class__ = _ProcBrowserModule


def _classify_file_kind(ext: str, adapter: str | None = None) -> str:
    """Backwards-compat alias for legacy callers; new code calls
    :func:`metabrowser.file_kinds.classify_by_ext` directly."""
    return classify_by_ext(ext, adapter)


# ── Static asset directories ────────────────────────────────────
#
# CSS / JS bundles are served as plain static files (Starlette's
# ``StaticFiles`` mount handles Last-Modified + If-Modified-Since for
# 304s), not inlined into the index HTML. That way edits show up on a
# normal browser refresh without restarting the server, and the
# browser's HTTP cache does the work it's designed to do.

STATIC_DIR: Path = Path(__file__).parent / "static"

# perf.js is optional (only present in dev builds with the perf overlay
# bundled). Probed at module load so the index template can skip the
# script tag rather than emit a 404 reference.
_PERF_JS_AVAILABLE: bool = (STATIC_DIR / "perf.js").is_file()


_SLOW_SERVER_REQUEST_MS = int(
    os.environ.get(
        "METABROWSER_SLOW_SERVER_MS",
        str(int(SLOW_OPERATION_LOG_SECONDS * 1000)),
    )
)

# Verbose request log: when METABROWSER_REQUEST_LOG=verbose, the
# slow-request middleware logs *every* request (not just the slow
# ones) with absolute wall-clock arrival + completion times. Useful
# for correlating server-side timing against the browser's perf.js
# numbers when chasing "why is this fetch slow" questions; off by
# default because it's chatty (1 line per request).
_VERBOSE_REQUEST_LOG = os.environ.get("METABROWSER_REQUEST_LOG", "").strip().lower() == "verbose"


def _etag_for(mtime_hash: str) -> str:
    """Return the strong-ETag string for a file with the given mtime hash.

    Strong ETags are quoted per RFC 7232. The token is stable across
    browser-server restarts for unchanged files so dev-loop restarts do not
    force clients to re-download every cached payload.
    """
    return f'"{mtime_hash}"'


# File-extension sets used by ``api_file`` to decide which branch to
# take. They are bound to module-level names for compatibility with
# callers that import ``_TEXT_EXTS`` / ``_IMAGE_EXTS`` directly.
import contextlib

from metabrowser.file_extensions import (
    BROWSER_IMAGE_EXTS as _IMAGE_EXTS,
)
from metabrowser.file_extensions import (
    BROWSER_TEXT_EXTS as _TEXT_EXTS,
)

# Files outside ``_TEXT_EXTS`` smaller than this are still tried as
# text (`read_text(errors="replace")`). Above this we treat them as
# binary unless they hit a known extension. 512 KiB is the
# pre-refactor default.
_INLINE_TEXT_FALLBACK_BYTES = 512 * 1024
_TEXT_PREVIEW_CHUNK_BYTES = int(os.environ.get("METABROWSER_TEXT_PREVIEW_BYTES", str(128 * 1024)))
_TEXT_PREVIEW_MAX_CHUNK_BYTES = int(
    os.environ.get("METABROWSER_TEXT_PREVIEW_MAX_BYTES", str(8 * 1024 * 1024))
)
_SYNTAX_HIGHLIGHT_MAX_BYTES = int(
    os.environ.get("METABROWSER_HIGHLIGHT_MAX_BYTES", str(512 * 1024))
)


class _ArtifactTextLimitError(OSError):
    """A decompressed text read exceeded its caller-owned byte budget."""


def _query_int(request: Request, name: str, default: int) -> int:
    raw = request.query_params.get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _read_artifact_text_chunk(
    artifact: ArtifactPath, offset: int, limit: int
) -> tuple[str, int, int, bool]:
    with artifact.open_binary(max_output_bytes=offset + limit + 1) as fh:
        if artifact.is_compressed:
            remaining = offset
            while remaining > 0:
                skipped = fh.read(min(_RAW_STREAM_CHUNK, remaining))
                if not skipped:
                    break
                remaining -= len(skipped)
        else:
            fh.seek(offset)
        raw_with_probe = fh.read(limit + 1)
    raw = raw_with_probe[:limit]
    return raw.decode(errors="replace"), len(raw), offset + len(raw), len(raw_with_probe) > limit


def _clear_browser_caches() -> None:
    """Reset every cache the browser reaches into per request.

    Used by the offline benchmark harness to measure cold-cache latency.
    Production code should not call this.
    """
    _IGNORE_CACHE.clear()
    _paths_safe._ROOT_PREFIX_CACHE.clear()
    _subtree_summary.cache_clear()
    _has_any_leaf.cache_clear()
    _has_any_nongitignored.cache_clear()
    _collect_trackable_files_cached.cache_clear()
    clear_charts_cache()


# Concrete bind hosts registered by the CLI (``--host``). Wildcard binds
# never land here; loopback names are always permitted by the middleware.
_EXTRA_ALLOWED_HOSTS: set[str] = set()

# Bind values that accept connections on every interface. They are not
# meaningful Host-header names, so they are never added to the allowlist.
_WILDCARD_BIND_HOSTS: frozenset[str] = frozenset({"", "0.0.0.0", "::", "[::]"})


def _register_allowed_host(bind_host: str) -> None:
    """Permit the CLI's concrete ``--host`` value at the HTTP boundary.

    A wildcard bind is a no-op: it names interfaces, not a hostname a
    browser would send, and allowing everything would defeat the
    DNS-rebinding check. Operators reaching a wildcard bind through a
    concrete name allow it explicitly with ``METABROWSER_ALLOWED_HOSTS``.
    """
    raw = bind_host.strip().lower()
    if raw in _WILDCARD_BIND_HOSTS:
        # Check before normalizing: the Host-header port-strip heuristic
        # would mangle a bare IPv6 wildcard ("::" -> ":").
        return
    hostname = _HostValidationMiddleware._hostname(raw)
    if hostname and hostname != ":" and hostname not in _WILDCARD_BIND_HOSTS:
        _EXTRA_ALLOWED_HOSTS.add(hostname)


class _HostValidationMiddleware:
    """Reject requests whose ``Host`` header is not a permitted name.

    Metabrowser binds to loopback, but loopback alone does not stop DNS
    rebinding: a malicious page on an attacker-controlled domain can point
    that domain's DNS at 127.0.0.1 and issue what the browser considers
    same-origin reads against this server. The browser sends the attacker's
    hostname in ``Host``, so an allowlist check defeats the attack.

    Permitted by default: loopback names (``localhost``, ``127.0.0.1``,
    ``[::1]``) with any port, plus Starlette's ``testserver``. Additional
    names (for a non-default ``--host`` bind) come from the
    ``METABROWSER_ALLOWED_HOSTS`` environment variable, comma-separated,
    read per request so tests and embedders can adjust it without
    rebuilding the app.
    """

    _DEFAULT_ALLOWED: frozenset[str] = frozenset(
        {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}
    )

    def __init__(self, app: Any) -> None:
        self.app = app

    @staticmethod
    def _hostname(host_header: str) -> str:
        host = host_header.strip().lower()
        if host.startswith("["):
            # Bracketed IPv6 literal, optionally with a port suffix.
            end = host.find("]")
            return host[: end + 1] if end >= 0 else host
        return host.rsplit(":", 1)[0] if ":" in host else host

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        host_header = ""
        for name, value in scope.get("headers") or []:
            if name == b"host":
                host_header = value.decode("latin-1")
                break
        hostname = self._hostname(host_header)
        allowed = self._DEFAULT_ALLOWED | _EXTRA_ALLOWED_HOSTS
        extra = os.environ.get("METABROWSER_ALLOWED_HOSTS", "")
        if extra:
            allowed = allowed | {
                self._hostname(entry) for entry in extra.split(",") if entry.strip()
            }
        # An absent Host header (HTTP/1.0 clients) is allowed: rebinding
        # requires a browser, and browsers always send Host.
        if hostname and hostname not in allowed:
            response = PlainTextResponse(
                f"Host {hostname!r} is not a permitted name for this local server. "
                "This guard blocks DNS-rebinding attacks. If this name is a "
                "trusted way to reach this machine, restart with "
                f"--host {hostname} or add it to the METABROWSER_ALLOWED_HOSTS "
                "environment variable (comma-separated).\n",
                status_code=421,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _SlowRequestLogMiddleware:
    """Time + log browser server requests.

    Default mode: only requests slower than ``threshold_ms`` are logged
    at WARNING. When ``verbose`` is True, every request gets an INFO
    line with absolute wall-clock arrival + completion timestamps —
    useful when correlating server-side timing against the browser's
    perf.js numbers ("why is this 5 KB fetch taking 2 s?"). Verbose mode
    is opt-in via ``METABROWSER_REQUEST_LOG=verbose``.
    """

    def __init__(
        self,
        app: Any,
        threshold_ms: int = _SLOW_SERVER_REQUEST_MS,
        verbose: bool = _VERBOSE_REQUEST_LOG,
    ) -> None:
        self.app = app
        self.threshold_ms = threshold_ms
        self.verbose = verbose

    # Long-poll endpoints we never want flagged as slow. The SSE
    # transport intentionally holds the connection open (heartbeat
    # cadence is ~15 s, see SSE_HEARTBEAT_INTERVAL_S); the slow-
    # request threshold is ~3 s. Without this skip every connected
    # browser tab would emit a slow-request warning at the heartbeat
    # interval.
    _LONG_LIVED_PATHS: tuple[str, ...] = ("/api/events", "/api/tail", "/api/stream")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        # Skip the timer entirely for long-lived endpoints.
        path = str(scope.get("path") or "")
        if any(path.startswith(prefix) for prefix in self._LONG_LIVED_PATHS):
            await self.app(scope, receive, send)
            return

        # Capture both monotonic (for duration arithmetic) AND wall-
        # clock (for correlating with browser-side timestamps). The
        # browser's perf.js logs UTC ms-since-epoch in slow_fetch
        # records, so `arrived` here lines up with that scale.
        started = time.perf_counter()
        arrived = time.time()
        status: int | None = None
        body_bytes = 0

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal body_bytes, status
            if message.get("type") == "http.response.start":
                status = message.get("status")
                # Inject Server-Timing so the browser's Network tab +
                # perf.js can read the server-self-reported duration
                # without an out-of-band channel. Format per RFC 8941
                # / W3C Server-Timing: ``<name>;dur=<ms>``. The single
                # ``srv`` metric reports the wall-clock from middleware
                # entry to response-start; client subtracts to get the
                # transit + queue portion. Done at response.start so
                # the duration captures everything before the body
                # streams (which is when downstream gzip / transport
                # latency dominates). Re-encode the headers list to
                # preserve any pre-existing Server-Timing value (no
                # plugin sets one today, but be safe).
                so_far_ms = (time.perf_counter() - started) * 1000
                hdrs = list(message.get("headers") or [])
                hdrs.append((b"server-timing", f"srv;dur={so_far_ms:.1f}".encode("latin-1")))
                message = {**message, "headers": hdrs}
            elif message.get("type") == "http.response.body":
                body = message.get("body") or b""
                body_bytes += len(body)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            query = (scope.get("query_string") or b"").decode("latin-1")
            full_path = f"{path}?{query}" if query else path
            if self.verbose:
                # Verbose mode: every request, with arrival + completion
                # epochs so correlation against browser-side perf.js
                # records is mechanical (subtract for transit time).
                LOG.info(
                    "metabrowser request t=%.3f -> %.3f (%.0f ms) method=%s path=%s status=%s bytes=%s",
                    arrived,
                    arrived + duration_ms / 1000,
                    duration_ms,
                    scope.get("method", ""),
                    full_path,
                    status,
                    body_bytes,
                )
            elif self.threshold_ms and duration_ms >= self.threshold_ms:
                # Include the arrival epoch even in non-verbose mode so
                # the line cross-references against perf.js slow_fetch
                # records (which carry started_at as a UTC epoch ms).
                LOG.warning(
                    "metabrowser slow server request t=%.3f %.0f ms method=%s path=%s status=%s bytes=%s",
                    arrived,
                    duration_ms,
                    scope.get("method", ""),
                    full_path,
                    status,
                    body_bytes,
                )


# ── Route handlers ──────────────────────────────────────────────


def _initial_path_html() -> str:
    """Server-render the served-root path so it shows on first paint."""
    root_str = str(_paths_safe.ROOT_DIR.resolve())
    base = _paths_safe.ROOT_DIR.resolve().name
    if base:
        dir_part = html_escape(root_str[: -len(base)])
        base_part = html_escape(base)
        return (
            f'<span class="path">'
            f'<span class="path-dir">{dir_part}</span>'
            f'<span class="path-base">{base_part}</span>'
            f"</span>"
        )
    return f'<span class="path"><span class="path-base">{html_escape(root_str)}</span></span>'


def _initial_file_path() -> str:
    """Return a cheap first-preview file path, without walking the tree."""

    root = _paths_safe.ROOT_DIR.resolve()
    for name in ("README.md", "readme.md", "Readme.md"):
        if (root / name).is_file():
            return name
    try:
        for child in root.iterdir():
            if child.is_file() and child.name.lower() == "readme.md":
                return child.name
    except OSError:
        return ""
    return ""


def _static_asset_url(rel_path: str) -> str:
    """Return a local static URL with an mtime-based cache buster."""

    target = STATIC_DIR / rel_path
    try:
        version = quote(str(file_mtime_hash(target)), safe="")
    except OSError:
        return f"/static/{rel_path}"
    return f"/static/{rel_path}?v={version}"


# Interface-font sets offered by the settings dropdown. The first entry is the
# default. Each set's actual font stacks live in styles.css as a
# `html[data-app-font="<value>"]` block (the default uses the :root base). To add
# a set, append one entry here and one CSS block there — the dropdown options and
# the pre-paint bootstrap both derive from this single list, so they stay in sync.
_FONT_SETS: tuple[dict[str, str], ...] = (
    {"value": "clean", "label": "Clean Fonts"},
    {"value": "system", "label": "System Fonts"},
)
_DEFAULT_FONT_SET = _FONT_SETS[0]["value"]


async def index(_request: Request) -> HTMLResponse:
    """Serve the SPA page; CSS/JS are linked, not inlined."""

    initial_path = _initial_path_html()
    initial_file_path = _initial_file_path()
    styles_url = _static_asset_url("styles.css")
    theme_state_url = _static_asset_url("theme_state.js")
    plugin_sdk_url = _static_asset_url("plugin_sdk.js")
    filter_state_url = _static_asset_url("filter_state.js")
    filter_controls_url = _static_asset_url("filter_controls.js")
    icons_url = _static_asset_url("icons.js")
    charts_url = _static_asset_url("charts.js")
    tree_expansion_url = _static_asset_url("tree_expansion.js")
    pending_tally_diagnostics_url = _static_asset_url("pending_tally_diagnostics.js")
    known_file_catalog_url = _static_asset_url("known_file_catalog.js")
    catalog_feed_url = _static_asset_url("catalog_feed.js")
    file_fuzzy_match_url = _static_asset_url("file_fuzzy_match.js")
    search_controller_url = _static_asset_url("search_controller.js")
    search_palette_url = _static_asset_url("search_palette.js")
    git_graph_url = _static_asset_url("git_graph.js")
    git_panel_url = _static_asset_url("git_panel.js")
    app_url = _static_asset_url("app.js")
    perf_block = (
        f'<script src="{_static_asset_url("perf.js")}"></script>' if _PERF_JS_AVAILABLE else ""
    )
    # Inject the client-visible settings dict before any app code
    # runs so JS can read window.METABROWSER_SETTINGS.* without
    # duplicating constants in the source.
    settings_block = (
        f"<script>window.METABROWSER_SETTINGS={_json.dumps(client_settings_dict())};"
        f"window.METABROWSER_INITIAL_PATH={_json.dumps(initial_file_path)};</script>"
    )
    # Read preferences from host-only cookies (not localStorage): cookies
    # ignore the port, so the choice is shared across every metabrowser instance
    # on this host (each folder server lands on its own port). Runs before the
    # stylesheet applies so the page paints in the right theme, reading font, and
    # font set on the first frame (no flash). The keys mirror app.js constants;
    # the font-set placeholders are filled from _FONT_SETS just below.
    theme_bootstrap = """<script>
  (function () {
    function cookie(name) {
      try {
        var parts = document.cookie.split("; ");
        for (var i = 0; i < parts.length; i++) {
          if (parts[i].indexOf(name + "=") === 0) {
            return decodeURIComponent(parts[i].slice(name.length + 1));
          }
        }
      } catch (_e) {}
      return null;
    }
    var mode = cookie("metabrowser.themeMode") || "system";
    if (mode !== "light" && mode !== "dark") mode = "system";
    var dark = false;
    try {
      dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch (_e) {}
    var resolved = mode === "dark" || (mode === "system" && dark) ? "dark" : "light";
    var de = document.documentElement;
    de.setAttribute("data-theme-mode", mode);
    de.setAttribute("data-theme", resolved);
    de.setAttribute("data-kpress-resolved-theme", resolved);
    de.setAttribute("data-prose-font", cookie("metabrowser.proseFont") === "sans" ? "sans" : "serif");
    var fontSets = __FONT_VALUES__;
    var fontPref = cookie("metabrowser.interfaceFont");
    de.setAttribute("data-app-font", fontSets.indexOf(fontPref) >= 0 ? fontPref : "__FONT_DEFAULT__");
  })();
  </script>"""
    theme_bootstrap = theme_bootstrap.replace(
        "__FONT_VALUES__", _json.dumps([s["value"] for s in _FONT_SETS])
    ).replace("__FONT_DEFAULT__", _DEFAULT_FONT_SET)
    app_font_options = "".join(
        f'<option value="{s["value"]}">{s["label"]}</option>' for s in _FONT_SETS
    )
    # Every third-party browser library is vendored into the wheel from
    # lockfile-verified npm packages (see devtools/vendor_assets.py and
    # static/vendor/manifest.json) and served same-origin, so the page has
    # no external origins and works offline. Bump a version by updating
    # package.json + package-lock.json, then run `make vendor-assets`.
    optional_script_assets = [
        {"src": _static_asset_url("vendor/mustache.min.js")},
        {"src": _static_asset_url("vendor/highlight.min.js")},
        {"src": _static_asset_url("vendor/highlight-toml.min.js"), "requires": "hljs"},
        {"src": _static_asset_url("vendor/chart.umd.min.js")},
        {
            "src": _static_asset_url("vendor/chartjs-plugin-annotation.min.js"),
            "requires": "Chart",
        },
        {
            "src": _static_asset_url("vendor/chartjs-adapter-date-fns.bundle.min.js"),
            "requires": "Chart",
        },
    ]
    optional_assets_block = f"""<script>
  (function () {{
    var assets = {_json.dumps(optional_script_assets)};
    function notifyLoaded(src) {{
      window.dispatchEvent(new CustomEvent("metabrowser:optional-asset-loaded", {{
        detail: {{ src: src }}
      }}));
    }}
    function loadNext(i) {{
      if (i >= assets.length) {{
        window.dispatchEvent(new Event("metabrowser:optional-assets-loaded"));
        return;
      }}
      var asset = assets[i];
      var src = asset.src || asset;
      if (asset.requires && !window[asset.requires]) {{
        loadNext(i + 1);
        return;
      }}
      var script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.onload = function () {{
        notifyLoaded(src);
        loadNext(i + 1);
      }};
      script.onerror = function () {{
        console.warn("metabrowser optional asset failed:", src);
        loadNext(i + 1);
      }};
      document.head.appendChild(script);
    }}
    function start() {{ loadNext(0); }}
    if (document.readyState === "loading") {{
      document.addEventListener("DOMContentLoaded", start, {{ once: true }});
    }} else {{
      start();
    }}
  }})();
  </script>"""
    # Emit per-plugin <link>/<script> tags from each loaded plugin's
    # manifest. Each plugin contributes (in discovery order):
    #   - <link rel="stylesheet"> for styles.css if present + every
    #     manifest.plugin.extra_styles entry
    #   - <script> for every manifest.plugin.extra_scripts entry
    #   - <script type="module" src=".../index.js"> last
    # Plugins that need additional JS/CSS files declare them in their
    # manifest; metabrowser core never special-cases plugin asset names.
    plugin_styles = _build_plugin_style_block()
    plugin_scripts = _build_plugin_script_block()

    # Reuse KPress's vendored reader faces for the whole UI. Link KPress's
    # style-tokens.css (the @font-face source of truth) and preload the chrome's
    # always-present Source Sans face, using the SAME version-keyed URLs the
    # embedded document requests so the woff2 downloads exactly once and is
    # served from the immutable font cache (see kpress_static_asset). Preloading
    # only the chrome face avoids an "unused preload" warning on tree-only views;
    # PT Serif (embedded prose) rides the same immutable cache + font-display:
    # block on first document open.
    _sans_url = kpress_adapter.kpress_static_url("fonts/source-sans-3-latin-wght-normal.woff2")
    _tokens_url = kpress_adapter.kpress_static_url("css/style-tokens.css")
    kpress_font_head = (
        f'<link rel="preload" as="font" type="font/woff2" crossorigin href="{_sans_url}">\n'
        f'  <link rel="stylesheet" href="{_tokens_url}">'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <title>Metabrowser</title>
  <!-- Reader fonts: preload the chrome's Source Sans face + link KPress's
       @font-face source of truth, version-keyed so chrome and the embedded
       document share one download. Built in kpress_font_head above from the
       required KPress package. No flash of unstyled text on first paint. -->
  {kpress_font_head}
  {theme_bootstrap}
  <!-- All third-party assets are vendored into the wheel and served
       same-origin (see static/vendor/manifest.json), so the page loads
       with no external origins and works offline. -->
  <link rel="stylesheet" href="{styles_url}">
  {plugin_styles}
</head>
<body>
  <main class="container">
    <div class="tree-pane" id="tree-pane">
      <header class="app-header">
        <span class="header-brand">Metabrowser</span>
        <a href="/" class="header-path" title="Jump to root">{initial_path}</a>
        <!-- Settings menu. A gear button opens a menu with two icon-segment
             choosers (theme + reading font) and a small font-set dropdown
             (#app-font-select, options from _FONT_SETS). Choices apply instantly.
             app.js (initSettingsControl) fills the icon segments and wires
             open/select + the dropdown. The wrapper's aria-expanded drives the
             menu's visibility via CSS. -->
        <div class="settings-toggle" id="settings-control" aria-expanded="false">
          <button class="icon-btn settings-btn" id="settings-btn" type="button"
                  aria-haspopup="true" title="Settings" aria-label="Settings"></button>
          <div class="settings-menu menu" role="menu" aria-label="Settings">
            <div class="menu-chooser" role="group" aria-label="Theme">
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="system" title="System theme" aria-label="System theme"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="light" title="Light theme" aria-label="Light theme"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="dark" title="Dark theme" aria-label="Dark theme"></button>
            </div>
            <div class="menu-separator"></div>
            <div class="menu-chooser" role="group" aria-label="Reading font">
              <button class="menu-seg" type="button" role="menuitemradio" data-font-choice="serif" title="Serif reading font" aria-label="Serif reading font"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-font-choice="sans" title="Sans-serif reading font" aria-label="Sans-serif reading font"></button>
            </div>
            <div class="menu-separator"></div>
            <select class="menu-select" id="app-font-select" aria-label="Fonts">{app_font_options}</select>
          </div>
        </div>
      </header>
      <div class="tab-bar nav-tab-bar" role="tablist">
        <button class="tab-btn active" type="button" role="tab" data-tab="files" aria-selected="true">Files</button>
      </div>
      <!-- Filter bar lives outside #tab-files: a tree reload replaces
           that container's contents wholesale, and the bar must also
           stay put while .tree-content scrolls. app.js fills it. -->
      <div class="nav-filter-bar" id="nav-filter-bar"></div>
      <div class="tree-content" id="tree-content">
        <div id="tab-files" data-tab-content="files">
          <div class="loading"><div class="spinner"></div>Loading files…</div>
        </div>
      </div>
      <div class="index-progress" id="index-progress" role="status" aria-live="polite" hidden>
        <span class="index-progress-spinner" aria-hidden="true"></span>
        <span class="index-progress-text">Scanning…</span>
      </div>
    </div>
    <div class="resize-handle" id="tree-resize"></div>
    <div class="preview-pane" id="preview-pane" data-kpress-viewport tabindex="-1">
      <div class="preview-empty">Select a file to preview.</div>
    </div>
  </main>
  <!-- Core shell scripts are local and first-paint critical. Optional
       third-party libraries are vendored into the wheel and loaded by
       the async enhancement loader below so they cannot block initial
       tree/readme rendering. TOML support comes from the official
       highlight.js ini.min.js grammar (`aliases:["toml"]`), vendored as
       highlight-toml.min.js. -->
  {perf_block}
  {settings_block}
  <script src="{theme_state_url}"></script>
  <script src="{plugin_sdk_url}"></script>
  <script src="{filter_state_url}"></script>
  <script src="{filter_controls_url}"></script>
  <script src="{icons_url}"></script>
  <script src="{charts_url}"></script>
  <script src="{tree_expansion_url}"></script>
  <script src="{pending_tally_diagnostics_url}"></script>
  <script src="{known_file_catalog_url}"></script>
  <script src="{catalog_feed_url}"></script>
  <script src="{file_fuzzy_match_url}"></script>
  <script src="{search_controller_url}"></script>
  <script src="{search_palette_url}"></script>
  <!-- Git graph modules load before app.js: the shell's DOMContentLoaded
       handler calls MetabrowserGitPanel.init(), which needs both present. -->
  <script src="{git_graph_url}"></script>
  <script src="{git_panel_url}"></script>
  <script src="{app_url}"></script>
  {plugin_scripts}
  {optional_assets_block}
</body>
</html>"""
    return HTMLResponse(html)


@log_async_calls()
async def api_tree(request: Request) -> JSONResponse:
    subpath = request.query_params.get("path", "")
    depth_str = request.query_params.get("depth", "")
    target = _safe_path(subpath)
    if target is None or not target.is_dir():
        return JSONResponse({"error": "Not found"}, status_code=404)

    remaining_depth = _tree_depth_from_query(depth_str)

    inventory = get_inventory()
    root_dir = _resolved_root_dir()
    inventory_root = getattr(inventory, "_root", None)
    if inventory_root != root_dir:
        inventory.clear()
    started_inventory = False
    if inventory_status() == "idle":
        inventory.start(root_dir)
        started_inventory = True

    if started_inventory:
        deadline = asyncio.get_running_loop().time() + _TREE_COLD_START_WAIT_S
        while asyncio.get_running_loop().time() < deadline:
            if inventory_status() in ("done", "truncated"):
                break
            if inventory.has_direct_child(subpath):
                break
            await asyncio.sleep(0.005)

    inv_can_serve = False
    if inventory_has_data():
        inv_can_serve = True if not subpath else inventory.get(subpath) is not None

    if inv_can_serve:
        tree = _build_inventory_tree(
            parent_rel=subpath,
            max_depth=remaining_depth,
            root_abs=root_dir,
        )
        LOG.debug(
            "api_tree (inventory) path=%r depth=%d entries=%d status=%s",
            subpath or "<root>",
            remaining_depth,
            len(tree),
            inventory_status(),
        )
    else:
        tree = []
        if inventory_status() in ("done", "truncated"):
            LOG.warning(
                "api_tree: inventory has no entry for existing path=%r status=%s",
                subpath or "<root>",
                inventory_status(),
            )
        LOG.debug(
            "api_tree (inventory-miss) path=%r depth=%d entries=%d status=%s",
            subpath or "<root>",
            remaining_depth,
            len(tree),
            inventory_status(),
        )
    # The nav tallies need one O(index) pass. The nav re-requests this route
    # (depth=0) while the walk converges, so running it on the loop would stall
    # the event stream at the design-center index size for the same reason
    # api_catalog offloads its own pass.
    summary = None
    extensions = None
    type_presets = None
    recency_tallies = None
    # Keep the response status in the same event-loop epoch as the tree and
    # tally snapshots. The walker can finish while the O(index) worker runs;
    # reporting that newer "done" state beside partial tallies would make the
    # browser stop polling before it requests the final snapshot.
    tally_cache_status = inventory_status()
    if inv_can_serve and not subpath:
        # Inventory writes are owned by the event loop. Snapshot there before
        # handing the O(index) tally pass to a worker; iterating the live dictionary
        # off-loop races the still-running walker.
        tally_entries = inventory.entries(scope="all-known")
        summary, extensions, type_presets, recency_tallies = await asyncio.to_thread(
            lambda: inventory.navigation_tallies(
                [(preset["id"], preset["values"]) for preset in FILTER_TYPE_PRESETS],
                [
                    (window_key, seconds)
                    for window_key, seconds in RECENT_WINDOW_SECONDS.items()
                    if seconds is not None
                ],
                entries=tally_entries,
            )
        )
    return JSONResponse(
        {
            "root": str(root_dir),
            "tree": tree,
            "tally_cache_status": tally_cache_status,
            "tally_cache_max_files": inventory.max_files(),
            # Tracked-versus-ignored split for the nav header, plus the age,
            # extension, and aggregate tallies behind the nav filters. None can be
            # derived client-side: summing top-level children
            # miscounts nested ignored files (see
            # InventoryIndex.root_summary), and the Quick File catalog
            # drops gitignored entries (see navigation_tallies). Only the
            # full-tree request needs these values.
            "summary": summary,
            "extensions": extensions,
            "type_presets": type_presets,
            "recency_tallies": recency_tallies,
        }
    )


@log_async_calls()
async def api_recent(request: Request) -> JSONResponse:
    """``GET /api/recent`` — top-N files by mtime within a
    rolling window (1h / 24h / 7d / 30d / all), filtered by
    optional ``ext`` and ``prefix`` query params, returned as
    a clustered tree (see :mod:`metabrowser.recent`).
    """

    window = request.query_params.get("window", "24h")
    if window not in RECENT_WINDOW_SECONDS:
        return JSONResponse({"error": f"Unknown window: {window!r}"}, status_code=400)
    limit_raw = request.query_params.get("limit", str(DEFAULT_LIMIT))
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = DEFAULT_LIMIT
    limit = max(1, min(limit, MAX_LIMIT))

    # ext filter: repeatable. Accept query like ?ext=.log&ext=.jsonl
    # or comma-separated ?ext=.log,.jsonl for convenience.
    ext_raw = (
        request.query_params.getlist("ext") if hasattr(request.query_params, "getlist") else []
    )
    if not ext_raw:
        # Fallback for fake-request shims that lack getlist.
        single = request.query_params.get("ext", "")
        ext_raw = [s for s in single.split(",") if s] if single else []
    ext_filter = tuple(e if e.startswith(".") else "." + e for e in ext_raw)
    prefix_filter = request.query_params.get("prefix", "")
    # Callers that hide gitignored entries pass include_ignored=0 so the
    # cap is not spent on rows they will drop on arrival.
    include_ignored = request.query_params.get("include_ignored", "1") not in ("0", "false")

    # Stay conservative if the walker finishes while collection runs. A
    # response built from a scanning inventory must remain labeled scanning so
    # the client schedules the completed result instead of stranding a prefix.
    tally_cache_status = inventory_status()
    result = await asyncio.to_thread(
        collect_recent_entries,
        root=_resolved_root_dir(),
        window=window,  # pyright: ignore[reportArgumentType]
        limit=limit,
        ext_filter=ext_filter,
        prefix_filter=prefix_filter,
        include_ignored=include_ignored,
    )
    return JSONResponse(
        {
            "root": str(_resolved_root_dir()),
            # Newest-first leaf list. Clustering (single-dir compaction +
            # cluster-collapse) is a rendering concern owned by the SPA;
            # see :mod:`metabrowser.recent` for the layering rationale.
            "entries_flat": result.entries_flat,
            # Ancestor dirs of the leaves above whose own path matches
            # gitignore. The SPA can't run pathspec, so it consults this
            # list to mark dirs gray after re-clustering.
            "gitignored_dirs": result.gitignored_dirs,
            "window": result.window,
            "limit": result.limit,
            "total_matching": result.total_matching,
            "truncated": result.truncated,
            "tally_cache_status": tally_cache_status,
        }
    )


def _json_safe_frontmatter(value: Any) -> Any:
    """Coerce YAML-parsed scalars into JSON-serializable equivalents.

    YAML parses ``date: 2026-05-07`` as ``datetime.date``, which json.dumps
    rejects — that path used to 500 the /api/file response. ISO-8601 is the
    standard wire form for dates/times, so emit that instead.
    """
    if isinstance(value, dict):
        return {k: _json_safe_frontmatter(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_frontmatter(v) for v in value]
    if isinstance(value, (_dt.date, _dt.time)):
        return value.isoformat()
    return value


def _json_default_safe(obj: Any) -> Any:
    """Last-resort coercion for ``json.dumps(default=…)`` in API responses.

    Targeted normalizations (date/time/Path/set/bytes) so common stdlib types
    serialize predictably. For anything else, log + fall back to repr() so a
    single rogue value can't 500 the whole route.
    """
    if isinstance(obj, (_dt.date, _dt.time)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if isinstance(obj, bytes):
        return f"<bytes len={len(obj)}>"
    LOG.warning(
        "api: non-JSON-serializable %s in response — falling back to repr", type(obj).__name__
    )
    return repr(obj)


class JSONResponse(_StarletteJSONResponse):
    """JSONResponse with a ``default=`` hook so unexpected types don't 500.

    The original ``JSONResponse.render`` calls ``json.dumps`` with no default,
    so anything stdlib doesn't natively know about (datetime, Path, set, …)
    raises and bubbles up as a 500. This subclass plugs ``_json_default_safe``
    in for graceful coercion + a warning log.
    """

    def render(self, content: Any) -> bytes:
        return _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=_json_default_safe,
        ).encode("utf-8")


# Every route in this module uses the safe variant. Plugin code that imports
# ``starlette.responses.JSONResponse`` directly is unaffected.


def _compression_identity_fields(artifact: ArtifactPath) -> dict[str, Any]:
    """Compression fields that do not require reading the decoded stream."""
    if not artifact.is_compressed:
        return {}
    return {
        "logical_ext": artifact.logical_ext,
        "compressed": True,
        "compression": artifact.compression,
    }


def _compression_envelope_fields(artifact: ArtifactPath, logical_size: int) -> dict[str, Any]:
    """Additive fields injected into successful compressed-file responses."""
    identity = _compression_identity_fields(artifact)
    if not identity:
        return {}
    return {"size_uncompressed": logical_size, **identity}


def _api_file_internal_error_response(subpath: str, exc: Exception) -> JSONResponse:
    """Return a renderable file-error envelope instead of bubbling a 500."""
    target = _safe_path(subpath)
    size: int | None = None
    if target is not None:
        try:
            if target.is_file():
                size = target.stat().st_size
        except OSError:
            size = None
    return JSONResponse(
        {
            "type": "error",
            "kind": "error",
            "views": [],
            "path": subpath,
            "size": size,
            "error": (f"Internal error while rendering this file. {type(exc).__name__}: {exc}"),
            "warning": (
                "Metabrowser returned a degraded error view instead of a server 500. "
                "Check the server log for the traceback."
            ),
        }
    )


@log_async_calls(if_slower_than=0.1)
async def api_file(request: Request) -> JSONResponse | Response:
    subpath = request.query_params.get("path", "")
    try:
        return await _api_file_impl(request)
    except Exception as exc:
        LOG.exception("api_file failed while rendering %s", subpath)
        return _api_file_internal_error_response(subpath, exc)


def _file_unavailable_response(subpath: str, target: Path | None) -> JSONResponse:
    """Explain file-path failures without weakening served-root containment."""

    # Inspect the final path component without resolving it so an escaping
    # symlink can still be identified. Resolve and validate the parent first;
    # otherwise an absolute path, ``..``, or a symlinked parent could turn this
    # error-classification check into a probe outside the served root.
    requested = Path(subpath)
    candidate: Path | None = None
    try:
        parent = (_paths_safe.ROOT_DIR / requested.parent).resolve()
        root = _paths_safe.ROOT_DIR.resolve()
        if subpath and requested.name and _paths_safe._is_within(parent, root):
            candidate = parent / requested.name
        is_symlink = candidate is not None and candidate.is_symlink()
    except OSError:
        is_symlink = False

    if is_symlink:
        if target is None:
            detail = (
                "This symbolic link points outside the served folder. "
                "Serve a folder containing its target to browse it."
            )
        elif not target.exists():
            detail = "The target of this symbolic link is unavailable."
        elif target.is_dir():
            detail = (
                "This symbolic link points to a folder. "
                "Open the target folder directly to browse it."
            )
        else:
            detail = "The target of this symbolic link cannot be opened."
        return JSONResponse(
            {"summary": "Could not open this link.", "error": detail},
            status_code=404,
        )

    if target is not None and target.is_dir():
        return JSONResponse(
            {
                "summary": "Could not open this folder.",
                "error": "Select the folder in the navigation panel to browse its contents.",
            },
            status_code=404,
        )

    return JSONResponse(
        {
            "summary": "Could not open this file.",
            "error": "This file is no longer available.",
        },
        status_code=404,
    )


async def _api_file_impl(request: Request) -> JSONResponse | Response:
    subpath = request.query_params.get("path", "")
    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return _file_unavailable_response(subpath, target)

    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    logical_size: int | None
    try:
        disk_size = artifact.disk_size
    except OSError:
        try:
            disk_size = target.stat().st_size
        except OSError:
            return JSONResponse({"error": "Not found"}, status_code=404)
        return JSONResponse(
            {
                "type": "binary",
                "kind": "binary",
                "views": _views_for_kind("binary"),
                "path": subpath,
                "size": disk_size,
                **_compression_identity_fields(artifact),
            }
        )

    try:
        # Validated compression scans must not run on the event loop.
        logical_size = await asyncio.to_thread(lambda: artifact.logical_size)
    except ArtifactCompressionError as exc:
        if artifact.is_gzip:
            # Caller-specific readers below can still return a bounded preview
            # or a limit error before reaching a malformed gzip trailer.
            logical_size = None
        else:
            try:
                disk_size = target.stat().st_size
            except OSError:
                return JSONResponse({"error": "Not found"}, status_code=404)
            return JSONResponse(
                {
                    "type": "error",
                    "kind": "error",
                    "views": [],
                    "path": subpath,
                    "size": disk_size,
                    "error": str(exc),
                    **_compression_identity_fields(artifact),
                }
            )
    except OSError:
        return JSONResponse(
            {
                "type": "binary",
                "kind": "binary",
                "views": _views_for_kind("binary"),
                "path": subpath,
                "size": disk_size,
                **_compression_identity_fields(artifact),
            }
        )
    mtime_hash = file_mtime_hash(target)
    etag = _etag_for(mtime_hash)
    etag_headers = {"etag": etag, "cache-control": "no-cache"}
    compression_fields = (
        _compression_envelope_fields(artifact, logical_size)
        if logical_size is not None
        else _compression_identity_fields(artifact)
    )
    requested_text_offset = max(0, _query_int(request, "offset", 0))
    text_limit = max(
        1,
        min(
            _query_int(request, "limit", _TEXT_PREVIEW_CHUNK_BYTES),
            _TEXT_PREVIEW_MAX_CHUNK_BYTES,
        ),
    )
    if (
        artifact.is_compressed
        and requested_text_offset + text_limit > _TEXT_PREVIEW_MAX_CHUNK_BYTES
    ):
        return JSONResponse(
            {
                "type": "error",
                "path": subpath,
                "error": "Requested preview window exceeds the decompression budget",
                "max_offset": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=416,
        )
    text_offset = (
        requested_text_offset if logical_size is None else min(requested_text_offset, logical_size)
    )

    # 304 short-circuit. Repeat clicks on an unchanged file return zero
    # bytes — meaningful over an SSH tunnel and free locally. We compare
    # bytewise against the full ETag including the process-epoch suffix
    # so a server restart guarantees a fresh body even if the file is
    # untouched.
    if text_offset == 0 and request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=etag_headers)

    # JSONL gets parsed into structured events (single-pass streaming).
    # ``ext`` is the *logical* extension here, so ``foo.jsonl.gz`` lands
    # in this branch the same as ``foo.jsonl``.
    if ext == ".jsonl":
        try:
            from metabrowser.projections import (
                parse_jsonl_file_cached,
            )

            parsed = await asyncio.to_thread(parse_jsonl_file_cached, target)
            adapter = parsed.get("summary", {}).get("adapter")
            kind = await asyncio.to_thread(_classify_with_plugins, target, ext, adapter)
            views = _views_for_kind(kind)
            return JSONResponse(
                {
                    "type": "jsonl",
                    "kind": kind,
                    "views": views,
                    "path": subpath,
                    "size": disk_size,
                    "mtime_hash": mtime_hash,
                    **compression_fields,
                    **parsed,
                },
                headers=etag_headers,
            )
        except (OSError, TypeError, ValueError) as exc:
            return JSONResponse({"type": "error", "path": subpath, "error": str(exc)})

    if ext in _IMAGE_EXTS:
        return JSONResponse(
            {
                "type": "image",
                "kind": "image",
                "views": [],
                "path": subpath,
                "size": disk_size,
                "mtime_hash": mtime_hash,
                **compression_fields,
            },
            headers=etag_headers,
        )

    if ext in _TEXT_EXTS or (
        logical_size is not None and logical_size < _INLINE_TEXT_FALLBACK_BYTES
    ):
        try:
            content_has_more = False
            if (
                artifact.is_compressed
                or text_offset > 0
                or (logical_size is not None and logical_size > _TEXT_PREVIEW_CHUNK_BYTES)
            ):
                content, content_bytes, bytes_read, content_has_more = await asyncio.to_thread(
                    _read_artifact_text_chunk,
                    artifact,
                    text_offset,
                    text_limit,
                )
            else:
                content = await asyncio.to_thread(target.read_text, errors="replace")
                content_bytes = disk_size
                bytes_read = disk_size
        except ArtifactCompressionError as exc:
            if artifact.is_gzip:
                return JSONResponse(
                    {
                        "type": "binary",
                        "kind": "binary",
                        "views": _views_for_kind("binary"),
                        "path": subpath,
                        "size": disk_size,
                        **_compression_identity_fields(artifact),
                    }
                )
            return JSONResponse(
                {
                    "type": "error",
                    "kind": "error",
                    "views": [],
                    "path": subpath,
                    "size": disk_size,
                    "error": str(exc),
                    **compression_fields,
                }
            )
        except OSError:
            return JSONResponse(
                {
                    "type": "binary",
                    "path": subpath,
                    "size": disk_size,
                    **compression_fields,
                }
            )

        if text_offset > 0:
            return JSONResponse(
                {
                    "type": "text_chunk",
                    "path": subpath,
                    "size": disk_size,
                    "mtime_hash": mtime_hash,
                    "content": content,
                    "content_offset": text_offset,
                    "content_bytes": content_bytes,
                    "bytes_read": bytes_read,
                    "content_truncated": content_has_more
                    or (logical_size is not None and bytes_read < logical_size),
                    "content_preview_limit": text_limit,
                    "highlight_disabled": True,
                    **compression_fields,
                },
                headers=etag_headers,
            )

        # Build the FileContext once so frontmatter parsing + classification
        # share a cached result; plugin classification may consult frontmatter
        # for specialized document detection.
        ctx = FileContext(target, ext)
        kind = await asyncio.to_thread(_classify_with_plugins, target, ext, file_ctx=ctx)
        views = _views_for_kind(kind)

        # For .md files, expose parsed frontmatter so plugin renderers can
        # use it directly via ctx.frontmatter without re-parsing client-side.
        # Malformed YAML fences must NOT silently fall through to markdown;
        # surface the parse error on the response so the operator sees it
        # instead of quietly substituting an empty frontmatter object.
        frontmatter: dict[str, Any] | None = None
        frontmatter_error: str | None = None
        if ext == ".md":
            frontmatter = _json_safe_frontmatter(ctx.frontmatter)
            frontmatter_error = ctx.frontmatter_parse_error
        result: dict[str, Any] = {
            "type": "text",
            "kind": kind,
            "views": views,
            "path": subpath,
            "ext": ext,
            "size": disk_size,
            "mtime_hash": mtime_hash,
            "content": content,
            "content_offset": 0,
            "content_bytes": content_bytes,
            "bytes_read": bytes_read,
            "content_truncated": content_has_more
            or (logical_size is not None and bytes_read < logical_size),
            "content_preview_limit": text_limit,
            "highlight_disabled": (
                content_has_more
                or (logical_size is not None and bytes_read < logical_size)
                or (logical_size is not None and logical_size > _SYNTAX_HIGHLIGHT_MAX_BYTES)
                or bytes_read > _SYNTAX_HIGHLIGHT_MAX_BYTES
            ),
            **compression_fields,
        }
        if frontmatter is not None:
            result["frontmatter"] = frontmatter
        if frontmatter_error is not None:
            result["frontmatter_error"] = frontmatter_error
        # Rendered Markdown is fetched separately through the KPress route.
        # Keeping this payload source-only avoids duplicating the rendered
        # document in the normal file response.
        return JSONResponse(result, headers=etag_headers)

    return JSONResponse(
        {
            "type": "binary",
            "kind": "binary",
            "views": _views_for_kind("binary"),
            "path": subpath,
            "size": disk_size,
            "mtime_hash": mtime_hash,
            **compression_fields,
        },
        headers=etag_headers,
    )


def _read_artifact_text(artifact: ArtifactPath, max_bytes: int) -> tuple[str, int]:
    """Read compression-transparent text under a decompressed byte cap."""
    with artifact.open_binary(max_output_bytes=max_bytes + 1) as fh:
        raw = fh.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise _ArtifactTextLimitError(f"decompressed content exceeds {max_bytes} bytes")
    return raw.decode(errors="replace"), len(raw)


@log_async_calls(if_slower_than=0.1)
async def api_kpress_render(request: Request) -> JSONResponse:
    """Render a safe served-root-relative file through the KPress adapter."""

    subpath = request.query_params.get("path", "")
    view = request.query_params.get("view", "document")
    profile = request.query_params.get("profile", "") or None

    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    content: str | None = None
    try:
        disk_size = artifact.disk_size
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    try:
        if artifact.is_compressed:
            content, logical_size = await asyncio.to_thread(
                _read_artifact_text,
                artifact,
                _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            )
        else:
            logical_size = artifact.logical_size
    except _ArtifactTextLimitError:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "File is too large for full document rendering",
                "path": subpath,
                "size": disk_size,
                "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=413,
        )
    except ArtifactDecompressionLimitError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "Compressed source exceeds safety limits",
                "detail": str(exc),
                "path": subpath,
                "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=413,
        )
    except ArtifactCompressionError as exc:
        if artifact.is_gzip:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "Unable to read compressed source",
                "detail": str(exc),
                "path": subpath,
            },
            status_code=400,
        )
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    if ext not in _TEXT_EXTS and logical_size >= _INLINE_TEXT_FALLBACK_BYTES:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "KPress render supports text-like files only",
                "path": subpath,
                "ext": ext,
                "size": disk_size,
            },
            status_code=415,
        )
    if logical_size > _TEXT_PREVIEW_MAX_CHUNK_BYTES:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "File is too large for full document rendering",
                "path": subpath,
                "size": disk_size,
                "logical_size": logical_size,
                "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=413,
        )

    try:
        if content is None:
            content = await asyncio.to_thread(target.read_text, errors="replace")
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    ctx = FileContext(target, ext)
    kind = await asyncio.to_thread(_classify_with_plugins, target, ext, file_ctx=ctx)
    frontmatter: dict[str, Any] | None = None
    frontmatter_error: str | None = None
    if ext == ".md":
        frontmatter = _json_safe_frontmatter(ctx.frontmatter)
        frontmatter_error = ctx.frontmatter_parse_error
    mtime_hash = file_mtime_hash(target)

    try:
        rendered = await asyncio.to_thread(
            kpress_adapter.render_kpress_view,
            source_text=content,
            source_path=subpath,
            kind=kind,
            view=view,
            ext=ext,
            mtime_hash=mtime_hash,
            size=logical_size,
            frontmatter=frontmatter,
            frontmatter_error=frontmatter_error,
            profile=profile,
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "Invalid KPress render request",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=400,
        )
    except kpress_adapter.KPressRenderError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "KPress render failed",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=502,
        )
    return JSONResponse(rendered, headers={"cache-control": "no-cache"})


_KPRESS_EXPORT_MODES_SUPPORTED = {"page", "static-hosted", "hashed-static-hosted", "pdf"}
# `single-file` is deferred by the KPress v0.3.0 contract. Reject explicitly so callers
# see a clear 400 with the reason rather than a half-supported artifact. The external
# package is authoritative: https://github.com/jlevy/kpress/blob/v0.3.0/docs/kpress-design.md
_KPRESS_EXPORT_MODES_DEFERRED = {"single-file"}
_KPRESS_EXPORT_ASSET_MODES_SUPPORTED = {"linked", "hashed"}


async def api_kpress_export(request: Request) -> JSONResponse:
    """POST /api/kpress/export — render a served-root file into a publishable artifact.

    Thin wrapper over ``kpress_adapter.export_kpress_document``. The host enforces
    path safety on both source and destination (both must stay under ROOT_DIR), maps
    the user's gesture into a ``KPressExportRequest``, and translates KPress
    exceptions into the same shape ``api_kpress_render`` uses.
    """

    if request.method != "POST":
        return JSONResponse({"error": "Method not allowed"}, status_code=405)

    try:
        body = await request.json()
    except _json.JSONDecodeError as exc:
        return JSONResponse(
            {"type": "kpress_export_error", "error": "Invalid JSON body", "detail": str(exc)},
            status_code=400,
        )

    if not isinstance(body, dict):
        return JSONResponse(
            {"type": "kpress_export_error", "error": "Request body must be a JSON object"},
            status_code=400,
        )

    raw_path = body.get("path", "")
    raw_destination = body.get("destination", "")
    view = body.get("view", "rendered")
    profile = body.get("profile") or "document"
    export_mode = body.get("export_mode", "page")
    asset_mode = body.get("asset_mode", "linked")
    optimize = bool(body.get("optimize", False))
    theme_mode = body.get("theme_mode", "system")

    if export_mode in _KPRESS_EXPORT_MODES_DEFERRED:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": (
                    f"Export mode {export_mode!r} is deferred and not supported in this release"
                ),
            },
            status_code=400,
        )
    if export_mode not in _KPRESS_EXPORT_MODES_SUPPORTED:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": f"Unsupported export_mode {export_mode!r}; expected one of "
                f"{sorted(_KPRESS_EXPORT_MODES_SUPPORTED)}",
            },
            status_code=400,
        )
    if asset_mode not in _KPRESS_EXPORT_ASSET_MODES_SUPPORTED:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": f"Unsupported asset_mode {asset_mode!r}; expected one of "
                f"{sorted(_KPRESS_EXPORT_ASSET_MODES_SUPPORTED)}",
            },
            status_code=400,
        )

    source = _safe_path(raw_path) if isinstance(raw_path, str) else None
    if source is None or not source.is_file():
        return JSONResponse(
            {"type": "kpress_export_error", "error": "Source path not found or unsafe"},
            status_code=404,
        )

    if not isinstance(raw_destination, str) or not raw_destination:
        return JSONResponse(
            {"type": "kpress_export_error", "error": "`destination` is required"},
            status_code=400,
        )
    destination = _safe_path(raw_destination)
    if destination is None:
        return JSONResponse(
            {"type": "kpress_export_error", "error": "Destination escapes served root"},
            status_code=400,
        )

    artifact = ArtifactPath(source)
    ext = artifact.logical_ext
    ctx = FileContext(source, ext)
    kind = await asyncio.to_thread(_classify_with_plugins, source, ext, file_ctx=ctx)

    export_source = source
    source_text: str | None = None
    if artifact.is_compressed:
        try:
            source_text, _ = await asyncio.to_thread(
                _read_artifact_text,
                artifact,
                _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            )
        except (_ArtifactTextLimitError, ArtifactDecompressionLimitError) as exc:
            return JSONResponse(
                {
                    "type": "kpress_export_error",
                    "error": "Compressed source is too large to export",
                    "detail": str(exc),
                    "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
                },
                status_code=413,
            )
        except ArtifactCompressionError as exc:
            return JSONResponse(
                {
                    "type": "kpress_export_error",
                    "error": "Unable to read compressed source",
                    "detail": str(exc),
                },
                status_code=400,
            )
        except OSError as exc:
            return JSONResponse(
                {
                    "type": "kpress_export_error",
                    "error": "Unable to read compressed source",
                    "detail": str(exc),
                },
                status_code=404,
            )
        export_source = source.with_suffix("")

    export_request = kpress_adapter.build_export_request(
        path=str(export_source),
        source_text=source_text,
        kind=kind,
        view=view,
        print_profile=profile,
        theme_mode=theme_mode,
        export_mode=export_mode,
        asset_mode=asset_mode,
        optimize=optimize,
        destination=destination,
    )

    try:
        report = await asyncio.to_thread(kpress_adapter.export_kpress_document, export_request)
    except kpress_adapter.KPressInvalidRequestError as exc:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": "Invalid KPress export request",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=400,
        )
    except kpress_adapter.KPressRenderError as exc:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": "KPress export failed",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=502,
        )

    return JSONResponse(
        {"type": "kpress-export-report", "report": report, "destination": str(destination)},
        headers={"cache-control": "no-cache"},
    )


async def kpress_static_asset(request: Request) -> Response:
    """Serve KPress package assets through Metabrowser's safe asset route."""

    rel = request.path_params.get("path", "")
    try:
        asset = await asyncio.to_thread(kpress_adapter.get_kpress_static_asset, rel)
    except kpress_adapter.KPressAssetNotFoundError:
        return PlainTextResponse(f"not found: {rel}", status_code=404)

    is_font = rel.rsplit(".", 1)[-1].lower() in {"woff2", "woff", "ttf", "otf"}
    if is_font:
        # Fonts are the one asset class we cache hard. They are large, stable
        # for a given KPress version (the URL is version-keyed), and — unlike
        # CSS/JS — are not edited during local development, so the staleness
        # risk that drives `no-cache` below does not apply. Metabrowser is
        # opened often, so an immutable cache means repeat visits pay zero font
        # bytes and skip the revalidation round-trip before first paint.
        headers = {
            "ETag": asset.etag,
            "Cache-Control": "public, max-age=31536000, immutable",
        }
    else:
        headers = {
            "ETag": asset.etag,
            # The /kpress-static/ URL is keyed by the KPress *version* (e.g.
            # v0.0.1), not by content, so the package's own long max-age would
            # serve stale CSS/JS for a year whenever an asset changes without a
            # version bump (the constant pain during local development — and
            # these assets load dynamically, so a hard reload doesn't bust
            # them). Force revalidation against the content-addressed ETag
            # instead: a 304 when unchanged (cheap), fresh bytes the moment an
            # asset changes.
            "Cache-Control": "no-cache",
        }
    if request.headers.get("if-none-match", "") == asset.etag:
        return Response(status_code=304, headers=headers)
    return Response(
        content=asset.content,
        media_type=asset.media_type,
        headers=headers,
    )


@log_async_calls()
async def api_activity(_request: Request) -> JSONResponse:
    """Return the list of files actively being written to.

    The SPA uses ``fs.change`` operations on ``/api/events``
    (active_tracker.py emits the active-flag flips inline). This route is
    retained for two reasons:

    * Scripted / curl callers — the JSON snapshot is convenient
      shell glue and preserves the snapshot endpoint contract.
    * Bench coverage — ``devtools/browser_bench.py`` measures it
      as the cold-path proxy for the inventory-backed activity
      walk (see :mod:`metabrowser.activity`).

    No SPA fetch path exercises this endpoint. If you're adding a
    new SPA caller, prefer subscribing to ``fs.change`` upserts on
    ``/api/events`` and reading ``entry.active`` / ``entry.labels``
    instead — that's the live-update path.
    """
    active_files = await asyncio.to_thread(_activity_snapshot, _resolved_root_dir())
    LOG.debug("api_activity: %d active files", len(active_files))
    return JSONResponse(
        {
            "active_files": active_files,
            "poll_interval_ms": ACTIVITY_POLL_INTERVAL_MS,
        }
    )


def _accepts_gzip(accept_encoding: str) -> bool:
    """Return True if ``Accept-Encoding`` allows gzip per RFC 7231.

    Honors comma-separated tokens with optional ``;q=`` weights:
    ``gzip;q=0`` explicitly forbids gzip; ``*`` accepts gzip unless
    paired with ``gzip;q=0``. Anything else without ``gzip`` or ``*``
    falls through to false.
    """
    if not accept_encoding:
        return False
    explicit_disable = False
    has_gzip = False
    has_wildcard = False
    for token in accept_encoding.lower().split(","):
        token = token.strip()
        if not token:
            continue
        parts = [p.strip() for p in token.split(";")]
        encoding = parts[0]
        q = 1.0
        for p in parts[1:]:
            if p.startswith("q="):
                with contextlib.suppress(ValueError):
                    q = float(p[2:])
        if encoding == "gzip":
            if q > 0:
                has_gzip = True
            else:
                explicit_disable = True
        elif encoding == "*" and q > 0:
            has_wildcard = True
    if explicit_disable:
        return False
    return has_gzip or has_wildcard


_RAW_STREAM_CHUNK = 64 * 1024


async def raw_file(request: Request) -> Response:
    subpath = request.query_params.get("path", "")
    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return PlainTextResponse("Not found", status_code=404)

    artifact = ArtifactPath(target)
    media_type = artifact.mime_type

    # Uncompressed path: stream the file as-is. ``FileResponse`` streams in
    # fixed-size chunks via aiofiles; the earlier ``read_bytes()`` +
    # ``Response`` shape allocated the entire file before the first byte
    # hit the wire (a 100 MB image stalled and spiked memory). Streaming
    # keeps the event loop responsive and bounds memory regardless of
    # file size. ``_safe_path`` already rejected paths outside ROOT_DIR.
    if not artifact.is_compressed:
        return FileResponse(target, media_type=media_type)

    accepts_gzip = _accepts_gzip(request.headers.get("accept-encoding", ""))

    # Passthrough: client accepts gzip → ship the on-disk bytes verbatim
    # with ``Content-Encoding: gzip`` so the browser decompresses
    # transparently. Zero server CPU. Starlette's ``GZipMiddleware``
    # skips responses with ``Content-Encoding`` already set, so we
    # don't double-wrap.
    if artifact.is_gzip and accepts_gzip:
        return FileResponse(
            target,
            media_type=media_type,
            headers=artifact.passthrough_headers(),
        )

    # Validate every compressed identity response before StreamingResponse sends
    # successful headers. Without this scan, malformed or over-limit gzip data
    # can fail only after a 200 response and a partial body reach the client.
    try:
        await asyncio.to_thread(lambda: artifact.logical_size)
    except ArtifactDecompressionLimitError as exc:
        return PlainTextResponse(str(exc), status_code=413)
    except ArtifactCompressionError as exc:
        return PlainTextResponse(str(exc), status_code=400)

    # Identity fallback: client refuses gzip (rare, e.g. ``curl`` without
    # ``--compressed``). Stream-decompress so the client gets plain
    # bytes.
    def _iter_decompressed() -> Any:
        with artifact.open_binary() as fh:
            while True:
                chunk = fh.read(_RAW_STREAM_CHUNK)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter_decompressed(),
        media_type=media_type,
        headers={"Vary": "Accept-Encoding"},
    )


# ── Plugin discovery (one-shot at module import) ────────────────
#
# Plugins are discovered once at module load. Built-in plugins are baked
# into the metabrowser wheel; entry-point plugins are pulled from any
# installed Python distribution declaring a `metabrowser.plugins` entry
# point; local plugin directories are only loaded when the operator names them through
# the CLI or `METABROWSER_PLUGINS_DIRS`.
#
# Discovery is best-effort: invalid plugins are logged and skipped, the
# server still starts. Hot reload (re-running discovery during a single
# server run) is deliberately deferred.

from metabrowser.plugin_loader.classify import (
    CompiledKindRule,
    build_classifier,
    collect_folder_markers,
)
from metabrowser.plugin_loader.discovery import (
    discover_plugins,
)
from metabrowser.plugin_loader.static_assets import (
    build_plugin_routes,
)
from metabrowser.tree import (
    set_folder_markers,
)

# Honor the CLI's --plugins-dir flags (merged into METABROWSER_PLUGINS_DIRS
# by the CLI) and direct-import settings loaded from .env / .env.local above.
# Anything in this list is operator-named — auto-discovery from the served
# root or the user's home is intentionally NOT a source (trust model).
_extra_plugin_dirs: list[Path] = []
_env_dirs = os.environ.get("METABROWSER_PLUGINS_DIRS", "")
if _env_dirs:
    _extra_plugin_dirs = normalize_plugin_dirs(
        Path(path) for path in _env_dirs.split(os.pathsep) if path
    )

_DISCOVERY = discover_plugins(
    extra_dirs=_extra_plugin_dirs or None,
)
_LOADED_PLUGINS = _DISCOVERY.plugins
if _DISCOVERY.errors:
    for _err in _DISCOVERY.errors:
        LOG.warning("metabrowser plugin discovery: %s", _err)
LOG.debug(
    "metabrowser loaded %d plugin(s): %s",
    len(_LOADED_PLUGINS),
    [p.name for p in _LOADED_PLUGINS],
)


# Pre-compile plugin kind rules and view bindings for fast lookup at
# request time. Order is the discovery order; ties broken by plugin
# name. Higher priority wins.
_PLUGIN_KIND_RULES: list[CompiledKindRule] = []
_PLUGIN_VIEWS_BY_KIND: dict[str, list[dict[str, Any]]] = {}
for _idx, _plugin in enumerate(_LOADED_PLUGINS):
    for _kr in _plugin.manifest.kind:
        _PLUGIN_KIND_RULES.append(
            CompiledKindRule(rule=_kr, plugin_name=_plugin.name, discovery_index=_idx)
        )
    for _view in _plugin.manifest.view:
        bucket = _PLUGIN_VIEWS_BY_KIND.setdefault(_view.kind, [])
        bucket.append(
            {
                "id": _view.id,
                "label": _view.label,
                "default": _view.default,
                "container_class": _view.container_class,
                "printable": _view.printable,
                "print_profile": _view.print_profile,
                "render_runtime": _view.render_runtime,
            }
        )

_PLUGIN_CLASSIFY = build_classifier(_PLUGIN_KIND_RULES)
# Hand the tree renderer the folder-marker set so directories whose direct
# children include a known marker get a ``marker_basename`` field on their
# row. This is the only piece of plugin state that ``tree.py`` needs.
set_folder_markers(collect_folder_markers(_PLUGIN_KIND_RULES))


def _classify_with_plugins(
    target: Path,
    ext: str,
    adapter: str | None = None,
    *,
    file_ctx: FileContext | None = None,
) -> str:
    """Classify a file. Plugin rules take precedence; legacy detector chain is the fallback.

    Returns the winning kind id. The legacy chain still drives the
    built-in kinds (markdown, text, binary, agent-log, unknown-jsonl).

    *file_ctx* is optional — pass an existing :class:`FileContext` to
    avoid re-parsing frontmatter in callers that need both classification
    and frontmatter access (the api_file handler does this).
    """
    ctx = file_ctx if file_ctx is not None else FileContext(target, ext, adapter)
    plugin_kind = _PLUGIN_CLASSIFY(ctx)
    if plugin_kind is not None:
        return plugin_kind
    return classify_file_kind(target, ext, adapter)


def _views_for_kind(kind: str) -> list[dict[str, Any]]:
    """Return the merged view list for a kind: built-in registry + plugin manifests.

    Plugin views are appended after built-in views; an exact (kind, id)
    collision means the plugin entry overrides the built-in (last write
    wins; the plugin author intentionally chose to register an existing
    id). The order in which they appear in the tab strip is built-ins
    first, then plugin order.
    """
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for v in VIEW_REGISTRY.get(kind, []):
        out.append(dict(v))
        seen_ids.add(v["id"])
    for v in _PLUGIN_VIEWS_BY_KIND.get(kind, []):
        if v["id"] in seen_ids:
            # Replace existing entry with plugin override.
            for i, existing in enumerate(out):
                if existing["id"] == v["id"]:
                    out[i] = v
                    break
        else:
            out.append(v)
            seen_ids.add(v["id"])
    if out and not any(v.get("default") for v in out):
        out[0] = {**out[0], "default": True}
    return out


def _build_plugin_style_block() -> str:
    """Emit <link rel='stylesheet'> tags for each plugin's styles.css + extra_styles.

    Emitted in the <head>; each plugin contributes its `styles.css`
    (auto-detected) followed by every entry in `[plugin].extra_styles`
    in manifest order.
    """
    parts: list[str] = []
    for plugin in _LOADED_PLUGINS:
        css_path = plugin.static_root / "styles.css"
        if css_path.is_file():
            parts.append(f'<link rel="stylesheet" href="/plugin-static/{plugin.name}/styles.css">')
        for extra in plugin.manifest.plugin.extra_styles:
            parts.append(f'<link rel="stylesheet" href="/plugin-static/{plugin.name}/{extra}">')
    return "\n  ".join(parts)


def _build_plugin_script_block() -> str:
    """Emit per-plugin <script> tags after the shell loads.

    For each plugin (in discovery order), emit any `extra_scripts`
    declared in its manifest as classic <script> tags first (so they
    set up globals that `index.js` can use), then the plugin's
    `index.js` as an ES module. Plugins that don't declare
    `extra_scripts` get just the index.js tag.
    """
    parts: list[str] = []
    for plugin in _LOADED_PLUGINS:
        for extra in plugin.manifest.plugin.extra_scripts:
            parts.append(f'<script src="/plugin-static/{plugin.name}/{extra}"></script>')
        parts.append(f'<script type="module" src="/plugin-static/{plugin.name}/index.js"></script>')
    return "\n  ".join(parts)


# ── Diagnostic routes (opt-in) ──────────────────────────────────


async def _debug_tasks(_request: Request) -> JSONResponse:
    """Snapshot of asyncio tasks in the running event loop.

    Returns ``{"task_count": N, "tasks": [...]}`` where each entry is
    ``{"name", "coro", "state"}``. Useful for diagnosing "why is the
    server slow" — if the count balloons during a hover-prefetch
    storm, the loop is overcommitted and requests queue behind in-
    flight work. Cheap (no I/O); each call iterates ``all_tasks()``
    and reads each task's repr.

    Off by default to avoid leaking introspection in dev mode; enable
    by setting ``METABROWSER_DEBUG=1`` in the environment.
    """
    if os.environ.get("METABROWSER_DEBUG", "").strip() not in ("1", "true", "yes"):
        return JSONResponse({"error": "set METABROWSER_DEBUG=1 to enable"}, status_code=404)
    tasks = asyncio.all_tasks()
    snapshot = []
    for t in tasks:
        try:
            coro = t.get_coro()
            coro_name = getattr(coro, "__qualname__", None) or repr(coro)
        except Exception as exc:  # pragma: no cover - defensive
            coro_name = f"<unreadable: {exc}>"
        snapshot.append(
            {
                "name": t.get_name(),
                "coro": coro_name,
                "done": t.done(),
                "cancelled": t.cancelled(),
            }
        )
    return JSONResponse(
        {
            "task_count": len(tasks),
            "tasks": snapshot,
        }
    )


# ── Starlette app ───────────────────────────────────────────────

routes = [
    Route("/", index),
    Route("/api/tree", api_tree),
    Route("/api/recent", api_recent),
    Route("/api/file", api_file),
    Route("/api/kpress/render", api_kpress_render),
    Route("/api/kpress/export", api_kpress_export, methods=["POST"]),
    Route("/api/activity", api_activity),
    Route("/api/stream", api_stream),
    Route("/_debug/tasks", _debug_tasks),
    Route("/raw", raw_file),
    Route("/kpress-static/{path:path}", kpress_static_asset),
    Mount("/static", app=StaticFiles(directory=STATIC_DIR), name="static"),
    # Read-only git history, kept as its own collection in
    # ``metabrowser.git.routes``: separate wire model, separate failure
    # modes, separate resource bounds.
    *GIT_ROUTES,
    *build_plugin_routes(_LOADED_PLUGINS),
]

# GZip every response above 1 KiB. This materially reduces tree and file
# payloads over an SSH tunnel. ``compresslevel=6`` is Starlette's default and
# trades CPU against compression ratio at the right point for the small
# JSON payloads this app emits. ``FileResponse`` is excluded automatically
# by Starlette since it sets its own headers.
middleware = [
    Middleware(_HostValidationMiddleware),
    Middleware(_SlowRequestLogMiddleware),
    Middleware(GZipMiddleware, minimum_size=1024, compresslevel=6),
]

# Lazy import: events_route.py pulls in the inventory + events
# layer; importing it at module top circles back through
# paths_safe / activity, which already import this module. The
# late import keeps the import graph acyclic.
from metabrowser.events_route import (
    add_inventory_routes,
    build_lifespan,
)


def _inventory_root_provider() -> object:
    """Resolve the served root for the lifespan hook. Returns
    ``None`` when no root has been set yet (e.g., test suites
    that import the app without invoking ``main()``); the
    inventory just stays idle in that case."""

    try:
        root = _resolved_root_dir()
    except Exception:
        return None
    return root if str(root) and root != Path() else None


def _lifespan(app: Starlette):  # type: ignore[no-untyped-def]
    return build_lifespan(root_provider=_inventory_root_provider)


app = Starlette(routes=routes, middleware=middleware, lifespan=_lifespan)
add_inventory_routes(app)


# ── CLI entry point ─────────────────────────────────────────────
