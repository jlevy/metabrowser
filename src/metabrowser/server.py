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
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.responses import (
    JSONResponse as _StarletteJSONResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from strif import file_mtime_hash

from metabrowser import __version__, kpress_adapter
from metabrowser.active_tracker import activity_snapshot
from metabrowser.activity import ACTIVITY_POLL_INTERVAL_MS
from metabrowser.build_version import display_version_line

# Cache invalidator: clear_charts_cache is invoked by the root-change
# handler so chart memos don't stick across served-root swaps.
from metabrowser.charts import clear_charts_cache
from metabrowser.content_sniff import ContentClass, sniff_artifact
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
from metabrowser.folder_discovery import discover_folder
from metabrowser.git.routes import GIT_ROUTES
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactPath,
)
from metabrowser.http_caching import (
    build_scoped_etag,
    etag_headers,
    matches_if_none_match,
)
from metabrowser.inventory_engine.contract import (
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    EntryType,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryFilter,
    LifecyclePhase,
    NavigationProjection,
    NavigationQuery,
    PriorityRequest,
    ReadQuery,
    ReadRequest,
    RecentProjection,
    RecentQuery,
    RollupProjection,
    RollupQuery,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import CoordinatedRead, HostVersion
from metabrowser.inventory_engine.runtime import InventoryRuntime
from metabrowser.inventory_engine.tree_page_assembly import (
    TreePageAssembly,
    TreePageQuery,
    assemble_tree_pages,
)
from metabrowser.inventory_rollup import RollupRank
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
from metabrowser.plugin_api import MAX_CONTAINER_INNER_DEPTH
from metabrowser.plugin_paths import normalize_plugin_dirs
from metabrowser.recent import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    WindowKey,
    recent_result_from_projection,
)
from metabrowser.repository_context import discover_repository_context
from metabrowser.settings import (
    FOLDER_DISCOVERY_MAX_ENTRIES,
    INVENTORY_TREE_PAGE_ROWS,
    RECENT_WINDOW_SECONDS,
    ROLLUP_BODY_CACHE_ENTRIES,
    ROLLUP_DEFAULT_DEPTH,
    ROLLUP_DEFAULT_EXT_RANK,
    ROLLUP_DEFAULT_EXT_TOP,
    ROLLUP_DEFAULT_TOP,
    ROLLUP_FILE_TYPE_FILENAME_LIMIT,
    ROLLUP_FILE_TYPE_REMAINING_LIMIT,
    ROLLUP_MAX_DEPTH,
    ROLLUP_MAX_EXT_TOP,
    ROLLUP_MAX_NODES,
    ROLLUP_MAX_TOP,
    SLOW_OPERATION_LOG_SECONDS,
    SYNTAX_HIGHLIGHT_MAX_BYTES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
    client_settings_dict,
)
from metabrowser.sse import api_stream
from metabrowser.tree import (
    _IGNORE_CACHE,
    DEFAULT_TREE_DEPTH,
    MAX_TREE_DEPTH,
    SENTINEL_SUMMARY_DEPTH,
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
    build_inventory_tree_from_entries,
)
from metabrowser.tree_filter import (
    TreeFilter,
    parse_recency,
    parse_size_floor,
    parse_types,
    reset_rollup_cache_for_tests,
)
from metabrowser.view_routes import (
    VIEW_ROUTE_PREFIX,
    decode_safe_commit_route,
    decode_safe_view_path,
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

# How stale the navigation tallies may be before a root /api/tree recomputes
# them. They cost one pass over every entry in the index, and during a walk the
# revision they memoize on advances on every write, so without an age bound
# every request during the scan repeats the pass: measured at 837-1,567 ms per
# root request on a 300,000-file tree against 15 ms once settled.
#
# This is the floor, not the bound. The bound the index applies is the larger
# of this and however long the last pass actually took, so the server never
# spends much over half its time recomputing a number the client is already
# told is provisional -- and so the policy scales with the tree instead of
# being tuned for one size. A fixed half second was measured first and moved
# the scanning cost only 638 ms to 518 ms, because the nav polls once a second
# and a bound shorter than the poll period can never be hit by a poller.
#
# The floor matters on a small tree, where the pass is cheap enough that its
# own duration would allow a recompute per request for no benefit.
# The tally pass's own row cap, passed explicitly so the memo key the route
# asks for is the memo key the route gets.
NAVIGATION_TALLY_LIMIT = 200

# How many of the root's immediate children the shell inlines so the tree can
# paint before its first fetch returns. A cap rather than the whole level
# because this rides in the HTML: every byte is on the critical path for every
# reader, including the ones whose root has ten thousand entries. Two hundred
# rows is past any viewport at any sane row height, so the reader sees a full
# screen either way and the rest arrives with the fetch a moment later.
# Set to 0 to disable the inline entirely.
_INLINE_INITIAL_TREE_ROWS = 200

# Encoded rollup bodies keyed by their ETag. The validator alone only helps a
# client that already holds the answer; a second tab opening the same folder,
# or a reconnect, arrives without one and would otherwise re-aggregate and
# re-serialize a body the server just produced. Bounded by
# ``ROLLUP_BODY_CACHE_ENTRIES``: entries from a superseded index revision can
# never be requested again, so they age out by insertion order.
_ROLLUP_BODY_CACHE: dict[str, bytes] = {}


def _remember_rollup_body(etag: str, body: bytes | memoryview[int]) -> None:
    """Retain one encoded rollup body for reuse by an identical request."""

    _ROLLUP_BODY_CACHE[etag] = bytes(body)
    while len(_ROLLUP_BODY_CACHE) > ROLLUP_BODY_CACHE_ENTRIES:
        _ROLLUP_BODY_CACHE.pop(next(iter(_ROLLUP_BODY_CACHE)))


# Rollup bodies currently being built, keyed by the ETag that identifies them.
# The retained body only helps a request that arrives after one finished;
# clients that arrive together — several tabs refreshing off the same inventory
# change — would each aggregate the same answer.
#
# The build is its own task rather than work owned by whichever request arrived
# first, and every request awaits it through a shield. That way a client
# disconnecting cancels only its own wait: the shared build runs to completion
# for everyone still waiting, and its body is still cached for whoever asks
# next.
_ROLLUP_IN_FLIGHT: dict[str, asyncio.Task[bytes]] = {}


def reset_response_caches_for_tests() -> None:
    """Drop process-retained rollup responses between isolated test apps."""

    _ROLLUP_BODY_CACHE.clear()
    _ROLLUP_IN_FLIGHT.clear()
    reset_rollup_cache_for_tests()


def _release_rollup_flight(etag: str, task: asyncio.Task[bytes]) -> None:
    """Retire a finished shared build and mark any failure as retrieved.

    Every waiter raises on its own, so the task's exception would otherwise
    surface as an "exception was never retrieved" warning once the last one
    goes away.
    """

    if _ROLLUP_IN_FLIGHT.get(etag) is task:
        del _ROLLUP_IN_FLIGHT[etag]
    if not task.cancelled():
        task.exception()


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
    "FileContext",
    "MAX_TREE_DEPTH",
    "SENTINEL_SUMMARY_DEPTH",
    "STATIC_DIR",
    "VIEW_REGISTRY",
    "_IGNORE_CACHE",
    "_cached_root_prefix",
    "_clear_browser_caches",
    "_dir_tree",
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

# ROOT_DIR proxy: tests (and old serve.py code) read/write
# ``proc_browser.ROOT_DIR`` directly. The canonical value now lives in
# ``paths_safe``; bridge both directions via a module class so reads and
# writes always go through ``_set_root_dir`` (which fires every
# registered cache-invalidation callback).
import sys as _sys
import types as _types

import metabrowser.paths_safe as _paths_safe


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


# ── Static asset directories ────────────────────────────────────
#
# CSS / JS bundles are served as plain static files (Starlette's
# ``StaticFiles`` mount handles Last-Modified + If-Modified-Since for
# 304s), not inlined into the index HTML. That way edits show up on a
# normal browser refresh without restarting the server, and the
# browser's HTTP cache does the work it's designed to do.

STATIC_DIR: Path = Path(__file__).parent / "static"

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

    It also carries this build's identity, because the body is a function of
    the file *and* of how this version renders it. Keying on the file alone
    made every rendering change invisible to a client that had already cached
    the file: after small binaries moved from the text fallback to the Bytes
    view, a cached browser kept replaying a field of U+FFFD, because the
    file's mtime had not changed and the server answered 304 to its
    revalidation. The salt is what makes an upgrade invalidate exactly once.
    """
    return build_scoped_etag(mtime_hash)


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

# Files outside ``_TEXT_EXTS`` are decided by looking at their content —
# see metabrowser.content_sniff and _prefers_text_body below. Size used to
# stand in for that check (under 512 KiB meant "try it as text"), which read
# every small binary through `errors="replace"` and rendered it as a field of
# U+FFFD, and refused every large extensionless text file the opposite way.


def _prefers_text_body(target: Path) -> bool:
    """Whether a file with no known text extension should render as text.

    Only consulted once the extension has failed to answer, so the bounded
    read inside costs nothing for the files this browser opens most.

    ``UNKNOWN`` resolves to text on purpose: it means the bytes could not be
    read at all, and the text path reports that failure with the real reason
    where the byte view would answer a broken file with an empty dump.
    """
    return sniff_artifact(target) is not ContentClass.BINARY


# Defaults live in settings.py, which is also what the client reads, so the
# chunk size cannot drift between the two planes. See
# docs/large-content-rendering.md for the measurements behind them.
_TEXT_PREVIEW_CHUNK_BYTES = int(
    os.environ.get("METABROWSER_TEXT_PREVIEW_BYTES", str(TEXT_PREVIEW_CHUNK_BYTES))
)
_TEXT_PREVIEW_MAX_CHUNK_BYTES = int(
    os.environ.get("METABROWSER_TEXT_PREVIEW_MAX_BYTES", str(TEXT_PREVIEW_REQUEST_MAX_BYTES))
)
_SYNTAX_HIGHLIGHT_MAX_BYTES = int(
    os.environ.get("METABROWSER_HIGHLIGHT_MAX_BYTES", str(SYNTAX_HIGHLIGHT_MAX_BYTES))
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


def _query_bounded_int(
    request: Request,
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    return max(minimum, min(_query_int(request, name, default), maximum))


def _query_choice(
    request: Request,
    name: str,
    default: str,
    allowed: frozenset[str],
) -> str:
    raw = request.query_params.get(name, "")
    value = default if raw == "" else raw
    if value not in allowed:
        raise ValueError(f"Unknown {name}: {value!r}")
    return value


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
    """Server-render the served root's *name* so it shows on first paint.

    The name and not the path: the directories above the served root are
    the same on every row of every view, and the navigation column is the
    scarcest width in the app. The whole path is one hover away on the
    anchor's title, and the file header across the divider spells it out.
    """
    base = _paths_safe.ROOT_DIR.resolve().name
    label = base or str(_paths_safe.ROOT_DIR.resolve())
    return f'<span class="path"><span class="path-base">{html_escape(label)}</span></span>'


def _served_root_str() -> str:
    """The served root, absolute. What the API reports and paths resolve against."""
    return str(_paths_safe.ROOT_DIR.resolve())


def _display_root_str() -> str:
    """The served root as a header shows it, with the home directory as ``~``.

    Display only, and only a shortening: the prefix is the same on every page
    of the app, so every character it spends is width taken from the part of
    the address that changes. A root under the home directory is the common
    case and ``~`` is the shortest true name for it.

    Falls through to the absolute path whenever the substitution would be a
    guess rather than a fact — a root outside the home directory, or a
    platform that does not report one.
    """

    resolved = _paths_safe.ROOT_DIR.resolve()
    try:
        home = Path.home().resolve()
    except (OSError, RuntimeError):
        return str(resolved)
    if resolved == home:
        return "~"
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return str(resolved)
    # Through Path rather than a slash join, so the separator is the
    # platform's rather than this file's assumption about it.
    return str(Path("~") / relative)


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

# Prefetched-tier scheduling. The chain waits for the first idle callback so it
# does not compete with the tree render, and the timeout is the floor: on a
# large tree the main thread is busy for seconds, and a source view that never
# highlights is worse than one that highlights late. Two seconds is the same
# bound the tree's own idle prefetch already uses
# (SUBTREE_PREFETCH_IDLE_TIMEOUT_MS in static/app.js).
PREFETCH_IDLE_TIMEOUT_MS = 2000
# requestIdleCallback is unavailable in Safari before 18.2, so the fallback is
# a plain timer past first paint rather than no deferral at all.
PREFETCH_FALLBACK_DELAY_MS = 200


async def index(request: Request) -> HTMLResponse:
    """Serve the SPA page; CSS/JS are linked, not inlined."""

    initial_path = _initial_path_html()
    initial_root = html_escape(_display_root_str(), quote=True)
    version_line = html_escape(display_version_line("metab", __version__))
    repository_context = await asyncio.to_thread(discover_repository_context, _resolved_root_dir())
    styles_url = _static_asset_url("styles.css")
    asset_loader_url = _static_asset_url("asset-loader.js")
    theme_state_url = _static_asset_url("theme-state.js")
    request_error_url = _static_asset_url("request-error.js")
    formatters_url = _static_asset_url("formatters.js")
    inventory_scope_url = _static_asset_url("inventory-scope.js")
    directory_totals_store_url = _static_asset_url("directory-totals-store.js")
    contribution_registry_url = _static_asset_url("contribution-registry.js")
    resource_context_url = _static_asset_url("resource-context.js")
    view_state_url = _static_asset_url("view-state.js")
    navigation_url = _static_asset_url("navigation.js")
    source_append_url = _static_asset_url("source-append.js")
    file_type_taxonomy_url = _static_asset_url("file-type-taxonomy.js")
    plugin_sdk_url = _static_asset_url("plugin-sdk.js")
    filter_state_url = _static_asset_url("filter-state.js")
    filter_controls_url = _static_asset_url("filter-controls.js")
    icons_url = _static_asset_url("icons.js")
    charts_url = _static_asset_url("charts.js")
    tree_expansion_url = _static_asset_url("tree-expansion.js")
    tree_filter_model_url = _static_asset_url("tree-filter-model.js")
    pending_tally_diagnostics_url = _static_asset_url("pending-tally-diagnostics.js")
    known_file_catalog_url = _static_asset_url("known-file-catalog.js")
    catalog_feed_url = _static_asset_url("catalog-feed.js")
    file_fuzzy_match_url = _static_asset_url("file-fuzzy-match.js")
    search_controller_url = _static_asset_url("search-controller.js")
    keyboard_shortcuts_url = _static_asset_url("keyboard-shortcuts.js")
    overlay_layer_url = _static_asset_url("overlay-layer.js")
    keyboard_help_url = _static_asset_url("keyboard-help.js")
    tree_keyboard_navigation_url = _static_asset_url("tree-keyboard-navigation.js")
    search_palette_url = _static_asset_url("search-palette.js")
    git_graph_url = _static_asset_url("git-graph.js")
    git_panel_url = _static_asset_url("git-panel.js")
    app_url = _static_asset_url("app.js")
    perf_url = _static_asset_url("perf.js")
    # Inject the client-visible settings dict before any app code
    # runs so JS can read window.METABROWSER_SETTINGS.* without
    # duplicating constants in the source.
    settings_block = (
        f"<script>window.METABROWSER_SETTINGS={_json.dumps(client_settings_dict())};</script>"
        f"<script>window.METABROWSER_CONTAINER_EXTS={_json.dumps(_container_exts())};</script>"
    )
    repository_context_json = _json.dumps(repository_context).replace("<", "\\u003c")
    # The tree's first rows, inlined. Without this the reader waits for a round
    # trip the server did not have to make them take: time to first row is
    # DOMContentLoaded plus the whole /api/tree request, and during a walk that
    # request is the slow one (exp-003 made it faster for everyone except the
    # first caller, whose cache is cold by construction). Depth 1 off the warm
    # index is the root's immediate children and nothing else, so it is bounded
    # by how wide the root is rather than by the tree.
    #
    # Only the unfiltered default view is inlined. A filter is client state the
    # server has not been told about at this point, so inlining a filtered view
    # would risk painting rows the reader's filter excludes; the fetch that
    # follows owns every case but this one.
    initial_tree_block = ""
    if _INLINE_INITIAL_TREE_ROWS:
        try:
            runtime = _inventory_runtime_for(request)
            initial_read = await runtime.coordinator.read(
                ReadRequest(
                    queries=(
                        DirectoryQuery(
                            query_id="initial-tree",
                            path="",
                            max_depth=1,
                            max_rows=_INLINE_INITIAL_TREE_ROWS,
                        ),
                    )
                )
            )
            initial_projection = initial_read.result.projection("initial-tree")
            if not isinstance(initial_projection, DirectoryProjection):
                raise TypeError("the initial-tree read returned the wrong projection")
            initial_tree = build_inventory_tree_from_entries(
                entries=initial_projection.entries,
                parent_rel="",
                max_depth=1,
                root_abs=_resolved_root_dir(),
                max_entries=_INLINE_INITIAL_TREE_ROWS,
            )
        except Exception:
            LOG.debug("initial tree inline failed", exc_info=True)
            initial_tree = []
        if initial_tree:
            initial_tree_json = _json.dumps({"tree": initial_tree}).replace("<", "\\u003c")
            initial_tree_block = (
                f"<script>window.METABROWSER_INITIAL_TREE={initial_tree_json};</script>"
            )
    repository_context_block = (
        f"<script>window.METABROWSER_REPOSITORY_CONTEXT={repository_context_json};</script>"
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
    # Prefetched tier: small relative to how likely they are to be wanted, and
    # visibly late if they arrive after the view that uses them. The chain
    # below starts them on the first idle callback after DOMContentLoaded, so
    # they do not compete with the tree render, and no later than
    # PREFETCH_IDLE_TIMEOUT_MS so a busy main thread cannot defer them
    # indefinitely. See docs/development.md "Asset Loading Tiers".
    optional_script_assets = [
        {"src": _static_asset_url("vendor/mustache.min.js")},
        {"src": _static_asset_url("vendor/highlight.min.js")},
        {"src": _static_asset_url("vendor/highlight-toml.min.js"), "requires": "hljs"},
    ]
    # On-demand tier: fetched by asset-loader.js the first time a consumer asks.
    # Chart.js and its two plugins are 297,531 bytes read by one view, and
    # eager loading measured ~374 ms of every document's load event whether or
    # not that view was ever opened. See docs/development.md "Asset Loading
    # Tiers" and the load-time plan for the measurement.
    on_demand_script_bundles = {
        # Navigation, search, Help, and Git controls are application-lifetime
        # tools, but none is needed to paint or fetch the first tree. Keeping
        # their ordered classic scripts behind that usable-state boundary
        # removes eleven requests from the shell's startup waterfall. They
        # begin immediately after loadTree settles, before inventory delivery
        # continues in the background.
        "shell-tools": [
            {"src": known_file_catalog_url},
            {"src": catalog_feed_url},
            {"src": file_fuzzy_match_url},
            {"src": search_controller_url},
            {"src": keyboard_shortcuts_url},
            {"src": overlay_layer_url},
            {"src": keyboard_help_url},
            {"src": tree_keyboard_navigation_url},
            {"src": search_palette_url},
            {"src": git_graph_url},
            {"src": git_panel_url},
        ],
        "chart": [
            {"src": _static_asset_url("vendor/chart.umd.min.js")},
            {
                "src": _static_asset_url("vendor/chartjs-plugin-annotation.min.js"),
                "requires": "Chart",
            },
            {
                "src": _static_asset_url("vendor/chartjs-adapter-date-fns.bundle.min.js"),
                "requires": "Chart",
            },
        ],
    }
    asset_bundles_block = (
        f"<script>window.METABROWSER_ASSET_BUNDLES="
        f"{_json.dumps(on_demand_script_bundles)};</script>"
    )
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
    // Prefetched, not eager: start when the main thread is free rather than
    // the moment the document parses, so fetching and evaluating these never
    // competes with the tree render that DOMContentLoaded also starts. The
    // timeout is the floor — a busy thread must not defer them forever,
    // because a source view that never highlights is worse than one that
    // highlights late.
    function start() {{ loadNext(0); }}
    function schedule() {{
      if (typeof window.requestIdleCallback === "function") {{
        window.requestIdleCallback(start, {{ timeout: {PREFETCH_IDLE_TIMEOUT_MS} }});
      }} else {{
        setTimeout(start, {PREFETCH_FALLBACK_DELAY_MS});
      }}
    }}
    if (document.readyState === "loading") {{
      document.addEventListener("DOMContentLoaded", schedule, {{ once: true }});
    }} else {{
      schedule();
    }}
  }})();
  </script>"""
    # Plugin assets are configured in the shell but fetched only when a
    # selected resource names a kind that consumes them. A cold directory
    # should not wait for Markdown, structured-data, diff, and log modules
    # before its first tree row. The manifest remains the source of every URL;
    # core does not special-case plugin names.
    plugin_asset_config = _build_plugin_asset_config_block()

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
</head>
<body>
  <main class="container">
    <div class="tree-pane" id="tree-pane">
      <header class="app-header">
        <!-- data-served-root is the one place the absolute root is written:
             the file header reads it back to render its dimmed prefix, so
             the two headers cannot disagree about what the root is. It is also
             what this heading's tooltip is built from.

             No data-tip-text here, deliberately. This element has a tooltip of
             its own in app.js — the folder's counts and age, not just its
             path — and an element carrying both would announce through two
             mechanisms at once, which is the bug the one-tooltip rule exists
             to prevent. See "One Tooltip, and It Is Ours" in
             docs/design-system.md. -->
        <a href="{VIEW_ROUTE_PREFIX}" class="header-path"
           data-served-root="{initial_root}">{initial_path}</a>
        <!-- The Metabrowser menu. The gear names the product rather than
             standing as an unlabelled settings control: the wordmark that
             used to sit on its own line above the path is this menu's title,
             which returns that line of the navigation column — the app's
             scarcest width — to the path. Inside: two icon-segment choosers
             (theme + reading font), a small font-set dropdown
             (#app-font-select, options from _FONT_SETS), and the same build
             version line printed by `metab --version`. Choices apply instantly.
             app.js (initSettingsControl) fills the icon segments and wires
             open/select + the dropdown. The wrapper's aria-expanded drives the
             menu's visibility via CSS.

             The title is a link to the project rather than a label: it is the
             one place the product names itself, so it is where someone goes
             looking for the project. It carries its own accessible name saying
             where it goes — the bare wordmark would announce as the menu's
             name repeated — and it is not aria-hidden, because a control that
             cannot be reached is not a control. -->
        <div class="settings-toggle" id="settings-control" aria-expanded="false">
          <button class="icon-btn settings-btn" id="settings-btn" type="button"
                  aria-haspopup="true" aria-label="Metabrowser menu"></button>
          <div class="settings-menu menu" role="menu" aria-label="Metabrowser">
            <a class="menu-title menu-title-link" href="https://github.com/jlevy/metabrowser"
               target="_blank" rel="noopener noreferrer"
               aria-label="Metabrowser on GitHub">Metabrowser<span class="menu-title-arrow"
               aria-hidden="true">→</span></a>
            <div class="menu-separator"></div>
            <div class="menu-chooser" role="group" aria-label="Theme">
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="system" data-tip-text="System theme" aria-label="System theme"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="light" data-tip-text="Light theme" aria-label="Light theme"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-theme-choice="dark" data-tip-text="Dark theme" aria-label="Dark theme"></button>
            </div>
            <div class="menu-separator"></div>
            <div class="menu-chooser" role="group" aria-label="Reading font">
              <button class="menu-seg" type="button" role="menuitemradio" data-font-choice="serif" data-tip-text="Serif reading font" aria-label="Serif reading font"></button>
              <button class="menu-seg" type="button" role="menuitemradio" data-font-choice="sans" data-tip-text="Sans-serif reading font" aria-label="Sans-serif reading font"></button>
            </div>
            <div class="menu-separator"></div>
            <select class="menu-select" id="app-font-select" aria-label="Fonts">{app_font_options}</select>
            <div class="menu-separator"></div>
            <div class="menu-version">{version_line}</div>
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
          <div class="loading mb-delayed-loading"><div class="spinner"></div><span
            class="sr-only">Loading files…</span></div>
        </div>
      </div>
      <!-- role="group" carries the accessible name: ARIA forbids naming a
           generic element, so a bare div would drop the label and announce
           the hints and their controls with no grouping context. Not a live
           region — contextual hints change with focus, and announcing every
           change would talk over the polite index-progress row below. -->
      <div class="nav-shortcut-hints" id="nav-shortcut-hints" role="group"
           aria-label="Keyboard shortcuts" hidden></div>
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
  {settings_block}
  {repository_context_block}
  {initial_tree_block}
  {asset_bundles_block}
  <script src="{asset_loader_url}"></script>
  <script src="{theme_state_url}"></script>
  <script src="{request_error_url}"></script>
  <script src="{formatters_url}"></script>
  <script src="{inventory_scope_url}"></script>
  <script src="{directory_totals_store_url}"></script>
  <script src="{contribution_registry_url}"></script>
  <script src="{resource_context_url}"></script>
  <script src="{view_state_url}"></script>
  <script src="{navigation_url}"></script>
  <script src="{source_append_url}"></script>
  <script src="{file_type_taxonomy_url}"></script>
  <script src="{plugin_sdk_url}"></script>
  <script src="{perf_url}"></script>
  <script src="{filter_state_url}"></script>
  <script src="{filter_controls_url}"></script>
  <script src="{icons_url}"></script>
  <script src="{charts_url}"></script>
  <script src="{tree_expansion_url}"></script>
  <script src="{tree_filter_model_url}"></script>
  <script src="{pending_tally_diagnostics_url}"></script>
  {plugin_asset_config}
  <script src="{app_url}"></script>
  {optional_assets_block}
</body>
</html>"""
    return HTMLResponse(html)


async def view_shell(request: Request) -> Response:
    """Serve the SPA shell only for one safely encoded canonical view path."""

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes) or decode_safe_view_path(raw_path) is None:
        return PlainTextResponse("Invalid view path.", status_code=400)
    return await index(request)


async def commit_shell(request: Request) -> Response:
    """Serve the SPA shell for ``/commit/<rev>[/<file>]``.

    One route per address space (see the Browser URL Grammar): revisions
    are not served-tree paths, so they are addressed here rather than
    through an escape inside ``/view/``.
    """

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes) or decode_safe_commit_route(raw_path) is None:
        return PlainTextResponse("Invalid commit route.", status_code=400)
    return await index(request)


async def root_redirect(_request: Request) -> Response:
    """Send the bare origin to the canonical served-root view.

    ``/view/`` is the only route that selects a path, so the origin must not be a
    second landing URL that renders an empty preview. The redirect is temporary so a
    browser cannot cache it past a change to the route scheme.
    """

    return RedirectResponse(VIEW_ROUTE_PREFIX, status_code=307)


def _query_values(request: Request, key: str) -> list[str]:
    """Repeated query values, tolerating the fake-request shims in tests."""

    params = request.query_params
    if hasattr(params, "getlist"):
        return list(params.getlist(key))
    single = params.get(key, "")
    return [single] if single else []


def tree_filter_from_request(request: Request) -> TreeFilter:
    """Read the nav filter off a request.

    Shares its vocabulary with ``static/filter-state.js``: ``recency`` names a
    window from :data:`RECENT_WINDOW_SECONDS`, ``types`` carries extension or
    filename tokens (repeated or comma-separated), ``min_size`` is a byte
    floor, and ``include_ignored=0`` drops gitignored entries. An absent or
    unrecognized value means "no constraint", so an older client sees more
    rather than a 400.
    """

    return TreeFilter(
        recency_seconds=parse_recency(request.query_params.get("recency", "")),
        types=parse_types(_query_values(request, "types")),
        min_size=parse_size_floor(request.query_params.get("min_size", "")),
        include_ignored=request.query_params.get("include_ignored", "1") not in ("0", "false"),
    )


def _inventory_runtime_for(request: Request) -> InventoryRuntime:
    runtime = getattr(request.app.state, "inventory_runtime", None)
    if not isinstance(runtime, InventoryRuntime):
        raise RuntimeError("the application inventory runtime is not available")
    return runtime


def _index_status_from_state(phase: LifecyclePhase, *, complete: bool, budget: bool) -> str:
    if phase is LifecyclePhase.DISCOVERING:
        return "scanning"
    if phase is LifecyclePhase.FAILED:
        return "failed"
    if phase is LifecyclePhase.STOPPED:
        return "idle"
    if budget:
        return "truncated"
    return "done" if complete else "scanning"


async def _read_tree_from_provider(
    request: Request,
    *,
    subpath: str,
    remaining_depth: int,
    tree_filter: TreeFilter,
) -> JSONResponse:
    runtime = _inventory_runtime_for(request)
    extensions = tuple(token for token in tree_filter.types if token.startswith("."))
    filenames = tuple(token for token in tree_filter.types if not token.startswith("."))
    as_of_ns = time.time_ns()
    companion_queries: list[ReadQuery] = [EntryQuery(query_id="tree-parent", path=subpath)]
    projection_id = "tree-filtered" if tree_filter.active else "tree-directory"
    page_query: TreePageQuery | None = None
    if tree_filter.active:
        page_query = FilteredTreeQuery(
            query_id=projection_id,
            path=subpath,
            max_depth=max(1, remaining_depth),
            max_rows=INVENTORY_TREE_PAGE_ROWS,
            filter=InventoryFilter(
                extensions=extensions,
                filenames=filenames,
                recency_seconds=(
                    float(tree_filter.recency_seconds) if tree_filter.recency_seconds else None
                ),
                minimum_size=tree_filter.min_size or None,
                include_ignored=tree_filter.include_ignored,
                as_of_ns=as_of_ns if tree_filter.recency_seconds else None,
            ),
        )
    elif remaining_depth > 0:
        page_query = DirectoryQuery(
            query_id=projection_id,
            path=subpath,
            max_depth=remaining_depth,
            max_rows=INVENTORY_TREE_PAGE_ROWS,
        )

    navigation_id: str | None = None
    if not subpath and remaining_depth == 0:
        navigation_id = "tree-navigation"
        companion_queries.append(
            NavigationQuery(
                query_id=navigation_id,
                presets=tuple(
                    (str(preset["id"]), tuple(str(value) for value in preset["values"]))
                    for preset in FILTER_TYPE_PRESETS
                ),
                recency_windows=tuple(
                    (window_key, seconds)
                    for window_key, seconds in RECENT_WINDOW_SECONDS.items()
                    if seconds is not None
                ),
                max_rows=NAVIGATION_TALLY_LIMIT,
                as_of_ns=as_of_ns,
            )
        )

    async def read_tree() -> tuple[CoordinatedRead, TreePageAssembly | None]:
        query = page_query
        if query is None:
            return (
                await runtime.coordinator.read(ReadRequest(queries=tuple(companion_queries))),
                None,
            )
        assembly = await assemble_tree_pages(
            runtime.coordinator,
            page_query=query,
            companion_queries=tuple(companion_queries),
        )
        return assembly.first_read, assembly

    read, assembly = await read_tree()
    parent = read.result.projection("tree-parent")
    if not isinstance(parent, EntryProjection):
        raise TypeError("the tree parent query returned the wrong projection")
    if parent.presence is EntryPresence.UNKNOWN:
        if subpath:
            await runtime.coordinator.prioritize(
                PriorityRequest(paths=(subpath,), max_depth=max(1, remaining_depth))
            )
        deadline = asyncio.get_running_loop().time() + _TREE_COLD_START_WAIT_S
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.005)
            read, assembly = await read_tree()
            parent = read.result.projection("tree-parent")
            if not isinstance(parent, EntryProjection):
                raise TypeError("the tree parent query returned the wrong projection")
            if parent.presence is not EntryPresence.UNKNOWN:
                break

    if parent.presence is EntryPresence.ABSENT or (
        parent.presence is EntryPresence.PRESENT
        and (parent.entry is None or parent.entry.type is not EntryType.DIRECTORY)
    ):
        return JSONResponse({"error": "Not found"}, status_code=404)

    tree_entries = ()
    filtered_projection: FilteredTreeProjection | None = None
    if assembly is not None:
        projection = assembly.projection
        if isinstance(projection, FilteredTreeProjection):
            filtered_projection = projection
        tree_entries = projection.entries

    root_dir = _resolved_root_dir()
    tree = (
        build_inventory_tree_from_entries(
            entries=tree_entries,
            parent_rel=subpath,
            max_depth=remaining_depth,
            root_abs=root_dir,
            parent_ignored=bool(parent.entry.gitignored) if parent.entry is not None else False,
        )
        if remaining_depth > 0
        else []
    )
    navigation = None
    if navigation_id is not None:
        candidate = read.result.projection(navigation_id)
        if not isinstance(candidate, NavigationProjection):
            raise TypeError("the navigation query returned the wrong projection")
        navigation = candidate.payload
    state = assembly.final_read.result.state if assembly is not None else read.result.state
    status = _index_status_from_state(
        state.phase,
        complete=state.coverage.complete,
        budget=any(issue.code.value == "resource_budget" for issue in state.issues),
    )
    return JSONResponse(
        {
            "root": str(root_dir),
            "tree": tree,
            "filtered": (
                {
                    "files": filtered_projection.matching_files,
                    "size": filtered_projection.matching_bytes,
                    "entries": filtered_projection.matching_leaves,
                }
                if filtered_projection is not None
                else None
            ),
            "tally_cache_status": status,
            "tally_cache_max_files": runtime.config.max_files,
            "summary": navigation["summary"] if navigation is not None else None,
            "file_type_registry": (
                navigation["file_type_registry"] if navigation is not None else None
            ),
            "extensions": navigation["extensions"] if navigation is not None else None,
            "canonical_extensions": (
                navigation["canonical_extensions"] if navigation is not None else None
            ),
            "type_families": navigation["type_families"] if navigation is not None else None,
            "type_presets": navigation["type_presets"] if navigation is not None else None,
            "recency_tallies": (navigation["recency_tallies"] if navigation is not None else None),
        }
    )


@log_async_calls()
async def api_tree(request: Request) -> JSONResponse:
    subpath = request.query_params.get("path", "")
    depth_str = request.query_params.get("depth", "")
    if _safe_path(subpath) is None:
        return JSONResponse({"error": "Not found"}, status_code=404)

    remaining_depth = _tree_depth_from_query(depth_str)
    tree_filter = tree_filter_from_request(request)

    return await _read_tree_from_provider(
        request,
        subpath=subpath,
        remaining_depth=remaining_depth,
        tree_filter=tree_filter,
    )


@log_async_calls(if_slower_than=0.1)
async def api_rollup(request: Request) -> Response:
    """Bounded treemap rollup for a directory subtree.

    `GET /api/rollup?path=&depth=&top=&ext_top=&filename_top=&remaining_top=`
    clamps parameters to the ROLLUP_* settings bounds. `node` is null while the
    index cannot serve the path yet (cold start); the client renders that as a
    pending treemap and refreshes off `/api/events` activity. Totals always
    cover the full subtree. Depth truncation is represented by `children: null`
    without a rest bucket; node-budget truncation can retain emitted `children`
    alongside a `rest` bucket for their omitted siblings.
    """

    subpath = request.query_params.get("path", "")
    if _safe_path(subpath) is None:
        return JSONResponse({"error": "Not found"}, status_code=404)

    depth = _query_bounded_int(
        request, "depth", ROLLUP_DEFAULT_DEPTH, minimum=0, maximum=ROLLUP_MAX_DEPTH
    )
    top = _query_bounded_int(request, "top", ROLLUP_DEFAULT_TOP, minimum=0, maximum=ROLLUP_MAX_TOP)
    ext_top = _query_bounded_int(
        request, "ext_top", ROLLUP_DEFAULT_EXT_TOP, minimum=0, maximum=ROLLUP_MAX_EXT_TOP
    )
    filename_top = _query_bounded_int(
        request,
        "filename_top",
        ROLLUP_FILE_TYPE_FILENAME_LIMIT,
        minimum=0,
        maximum=ROLLUP_FILE_TYPE_FILENAME_LIMIT,
    )
    remaining_top = _query_bounded_int(
        request,
        "remaining_top",
        ROLLUP_FILE_TYPE_REMAINING_LIMIT,
        minimum=0,
        maximum=ROLLUP_FILE_TYPE_REMAINING_LIMIT,
    )
    try:
        ext_rank = cast(
            RollupRank,
            _query_choice(
                request,
                "ext_rank",
                ROLLUP_DEFAULT_EXT_RANK,
                frozenset({"bytes", "dual"}),
            ),
        )
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)

    runtime = _inventory_runtime_for(request)
    preflight = await runtime.coordinator.read(
        ReadRequest(queries=(EntryQuery(query_id="rollup-parent", path=subpath),))
    )
    parent = preflight.result.projection("rollup-parent")
    if not isinstance(parent, EntryProjection):
        raise TypeError("the rollup parent query returned the wrong projection")
    if parent.presence is EntryPresence.ABSENT or (
        parent.presence is EntryPresence.PRESENT
        and (parent.entry is None or parent.entry.type is not EntryType.DIRECTORY)
    ):
        return JSONResponse({"error": "Not found"}, status_code=404)
    query = RollupQuery(
        query_id="rollup",
        path=subpath,
        max_depth=depth,
        max_nodes=ROLLUP_MAX_NODES,
        top=top,
        extension_top=ext_top,
        remaining_top=remaining_top,
        filename_top=filename_top,
        rank=ext_rank,
    )
    diagnostics = DiagnosticsQuery(query_id="rollup-diagnostics")
    request_shape = f"{subpath}-{depth}.{top}.{ext_top}.{remaining_top}.{filename_top}.{ext_rank}"

    def etag_for(version: HostVersion) -> str:
        engine = version.engine
        return build_scoped_etag(
            f"rollup-{_resolved_root_dir()}-{engine.session}-{engine.sequence}-"
            f"{engine.scope_fingerprint}-{engine.semantic_fingerprint}-{request_shape}"
        )

    async def encode(*, at_version: EngineVersion | None = None) -> tuple[str, bytes]:
        coordinated = await runtime.coordinator.read(
            ReadRequest(
                queries=(query, diagnostics),
                at_version=at_version,
            )
        )
        rollup = coordinated.result.projection("rollup")
        diagnostic = coordinated.result.projection("rollup-diagnostics")
        if not isinstance(rollup, RollupProjection) or not isinstance(
            diagnostic, DiagnosticsProjection
        ):
            raise TypeError("the rollup read returned the wrong projections")
        payload = rollup.payload
        state = coordinated.result.state
        indexed_value = diagnostic.counters.get("files_indexed", 0)
        indexed_files = indexed_value if isinstance(indexed_value, int) else 0
        status = _index_status_from_state(
            state.phase,
            complete=state.coverage.complete,
            budget=any(issue.code.value == "resource_budget" for issue in state.issues),
        )
        body = bytes(
            JSONResponse(
                {
                    "root": str(_resolved_root_dir()),
                    "path": subpath,
                    "node": payload.get("node") if payload is not None else None,
                    "ext_tallies": (payload.get("ext_tallies", []) if payload is not None else []),
                    "file_type_breakdown": (
                        payload.get("file_type_breakdown") if payload is not None else None
                    ),
                    "index_status": status,
                    "indexed_files": indexed_files,
                    "max_files": runtime.config.max_files,
                    "truncated": status == "truncated",
                }
            ).body
        )
        return etag_for(coordinated.version), body

    _cursor, checkpoint_version, _state = await runtime.coordinator.checkpoint()
    etag = etag_for(checkpoint_version)
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=etag_headers(etag))
    cached = _ROLLUP_BODY_CACHE.get(etag)
    if cached is not None:
        return Response(cached, media_type="application/json", headers=etag_headers(etag))

    async def build_pinned() -> bytes:
        actual_etag, body = await encode(at_version=checkpoint_version.engine)
        if actual_etag != etag:
            raise VersionUnavailableError("the host rollup version moved during a pinned read")
        _remember_rollup_body(etag, body)
        return body

    shared = _ROLLUP_IN_FLIGHT.get(etag)
    if shared is None:
        shared = asyncio.ensure_future(build_pinned())
        _ROLLUP_IN_FLIGHT[etag] = shared
        shared.add_done_callback(functools.partial(_release_rollup_flight, etag))
    try:
        body = await asyncio.shield(shared)
    except VersionUnavailableError:
        # Discovery can advance between the checkpoint and the pinned read.
        # Fall back to one unpinned coherent result rather than starving a
        # request behind a continuously moving scan.
        etag, body = await encode()
        _remember_rollup_body(etag, body)
        if matches_if_none_match(request, etag):
            return Response(status_code=304, headers=etag_headers(etag))
    return Response(body, media_type="application/json", headers=etag_headers(etag))


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

    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(
            queries=(
                RecentQuery(
                    query_id="recent",
                    max_rows=limit,
                    as_of_ns=time.time_ns(),
                    prefix=prefix_filter,
                    extensions=ext_filter,
                    within_seconds=RECENT_WINDOW_SECONDS[window],
                    include_ignored=include_ignored,
                ),
            )
        )
    )
    projection = coordinated.result.projection("recent")
    if not isinstance(projection, RecentProjection):
        raise TypeError("the recent read returned the wrong projection")
    result = recent_result_from_projection(
        projection,
        window=cast(WindowKey, window),
        limit=limit,
    )
    state = coordinated.result.state
    tally_cache_status = _index_status_from_state(
        state.phase,
        complete=state.coverage.complete,
        budget=any(issue.code.value == "resource_budget" for issue in state.issues),
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


async def _api_folder_envelope(
    request: Request,
    subpath: str,
    target: Path,
) -> JSONResponse:
    """Directory envelope for `/api/file`: the folder analog of a file response.

    Mirrors the file envelope shape (`type` / `kind` / `views` / `path`)
    so `renderFile` routes folders through the same tab pipeline. The
    `dir` block carries the inventory aggregates (null while the walker
    is still finalizing, matching the tree wire contract) and
    `readme_path` names a direct-child README for Overview panel discovery.
    Served no-store: the envelope is tiny and its aggregates change
    while a scan is running.
    """

    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(queries=(EntryQuery(query_id="folder", path=subpath),))
    )
    projection = coordinated.result.projection("folder")
    if not isinstance(projection, EntryProjection):
        raise TypeError("the folder read returned the wrong projection")
    entry = projection.entry
    discovery = await asyncio.to_thread(
        discover_folder,
        target,
        max_entries=FOLDER_DISCOVERY_MAX_ENTRIES,
    )
    readme_path = (
        f"{subpath}/{discovery.readme_name}"
        if subpath and discovery.readme_name
        else discovery.readme_name
    )
    total_files = entry.total_files if entry is not None else None
    total_size = entry.total_size if entry is not None else None
    unignored_files = entry.unignored_files if entry is not None else None
    unignored_size = entry.unignored_size if entry is not None else None
    newest_ns = entry.newest_mtime_ns if entry is not None else None
    payload: dict[str, Any] = {
        "type": "folder",
        "kind": "folder",
        "path": subpath,
        "name": target.name,
        "views": _views_for_kind("folder"),
        "dir": {
            "total_files": total_files,
            "total_size": total_size,
            "unignored_files": unignored_files,
            "unignored_size": unignored_size,
            "mtime": newest_ns / 1_000_000_000.0 if newest_ns is not None else None,
            "gitignored": bool(entry.gitignored) if entry is not None else False,
            "state": "pending" if total_files is None else "complete",
        },
        "readme_path": readme_path,
        "readme_search_truncated": discovery.readme_search_truncated,
    }
    return JSONResponse(payload, headers={"cache-control": "no-store"})


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
    if target is None or (target.exists() and not target.is_dir() and not target.is_file()):
        # Before declaring the path unavailable: a missing path whose
        # nearest file ancestor is a container kind is that container's
        # virtual child. Classification reads the file, so off the loop.
        container = await asyncio.to_thread(_resolve_container_child, subpath)
        if container is not None:
            return container
        return _file_unavailable_response(subpath, target)
    if target.is_dir():
        return await _api_folder_envelope(request, subpath, target)
    if not target.is_file():
        container = await asyncio.to_thread(_resolve_container_child, subpath)
        if container is not None:
            return container
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

    # The window is part of what the body is, so it is part of the validator,
    # and the tag can only be built once the window is known. Keyed on the file
    # alone, one tag covered every chunk, and the 304 path had to be fenced off
    # to `text_offset == 0` to stay correct — the knowledge lived in a guard at
    # one call site instead of in the tag.
    etag = _etag_for(f"{mtime_hash}-{text_offset}-{text_limit}")
    etag_headers = {"etag": etag, "cache-control": "no-cache"}

    # 304 short-circuit. Repeat clicks on an unchanged file return zero
    # bytes — meaningful over an SSH tunnel and free locally. Every chunk can
    # take this path now, not only the first.
    if matches_if_none_match(request, etag):
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

    if ext in _TEXT_EXTS or await asyncio.to_thread(_prefers_text_body, target):
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
                    "content_max_preview_limit": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
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
            "content_max_preview_limit": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
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

    source_override: str | None = None
    if getattr(request, "method", "GET") == "POST":
        # ``JSON.stringify`` can expand one UTF-8 source byte to a six-byte
        # JSON escape. Bound the transport independently of the decoded
        # source cap so request-body reads cannot grow without limit.
        request_limit = (_TEXT_PREVIEW_MAX_CHUNK_BYTES * 6) + (64 * 1024)
        chunks: list[bytes] = []
        request_size = 0
        async for chunk in request.stream():
            request_size += len(chunk)
            if request_size > request_limit:
                return JSONResponse(
                    {
                        "type": "kpress_render_error",
                        "error": "Render request exceeds safety limits",
                        "max_size": request_limit,
                    },
                    status_code=413,
                )
            chunks.append(chunk)
        try:
            body = _json.loads(b"".join(chunks))
        except (_json.JSONDecodeError, UnicodeDecodeError) as exc:
            return JSONResponse(
                {"type": "kpress_render_error", "error": "Invalid JSON body", "detail": str(exc)},
                status_code=400,
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"type": "kpress_render_error", "error": "Request body must be a JSON object"},
                status_code=400,
            )
        subpath = body.get("path", "")
        view = body.get("view", "document")
        profile_value = body.get("profile")
        profile = profile_value or None
        source_override = body.get("source_text")
        if (
            not all(isinstance(value, str) for value in (subpath, view))
            or not isinstance(source_override, str)
            or (profile is not None and not isinstance(profile, str))
        ):
            return JSONResponse(
                {"type": "kpress_render_error", "error": "Invalid render body fields"},
                status_code=400,
            )
        try:
            source_size = len(source_override.encode())
        except UnicodeEncodeError as exc:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": "Invalid transformed source encoding",
                    "detail": str(exc),
                },
                status_code=400,
            )
        if source_size > _TEXT_PREVIEW_MAX_CHUNK_BYTES:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": "Transformed source exceeds safety limits",
                    "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
                },
                status_code=413,
            )
    else:
        subpath = request.query_params.get("path", "")
        view = request.query_params.get("view", "document")
        profile = request.query_params.get("profile", "") or None
    # A document embedded in Metabrowser's own navigation (the folder
    # Overview's README) asks for no TOC of its own. Closed choice: an
    # unrecognized value is rejected here rather than silently rendering the
    # other layout. KPress validates it again at its request boundary.
    # The SDK carries ``toc`` on the query string for GET and POST alike, so
    # it is read here, after the method branch, rather than from the body.
    include_toc = request.query_params.get("toc", "auto")
    if include_toc not in ("auto", "on", "off"):
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "Invalid toc",
                "detail": f"Invalid toc: {include_toc!r}; expected 'auto', 'on', or 'off'",
                "diagnostics": [],
            },
            status_code=400,
        )

    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    content: str | None = source_override
    try:
        disk_size = artifact.disk_size
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    try:
        if artifact.is_compressed and source_override is None:
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
    if ext not in _TEXT_EXTS and not await asyncio.to_thread(_prefers_text_body, target):
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
            include_toc=include_toc,
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
    if matches_if_none_match(request, asset.etag):
        return Response(status_code=304, headers=headers)
    return Response(
        content=asset.content,
        media_type=asset.media_type,
        headers=headers,
    )


@log_async_calls()
async def api_activity(request: Request) -> JSONResponse:
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
    runtime = _inventory_runtime_for(request)
    active_files = await activity_snapshot(
        runtime.coordinator,
        config=runtime.config,
        root=_resolved_root_dir(),
    )
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


def _container_kinds() -> dict[str, dict[str, str]]:
    """Kinds whose files are folder-like containers in the tree.

    Maps kind id -> {"plugin": name, "children": data-hook route}. Built
    from loaded plugin manifests; the shell and the /api/file container
    resolution below both consume it, so the capability has exactly one
    source of truth.
    """
    out: dict[str, dict[str, str]] = {}
    for plugin in _LOADED_PLUGINS:
        for rule in plugin.manifest.kind:
            if rule.container is not None:
                out[rule.id] = {
                    "plugin": plugin.name,
                    "children": rule.container.children,
                }
    return out


def _container_exts() -> dict[str, dict[str, str]]:
    """Extension -> container info, for the tree's row affordance.

    Only ext-matched kinds project here: a kind matched by content
    sniffing cannot be recognized from a bare tree row. Such kinds still
    resolve as containers server-side; their rows simply lack the
    chevron until selected.
    """
    kinds = _container_kinds()
    out: dict[str, dict[str, str]] = {}
    for plugin in _LOADED_PLUGINS:
        for rule in plugin.manifest.kind:
            if rule.id not in kinds:
                continue
            exts = [rule.match.ext] if rule.match.ext else (rule.match.exts or [])
            for ext in exts:
                if ext:
                    out[ext] = {"kind": rule.id, **kinds[rule.id]}
    return out


def _resolve_container_child(subpath: str) -> JSONResponse | None:
    """Resolve ``<container-file>/<inner>`` to a file envelope.

    Walks the requested path's ancestors from longest to shortest,
    bounded, through the same safe-path gate as every other read. The
    nearest existing ancestor decides: a directory means the request was
    an ordinary missing file; a file whose kind declares the container
    capability owns everything beneath it, and its views render the
    virtual path. Returns None when no container claims the path.
    """
    parts = subpath.split("/")
    if len(parts) < 2:
        return None
    kinds = _container_kinds()
    if not kinds:
        return None
    for cut in range(len(parts) - 1, 0, -1):
        prefix = "/".join(parts[:cut])
        target = _safe_path(prefix)
        if target is None:
            continue
        if target.is_dir():
            # A real directory ancestor: the leaf is genuinely missing.
            return None
        if not target.is_file():
            # Nothing at this depth; keep walking toward the root.
            continue
        artifact = ArtifactPath(target)
        ext = artifact.logical_ext
        kind = _classify_with_plugins(target, ext)
        info = kinds.get(kind)
        if info is None:
            return None
        if len(parts) - cut > MAX_CONTAINER_INNER_DEPTH:
            # The bound is on the inner path, measured from the claiming
            # file; the shared constant keeps this walk and the plugins'
            # own walks agreeing.
            return None
        inner = "/".join(parts[cut:])
        return JSONResponse(
            {
                "type": "text",
                "kind": kind,
                "views": _views_for_kind(kind),
                "path": subpath,
                "container": prefix,
                "container_inner": inner,
                "ext": ext,
                "size": 0,
                "mtime_hash": file_mtime_hash(target),
                "content": "",
                "content_offset": 0,
                "content_bytes": 0,
                "bytes_read": 0,
                "content_truncated": False,
            }
        )
    return None


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


def _build_plugin_asset_config_block() -> str:
    """Configure manifest-owned assets by the kinds that consume them.

    No plugin asset is an eager shell dependency. The private plugin host
    loads one descriptor at most once when ``app.js`` selects any kind in its
    manifest. Extra classic scripts retain manifest order before ``index.js``;
    styles load in parallel and settle before the plugin renderer mounts.
    """
    assets_by_kind: dict[str, list[dict[str, object]]] = {}
    for plugin in _LOADED_PLUGINS:
        prefix = f"/plugin-static/{plugin.name}"
        styles: list[str] = []
        if plugin.static_root.joinpath("styles.css").is_file():
            styles.append(f"{prefix}/styles.css")
        styles.extend(f"{prefix}/{extra}" for extra in plugin.manifest.plugin.extra_styles)
        descriptor: dict[str, object] = {
            "name": plugin.name,
            "module": f"{prefix}/index.js",
            "scripts": [f"{prefix}/{extra}" for extra in plugin.manifest.plugin.extra_scripts],
            "styles": styles,
        }
        kinds = {view.kind for view in plugin.manifest.view}
        kinds.update(kind.id for kind in plugin.manifest.kind)
        for kind in sorted(kinds):
            assets_by_kind.setdefault(kind, []).append(descriptor)
    encoded = _json.dumps(assets_by_kind).replace("<", "\\u003c")
    return f"<script>window.MetabrowserPluginHost.configureAssets({encoded});</script>"


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


async def _debug_inventory(request: Request) -> JSONResponse:
    """Provider identity and cumulative contract work for performance runs."""

    if os.environ.get("METABROWSER_DEBUG", "").strip() not in ("1", "true", "yes"):
        return JSONResponse({"error": "set METABROWSER_DEBUG=1 to enable"}, status_code=404)
    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(queries=(DiagnosticsQuery(query_id="debug-inventory"),))
    )
    diagnostic = coordinated.result.projection("debug-inventory")
    if not isinstance(diagnostic, DiagnosticsProjection):
        raise TypeError("the inventory diagnostic returned the wrong projection")
    counters = diagnostic.counters

    def counter(name: str) -> int:
        value = counters.get(name, 0)
        return value if isinstance(value, int) else 0

    def optional_counter(name: str) -> int | None:
        value = counters.get(name)
        return value if isinstance(value, int) else None

    return JSONResponse(
        {
            "provider": str(counters.get("provider", "")),
            "contract": str(counters.get("contract", "")),
            "phase": coordinated.result.state.phase.value,
            "complete": coordinated.result.state.coverage.complete,
            "version": coordinated.version.engine.sequence,
            "work": {
                "read_requests": counter("read_requests"),
                "entries_visited": counter("work_entries_visited"),
                "directories_visited": counter("work_directories_visited"),
                "rows_returned": counter("work_rows_returned"),
                "binding_bytes_copied": counter("work_bytes_copied"),
                "lock_wait_ns": counter("work_lock_wait_ns"),
                "cpu_time_ns": optional_counter("work_cpu_time_ns"),
                "wall_time_ns": counter("work_wall_time_ns"),
            },
        }
    )


# ── Starlette app ───────────────────────────────────────────────

routes = [
    Route("/", root_redirect),
    Route("/view/{path:path}", view_shell),
    Route("/commit/{rest:path}", commit_shell),
    Route("/api/tree", api_tree),
    Route("/api/rollup", api_rollup),
    Route("/api/recent", api_recent),
    Route("/api/file", api_file),
    Route("/api/kpress/render", api_kpress_render, methods=["GET", "POST"]),
    Route("/api/kpress/export", api_kpress_export, methods=["POST"]),
    Route("/api/activity", api_activity),
    Route("/api/stream", api_stream),
    Route("/_debug/tasks", _debug_tasks),
    Route("/_debug/inventory", _debug_inventory),
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
    return build_lifespan(app=app, root_provider=_inventory_root_provider)


app = Starlette(routes=routes, middleware=middleware, lifespan=_lifespan)
add_inventory_routes(app)


# ── CLI entry point ─────────────────────────────────────────────
