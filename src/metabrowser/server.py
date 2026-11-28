"""Metabrowser's Starlette application: the shell page, the core routes, the
middleware stack, and the application lifespan.

The request flow, safe paths, validators, and the content-trust model are described in
``docs/project/architecture/arch-server-and-content.md``. Work beyond routing lives in
dedicated modules, among them:

* ``file_kinds``  — file kind taxonomy + view registry
* ``paths_safe``  — ROOT_DIR + path-safety helpers
* ``http_caching`` — the only producer of validators
* ``capabilities`` — the trust profile and its CSP and sandbox policies
* ``events_route`` — the inventory routes, the event stream, and the inventory lifespan
* ``tree``        — tree-row helpers and the gitignore checker
* ``jsonl_view``  — single-pass JSONL parser
* ``charts``      — chart-data extractors

The ``__all__`` below forwards internal names that tests import from this module.

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
import contextlib
import datetime as _dt
import json as _json
import logging
import os
import re
import secrets
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, MutableMapping
from contextlib import asynccontextmanager
from dataclasses import replace
from html import escape as html_escape
from pathlib import Path
from stat import S_ISREG
from typing import TYPE_CHECKING, Any, Final, TextIO, cast

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.middleware import Middleware
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
from strif import file_mtime_hash

from metabrowser import (
    __version__,
    delivery,
    event_log,
    event_log_reports,
    kpress_adapter,
    server_timing,
)
from metabrowser.active_tracker import activity_snapshot
from metabrowser.activity import ACTIVITY_POLL_INTERVAL_MS
from metabrowser.asset_stamps import StampedStaticFiles, StampedTree, split_stamp
from metabrowser.build_version import display_version_line
from metabrowser.builtin_plugins.html.detect import sniff_full_page_html
from metabrowser.cache.routes import CACHE_ROUTES
from metabrowser.capabilities import (
    capabilities_for,
    get_capabilities,
    raw_sandbox_csp,
    untrusted_shell_csp,
)
from metabrowser.checkout_revisions import checkout_revisions, lifespan_checkout
from metabrowser.checkout_store import lifespan_checkout_store
from metabrowser.client_disconnect import CLIENT_CLOSED, unless_disconnected
from metabrowser.commit_ids import short_commit
from metabrowser.content_errors import ContentReadError
from metabrowser.content_sniff import (
    MEDIA_SIGNATURE_BYTES,
    SNIFF_PREFIX_BYTES,
    ContentClass,
    classify_prefix,
    media_type_from_prefix,
    sniff_artifact,
    sniff_artifact_prefix,
)
from metabrowser.counterpart import COUNTERPART_ROUTES
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    kpress_refusal_payload,
    shared_worker,
    start_for_pages,
    text_identity,
)
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.embedded_resources import embedded_raw_paths
from metabrowser.encoded_assets import EncodedAssetResponse
from metabrowser.event_log_route import EVENT_LOG_ROUTES
from metabrowser.file_extensions import (
    BROWSER_IMAGE_EXTS,
    BROWSER_TEXT_EXTS,
    syntax_language_for_path,
)
from metabrowser.file_kinds import (
    FILE_KIND_DETECTORS,
    VIEW_REGISTRY,
    FileContext,
    classify_by_ext,
    classify_file_kind,
    register_file_kind_detector,
)
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_legend import build_file_type_legend
from metabrowser.folder_discovery import discover_folder
from metabrowser.frontmatter_yaml import frontmatter_error_fields, shown_frontmatter_error
from metabrowser.fs_paths import is_visible_segment
from metabrowser.git.history import lifespan_history_sessions
from metabrowser.git.routes import GIT_ROUTES, prepare_initial_history
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactPath,
)
from metabrowser.http_caching import (
    BUILD_TAG,
    address_version,
    build_scoped_etag,
    editable_install,
    etag_headers,
    immutable_headers,
    matches_if_none_match,
    stamped_asset_cache_control,
    store_tag,
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
    GroupedTreeQuery,
    InventoryEntry,
    InventoryFilter,
    LifecyclePhase,
    NavigationProjection,
    NavigationQuery,
    PriorityRequest,
    QueryWorkLimitError,
    ReadQuery,
    ReadRequest,
    RecentProjection,
    RecentQuery,
    RollupProjection,
    RollupQuery,
    VersionUnavailableError,
    canonical_inventory_path,
    native_inventory_path,
    parse_inventory_path,
)
from metabrowser.inventory_engine.coordinator import CoordinatedRead, HostVersion
from metabrowser.inventory_engine.runtime import InventoryRuntime
from metabrowser.inventory_engine.tree_page_assembly import (
    GroupedTreeAssembly,
    TreePageAssembly,
    TreePageQuery,
    assemble_grouped_tree,
    assemble_tree_pages,
)
from metabrowser.inventory_rollup import RollupEncoding, RollupIgnored, RollupOptions, RollupRank
from metabrowser.jsonl_view import JsonlParseLimitError, _parse_jsonl_file
from metabrowser.keymap import check_view_keys, live_view_keys
from metabrowser.kpress_fences import read_fence_origin
from metabrowser.mirror_refresh import lifespan_refresh, mirror_session

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
from metabrowser.repository_context import (
    CheckedOutHead,
    checked_out_head,
    discover_repository_context,
    is_checkout_root,
)
from metabrowser.root_identity import (
    IDENTITY_ROUTES,
    abbreviate_origin,
    canonical_repository_url,
    identity_kind_tip,
    root_identity,
)
from metabrowser.server_utils import ipv6_literal, wildcard_host
from metabrowser.settings import (
    DOC_MAX_CHARS_DEFAULT,
    FOLDER_DISCOVERY_MAX_ENTRIES,
    INVENTORY_TREE_PAGE_ROWS,
    RECENT_WINDOW_SECONDS,
    ROLLUP_BODY_CACHE_BYTES,
    ROLLUP_BODY_CACHE_ENTRIES,
    ROLLUP_DEFAULT_DEPTH,
    ROLLUP_DEFAULT_EXT_RANK,
    ROLLUP_DEFAULT_EXT_TOP,
    ROLLUP_DEFAULT_NODES,
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
    VALID_LOG_LEVELS,
    blocks_remote_images,
    client_settings_dict,
)
from metabrowser.shell_glyphs import REFRESH_SVG
from metabrowser.source import (
    ContentRef,
    SubjectNotOpenError,
    UnsupportedSourceCapabilityError,
    as_git_revision_subject,
    get_source_session,
    lifespan_subject,
    read_content_window,
    require_filesystem_hooks,
    require_filter_capabilities,
    require_source_capability,
    resolve_session_identity,
    session_filesystem_root,
    unsupported_source_payload,
)
from metabrowser.source_kind_marks import source_kind_svg
from metabrowser.source_routes import (
    SOURCE_ROUTES,
    SourcePinGuard,
    SourceStatus,
    crossed_view_href,
    source_status,
)
from metabrowser.sse import api_stream
from metabrowser.table_source import TableSourceDeclaration, install_table_sources
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
)
from metabrowser.tree_groups import (
    UNDATED_GROUP_ID,
    GroupBy,
    age_band,
    group_row,
    groups_for,
    groups_payload,
    inventory_group_filter,
    parse_group,
    parse_group_by,
)
from metabrowser.view_routes import (
    VIEW_ROUTE_PREFIX,
    decode_safe_commit_route,
    decode_safe_pull_route,
    decode_safe_stack_route,
    decode_safe_view_path,
)

if TYPE_CHECKING:
    from kpress.models import KPressAsset
    from starlette.requests import Request

    from metabrowser.git.tree_source import GitRevisionSubject


# Direct ASGI imports bypass the CLI bootstrap. Load the working tree's
# allowlisted configuration before logging flags are read. The tree is not
# trusted -- see ``metabrowser.dotenv`` for what a file may contribute.
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

# How many folders of a landing's path the shell also inlines, expanded, so a deep landing's
# first tree paint already shows its row: the reveal that opened them after first paint
# moved the tree with no input (layout shift 0.050 to 0.057 on a file three folders down,
# Chrome 152). A deeper landing inlines the root alone and the page reveals its path, as
# before. The depth bounds the queries one shell read makes; what a landing costs the
# reader is the rows, which _INLINE_LANDING_ROWS bounds.
_INLINE_LANDING_DEPTH = 8

# How many rows a landing's folders may add to the shell in all, past the root's own. Each
# folder is inlined with its whole listing, and a path whose folders do not fit inlines the
# root alone, as before.
#
# Measured on landings one to eight folders down, 152 entries a folder, against the root-only
# shell (headless Chrome 152, median of 5 loads, two rounds, load average 6 to 13): each
# folder added 21 KB of shell (2 KB gzipped) and about 1 ms on the server, and the 1,215
# rows of eight such folders added 84 to 90 ms to DOMContentLoaded and 73 to 75 ms to the
# first tree row, about 11 and 9 ms a folder. Two folders, 304 rows, cost 15 to 16 ms of
# first tree row, one frame at 60 Hz; the reveal they replace moved the tree by 0.10 to
# 0.46 with no input. So the budget is about one frame of first tree row.
_INLINE_LANDING_ROWS = 300

# Encoded rollup bodies keyed by their ETag. The validator alone only helps a
# client that already holds the answer; a second tab opening the same folder,
# or a reconnect, arrives without one and would otherwise re-aggregate and
# re-serialize a body the server just produced. Bounded by
# ``ROLLUP_BODY_CACHE_ENTRIES`` and ``ROLLUP_BODY_CACHE_BYTES``: entries from a
# superseded index revision can never be requested again, so they age out by
# insertion order.
_ROLLUP_BODY_CACHE: dict[str, bytes] = {}


def _remember_rollup_body(etag: str, body: bytes | memoryview[int]) -> None:
    """Retain one encoded rollup body for reuse by an identical request.

    The oldest bodies go first until both bounds hold; a body larger than the byte
    bound is not retained, since it would evict every other and then itself.
    """

    retained = bytes(body)
    if len(retained) > ROLLUP_BODY_CACHE_BYTES:
        return
    _ROLLUP_BODY_CACHE[etag] = retained
    while len(_ROLLUP_BODY_CACHE) > ROLLUP_BODY_CACHE_ENTRIES or (
        sum(len(cached) for cached in _ROLLUP_BODY_CACHE.values()) > ROLLUP_BODY_CACHE_BYTES
    ):
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
    # ``getattr(logging, name)`` would accept any module attribute, so a
    # name like ``BASIC_FORMAT`` returned a format string that ``setLevel``
    # then rejected. Check membership first: an unknown value is INFO.
    level_name = os.environ.get("METABROWSER_LOG_LEVEL", "INFO").upper()
    if level_name not in VALID_LOG_LEVELS:
        level_name = "INFO"
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
# CSS / JS bundles are served as plain static files, not inlined into the
# index HTML. The shell names each with a ``?v=`` stamp of the file
# (``_static_asset_url``), and the mount answers that address immutable while
# the stamp is current (``asset_stamps.StampedStaticFiles``), so a reload asks
# for nothing it already holds, and an edit shows up on a normal refresh
# without restarting the server because the next shell names a new stamp.

STATIC_DIR: Path = Path(__file__).parent / "static"
# The stamp `?v=` names: each static file's own bytes (asset_stamps.StampedStaticFiles).
_STATIC_TREE = StampedTree(STATIC_DIR, live=editable_install("metabrowser"))
# Mermaid's chunks, which its build names `<name>-<hash>.mjs` by a hash of each one's
# content and its entry imports by relative specifiers that drop the entry's `?v=`. The
# name names the bytes, so a chunk the stamp holds is answered immutable at its plain
# address. Before this, each chunk a page imported, of 105 (5,404,632 bytes), was
# `no-cache` and asked for again on every load with a conditional request answered 304
# (measured 2026-11-19). Its bytes change only with its name: `devtools/vendor_assets.py
# --check` refuses vendored bytes its manifest does not pin.
_SELF_NAMED_STATIC = ("vendor/mermaid/chunks/",)
# The reading-width state machine is first-paint configuration and only 1 KiB
# compressed. Embed its exact tested source once instead of spending a startup
# request on it; keeping the file authoritative preserves the browserless
# golden without copying a second implementation into this template.
_DOCUMENT_WIDTH_SCRIPT = STATIC_DIR.joinpath("document-width.js").read_text(encoding="utf-8")
if "</script" in _DOCUMENT_WIDTH_SCRIPT.lower():
    raise RuntimeError("document-width.js cannot be safely embedded in the index shell")
# A pin's page names its commit on every data request, and must before any script
# fetches, so the wrapper is inline on a pin and absent from a folder's page.
_SOURCE_PIN_GUARD_SCRIPT = STATIC_DIR.joinpath("source-pin-guard.js").read_text(encoding="utf-8")
if "</script" in _SOURCE_PIN_GUARD_SCRIPT.lower():
    raise RuntimeError("source-pin-guard.js cannot be safely embedded in the index shell")

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


# Files outside ``BROWSER_TEXT_EXTS`` are decided by looking at their content —
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


def _sniff_text_body(target: Path) -> tuple[bool, bytes | None]:
    """:func:`_prefers_text_body`, with the bytes on disk the sniff read.

    The bytes are the file's own leading bytes, which a ``magic`` kind rule is matched
    against when the file falls to the ``binary`` fallback (:func:`_magic_kind`); they
    are None for a compressed artifact, whose sniff read decompressed bytes.
    """
    content_class, prefix = sniff_artifact_prefix(target)
    return content_class is not ContentClass.BINARY, prefix


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
    # "max" asks for the bound itself, so a client need not know its value.
    if request.query_params.get(name) == "max":
        return maximum
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

    from metabrowser.charts import clear_charts_cache

    clear_charts_cache()


# Concrete bind hosts registered by the CLI (``--host``). Wildcard binds
# (``server_utils.wildcard_host``) never land here: they accept connections on
# every interface and are not meaningful Host-header names. Loopback names are
# always permitted by the middleware.
_EXTRA_ALLOWED_HOSTS: set[str] = set()


def _register_allowed_host(bind_host: str) -> None:
    """Permit the CLI's concrete ``--host`` value at the HTTP boundary.

    A wildcard bind is a no-op: it names interfaces, not a hostname a
    browser would send, and allowing everything would defeat the
    DNS-rebinding check. Operators reaching a wildcard bind through a
    concrete name allow it explicitly with ``METABROWSER_ALLOWED_HOSTS``.

    An IPv6 literal is registered in brackets, as a ``Host`` header carries
    it, in the spelling given (the printed URL's) and in the compressed one
    a browser rewrites it to.
    """
    raw = bind_host.strip().lower()
    if wildcard_host(raw):
        return
    address = ipv6_literal(raw)
    if address is not None:
        _EXTRA_ALLOWED_HOSTS.update({f"[{raw.strip('[]')}]", f"[{address.compressed}]"})
        return
    hostname = _HostValidationMiddleware._hostname(raw)
    if hostname and not wildcard_host(hostname):
        _EXTRA_ALLOWED_HOSTS.add(hostname)


_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _is_json_content_type(content_type: str) -> bool:
    media = content_type.split(";", 1)[0].strip().lower()
    return media == "application/json"


def _origin_matches_request(origin: str, scheme: str, host_header: str) -> bool:
    expected = f"{scheme}://{host_header.strip()}"
    return origin.strip().lower() == expected.lower()


def _route_path(scope: Mapping[str, Any]) -> str:
    """The scope's path with any ASGI ``root_path`` prefix removed.

    Mirrors Starlette's own ``get_route_path``, which is what the router
    matches on. A guard that derived the path differently could be
    weaker than the router: stripping a prefix that is not a path-segment
    boundary turned ``root_path="/"`` with ``/api/x`` into ``api/x``, and
    the ``/api`` check then skipped a route the router still served.
    Only a prefix that ends at a segment boundary is removed.

    The two security middlewares and the slow-request log all call this,
    so a prefix mount cannot make one of them name a different route than
    another.
    """

    path = str(scope.get("path") or "")
    root_path = str(scope.get("root_path") or "")
    if not root_path or not path.startswith(root_path):
        return path
    rest = path[len(root_path) :]
    if rest == "" or rest.startswith("/"):
        return rest
    return path


# Fetch-metadata values that are not a request from another document.
# ``same-origin`` is the application's own page. ``none`` is a
# user-initiated navigation — a typed URL, a bookmark, a browser restore
# — which has no initiator document and so no attacker-controlled origin;
# a hostile page cannot make a browser send it, because anything a
# document initiates is labelled ``same-origin``, ``same-site``, or
# ``cross-site``.
_TRUSTED_FETCH_SITES = frozenset({"same-origin", "none"})


def _has_same_origin_proof(
    *,
    scheme: str,
    host_header: str,
    origin: str,
    sec_fetch_site: str,
) -> bool:
    """Return whether an ``/api`` request proved it came from this app.

    ``Origin: null`` is always refused: that is what an opaque-origin
    document sends. ``Sec-Fetch-Site: same-origin`` or ``none``, or a
    matching ``Origin``, is accepted. A request with neither header
    (curl, ``metab --api``) is accepted. ``/raw`` is not behind this
    check.
    """

    if origin.lower() == "null":
        return False
    if sec_fetch_site.lower() in _TRUSTED_FETCH_SITES:
        return True
    if origin and _origin_matches_request(origin, scheme, host_header):
        return True
    return not origin and not sec_fetch_site


class _HostValidationMiddleware:
    """Reject rebound Host values and unproven ``/api`` callers.

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

    ``/api/*`` additionally requires same-origin proof so sandboxed
    content and third-party pages cannot invoke application routes,
    including fire-and-forget writes. The Host allowlist does not stop
    those: they send a genuine Host. State-changing methods also require
    ``Content-Type: application/json`` because Starlette parses JSON
    bodies without looking at that header.
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
        origin = ""
        sec_fetch_site = ""
        content_type = ""
        for name, value in scope.get("headers") or []:
            if name == b"host":
                host_header = value.decode("latin-1")
            elif name == b"origin":
                origin = value.decode("latin-1")
            elif name == b"sec-fetch-site":
                sec_fetch_site = value.decode("latin-1")
            elif name == b"content-type":
                content_type = value.decode("latin-1")
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
            # One statement and one remedy (docs/design-system-messages.md). Why the
            # guard exists, DNS rebinding, is this class's docstring. The remedy is the
            # setting, not `--host NAME`, which also admits a name: binding to it fails
            # for a name a tunnel or proxy reaches this machine by.
            response = PlainTextResponse(
                f"{hostname!r} is not a permitted name for this local server. "
                "If it is a trusted way to reach this machine, restart with it in "
                "METABROWSER_ALLOWED_HOSTS.\n",
                status_code=421,
            )
            await response(scope, receive, send)
            return
        path = _route_path(scope)
        if path == "/api" or path.startswith("/api/"):
            scheme = str(scope.get("scheme") or "http")
            if not _has_same_origin_proof(
                scheme=scheme,
                host_header=host_header,
                origin=origin,
                sec_fetch_site=sec_fetch_site,
            ):
                response = PlainTextResponse(
                    "This /api request did not prove it came from this application's "
                    "own pages. Browsers send Sec-Fetch-Site: same-origin, "
                    "Sec-Fetch-Site: none for a typed URL or bookmark, or a "
                    "matching Origin; Origin: null is refused because that is what "
                    "an opaque-origin document sends. curl and metab --api send "
                    "neither header and still work.\n",
                    status_code=403,
                )
                await response(scope, receive, send)
                return
            method = str(scope.get("method") or "GET").upper()
            if method in _STATE_CHANGING_METHODS and not _is_json_content_type(content_type):
                response = PlainTextResponse(
                    "State-changing /api routes require Content-Type: application/json "
                    "so a cross-site form POST cannot reach a write path.\n",
                    status_code=415,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# Fetch destinations that run or apply what they load. Under the untrusted profile /raw
# refuses them, so no page -- the application's included -- takes a browsed file as code.
_CODE_DESTINATIONS: Final = frozenset(
    {
        b"script",
        b"style",
        b"worker",
        b"sharedworker",
        b"serviceworker",
        b"audioworklet",
        b"paintworklet",
    }
)
# Media types a browser runs or applies as code. Under the untrusted profile /raw sends
# them as text/plain, which with nosniff no browser takes as a script or stylesheet, for a
# browser that does not send Sec-Fetch-Dest.
_SCRIPT_CAPABLE: Final = re.compile(
    r"^\s*(?:text|application)/(?:x-)?(?:javascript|ecmascript|jscript|livescript|css)\b",
    re.IGNORECASE,
)
# Raster images: a browser decodes them and runs nothing, whether they are loaded as an
# image or opened as a document, so their execution policy is the same under both trust
# profiles. /raw sends them the sandbox without `allow-scripts` under either profile,
# rewrites no profile's type for them, and so answers them with the same execution
# headers whichever profile serves. Only they may be kept for a year at a versioned address
# (raw_file): an answer kept under one profile is replayed, unasked, under another on the
# same origin, and an SVG or HTML document's headers differ by profile. Matched by the type
# /raw sends, which `nosniff` makes the one a browser takes, not by the file's bytes.
_PROFILE_INDEPENDENT_MEDIA_TYPES: Final = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}
)


def _profile_independent(content_type: str) -> bool:
    """Whether a /raw answer of *content_type* has the same execution policy in every profile."""

    return content_type.split(";", 1)[0].strip().lower() in _PROFILE_INDEPENDENT_MEDIA_TYPES


def _request_header(scope: Mapping[str, Any], name: bytes) -> bytes:
    """One request header's value, lowercased, or empty."""

    for key, value in scope.get("headers") or ():
        if key.lower() == name:
            return bytes(value).strip().lower()
    return b""


class _RawTrustHeaderMiddleware:
    """Sandbox every ``/raw`` response, whichever layer produced it.

    The content-trust model (``docs/project/architecture/arch-server-and-content.md``)
    promises the opaque-origin sandbox on *every* raw
    response, and a wrapper applied per ``return`` inside ``raw_file``
    cannot keep that promise. It misses the responses the handler never
    builds — Starlette's 400 and 416 for a malformed or unsatisfiable
    ``Range``, the router's 405, the error handler's 500 — and it misses
    any return path a later change adds, including a handler that
    delegates to another source of bytes. Setting the headers on the
    outgoing ``http.response.start`` message makes the guarantee
    structural instead: a response on this path is sandboxed because of
    where it is served, not because someone remembered to wrap it.

    ``allow-scripts`` is present only while ``active_content`` is on,
    read per response so the capability block stays authoritative.
    ``frame-ancestors`` is omitted: inside a sandboxed page the ancestor
    origin is opaque and would never match ``'self'``, which would break
    nested iframes and framesets.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    @staticmethod
    def _is_raw_scope(scope: dict[str, Any]) -> bool:
        """True for ``/raw`` and ``/raw/...``, false for ``/rawfoo``.

        ``_route_path`` strips any ``root_path`` first, so the check
        still names the route when the app is mounted under a prefix.
        """

        path = _route_path(scope)
        return path == "/raw" or path.startswith("/raw/")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not self._is_raw_scope(scope):
            await self.app(scope, receive, send)
            return

        started = False
        # The profile of the subject served as the request arrives: a pin is never
        # trusted. The handler resolves the subject again and marks the scope when it
        # answers a pin (`_RAW_PINNED_SCOPE`), so a pin attached in between still gets a
        # pin's headers; a pin replaced in between keeps the stricter ones it began with.
        process_active = capabilities_for(pinned_revision=_pin_is_served()).active_content

        # ``MutableMapping``, not ``dict``: this wrapper is handed to
        # ``Response.__call__`` below, whose ``Send`` alias is written
        # against the ASGI message protocol rather than a concrete dict.
        async def send_sandboxed(message: MutableMapping[str, Any]) -> None:
            nonlocal started
            if message.get("type") == "http.response.start":
                started = True
                active_content = process_active and not scope.get(_RAW_PINNED_SCOPE, False)
                headers = MutableHeaders(scope=message)
                # A raster image runs nothing, so it never needs `allow-scripts`, and without it
                # its policy is the same in both profiles (_PROFILE_INDEPENDENT_MEDIA_TYPES).
                # raw_file decides that by the type it chose and sends the scriptless sandbox
                # itself, since a 304 has no Content-Type and a multipart range answer
                # another; it is kept, as a stricter policy is. The outgoing type covers the
                # rest, a decompressed stream and a pin's blob among them.
                scriptless = raw_sandbox_csp(active_content=False)
                headers["Content-Security-Policy"] = raw_sandbox_csp(
                    active_content=active_content
                    and headers.get("content-security-policy") != scriptless
                    and not _profile_independent(headers.get("content-type", ""))
                )
                # Never kept as fresh, whichever branch answered: its headers are this
                # profile's (arch-server-and-content.md, "Raw Responses"). raw_file sets
                # it with its tag; this covers the rest -- the decompressed stream, a 404
                # or a 403 -- by construction.
                if "cache-control" not in headers:
                    headers["Cache-Control"] = "no-cache"
                headers["X-Content-Type-Options"] = "nosniff"
                if not active_content and _SCRIPT_CAPABLE.match(headers.get("content-type", "")):
                    # A browsed script or stylesheet is text to a reader, never code.
                    headers["Content-Type"] = "text/plain; charset=utf-8"
            await send(message)

        if not process_active and _request_header(scope, b"sec-fetch-dest") in _CODE_DESTINATIONS:
            # Under the untrusted profile a browsed file is never a script, stylesheet,
            # or worker of any page, the application's included: its own static paths
            # are the only code it runs (capabilities.untrusted_shell_csp).
            await PlainTextResponse("A browsed file is not loaded as code here.", status_code=403)(
                scope, receive, send_sandboxed
            )
            return

        try:
            await self.app(scope, receive, send_sandboxed)
        except Exception:
            # Starlette builds ``ServerErrorMiddleware`` outside every
            # application middleware, so the 500 it writes for an
            # unhandled exception would leave this path unsandboxed.
            # Send the same body from inside the sandbox and re-raise:
            # that middleware records the cause and skips its own send
            # because the response has already started, and the test
            # client can still surface the exception.
            if not started:
                await PlainTextResponse("Internal Server Error", status_code=500)(
                    scope, receive, send_sandboxed
                )
            raise


# Set on a ``/raw`` request's scope by the handler when it answers a pinned revision.
_RAW_PINNED_SCOPE: Final = "metabrowser.raw_pinned_revision"


def _pin_is_served() -> bool:
    """Whether a pinned revision is the served subject now, or is about to be.

    A subject configured and not yet open is a pin's, so it counts: nothing is trusted on
    its behalf.
    """

    try:
        return as_git_revision_subject(get_source_session().subject) is not None
    except SubjectNotOpenError:
        return True


def _end_request_span(
    span: event_log.Span,
    *,
    status: int | None,
    body_bytes: int,
    start_ms: float | None,
    query: str,
    record: server_timing.Record,
    failure: BaseException | None,
) -> None:
    """End a request's event-log span with what the request log line says.

    A status of 500 or more is ``failed``; a request cancelled, as when the client left,
    is ``cancelled`` whether or not its answer had begun, and one the application raised
    on is ``failed``.
    """

    attrs: dict[str, Any] = {"status": status, "bytes": body_bytes}
    if query:
        attrs["query"] = event_log.redact(query, limit=event_log.MAX_TEXT_CHARS)
    if start_ms is not None:
        attrs["start_ms"] = round(start_ms, 1)
    phases = record.totals()
    if phases:
        attrs["phases"] = {name: round(ms, 1) for name, ms in phases}
    processes = record.git_processes()
    if processes:
        attrs["git_processes"] = processes
    if failure is not None:
        cancelled = isinstance(failure, asyncio.CancelledError)
        if not cancelled:
            attrs["error"] = event_log.describe_error(failure)
        span.end("cancelled" if cancelled else "failed", **attrs)
    else:
        span.end("failed" if status is not None and status >= 500 else "ok", **attrs)


# Long-lived endpoints never flagged as slow. The SSE transport intentionally holds the
# connection open for as long as the tab does, far past ``_SLOW_SERVER_REQUEST_MS``, so
# without this skip every connected browser tab would emit a slow-request warning. These
# paths also get no ``Server-Timing`` header, and a page never reports them as slow or
# pending (``event_log_reports.browser_settings``). ``/api/tail`` has no route.
LONG_LIVED_PATHS: Final[tuple[str, ...]] = ("/api/events", "/api/tail", "/api/stream")


def _request_client(scope: dict[str, Any]) -> str | None:
    """The page's ID for this request (``event_log.CLIENT_HEADER``), when it sent one."""

    wanted = event_log.CLIENT_HEADER.encode("latin-1")
    for name, value in scope.get("headers") or []:
        if name == wanted:
            return event_log.client_id(value)
    return None


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

    _LONG_LIVED_PATHS: tuple[str, ...] = LONG_LIVED_PATHS

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        # Skip the timer entirely for long-lived endpoints.
        path = _route_path(scope)
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
        start_ms: float | None = None
        record, token = server_timing.begin()
        # The event log's record of the request (metabrowser.event_log): current while
        # the application runs, so a job the request starts names it as its parent, and
        # carries the page's ID for it, which a page's reports name too.
        method = scope.get("method", "")
        # A request for something inside the events directory is not recorded, when this
        # server's folder holds the directory (event_log.quiet_request says why).
        request_span = (
            event_log.begin("request", f"{method} {path}", client=_request_client(scope))
            if event_log.enabled()
            and not event_log.quiet_request(
                path, (scope.get("query_string") or b"").decode("latin-1")
            )
            else event_log.NULL_SPAN
        )

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal body_bytes, start_ms, status
            if message.get("type") == "http.response.start":
                status = message.get("status")
                # Inject Server-Timing so the browser's Network tab +
                # perf.js can read the server-self-reported duration
                # without an out-of-band channel. Format per W3C
                # Server-Timing: ``<name>;dur=<ms>``. ``srv`` is the
                # wall-clock from middleware entry to response-start;
                # client subtracts to get the transit + queue portion.
                # Beside it go the named phases finished by then
                # (metabrowser.server_timing): for a JSON answer that is
                # its serialization and compression too, which happen
                # before the headers; a streamed body's later reads and
                # compression reach only the request log below. Re-encode
                # the headers list to preserve any pre-existing
                # Server-Timing value (no plugin sets one today).
                start_ms = (time.perf_counter() - started) * 1000
                timing = server_timing.header_value(record, start_ms)
                hdrs = list(message.get("headers") or [])
                hdrs.append((b"server-timing", timing.encode("latin-1")))
                message = {**message, "headers": hdrs}
            elif message.get("type") == "http.response.body":
                body = message.get("body") or b""
                body_bytes += len(body)
            await send(message)

        failure: BaseException | None = None
        try:
            with event_log.within(request_span):
                await self.app(scope, receive, send_wrapper)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            server_timing.end(record, token)
            # The time to the end of the body, which no header can carry.
            duration_ms = (time.perf_counter() - started) * 1000
            first_byte = "-" if start_ms is None else f"{start_ms:.0f}"
            phases = server_timing.log_value(record)
            query = (scope.get("query_string") or b"").decode("latin-1")
            full_path = f"{path}?{query}" if query else path
            if request_span is not event_log.NULL_SPAN:
                _end_request_span(
                    request_span,
                    status=status,
                    body_bytes=body_bytes,
                    start_ms=start_ms,
                    query=query,
                    record=record,
                    failure=failure,
                )
            if self.verbose:
                # Verbose mode: every request, with arrival + completion
                # epochs so correlation against browser-side perf.js
                # records is mechanical (subtract for transit time).
                # `end_ms` is the time to the end of the body again, to the
                # tenth of a millisecond the phases have, for a reader that
                # sums many small answers (server-time.mjs); the rounded
                # figure in parentheses stays where older readers find it.
                # Taken when the application returns, it includes a response's
                # background tasks and the waits for the client to drain the body.
                LOG.info(
                    "metabrowser request t=%.3f -> %.3f (%.0f ms) method=%s path=%s status=%s "
                    "bytes=%s start_ms=%s phases=%s end_ms=%.1f",
                    arrived,
                    arrived + duration_ms / 1000,
                    duration_ms,
                    scope.get("method", ""),
                    full_path,
                    status,
                    body_bytes,
                    first_byte,
                    phases,
                    duration_ms,
                )
            elif self.threshold_ms and duration_ms >= self.threshold_ms:
                # Include the arrival epoch even in non-verbose mode so
                # the line cross-references against perf.js slow_fetch
                # records (which carry started_at as a UTC epoch ms).
                LOG.warning(
                    "metabrowser slow server request t=%.3f %.0f ms method=%s path=%s status=%s "
                    "bytes=%s start_ms=%s phases=%s",
                    arrived,
                    duration_ms,
                    scope.get("method", ""),
                    full_path,
                    status,
                    body_bytes,
                    first_byte,
                    phases,
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


def _pin_label_html(status: SourceStatus) -> str:
    """The navigation heading for a pinned revision.

    A pin with a name is headed by the name alone, where a folder's name stands and with
    the same `.path-base` emphasis: a served mirror by the repository's name, as a
    checkout of it would be called, and a revision a folder's server shows of its own
    checkout by the folder's name. The ref selector beneath the tabs names the ref,
    so the heading can stay focused on the name (mb-qq4e).

    A pin with no mirror has no origin to take a name from, and no ref selector, so its
    heading is the only place that names it. Its ref stands as the name with the short
    commit after it, muted, in the commit-ID face (`.git-commit-sha`) a commit has
    wherever it appears, or the short commit alone when no ref is known; the full commit
    is its served root.
    """

    def base(text: str) -> str:
        return f'<span class="path"><span class="path-base">{text}</span></span>'

    name = status["name"]
    if name is not None:
        return base(html_escape(name))
    short = html_escape(short_commit(status["pin"] or ""))
    ref_name = status["ref_name"]
    if ref_name is None:
        return base(f'<span class="git-commit-sha">{short}</span>')
    return (
        base(html_escape(ref_name)) + f'<span class="header-revision git-commit-sha">{short}</span>'
    )


def _mirror_tip(status: SourceStatus) -> str | None:
    """Explain how the root's files are read, beside the separately displayed path."""
    if status["location"] is None:
        return None
    if status["origin"] is None:
        return "Files come from a committed revision of this checkout."
    if status["borrows"]:
        return "Bare Git mirror that shares objects with a local checkout."
    return "Bare Git mirror with no checked-out files."


def _mirror_heading_attrs(status: SourceStatus) -> str:
    """The navigation heading's attributes that say where a served mirror is kept.

    The root menu and the file header read `data-mirror-location`. The heading preserves
    the same description in `data-mirror-tip` for the browserless shell fixture.
    The location attribute and the status envelope are the only places a response names
    a path in the cache.
    """

    tip = _mirror_tip(status)
    if tip is None:
        return ""
    location = html_escape(status["location"] or "", quote=True)
    # What the note after the main heading's address says before the location. A mirror
    # is kept there, which is the words static/mirror-heading.js has; a checkout's
    # revision is of the folder there, so its page names the words.
    note = "" if status["origin"] is not None else ' data-mirror-note="committed revision of"'
    return (
        f' data-mirror-location="{location}"{note} data-mirror-tip="{html_escape(tip, quote=True)}"'
    )


@functools.cache
def _mirror_heading_script() -> str:
    """`static/mirror-heading.js`, as a served mirror's shell carries it inline.

    Mirrors and pinned checkouts can show a location note in their view header.
    """

    script = STATIC_DIR.joinpath("mirror-heading.js").read_text(encoding="utf-8")
    if "</script" in script.lower():
        raise RuntimeError("mirror-heading.js cannot be safely embedded in the index shell")
    return script


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
    return _paths_safe.tilde_path(resolved, home)


def _static_asset_url(rel_path: str) -> str:
    """A local static URL stamped with the digest of the file's bytes.

    The digest is from the stamp :func:`_shell_asset_prefixes` took for this page, or, in a
    process that has not rendered one, a stamp taken now. A file the stamp does not name
    gets the unstamped address, which is revalidated.
    """

    stamp = _STATIC_TREE.latest() or _STATIC_TREE.stamp()
    digest = stamp.digests.get(rel_path) if stamp is not None else None
    return f"/static/{rel_path}" if digest is None else f"/static/{rel_path}?v={digest}"


# Interface-font sets offered by the settings dropdown. The first entry is the
# default. Each set's actual font stacks live in styles.css as a
# `html[data-app-font="<value>"]` block (the default uses the :root base). To add
# a set, append one entry here and one CSS block there, which sets both --font-sans and
# the sans's x-height, --font-sans-ex-height (tests/test_short_commit.py checks each) —
# the dropdown options and the pre-paint bootstrap both derive from this single list,
# so they stay in sync.
_FONT_SETS: tuple[dict[str, str], ...] = (
    {"value": "clean", "label": "Clean Fonts"},
    {"value": "system", "label": "System Fonts"},
)
_DEFAULT_FONT_SET = _FONT_SETS[0]["value"]

# The theme, reading font, and font set a page paints with on its first frame, from the
# preference cookies (see the index shell below, which explains the keys). It reads the
# reading width from `window.MetabrowserDocumentWidth`, so a page embeds
# :data:`_DOCUMENT_WIDTH_SCRIPT` before it, and that script reads its default from
# `window.METABROWSER_SETTINGS`, which the shell writes first.
_THEME_BOOTSTRAP_SCRIPT = """
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
    // Reading width is also pre-paint. The exact browserless-tested state
    // machine is embedded above this bootstrap, so cookie normalization has
    // one implementation rather than a second copy of its bounds here.
    var width = window.MetabrowserDocumentWidth;
    de.style.setProperty("--doc-max-chars", String(width.readStored(cookie)));
  })();
  """.replace("__FONT_VALUES__", _json.dumps([s["value"] for s in _FONT_SETS])).replace(
    "__FONT_DEFAULT__", _DEFAULT_FONT_SET
)


# Prefetched-tier scheduling. The chain waits for the page to be idle so it
# does not compete with the tree render, and the timeout is the floor: on a
# large tree the main thread is busy for seconds, and a source view that never
# highlights is worse than one that highlights late. Two seconds is the same
# bound the tree's own idle prefetch already uses
# (SUBTREE_PREFETCH_IDLE_TIMEOUT_MS in static/app.js). "Idle" is
# `metabrowser.whenIdle` in static/plugin-sdk.js: requestIdleCallback where the
# engine has it, and where it does not -- the app's WebKit (WKWebView on macOS 26,
# measured 2026-11-11; WebKit enabled it in February 2025 and backed it out, bug
# 285049) -- the first view settled and input quiet, rather than a fixed timer.
PREFETCH_IDLE_TIMEOUT_MS = 2000


# Startup scripts only some shells carry, by static file name. A pin's page needs the
# GitPath wire codec before its first paint, and a page at a pull-request address needs
# that page's routes before it can show anything; a folder's page at any other address
# fetches neither. devtools/check_startup_scripts.py reports what each adds to the
# startup-script budget, so they are named here once.
PIN_STARTUP_SCRIPTS: tuple[str, ...] = ("git-path.js",)
PULL_PAGE_STARTUP_SCRIPTS: tuple[str, ...] = ("pull-route.js",)


def _startup_script_tags(names: tuple[str, ...]) -> str:
    return "".join(f'\n  <script src="{_static_asset_url(name)}"></script>' for name in names)


_PULL_HEAD_REF: Final = re.compile(r"refs/pull/([1-9][0-9]{0,9})/head")


def _source_ref_chip_html(name: str, kind: str) -> str:
    return (
        f'<span class="git-ref git-ref-{kind}">'
        f'<span class="git-ref-label">{html_escape(name)}</span></span>'
    )


# What a checkout's row says before the branch its files on disk are on, then the dot
# before that branch (static/source-ref-selector.js, `WORKING_TREE`).
_WORKING_TREE_WORD: Final = '<span class="source-ref-selector-view">Working tree</span>'
# The spaces are the text's alone: as a flex item's edges they collapse, and the label's
# gap sets the room.
_WORKING_TREE_DOT: Final = '<span class="source-ref-selector-sep" aria-hidden="true"> · </span>'


def _source_ref_label_html(
    pin: GitRevisionSubject | None, *, checkout: bool, working_head: CheckedOutHead | None
) -> str:
    """The selected source before the chooser mounts, in the same faces and dimensions.

    The row names what the page shows, in one form: a ref or a commit alone, on a mirror
    and on a checkout alike, and, for a checkout's files on disk, "Working tree" and the
    branch they are on, or the commit a detached ``HEAD`` is at
    (``static/source-ref-selector.js``, ``describe``).
    """

    if pin is None:
        if not checkout:
            return "Revision"
        if working_head is None:
            return _WORKING_TREE_WORD
        on = (
            _source_ref_chip_html(working_head.branch, "local")
            if working_head.branch is not None
            else f'<span class="git-commit-sha">{html_escape(short_commit(working_head.revision))}</span>'
        )
        return _WORKING_TREE_WORD + _WORKING_TREE_DOT + on
    return _source_ref_revision_html(pin, checkout=checkout)


def _source_ref_revision_html(pin: GitRevisionSubject, *, checkout: bool) -> str:
    """The ref a revision's page was drawn for: its chip, a pull request, or a bare commit."""

    if checkout:
        from metabrowser.checkout_revisions import checkout_ref_name

        name = checkout_ref_name(pin.ref)
    else:
        from metabrowser.git.tree_source import ref_short_name

        pull = _PULL_HEAD_REF.fullmatch(pin.ref or "")
        if pull is not None:
            return f'Pull request: <span class="source-ref-selector-pull-number">#{pull[1]}</span>'
        name = ref_short_name(pin.ref)
    if name:
        ref = pin.ref or ""
        kind = (
            "tag"
            if ref.startswith("refs/tags/")
            else "local"
            if checkout and ref.startswith("refs/heads/")
            else "remote"
        )
        return _source_ref_chip_html(name, kind)
    return (
        f'Commit: <span class="git-commit-sha">{html_escape(short_commit(pin.commit_oid))}</span>'
    )


async def index(
    request: Request,
    *,
    pull_page: bool = False,
    pull_list: bool = False,
    commit_page: bool = False,
    view_path: str | None = None,
) -> HTMLResponse:
    """Serve the SPA page with linked assets and one pre-paint state machine.

    *pull_page* is set by the pull-request route: its shell carries that page's routes
    as a startup script. *pull_list* is set by the list's route. At either address a
    repository's shell draws the Pulls tab in front, so its first paint is not the Files tree.
    """
    # Every asset address on the page names the stamps taken here, in a thread for a live
    # tree, so this comes before the first one is written.
    plugin_prefixes, kpress_prefix = await _shell_asset_prefixes()

    subject = get_source_session().subject
    pin = as_git_revision_subject(subject)
    git_pin = pin is not None
    # The folder this page is of, read once with its subject: a folder's server can come
    # to serve a revision of its checkout while this request awaits, and a second reading
    # would then find no folder.
    folder_root = subject.filesystem_root
    # The trust profile of this page is its subject's, decided here before anything is
    # awaited: a pin is never trusted, so a switch of the served subject while this
    # request renders cannot hand a revision's shell the folder's policy.
    page_capabilities = capabilities_for(pinned_revision=git_pin)
    # The reader's privacy preference, read from the request's cookies once, so the
    # settings the page carries and the policy it is served under cannot disagree.
    block_remote_images = blocks_remote_images(request.cookies)
    remote_images_checked = " checked" if block_remote_images else ""
    # Only a pin has a mirror session; a folder's shell never reads the app's state.
    mirror = mirror_session(request.app) if pin is not None else None
    # The served checkout's own refs and revisions: a folder that is a repository's root,
    # on its working tree and on each revision it shows. A mirror and a plain folder
    # have none. Kept for the process, as the session is, so a folder's shell still
    # reads nothing of the application's state.
    checkout = checkout_revisions()
    # The tab's title, and a native window's: what the served subject is called, from the
    # model `/api/identity` answers, so the two cannot disagree. A page changes subject
    # only by loading again, so the title written here stays current.
    identity = root_identity(mirror, checkout)
    page_title = html_escape(identity["title"])
    if pin is not None:
        # Imported where a pin is served, like every other Git import below: the
        # modules behind a pinned revision are start-up work a folder never uses.
        from metabrowser.git.tree_source import ref_branch_name

        pin_oid = pin.commit_oid
        status = source_status(mirror, checkout)
        initial_path = _pin_label_html(status)
        # A mirror's served root is the repository's name, as a folder's is its path:
        # what the file header's prefix and this heading's tooltip call the root.
        initial_root = html_escape(status["name"] or pin_oid, quote=True)
        mirror_attrs = _mirror_heading_attrs(status)
        root_source_tip = html_escape(_mirror_tip(status) or "")
        # A mirror's root is a name rather than a path, so the heading cuts it at its end.
        mirror_class = " mirror-source" if mirror_attrs else ""
        # Core holds no provider URL grammar: the served mirror asks the installed
        # providers, and only a hosted repository's has an answer (a GitHub mirror's
        # comes from the GitHub plugin). A file:// mirror, or a pin with no mirror,
        # has none.
        repository_context = (
            mirror.mirror.repository_context(revision=pin_oid, branch=ref_branch_name(pin.ref))
            if mirror is not None
            else None
        )
    else:
        initial_path = _initial_path_html()
        initial_root = html_escape(_display_root_str(), quote=True)
        mirror_attrs = mirror_class = root_source_tip = ""
        repository_context = await asyncio.to_thread(
            discover_repository_context, _shell_folder(folder_root)
        )
    # The mark before the root's name names which of the three kinds of root the page shows,
    # a plain folder, a Git checkout, or a cloud mirror (docs/design-system-icons.md,
    # "Source Kinds"). The server writes the kind, the glyph for it, and the sentence, the
    # same one `/api/identity` answers as `kind_tip`. The glyph is not in the icon registry:
    # the registry is a startup script every page pays for under a gated budget, and a page
    # draws one of the three, which only the server knows (source_kind_marks.py).
    #
    # A revision of the served checkout has no mirror but belongs to its checkout's
    # repository. Keep the checkout's HEAD context for ref actions. The page's
    # repository context names the pinned commit.
    tip_context = repository_context
    if pin is not None and checkout is not None and checkout.serves(pin):
        tip_context = await asyncio.to_thread(discover_repository_context, checkout.root)
        if tip_context is not None:
            repository_context = {
                **tip_context,
                "revision": pin.commit_oid,
                "branch": None,
                "branch_on_origin": False,
            }
    root_kind = identity["kind"]
    root_kind_svg = source_kind_svg(root_kind)
    root_kind_tip = html_escape(identity_kind_tip(identity, tip_context), quote=True)
    root_kind_label = html_escape(identity["kind_label"], quote=True)
    root_repository_url = (
        canonical_repository_url(tip_context)
        if root_kind != "folder"
        and tip_context is not None
        and {tip_context["owner"], tip_context["name"]}.isdisjoint({".", ".."})
        else None
    )
    root_repository_attr = root_repository_links = ""
    if root_repository_url is not None:
        safe_url = html_escape(root_repository_url, quote=True)
        root_repository_attr = f' data-repository-url="{safe_url}"'
        root_repository_links = f"""
            <div class="root-details-links">
              <div class="menu-link-url" id="root-repository-url">{safe_url}</div>
              <div class="root-details-actions" hidden></div>
            </div>"""
    root_checkout_meta = ""
    if root_kind == "git" and pin is None and tip_context is not None:
        revision = tip_context["revision"]
        root_checkout_meta += (
            '<div>Commit: <span class="git-commit-revision"'
            f' data-revision="{html_escape(revision, quote=True)}">'
            f'<span class="git-commit-sha">{html_escape(short_commit(revision))}</span></span></div>'
        )
    version_line = html_escape(display_version_line("metab", __version__))
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
    revision_ages_url = _static_asset_url("revision-ages.js")
    file_type_taxonomy_url = _static_asset_url("file-type-taxonomy.js")
    plugin_sdk_url = _static_asset_url("plugin-sdk.js")
    plugin_sdk_views_url = _static_asset_url("plugin-sdk-views.js")
    pull_route_url = _static_asset_url("pull-route.js")
    # The GitPath wire codec, which only a pin's page uses and which it needs before
    # its first paint: a startup script on a pin's shell and absent from a folder's,
    # like the pin guard below. Measured 2026-10-01: 885 compressed bytes of
    # navigation.js on every folder's page. See exp-037.
    git_path_script = _startup_script_tags(PIN_STARTUP_SCRIPTS if git_pin else ())
    # The pull-request page's routes and host, on the shell of a pull-request address
    # only. The server knows the address when it renders, so the script is fetched
    # with the rest of the shell and not one round trip after it. Any other page that
    # lands on such an address, through history, takes it from the `pull-route` bundle.
    pull_route_script = _startup_script_tags(PULL_PAGE_STARTUP_SCRIPTS if pull_page else ())
    view_composition_url = _static_asset_url("view-composition.js")
    inert_html_url = _static_asset_url("inert-html.js")
    remote_images_url = _static_asset_url("remote-images.js")
    diff_settings_url = _static_asset_url("diff-settings.js")
    filter_state_url = _static_asset_url("filter-state.js")
    filter_controls_url = _static_asset_url("filter-controls.js")
    icons_url = _static_asset_url("icons.js")
    charts_url = _static_asset_url("charts.js")
    tree_expansion_url = _static_asset_url("tree-expansion.js")
    nav_collapse_url = _static_asset_url("nav-collapse.js")
    # How every menu closes (docs/design-system.md, "Every Menu Closes Alike"): no menu is
    # open before the first tree, and one opened sooner asks for this bundle. Loaded at
    # startup, it put the startup scripts 870 bytes over their budget (2026-11-25).
    menus_url = _static_asset_url("menus.js")
    tree_filter_model_url = _static_asset_url("tree-filter-model.js")
    pending_tally_diagnostics_url = _static_asset_url("pending-tally-diagnostics.js")
    known_file_catalog_url = _static_asset_url("known-file-catalog.js")
    catalog_feed_url = _static_asset_url("catalog-feed.js")
    file_fuzzy_match_url = _static_asset_url("file-fuzzy-match.js")
    search_controller_url = _static_asset_url("search-controller.js")
    keyboard_shortcuts_url = _static_asset_url("keyboard-shortcuts.js")
    overlay_layer_url = _static_asset_url("overlay-layer.js")
    keyboard_help_url = _static_asset_url("keyboard-help.js")
    # The Shift key reveal and the shell's own keys: neither has work before the registry.
    key_reveal_url = _static_asset_url("key-reveal.js")
    shell_keymap_url = _static_asset_url("shell-keymap.js")
    # The plugin shortcut facade, which takes the keys plugin-sdk.js queued before it.
    plugin_shortcuts_url = _static_asset_url("plugin-shortcuts.js")
    tree_keyboard_navigation_url = _static_asset_url("tree-keyboard-navigation.js")
    search_palette_url = _static_asset_url("search-palette.js")
    git_graph_url = _static_asset_url("git-graph.js")
    git_history_window_url = _static_asset_url("git-history-window.js")
    git_panel_url = _static_asset_url("git-panel.js")
    event_reports_url = _static_asset_url("event-reports.js")
    source_freshness_url = _static_asset_url("source-freshness.js")
    source_ref_selector_url = _static_asset_url("source-ref-selector.js")
    app_url = _static_asset_url("app.js")
    perf_url = _static_asset_url("perf.js")
    # Inject the client-visible settings dict before any app code
    # runs so JS can read window.METABROWSER_SETTINGS.* without
    # duplicating constants in the source. A store's token travels beside the build, so
    # an answer a browser keeps is scoped to this store; a folder has none.
    client_settings = {
        **client_settings_dict(
            syntax_highlight_max_bytes=_SYNTAX_HIGHLIGHT_MAX_BYTES,
            capabilities=page_capabilities,
            block_remote_images=block_remote_images,
        ),
        "BUILD_TAG": BUILD_TAG,
        "EVENT_REPORTS": event_log_reports.browser_settings(long_lived=LONG_LIVED_PATHS),
    }
    if pin is not None:
        client_settings["STORE_TAG"] = store_tag(pin.command_target.git_dir)
    client_settings_block = (
        f"<script>window.METABROWSER_SETTINGS={_json.dumps(client_settings)};</script>"
    )
    settings_block = (
        f"<script>window.METABROWSER_PATH_ENCODING={_json.dumps('utf16' if os.name == 'nt' else 'bytes')};</script>"
        f"<script>window.METABROWSER_CONTAINER_EXTS={_json.dumps(_container_exts())};</script>"
    )
    repository_context_json = _json.dumps(repository_context).replace("<", "\\u003c")
    # A pin's freshness row, filled by static/source-freshness.js, which mounts on a
    # pinned revision only (app.js, `startSourceFreshness`). A plain folder has none, and
    # neither has a checkout's working tree: it shows the disk, and the store of its origin
    # is fetched from there by the navigation's Refresh (static/refresh-plan.js, `origin`).
    # It sits above the keyboard shortcut strip, so the strip stays the pane's last row
    # (owner, 2026-11-20).
    source_freshness_row = (
        '\n      <div class="source-freshness" id="source-freshness" hidden></div>'
        if git_pin
        else ""
    )
    # The selector is its own row, under the tabs and above the Files and Commits toolbars,
    # since both tabs show the revision it chooses. Reserve the label and its chooser
    # button at first paint: the row is those two whatever is shown, so nothing in it
    # moves when the chooser mounts or the page changes what it shows. A checkout's
    # working tree, the live files on disk, is named with the branch or commit they are
    # on; anything else by its ref (docs/design-system.md, "The Ref Selector").
    source_ref_selector = ""
    if checkout is not None or (git_pin and mirror is not None):
        from metabrowser.invisible_chars import display_segment

        origin = checkout.origin if checkout is not None else None
        read_mirror = (
            origin if pin is not None and origin is not None and origin.owns(pin) else mirror
        )
        view_attrs = ""
        if read_mirror is not None:
            origin_address = read_mirror.mirror.display.origin
            local_origin = origin_address.lower().startswith(("file://", "/", "~"))
            mode = "local-mirror" if local_origin else "cloud-mirror"
            view_attrs = f' data-source-mode="{mode}"'
            if not local_origin:
                location = html_escape(abbreviate_origin(origin_address, home=None), quote=True)
                view_attrs += f' data-source-origin="{location}"'
            if (synced_at := read_mirror.last_fetch_at()) is not None:
                view_attrs += f' data-source-synced-at="{html_escape(synced_at, quote=True)}"'
        elif checkout is not None:
            mode = "working-tree" if pin is None else "checkout-revision"
            path = html_escape(display_segment(os.fsencode(checkout.root)), quote=True)
            view_attrs = f' data-source-mode="{mode}" data-source-path="{path}"'
        working_head: CheckedOutHead | None = None
        if checkout is not None and pin is None:
            working_head = (
                CheckedOutHead(tip_context["branch"], tip_context["revision"])
                if tip_context is not None
                else await asyncio.to_thread(checked_out_head, checkout.root)
            )
            if working_head is not None and working_head.branch is not None:
                view_attrs += (
                    f' data-working-branch="{html_escape(working_head.branch, quote=True)}"'
                )
            if working_head is not None:
                view_attrs += f' data-working-commit="{working_head.revision}"'
        label = _source_ref_label_html(
            pin, checkout=checkout is not None, working_head=working_head
        )
        source_ref_selector = (
            f'<div class="source-ref-selector" id="source-ref-selector"{view_attrs}>'
            '<span class="source-ref-selector-button">'
            f'<span class="source-ref-selector-label">{label}</span>'
            '<button type="button" class="icon-btn source-ref-selector-toggle disclosure-toggle"'
            ' aria-label="Switch branch or tag" aria-haspopup="dialog" aria-expanded="false"'
            ' data-tip-text="Switch branch or tag"></button></span></div>'
        )
    # The Pulls tab follows a hosted mirror or a GitHub checkout, including a
    # checkout's revisions and subdirectories. It costs a plain folder nothing,
    # and a page with the tab draws it at first paint so the tabs never shift.
    pulls_tab = repository_context is not None
    pulls_in_front = pulls_tab and (pull_page or pull_list)
    # Commits is drawn here when the served root is a repository's root, the one root Git
    # discovery accepts (git/repo.py), so it does not appear when discovery registers it;
    # discovery removes it in the rare case Git does not agree. It comes after Pulls, in the
    # main tabs' order (static/main-tabs.js, MAIN_TABS).
    commits_tab = git_pin or await asyncio.to_thread(
        lambda: is_checkout_root(_shell_folder(folder_root).resolve())
    )
    # A commit's address lands on Commits, so it is drawn in front, with its toolbar and its
    # panel's container, and the landing never shows Files and then swaps it. The neutral Git
    # landing is /view/ with a history entry's state, which only the page can read.
    commits_in_front = commits_tab and commit_page
    files_in_front = not (pulls_in_front or commits_in_front)
    files_active = " active" if files_in_front else ""
    files_selected = "true" if files_in_front else "false"
    files_behind = "" if files_in_front else ' style="display: none"'
    # The navigation's toolbar slot holds the toolbar of the tab in front: the Files filters, or
    # the Commits tally, or the Pulls filters, each at the slot's one height, so the panel
    # below starts at one y on every tab (static/main-tabs.js#activateNavPanel). A tab whose
    # toolbar its script fills later ships the shared pending tally, never an empty slot.
    filter_bar_behind = "" if files_in_front else " hidden"
    pending_tally = '<span class="count tally-pending"></span>'
    # The served revision's row heads the two tabs that show it, Files and Commits, and hides
    # under Pulls, which has its own scope (static/main-tabs.js#activateNavPanel).
    source_ref_behind = "" if files_in_front or commits_in_front else " hidden"
    source_ref_row = (
        f'<div class="nav-source-ref" id="nav-source-ref"{source_ref_behind}>'
        f"{source_ref_selector}</div>"
        if source_ref_selector
        else ""
    )
    commits_button = (
        f'\n        <button class="tab-btn{" active" if commits_in_front else ""}" type="button"'
        f' role="tab" data-tab="git" aria-selected="{"true" if commits_in_front else "false"}">'
        "Commits</button>"
        if commits_tab
        else ""
    )
    git_container = (
        '\n        <div id="tab-git" data-tab-content="git">'
        '<div class="loading mb-delayed-loading" role="status">'
        '<div class="spinner spinner-sm" aria-hidden="true"></div>'
        '<span class="sr-only">Loading history…</span></div></div>'
        if commits_in_front
        else ""
    )
    toolbars = (
        '\n      <div class="nav-toolbar" id="nav-toolbar-git" data-nav-toolbar="git"'
        f"{'' if commits_in_front else ' hidden'}>"
        # The pending tally sits in the count's own span, where the count will be, as the
        # Files totals' does: a lone flex item would sit at the top of the line.
        '<div class="git-history-summary nav-metadata">'
        f'<span class="git-history-summary-count">{pending_tally}</span></div></div>'
        if commits_tab
        else ""
    ) + (
        '\n      <div class="nav-toolbar" id="nav-toolbar-pulls" data-nav-toolbar="pulls"'
        f"{'' if pulls_in_front else ' hidden'}>{pending_tally}</div>"
        # The band under the Pulls filters, which the list's count and connection lines
        # fill (builtin_plugins/github/pulls-panel.js), as the Files totals fill theirs.
        '\n      <div class="nav-metadata-band" id="nav-metadata-pulls"></div>'
        if pulls_tab
        else ""
    )
    pulls_button = (
        f'\n        <button class="tab-btn{" active" if pulls_in_front else ""}" type="button"'
        f' role="tab" data-tab="pulls" aria-selected="{"true" if pulls_in_front else "false"}">'
        "Pulls</button>"
        if pulls_tab
        else ""
    )
    # The navigation's one Refresh, at the top of the navigation pane just before the
    # Metabrowser menu, an icon button as the menu's gear is, on every page and under every
    # tab. It is here, glyph and all, from the first paint (shell_glyphs.py), so nothing in
    # the header appears or moves after it. A press refreshes what the page shows, the parts
    # on screen first (static/refresh-plan.js, which wires it once `shell-tools` loads).
    # Its cost is page bytes, not a request. With the original button and
    # refresh-plan.js's entry in the `shell-tools` bundle, a folder's page grew from 67,950
    # to 68,402 bytes, and from 17,772 to 17,881 as sent compressed, against main at
    # a96ac3304, measured 2026-11-25 with `render_shells` and `sent_body_bytes` in
    # devtools/check_startup_scripts.py (the served root's temporary name moves the sent
    # size by a few bytes from run to run).
    nav_refresh = (
        '\n        <button class="icon-btn nav-refresh" id="nav-refresh" type="button"'
        f' aria-label="Refresh" data-tip-text="Refresh">{REFRESH_SVG}'
        '<span class="spinner spinner-sm nav-refresh-spinner" aria-hidden="true"></span>'
        "</button>"
    )
    pulls_container = ""
    if pulls_tab:
        pulls_container = (
            '\n        <div id="tab-pulls" data-tab-content="pulls">'
            '<div class="loading mb-delayed-loading" role="status">'
            '<div class="spinner spinner-sm" aria-hidden="true"></div>'
            '<span class="sr-only">Fetching pull requests…</span></div></div>'
            if pulls_in_front
            else '\n        <div id="tab-pulls" data-tab-content="pulls"'
            ' style="display: none"></div>'
        )
    # The Pulls landing has no selection to load. Its spinner belongs in the sidebar.
    if pull_list and pulls_in_front:
        preview_loading = '<div class="preview-empty">Select a pull request.</div>'
    elif pull_page:
        # Nothing to keep on screen while the page is staged: the page's own loading state,
        # its header rows at their heights and the tab bar over a body skeleton, replaces
        # this at once (static/app.js#beginPreviewNavigation). Staged, it stayed hidden
        # behind this skeleton until the record landed, 1.9 s on a cold cache.
        preview_loading = (
            '<div class="pull-request-placeholder mb-delayed-loading" role="status"'
            ' aria-label="Loading pull request" data-preview-empty>'
            '<div class="recent-loading" aria-hidden="true"></div></div>'
        )
    else:
        preview_loading = (
            '<div class="loading mb-delayed-loading"><div class="spinner"></div>'
            '<span class="sr-only">Loading preview…</span></div>'
        )
    source_kind_json = _json.dumps("git_revision" if git_pin else "filesystem")
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
    #
    # A landing on a path inlines its folders' listings too, each grafted under its row and
    # expanded, and names the path when its row is among them: the page then selects and
    # shows that row at its first tree paint, and fetches and scrolls nothing for it after
    # (static/app.js#renderInitialTreeRows). The inline stays a strict subset of what the
    # page builds: no route reconciles a folder below the first level once it has rows, so
    # a folder is grafted only with its whole listing. A path with a folder that cannot be
    # (its listing has a further page, or the path's rows would pass _INLINE_LANDING_ROWS),
    # or deeper than _INLINE_LANDING_DEPTH, inlines the root alone and the page reveals the
    # path as before. The rows carry the canonical path, so the landing is canonicalized
    # before it is split.
    #
    # The root's own entry rides in the same read, so the Files totals line paints its
    # tracked and ignored halves from the first frame (`_root_totals`), and a folder with
    # nothing ignored never holds a line for it (static/app.js, `_rootTotals`).
    initial_tree_block = ""
    landed: str | None = None
    root_totals: dict[str, int] | None = None
    if _INLINE_INITIAL_TREE_ROWS and not git_pin:
        landing = canonical_inventory_path(view_path) if view_path else ""
        landing_parts = [part for part in landing.split("/") if part]
        ancestors = (
            ["/".join(landing_parts[: index + 1]) for index in range(len(landing_parts) - 1)]
            if len(landing_parts) - 1 <= _INLINE_LANDING_DEPTH
            else []
        )
        try:
            runtime = _inventory_runtime_for(request)
            initial_read = await runtime.coordinator.read(
                ReadRequest(
                    queries=(
                        *(
                            DirectoryQuery(
                                query_id=f"initial-tree-{index}",
                                path=path,
                                max_depth=1,
                                max_rows=_INLINE_INITIAL_TREE_ROWS,
                            )
                            for index, path in enumerate(["", *ancestors])
                        ),
                        EntryQuery(query_id="initial-root", path=""),
                    )
                )
            )
            root_entry = initial_read.result.completed_projection("initial-root")
            if not isinstance(root_entry, EntryProjection):
                raise TypeError("the initial-root read returned the wrong projection")
            root_totals = _root_totals(root_entry.entry)

            def inline_level(
                index: int, path: str, *, parent_ignored: bool = False
            ) -> tuple[list[dict[str, Any]], bool]:
                projection = initial_read.result.completed_projection(f"initial-tree-{index}")
                if not isinstance(projection, DirectoryProjection):
                    raise TypeError("the initial-tree read returned the wrong projection")
                rows = build_inventory_tree_from_entries(
                    entries=projection.entries,
                    parent_rel=path,
                    max_depth=1,
                    parent_ignored=parent_ignored,
                    max_entries=_INLINE_INITIAL_TREE_ROWS,
                )
                return rows, projection.next_page is None

            initial_tree, _ = inline_level(0, "")
            # Every folder of the path, or none of them: a landing that opened some of its
            # folders at first paint and the rest after moved the tree no less than one that
            # opened them all after (layout shift 0.19 to 0.38 against 0.11 to 0.39, two to
            # eight folders of the fixture measured at _INLINE_LANDING_ROWS), and paid for
            # the rows it inlined.
            grafts: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
            level = initial_tree
            landing_rows = 0
            for index, ancestor in enumerate(ancestors, start=1):
                row = next((n for n in level if n["path"] == ancestor and n["type"] == "dir"), None)
                if row is None:
                    break
                try:
                    children, whole = inline_level(
                        index, ancestor, parent_ignored=bool(row.get("gitignored"))
                    )
                except Exception:
                    LOG.debug("landing ancestry inline stopped at %s", ancestor, exc_info=True)
                    break
                landing_rows += len(children)
                if not whole or landing_rows > _INLINE_LANDING_ROWS:
                    break
                grafts.append((row, children))
                level = children
            # While discovery runs, a folder the walk has not reached yet reads as an empty
            # listing with no further page: grafted, the page drew it empty and open, with
            # nothing to load, and never selected the landing's row. So the path's folders
            # are grafted only from a read of complete coverage.
            if len(grafts) == len(ancestors) and (
                not ancestors or initial_read.result.state.coverage.complete
            ):
                for row, children in grafts:
                    row["children"] = children
                    row["expanded"] = True
                target = "/".join(landing_parts)
                if any(n["path"] == target for n in level):
                    landed = target
        except Exception:
            LOG.debug("initial tree inline failed", exc_info=True)
            initial_tree = []
            root_totals = None
        if initial_tree or root_totals is not None:
            initial_tree_json = _json.dumps(
                {
                    "tree": initial_tree,
                    **({"path": landed} if landed else {}),
                    **({"summary": root_totals} if root_totals is not None else {}),
                }
            ).replace("<", "\\u003c")
            initial_tree_block = (
                f"<script>window.METABROWSER_INITIAL_TREE={initial_tree_json};</script>"
            )
    repository_context_block = (
        f"<script>window.METABROWSER_SOURCE_KIND={source_kind_json};</script>"
        f"<script>window.METABROWSER_REPOSITORY_CONTEXT={repository_context_json};</script>"
    )
    if pin is not None:
        # The commit and ref the page is rendered for: its data requests name the commit,
        # and the freshness row compares both with what the server serves, so a switch
        # or a restart onto another pin before its first poll still offers a reload.
        page_pin = _json.dumps({"pin": pin.commit_oid, "ref": pin.ref}).replace("<", "\\u003c")
        # Whether the Git this server runs dates a revision's files, which is what the Files
        # tab's age menus wait for: Group by age and Modified within, hidden on a revision
        # that has no times (static/app.js `noFileAges`).
        has_ages = "true" if pin.capabilities.recency else "false"
        repository_context_block += (
            f"<script>window.METABROWSER_FILE_AGES={has_ages};</script>"
            f"<script>window.METABROWSER_SOURCE_PIN={page_pin};</script>"
            f"<script>{_SOURCE_PIN_GUARD_SCRIPT}</script>"
        )
        if mirror_attrs:
            repository_context_block += f"<script>{_mirror_heading_script()}</script>"

    if pin is not None and checkout is not None and checkout.serves(pin) and tip_context:
        ref_context = _json.dumps(tip_context).replace("<", "\\u003c")
        repository_context_block += (
            f"<script>window.METABROWSER_CHECKOUT_REF_CONTEXT={ref_context};</script>"
        )
    if checkout is not None:
        # A checkout's page says so, and whether it shows the working tree: the ref
        # selector reads it for what it offers, and the pin guard, which the selector's
        # bundle brings to a working-tree page, for what the page's requests name.
        page_checkout = _json.dumps({"working_tree": pin is None})
        repository_context_block += (
            f"<script>window.METABROWSER_SOURCE_CHECKOUT={page_checkout};</script>"
        )
    # Read preferences from host-only cookies (not localStorage): cookies
    # ignore the port, so the choice is shared across every metabrowser instance
    # on this host (each folder server lands on its own port). Runs before the
    # stylesheet applies so the page paints in the right theme, reading font, and
    # font set on the first frame (no flash). The keys mirror app.js constants;
    # _THEME_BOOTSTRAP_SCRIPT fills the font-set placeholders from _FONT_SETS.
    theme_bootstrap = f"<script>{_THEME_BOOTSTRAP_SCRIPT}</script>"
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
    # indefinitely. See docs/project/architecture/arch-browser-shell.md,
    # "Asset Loading Tiers".
    #
    # A grammar here is fetched on every page for a language few folders hold, so
    # it stays only while it is small beside the 121,727-byte runtime it extends.
    # Measured 2026-11-26: highlight-toml.min.js is 1,044 bytes (644 gzipped) and
    # syntax/lean.js 12,750 (4,824 gzipped); evaluating lean.js takes 0.3 ms in
    # Node 24, since registering a language compiles nothing until the first
    # highlight, which then takes about 1 ms more. When the grammars together stop
    # being small beside the runtime, load each on demand by language instead.
    optional_script_assets = [
        {"src": _static_asset_url("vendor/highlight.min.js")},
        {"src": _static_asset_url("vendor/highlight-toml.min.js"), "requires": "hljs"},
        {"src": _static_asset_url("syntax/lean.js"), "requires": "hljs"},
    ]
    # On-demand tier: fetched by asset-loader.js the first time a consumer asks.
    # Chart.js and its two plugins are 297,531 bytes read by one view, and
    # eager loading measured ~374 ms of every document's load event whether or
    # not that view was ever opened. See docs/project/architecture/arch-browser-shell.md,
    # "Asset Loading Tiers", and the load-time plan for the measurement.
    main_tabs_asset = {"src": _static_asset_url("main-tabs.js"), "provides": "MetabrowserMainTabs"}
    on_demand_script_bundles = {
        # Idle prefetch and plugin demand share this loader. A plugin may call
        # synchronous mb.render() while its module evaluates, before idle runs.
        "mustache": [{"src": _static_asset_url("vendor/mustache.min.js"), "provides": "Mustache"}],
        # A main tab click can arrive before the initial tree request settles.
        "main-tabs": [main_tabs_asset],
        # Navigation, search, Help, and Git controls are application-lifetime
        # tools, but none is needed to paint or fetch the first tree. Keeping
        # their ordered classic scripts behind that usable-state boundary
        # removes eleven requests from the shell's startup waterfall. They
        # begin immediately after loadTree settles, before inventory delivery
        # continues in the background.
        "shell-tools": [
            main_tabs_asset,
            {"src": menus_url, "provides": "MetabrowserMenus"},
            {"src": known_file_catalog_url},
            {"src": catalog_feed_url},
            {"src": file_fuzzy_match_url},
            {"src": search_controller_url},
            {"src": keyboard_shortcuts_url},
            {"src": overlay_layer_url},
            {"src": keyboard_help_url},
            {"src": key_reveal_url},
            # Hiding the navigation pane: app.js draws its chevron at first paint, and a
            # click before this bundle arrives loads it and then hides the pane.
            {"src": nav_collapse_url},
            {"src": shell_keymap_url},
            {"src": plugin_shortcuts_url},
            {"src": tree_keyboard_navigation_url},
            {"src": search_palette_url},
            {"src": git_graph_url},
            {"src": git_history_window_url},
            {"src": git_panel_url},
            {"src": _static_asset_url("page-labels.js")},
            # The navigation's Refresh: mounts as it evaluates, on the button the server drew.
            {"src": _static_asset_url("refresh-plan.js"), "provides": "MetabrowserRefreshPlan"},
            # Only a shell that drew the Pulls tab has it, so a folder fetches nothing new.
            *([{"src": _static_asset_url("pulls-nav.js")}] if pulls_tab else []),
            # The event log's reporter, last: nothing here waits on it (`event-reports`).
            {"src": event_reports_url},
        ],
        # The compositor is needed only once file navigation begins, after the
        # first tree is usable. renderFile awaits this bundle and rechecks its
        # ownership claim before preparing or mounting a view.
        "view-composition": [{"src": view_composition_url}],
        # What the page reports to the event log, and the Details a failure or a late
        # wait offers (static/event-reports.js). It is the last script of `shell-tools`,
        # so it loads after the first usable tree, and a page that waits on something
        # before then asks for it by this name; the loader runs a script once whichever
        # bundle asks. A report of what came earlier reads the browser's Resource Timing.
        # Not a startup script, nor a call in app.js: the startup budget had 99 bytes left
        # when it was written, and #622's changes left 2 after such a call (2026-11-19).
        "event-reports": [{"src": event_reports_url}],
        # Mermaid 12.3.0's ESM entry (static/vendor/mermaid/), imported by the Markdown
        # plugin's diagram renderer only when a mounted view holds a diagram. The entry
        # imports the chunks of each diagram type it draws by relative specifiers, so a
        # document fetches the 30,936-byte entry and its types' chunks, and a document
        # with no diagram fetches nothing (docs/project/specs/active/
        # plan-2026-08-21-mermaid-diagram-rendering.md has the measurement).
        "mermaid": [{"module": _static_asset_url("vendor/mermaid/mermaid.esm.min.mjs")}],
        # KPress's diagram renderer and its opt-in controls, at the stamped URLs a
        # render's asset manifest names, so they import the one KPress runtime the
        # document's other modules share. Fetched with the first diagram, beside Mermaid.
        "kpress-diagrams": [
            {"module": kpress_adapter.kpress_static_url("js/diagrams.js", prefix=kpress_prefix)}
        ],
        "kpress-diagram-controls": [
            {
                "module": kpress_adapter.kpress_static_url(
                    "js/diagram-controls.js", prefix=kpress_prefix
                )
            }
        ],
        # A file's and a folder's view header: its builders, and the folder line's live
        # refresh. renderFile draws a header only after loadViewComposition, which fetches
        # this beside the compositor and the SDK's view helpers, so the first tree never
        # waits for it. What that costs a view, measured in Chrome on 2026-11-18 against
        # the builders in app.js, 36 cold loads of a folder and of a file a side in
        # alternating back-to-back pairs, at load averages of 24 to 33 on 10 cores: the
        # bundle is 14,102 bytes, 4,514 as a gzip client receives it; its request starts
        # with the other two and ended no later than both in 48 of 72 loads; and the
        # header's median time after DOMContentLoaded went from 40 to 41 ms on a folder
        # and stayed at 58 ms on a file.
        "view-header": [
            {"src": _static_asset_url("view-header.js"), "provides": "MetabrowserViewHeader"}
        ],
        # The page's file watches on its event stream (static/file-watches.js), fetched
        # the first time a view calls metabrowser.watchFile: a table, or a container
        # whose children the tree shows. Most pages watch nothing, so it is no startup
        # script; app.js only hands it each snapshot's connection and each change.
        "file-watches": [
            {"src": _static_asset_url("file-watches.js"), "provides": "MetabrowserFileWatches"}
        ],
        # What a view's renderer calls: the line-number gutter with its `#L` anchors,
        # and the SDK helpers a renderer builds its markup with (the Source surface,
        # the copy wrapper, the partial-content notice, the syntax service). Nothing
        # runs either until a view renders. loadViewComposition fetches this beside
        # the compositor and waits for both, and plugin-sdk.js fetches it before it
        # evaluates a plugin where no compositor ran, so a renderer always finds all
        # of it. One file, because nothing uses one half without the other and a
        # bundle's scripts are fetched one after another.
        # Measured 2026-09-30 and 2026-10-01 in Chrome 152: as startup scripts the
        # gutter was 7,992 of 191,862 bytes transferred before DOMContentLoaded and
        # one of 21 requests, on a folder shell that draws no gutter, and the helpers
        # 5,632 of plugin-sdk.js's 22,308 compressed bytes. The gutter's compile and
        # evaluate took 0.09 ms, so the cost is transfer, which is what
        # `startup_script_transfer_kb` in performance-budgets.toml bounds. On an
        # anchored deep link the Source view appeared with its gutter in every load,
        # with no layout shift in the pane, in this tier as in the eager one. See
        # explorations/performance-loop/experiments/exp-037.
        "sdk-views": [{"src": plugin_sdk_views_url, "provides": "MetabrowserSourceLineAnchors"}],
        # The pull-request page's routes and host, for a page that reaches a
        # pull-request address without loading there. A page that loads at one has
        # them as a startup script (PULL_PAGE_STARTUP_SCRIPTS). Measured 2026-10-01:
        # 1,818 of navigation.js's 13,265 compressed bytes as a startup script on
        # every folder's page. See exp-037.
        "pull-route": [{"src": pull_route_url, "provides": "MetabrowserPullRoute"}],
        # Only untrusted Markdown needs the allowlist: a pull-request comment, or a
        # document under the untrusted profile, which the server marks inert.
        "inert-html": [{"src": inert_html_url}],
        # What a link in authored text opens (static/repository-links.js), which views load
        # through metabrowser.loadRepositoryLinks(): only a page with a GitHub repository's
        # identity reads one, beside the text that holds it, a Markdown render, a pull
        # request's text, a commit's message, or a rendered diff. As a startup script it
        # would cost every folder's shell its compressed size, and the startup scripts were
        # 109 bytes under their budget when it was written (2026-11-26). On demand it arrives
        # before a Markdown file's render is asked for (static/plugin-sdk-views.js has the
        # measurement). The GitPath codec it spells a pin's addresses with comes first: a
        # startup script of a pin's shell, which a browser has cached there, and needed
        # elsewhere only by a rendered diff beside a checkout, whose link to a file of the
        # head it reads back. Measured 2026-11-27 at `delivery.GZIP_LEVEL`, as
        # devtools/check_startup_scripts.py measures a script sent: 1,742 and 10,394 bytes
        # (4,626 and 36,633 raw). Its wait, `ensureAsset("repository-links")` to its
        # answer, which `REPOSITORY_LINKS_WAIT_MS` bounds (static/plugin-sdk-views.js): on a
        # checkout's Markdown file in headless Chrome 158 from 127.0.0.1, to which the server
        # sends every script uncompressed, on a 4-core Linux container at load averages of
        # 0.1 to 2.6, cold loads with the cache off alternating this bundle with the one it
        # was, which also held the link card's two scripts (`link-previews` below), 20 loads
        # of each in each of two runs: medians of 24.7 and 23.1 ms (at most 31.6) here,
        # against 41.2 and 40.1 ms (at most 52.9) with the card.
        "repository-links": [
            {"src": _static_asset_url("git-path.js"), "provides": "MetabrowserGitPath"},
            {
                "src": _static_asset_url("repository-links.js"),
                "provides": "MetabrowserRepositoryLinks",
            },
        ],
        # The link card (static/link-previews.js), its registry, and its providers
        # (static/link-preview-providers.js), which register with it and so come after it:
        # code that runs only once a pointer rests on a link a surface registered, on any
        # page, through metabrowser.previewLink() (static/plugin-sdk-views.js), which loads
        # this at the page's first such rest and hands it that rest. Measured 2026-11-27 at
        # `delivery.GZIP_LEVEL`: 12,899 and 7,003 bytes sent (45,001 and 23,974 raw; the
        # timings below were taken at 13,069 and 6,970, before review I's fixes, which read
        # an outside link's address through the SDK's `outsideAddress`, dropped the file
        # catalog, and give an author's title back), which as a startup script, or
        # in the resolver's bundle, every page would wait for; at a
        # rest, the card's appear delay (`TOOLTIP_APPEAR_DELAY` in static/app.js) hides most
        # of its load. In headless Chrome 158 from 127.0.0.1 as above, the first rest on a
        # file's link of a fresh page, a checkout's Markdown file and a plain folder's, cache
        # off, 20 pages of each variant in each of three runs, two resting a second after the
        # links were in and one as soon as they were: the bundle loaded in medians of 9.1 to
        # 16.2 ms (at most 42.8), and the card was up medians of 314.0 to 330.8 ms after the
        # pointer arrived (at most 349.6), inside the window every rest's card comes in
        # (tests/test_link_card_chrome.py), against 302.4 to 315.4 ms when the page
        # preloaded the bundle in idle time after its first registration. Preloading costs
        # every page with a link the bundle whether or not a pointer rests on one, and had
        # loaded by a rest as soon as the links were in on only 9 and 12 of 20 pages. On the
        # first page of a freshly started server, 10 servers a variant, the card was up a
        # median of 337 ms (at most 367) with the bundle loaded at the rest and 311 ms (at
        # most 367) preloaded, loaded by the rest on 4 of 10; the Chrome check's first rests
        # there waited up to 188 ms for the bundle. So the page loads it at the rest.
        "link-previews": [
            {
                "src": _static_asset_url("link-previews.js"),
                "provides": "MetabrowserLinkPreviews",
            },
            {"src": _static_asset_url("link-preview-providers.js")},
        ],
        # These preferences need listeners only when the reader opens the menu.
        "settings-menu": [
            {"src": remote_images_url, "provides": "MetabrowserRemoteImages"},
            {"src": diff_settings_url},
        ],
        # The tree of a change set's files that both the Pulls tab and a diff's Diff summary
        # draw, which two plugins share through metabrowser.loadChangedFilesTree(). Only a
        # page that shows a pull request's files or a multi-file diff asks for it: a diff
        # asks beside its comparison, and the Pulls tab when it mounts. Measured on
        # 2026-11-15 in headless Chrome 152 from 127.0.0.1: 8,715 compressed bytes (9,015
        # transferred), a cold load with the cache off 4.1 and 4.6 ms (medians of 9 and 7,
        # at most 8.7), its fetch 3.1 to 3.4 ms.
        "changed-files-tree": [
            {
                "src": _static_asset_url("changed-files-tree.js"),
                "provides": "MetabrowserChangedFilesTree",
            }
        ],
        # Only a served mirror has freshness to show, so a folder never fetches
        # this; a pin starts it after the first tree request settles, and the
        # label it paints is a quiet row the page does not wait for.
        "source-freshness": [{"src": source_freshness_url}],
        # Only a pin served from a mirror, or a checkout, has the selector; it is fetched
        # after the first tree request settles, like the freshness row, and no request is
        # made for the refs until a reader opens it. A pin's page carries the pin guard
        # inline. A checkout's working-tree page takes it here, ahead of the selector
        # that can make the server serve something else, so that a folder's first paint
        # carries none of it: inline it would add its compressed size to the page of
        # every checkout, most of which never switch. That is 4,751 bytes and the
        # selector's 10,538, at gzip -6 (`delivery.GZIP_LEVEL`), as of the switch hold
        # (mb-bio7, 2026-11-18). Measured 2026-11-18 in headless Chrome 152 from
        # 127.0.0.1, three runs on a 10-core Mac at a load average of 13 to 16, when they
        # were 3,354 and 9,879 bytes: the guard in 8.6 to 10.5 ms and the selector in 7.0
        # to 9.7 ms, both asked for 124 to 142 ms after the navigation began, once the
        # first tree rows were in; the selector was mounted 170 to 181 ms after it
        # (tests/dom/checkout-ref-selector-chrome.mjs prints them).
        "source-ref-selector": [
            *(
                [{"src": _static_asset_url("source-pin-guard.js")}]
                if checkout is not None and pin is None
                else []
            ),
            {"src": source_ref_selector_url},
        ],
        "source-append": [{"src": source_append_url}],
        "structured-tree": [
            {"src": _static_asset_url("structured-preview.js"), "provides": "__structuredPreview"},
            {"src": _static_asset_url("structured-tree.js"), "provides": "__structuredTree"},
        ],
        # The watch on a revision's file ages and the notes about them, which only a page whose
        # Git can read ages and whose response says they are not all in yet needs: asked for
        # the first time a response says `dating`, `partial`, or `failed`, and never by a page
        # whose answer is whole or whose Git cannot (it is not offered to that page at all).
        # It was a startup script of every pin's shell, 4,940 bytes (1,896 gzipped) before a
        # page could use it, and 3,783 bytes of that shell over the folder's budget.
        **(
            {"revision-ages": [{"src": revision_ages_url, "provides": "MetabrowserRevisionAges"}]}
            if pin is not None and pin.capabilities.recency
            else {}
        ),
        "chart": [
            {"src": _static_asset_url("vendor/chart.umd.min.js"), "provides": "Chart"},
            {"src": charts_url, "requires": "Chart"},
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
        // The event tells a listener that is already there. The flag tells one that
        // arrives later, such as the syntax service, which loads with the first view.
        window.METABROWSER_OPTIONAL_ASSETS_SETTLED = true;
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
    function start() {{
      window.MetabrowserAssets.ensureAsset("mustache").then(
        function () {{ loadNext(0); }},
        function (error) {{
          console.warn("metabrowser optional asset failed:", error);
          loadNext(0);
        }}
      );
    }}
    function schedule() {{
      window.metabrowser.whenIdle(start, {{ timeout: {PREFETCH_IDLE_TIMEOUT_MS} }});
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
    plugin_asset_config = _build_plugin_asset_config_block(plugin_prefixes)

    # The sidebar uses an optional-display alias of KPress's stamped Source Sans
    # faces so a late response cannot move its tabs, filter bar, or root menu.
    # The rest of the app uses KPress's original faces and the same font bytes.
    sans_url = kpress_adapter.kpress_static_url(
        "fonts/source-sans-3-latin-wght-normal.woff2", prefix=kpress_prefix
    )
    italic_sans_url = kpress_adapter.kpress_static_url(
        "fonts/source-sans-3-latin-wght-italic.woff2", prefix=kpress_prefix
    )
    tokens_url = kpress_adapter.kpress_static_url("css/style-tokens.css", prefix=kpress_prefix)
    sidebar_sans_faces = _json.dumps((("normal", sans_url), ("italic", italic_sans_url)))
    kpress_font_head = f"""<link rel="preload" as="font" type="font/woff2" crossorigin href="{sans_url}">
  <link rel="stylesheet" href="{tokens_url}">
  <script>
    if (typeof FontFace === "function" && document.fonts) {{
      for (const [style, url] of {sidebar_sans_faces}) {{
        document.fonts.add(new FontFace("Metabrowser Sidebar Sans", 'url("' + url + '")', {{
          style, weight: "200 900", display: "optional",
        }}));
      }}
    }}
  </script>"""

    html = f"""<!DOCTYPE html>
<html lang="en" style="--doc-max-chars: {DOC_MAX_CHARS_DEFAULT}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <title>{page_title}</title>
  <!-- Preload the shared Source Sans bytes and register the sidebar face before layout. -->
  {kpress_font_head}
  {client_settings_block}
  <script>{_DOCUMENT_WIDTH_SCRIPT}</script>
  {theme_bootstrap}
  <!-- All third-party assets are vendored into the wheel and served
       same-origin (see static/vendor/manifest.json), so the page loads
       with no external origins and works offline. -->
  <link rel="stylesheet" href="{styles_url}">
</head>
<body>
  <main class="container{mirror_class}">
    <div class="tree-pane" id="tree-pane">
      <header class="app-header" data-kbd-badge-anchor>
        <!-- data-served-root is the one place the absolute root is written:
             the file header reads it back to render the root's address, so
             the two headers cannot disagree about what the root is. The
             details disclosure uses it for the root's address.

             The folder's icon and name link Home (docs/design-system.md, "Home"). A
             plain activation in app.js and the `0` shortcut return to the fresh-load
             view. The accessible name uses just the heading text after "Home:", so a
             pin's ref and commit count as the name. The header anchors the key badge
             beside the heading because the name clips. -->
        <a href="{VIEW_ROUTE_PREFIX}" class="header-path" id="header-home"
           aria-labelledby="header-home-label header-home-name"
           data-served-root="{initial_root}"{mirror_attrs}>
          <span class="header-root-kind" id="header-root-kind" role="img"
                data-root-kind="{root_kind}" data-tip-text="{root_kind_tip}"
                aria-label="{root_kind_tip}">{root_kind_svg}</span>
          <span class="header-home-name" id="header-home-name">{initial_path}</span>
        </a>
        <span id="header-home-label" hidden>Home:</span>
        <div id="root-details" class="root-details"{root_repository_attr}>
          <button type="button" class="icon-btn root-details-trigger disclosure-toggle"
                  aria-expanded="false" aria-controls="root-details-panel"
                  aria-label="{root_kind_label} details" data-tip-text="{root_kind_label} details"></button>
          <div id="root-details-panel" class="menu root-details-panel" hidden>
            <div class="root-details-info">
              <strong>{root_kind_label}</strong>
              <div class="root-details-local">
                Local path
                <div class="root-details-location">{"" if git_pin else initial_root}</div>
              </div>
              <div class="root-details-stats"></div>
              {root_checkout_meta}
              <div class="root-details-source">{root_source_tip}</div>
            </div>
            {root_repository_links}
            <div class="root-details-status" role="status"></div>
          </div>
        </div>{nav_refresh}
        <!-- The Metabrowser menu. The gear names the product rather than
             standing as an unlabelled settings control: the wordmark that
             used to sit on its own line above the path is this menu's title,
             which returns that line of the navigation column — the app's
             scarcest width — to the path. Inside: two icon-segment choosers
             (theme + reading font), a small font-set dropdown
             (#app-font-select, options from _FONT_SETS), a privacy checkbox
             (Block remote images, which reloads the page because the server's
             policy follows it), and the same build version line printed by
             `metab --version`. Other choices apply instantly.
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
            <select class="field menu-select" id="app-font-select" aria-label="Fonts">{app_font_options}</select>
            <div class="menu-separator"></div>
            <label class="menu-row" for="default-diff-layout">Default diff layout
              <select class="field" id="default-diff-layout" disabled
                      data-tip-text="Layout for source diffs in new comparisons">
                <option value="split">Split</option>
                <option value="unified">Unified</option>
              </select>
            </label>
            <div class="menu-separator"></div>
            <label class="menu-row" for="doc-max-chars-input">Max text width
              <input class="field menu-number" id="doc-max-chars-input" type="number"
                     min="40" max="160" step="1" inputmode="numeric"
                     data-tip-text="Characters per line in rendered documents"></label>
            <div class="menu-separator"></div>
            <label class="menu-row" for="block-remote-images-input">Block remote images
              <input class="menu-check" id="block-remote-images-input" type="checkbox"{remote_images_checked} disabled
                     data-tip-text="Show an untrusted document's images from the web as their alt text. Reloads the page"></label>
            <div class="menu-separator"></div>
            <div class="menu-version">{version_line}</div>
          </div>
        </div>
      </header>
      <div class="tab-bar nav-tab-bar" role="tablist">
        <button class="tab-btn{files_active}" type="button" role="tab" data-tab="files" aria-selected="{files_selected}">Files</button>{pulls_button}{commits_button}
      </div>
      {source_ref_row}
      <!-- Filter bar lives outside #tab-files: a tree reload replaces
           that container's contents wholesale, and the bar must also
           stay put while .tree-content scrolls. app.js fills it.

           Under it, the Files totals and the remarks on them, a band of
           navigation metadata lines that app.js fills. It is outside
           .tree-content too: that scroller reserves its scrollbar's gutter
           and clips what it holds short of it, so a line inside it drew its
           rule short of the pane's edge. The band shows with its toolbar
           (`.nav-metadata-band` in styles.css). -->
      <div class="nav-filter-bar" id="nav-filter-bar" data-nav-toolbar="files"{filter_bar_behind}>{pending_tally}</div>
      <div class="nav-metadata-band" id="nav-metadata-files"></div>{toolbars}
      <div class="tree-content" id="tree-content">
        <div id="tab-files" data-tab-content="files"{files_behind}>
          <div class="loading mb-delayed-loading"><div class="spinner"></div><span
            class="sr-only">Loading files…</span></div>
        </div>{git_container}{pulls_container}
      </div>{source_freshness_row}
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
    <!-- Every route that serves this shell selects something: /view/ names a
         file or folder (the bare origin redirects to the served root),
         /commit/ names a revision, /pull/ a pull request, and /pulls their
         list. So the pane ships loading, never a prompt to select a file. It is
         navigation.js's starting placeholder. The frame around it does not
         scroll, so KPress's floating UI pins to it (see .preview-frame). -->
    <div class="preview-frame kpress-frame">
      <div class="preview-pane" id="preview-pane" data-kpress-viewport tabindex="-1">
        {preview_loading}
      </div>
      <!-- Hides and shows the navigation pane, as the backslash key does: at the start
           of the main page's foot, in its gutter, on the row of the navigation's shortcut
           strip. It is in the frame, not the pane, so it stays when the pane is hidden and
           slides with the page. app.js draws its chevron; static/nav-collapse.js runs it,
           and static/styles.css places it. -->
      <button class="icon-btn nav-collapse-toggle disclosure-toggle" id="nav-collapse-toggle" type="button"
              aria-controls="tree-pane" aria-expanded="true"
              aria-label="Hide navigation"></button>
    </div>
  </main>
  <!-- Core shell scripts are local and first-paint critical. Optional
       third-party libraries are vendored into the wheel and loaded by
       the async enhancement loader below so they cannot block initial
       tree/readme rendering. TOML support comes from the official
       highlight.js ini.min.js grammar (`aliases:["toml"]`), vendored as
       highlight-toml.min.js; Lean's from syntax/lean.js, a port of
       the official Lean 4 grammar. -->
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
  <script src="{view_state_url}"></script>{git_path_script}
  <script src="{navigation_url}"></script>{pull_route_script}
  <script src="{file_type_taxonomy_url}"></script>
  <script src="{plugin_sdk_url}"></script>
  <script src="{perf_url}"></script>
  <script src="{filter_state_url}"></script>
  <script src="{filter_controls_url}"></script>
  <script src="{icons_url}"></script>
  <script src="{tree_expansion_url}"></script>
  <script src="{tree_filter_model_url}"></script>
  <script src="{pending_tally_diagnostics_url}"></script>
  {plugin_asset_config}
  <script src="{app_url}"></script>
  {optional_assets_block}
</body>
</html>"""
    if page_capabilities.active_content:
        return HTMLResponse(html)
    # An untrusted source: the page runs only what this server wrote. Every inline script
    # of the shell carries this response's nonce (capabilities.untrusted_shell_csp).
    nonce = secrets.token_urlsafe(18)
    html = html.replace("<script>", f'<script nonce="{nonce}">')
    origin = f"{request.url.scheme}://{request.url.netloc}"
    return HTMLResponse(
        html,
        headers={
            "Content-Security-Policy": untrusted_shell_csp(
                nonce,
                origin,
                tuple(
                    kpress_adapter.kpress_static_url(module, prefix=kpress_prefix)
                    for module in kpress_adapter.DIAGRAM_MODULES
                ),
                remote_images=not block_remote_images,
            ),
            "X-Frame-Options": "DENY",
            # No page address goes to an image's host, from an image the allowlist wrote
            # (`referrerpolicy` on it says so too) or one a Mermaid diagram drawn in the
            # page names, which no markup of the document reaches
            # (`builtin_plugins/markdown/diagram-frame.js`). Nothing here reads a Referer.
            "Referrer-Policy": "no-referrer",
        },
    )


def _shell_folder(root: Path | None) -> Path:
    """The folder a shell was rendered for, read with its subject at the request's start."""

    if root is None:
        raise UnsupportedSourceCapabilityError("filesystem")
    return root


async def view_shell(request: Request) -> Response:
    """Serve the SPA shell only for one safely encoded canonical view path."""

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes):
        return PlainTextResponse("Invalid view path.", status_code=400)
    crossed: str | None = None
    if as_git_revision_subject(get_source_session().subject) is not None:
        from metabrowser.git.content_routes import decode_git_view_path

        decoded = decode_git_view_path(raw_path)
        if decoded is None:
            # A folder's address on a revision of its checkout: a tab, a history entry,
            # or a bookmark from the working tree. It goes where a switch would send it.
            crossed = await crossed_view_href(raw_path)
    else:
        decoded = decode_safe_view_path(raw_path)
        # A revision's address on its checkout's working tree, unless the folder has an
        # entry by that very name.
        if (
            decoded is not None
            and decoded.startswith("g1-")
            and not await asyncio.to_thread(_view_path_exists, decoded)
        ):
            crossed = await crossed_view_href(raw_path)
    if crossed is not None:
        return RedirectResponse(crossed, status_code=307)
    if decoded is None:
        return PlainTextResponse("Invalid view path.", status_code=400)
    return await index(request, view_path=decoded)


def _view_path_exists(decoded: str) -> bool:
    target = _safe_path(decoded)
    try:
        return target is not None and target.exists()
    except OSError:
        return False


async def commit_shell(request: Request) -> Response:
    """Serve the SPA shell for ``/commit/<rev>[/<file>]``.

    One route per address space (see the Browser URL Grammar): revisions
    are not served-tree paths, so they are addressed here rather than
    through an escape inside ``/view/``.
    """

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes) or decode_safe_commit_route(raw_path) is None:
        return PlainTextResponse("This address is not a commit.", status_code=400)
    return await index(request, commit_page=True)


async def pull_shell(request: Request) -> Response:
    """Serve the SPA shell for a pull request page and its subroutes.

    A pull request is its own address space, like a commit: the page is not a path in
    the served tree, and a changed file's path is one in its comparison, never on disk.
    The view that renders it is the one a plugin registers for the `pull-request` kind;
    the pull route says what this server has of that number.
    """

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes) or decode_safe_pull_route(raw_path) is None:
        return PlainTextResponse("This address is not a pull request.", status_code=400)
    return await index(request, pull_page=True)


async def stack_shell(request: Request) -> Response:
    """Serve the SPA shell for a native stack's page and its subroutes.

    A stack is an address space of its own, as a pull request is, and its shell is a pull
    request page's: the Pulls tab in front and the same startup script. The view that
    renders it is the one a plugin registers for the `pull-stack` kind; the stack route
    says what this server has of that number.
    """

    raw_path = request.scope.get("raw_path")
    if not isinstance(raw_path, bytes) or decode_safe_stack_route(raw_path) is None:
        return PlainTextResponse("Invalid stack route.", status_code=400)
    return await index(request, pull_page=True)


async def pulls_shell(request: Request) -> Response:
    """Serve the SPA shell for ``/pulls``, a repository's list of pull requests.

    It belongs to the pull-request address space and adds no startup script. The list route
    says what this server has to list, which on a folder is nothing.
    """

    return await index(request, pull_list=True)


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
    rather than a 400. `group` names one Group by group, `<by>:<id>`
    (metabrowser/tree_groups.py), which narrows the tree as one more filter.
    """

    return TreeFilter(
        recency_seconds=parse_recency(request.query_params.get("recency", "")),
        types=parse_types(_query_values(request, "types")),
        min_size=parse_size_floor(request.query_params.get("min_size", "")),
        include_ignored=request.query_params.get("include_ignored", "1") not in ("0", "false"),
        group=parse_group(request.query_params.get("group", "")),
    )


def _inventory_filter(tree_filter: TreeFilter, *, as_of_ns: int) -> InventoryFilter:
    """Translate the shared navigation vocabulary into the provider contract."""

    extensions = tuple(token for token in tree_filter.types if token.startswith("."))
    filenames = tuple(token for token in tree_filter.types if not token.startswith("."))
    group = tree_filter.group
    recency: float | None = (
        float(tree_filter.recency_seconds) if tree_filter.recency_seconds else None
    )
    band_within: float | None = None
    older_than: float | None = None
    if group is not None and group.by == "age":
        # An age group is a band of its own; the recency window, a filter, cuts it as the
        # provider applies both (metabrowser/tree_groups.py, `age_band`).
        band = age_band(group, 0)
        band_within = band.within_seconds
        older_than = band.older_than_seconds
    timed = recency is not None or band_within is not None or older_than is not None
    return InventoryFilter(
        extensions=extensions,
        filenames=filenames,
        recency_seconds=recency,
        band_within_seconds=band_within,
        older_than_seconds=older_than,
        type_group=group.id if group is not None and group.by == "type" else None,
        minimum_size=tree_filter.min_size or None,
        include_ignored=tree_filter.include_ignored,
        as_of_ns=as_of_ns if timed else None,
    )


def _inventory_runtime_for(request: Request) -> InventoryRuntime:
    runtime = getattr(request.app.state, "inventory_runtime", None)
    if not isinstance(runtime, InventoryRuntime):
        raise RuntimeError("the application inventory runtime is not available")
    return runtime


def _index_status_from_state(phase: LifecyclePhase, *, complete: bool, budget: bool) -> str:
    # The budget first: the walk it stops is STOPPED, which would otherwise read as "idle".
    # `events_route._status_from_phase` and `walk.py` answer in this order too.
    if budget:
        return "truncated"
    if phase is LifecyclePhase.DISCOVERING:
        return "scanning"
    if phase is LifecyclePhase.FAILED:
        return "failed"
    if phase is LifecyclePhase.STOPPED:
        return "idle"
    return "done" if complete else "scanning"


async def _read_tree_from_provider(
    request: Request,
    *,
    subpath: str,
    remaining_depth: int,
    tree_filter: TreeFilter,
) -> JSONResponse:
    payload = await _tree_payload_from_provider(
        request,
        subpath=subpath,
        remaining_depth=remaining_depth,
        tree_filter=tree_filter,
        as_of_ns=time.time_ns(),
    )
    if payload is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(payload)


async def _read_with_known_parent[T](
    runtime: InventoryRuntime,
    *,
    subpath: str,
    remaining_depth: int,
    read: Callable[[], Awaitable[T]],
    first_read: Callable[[T], CoordinatedRead],
) -> tuple[T, EntryProjection]:
    """Run *read*, whose first read carries the `tree-parent` entry query, and on a cold
    start, while the index cannot yet say whether *subpath* exists, prioritize it and read
    again for up to `_TREE_COLD_START_WAIT_S`."""

    def parent_of(answer: T) -> EntryProjection:
        parent = first_read(answer).result.completed_projection("tree-parent")
        if not isinstance(parent, EntryProjection):
            raise TypeError("the tree parent query returned the wrong projection")
        return parent

    answer = await read()
    parent = parent_of(answer)
    if parent.presence is EntryPresence.UNKNOWN:
        if subpath:
            await runtime.coordinator.prioritize(
                PriorityRequest(paths=(subpath,), max_depth=max(1, remaining_depth))
            )
        deadline = asyncio.get_running_loop().time() + _TREE_COLD_START_WAIT_S
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.005)
            answer = await read()
            parent = parent_of(answer)
            if parent.presence is not EntryPresence.UNKNOWN:
                break
    return answer, parent


def _root_totals(root: InventoryEntry | None) -> dict[str, int] | None:
    """The served root's tracked and ignored files and bytes, from its own aggregates.

    The root's entry carries its descendant totals with and without ignored files, which
    the provider keeps current on every write, so this costs nothing beyond reading one
    entry. They are the figures the navigation tally's pass over every file counts
    (`root_summary`), in the same shape as its `summary`, and the shell inlines them so the
    Files totals line paints both halves from its first frame. None while the walk has
    not finished the root, whose totals are pending until then.
    """

    if (
        root is None
        or root.total_files is None
        or root.total_size is None
        or root.unignored_files is None
        or root.unignored_size is None
    ):
        return None
    return {
        "files": root.unignored_files,
        "size": root.unignored_size,
        "ignored_files": root.total_files - root.unignored_files,
        "ignored_size": root.total_size - root.unignored_size,
    }


def _is_folder(parent: EntryProjection) -> bool:
    """Whether the tree's parent may be a folder: present as one, or not yet known."""

    return not (
        parent.presence is EntryPresence.ABSENT
        or (
            parent.presence is EntryPresence.PRESENT
            and (parent.entry is None or parent.entry.type is not EntryType.DIRECTORY)
        )
    )


async def _grouped_tree_from_provider(
    request: Request,
    *,
    subpath: str,
    remaining_depth: int,
    tree_filter: TreeFilter,
    group_by: GroupBy,
) -> JSONResponse:
    """`/api/tree?group_by=`: every group's tree under the filter, from one grouped read.

    The provider computes every group from one pass over the index at one version
    (`GroupedTreeQuery`), and cuts every age band at one instant, so the bands partition
    mtimes and a file written mid-request is counted in one group or in none.
    """

    runtime = _inventory_runtime_for(request)
    as_of_ns = time.time_ns()
    groups = tuple(
        group
        for group in groups_for(group_by)
        if not (group.by == "age" and age_band(group, tree_filter.recency_seconds).empty)
    )
    shared = _inventory_filter(tree_filter, as_of_ns=as_of_ns)
    if group_by == "age":
        shared = replace(shared, as_of_ns=as_of_ns)
    query = GroupedTreeQuery(
        query_id="tree-groups",
        groups=tuple(inventory_group_filter(group) for group in groups),
        path=subpath,
        max_depth=max(1, remaining_depth),
        max_rows=INVENTORY_TREE_PAGE_ROWS,
        filter=shared,
    )

    async def read_groups() -> GroupedTreeAssembly:
        # One grouped assembly at a time, so overlapping reads cannot evict each other's
        # continuations (InventoryRuntime.grouped_tree_admission).
        async with runtime.grouped_tree_admission:
            return await assemble_grouped_tree(
                runtime.coordinator,
                query=query,
                companion_queries=(EntryQuery(query_id="tree-parent", path=subpath),),
            )

    assembly, parent = await _read_with_known_parent(
        runtime,
        subpath=subpath,
        remaining_depth=remaining_depth,
        read=read_groups,
        first_read=lambda answer: answer.first_read,
    )
    if not _is_folder(parent):
        return JSONResponse({"error": "Not found"}, status_code=404)
    parent_ignored = bool(parent.entry.gitignored) if parent.entry is not None else False
    rows: list[dict[str, Any]] = []
    for group, answer in zip(groups, assembly.groups, strict=True):
        rows.append(
            group_row(
                group,
                {
                    "filtered": {
                        "files": answer.matching_files,
                        "size": answer.matching_bytes,
                        "entries": answer.matching_leaves,
                    },
                    "tree": (
                        build_inventory_tree_from_entries(
                            entries=answer.entries,
                            parent_rel=subpath,
                            max_depth=remaining_depth,
                            parent_ignored=parent_ignored,
                        )
                        if remaining_depth > 0
                        else []
                    ),
                },
            )
        )
        # Each group's tree, and then the body, takes an event-loop turn of its own. On
        # 200,000 files in 20 folders, where a depth-2 tree lists every file, building
        # every tree and the JSON in one turn held the loop for 0.80-0.98 s; a turn each
        # holds it for 0.33-0.64 s, the largest group's tree or the body (measured in
        # process, warm, with a 5 ms ticker beside the request, 2026-11-15).
        await asyncio.sleep(0)
    state = assembly.final_read.result.state
    envelope = {
        "root": str(session_filesystem_root()),
        "tally_cache_status": _index_status_from_state(
            state.phase,
            complete=state.coverage.complete,
            budget=any(issue.code.value == "resource_budget" for issue in state.issues),
        ),
        "tally_cache_max_files": runtime.config.budget.max_files,
    }
    return JSONResponse(groups_payload(group_by, rows, envelope))


async def _tree_payload_from_provider(
    request: Request,
    *,
    subpath: str,
    remaining_depth: int,
    tree_filter: TreeFilter,
    as_of_ns: int,
) -> dict[str, Any] | None:
    """One /api/tree answer from the inventory, or None when *subpath* is no folder.

    *as_of_ns* is the instant every time filter is cut at.
    """

    runtime = _inventory_runtime_for(request)
    companion_queries: list[ReadQuery] = [EntryQuery(query_id="tree-parent", path=subpath)]
    projection_id = "tree-filtered" if tree_filter.active else "tree-directory"
    page_query: TreePageQuery | None = None
    if tree_filter.active:
        page_query = FilteredTreeQuery(
            query_id=projection_id,
            path=subpath,
            max_depth=max(1, remaining_depth),
            max_rows=INVENTORY_TREE_PAGE_ROWS,
            filter=_inventory_filter(tree_filter, as_of_ns=as_of_ns),
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

    (read, assembly), parent = await _read_with_known_parent(
        runtime,
        subpath=subpath,
        remaining_depth=remaining_depth,
        read=read_tree,
        first_read=lambda answer: answer[0],
    )
    if not _is_folder(parent):
        return None

    tree_entries = ()
    filtered_projection: FilteredTreeProjection | None = None
    if assembly is not None:
        projection = assembly.projection
        if isinstance(projection, FilteredTreeProjection):
            filtered_projection = projection
        tree_entries = projection.entries

    root_dir = session_filesystem_root()
    tree = (
        build_inventory_tree_from_entries(
            entries=tree_entries,
            parent_rel=subpath,
            max_depth=remaining_depth,
            parent_ignored=bool(parent.entry.gitignored) if parent.entry is not None else False,
        )
        if remaining_depth > 0
        else []
    )
    navigation = None
    if navigation_id is not None:
        candidate = read.result.completed_projection(navigation_id)
        if not isinstance(candidate, NavigationProjection):
            raise TypeError("the navigation query returned the wrong projection")
        navigation = candidate.payload
    state = assembly.final_read.result.state if assembly is not None else read.result.state
    status = _index_status_from_state(
        state.phase,
        complete=state.coverage.complete,
        budget=any(issue.code.value == "resource_budget" for issue in state.issues),
    )
    return {
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
        "tally_cache_max_files": runtime.config.budget.max_files,
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


@log_async_calls()
async def api_tree(request: Request) -> Response:
    requested = request.query_params.get("path", "")
    depth_str = request.query_params.get("depth", "")
    tree_filter = tree_filter_from_request(request)
    # `group_by` without `group` asks for the groups themselves (`tree_groups.groups_payload`).
    group_by = (
        parse_group_by(request.query_params.get("group_by", ""))
        if tree_filter.group is None
        else None
    )
    require_source_capability("navigation")
    require_source_capability("index")
    pin = as_git_revision_subject(get_source_session().subject)
    git_pin = pin is not None
    require_filter_capabilities(
        # An age group is a recency band: a source without mtimes has none to offer.
        recency=bool(tree_filter.recency_seconds)
        or group_by == "age"
        or (tree_filter.group is not None and tree_filter.group.by == "age"),
        # Ignore is absent on a pin: unignored equals total, so hiding
        # ignored files is a no-op rather than unsupported_for_subject.
        include_ignored=True if git_pin else tree_filter.include_ignored,
    )
    if pin is not None:
        from metabrowser.git.content_routes import git_revision_tree, git_revision_tree_groups

        if group_by is not None:
            return await git_revision_tree_groups(request, pin, tree_filter, group_by)
        return await git_revision_tree(request, pin, tree_filter)
    if tree_filter.group is not None and tree_filter.group.id == UNDATED_GROUP_ID:
        # Only a Git revision has files with no time.
        return JSONResponse({"error": "Not found"}, status_code=404)
    subpath = parse_inventory_path(requested)
    remaining_depth = _tree_depth_from_query(depth_str)
    if subpath is None or resolve_session_identity(subpath) is None:
        return JSONResponse({"error": "Not found"}, status_code=404)

    if group_by is not None:
        return await _grouped_tree_from_provider(
            request,
            subpath=subpath,
            remaining_depth=remaining_depth,
            tree_filter=tree_filter,
            group_by=group_by,
        )

    return await _read_tree_from_provider(
        request,
        subpath=subpath,
        remaining_depth=remaining_depth,
        tree_filter=tree_filter,
    )


@log_async_calls(if_slower_than=0.1)
async def api_rollup(request: Request) -> Response:
    """Bounded treemap rollup for a directory subtree.

    `GET /api/rollup?path=&depth=&top=&nodes=&ext_top=&filename_top=&remaining_top=`
    `&ext_rank=&ignored=&encoding=` clamps the numeric parameters to the ROLLUP_*
    settings bounds, and `max` asks for the bound itself (the Treemap asks for
    `depth=max&top=max&nodes=max`). `nodes` is the node budget, ROLLUP_DEFAULT_NODES
    unless named, which expands the heaviest folders first and gives each the share
    of it `_emit_limit` in `inventory_rollup.py` sets. `node` is null while the
    index cannot serve the path yet (cold start); the client renders that as a
    pending treemap and refreshes off `/api/events` activity. Totals always
    cover the full subtree. `children: null`, without a rest bucket, means the
    directory was not expanded: it is at `depth`, or the node budget did not
    reach it. A directory whose children ran past `top` or its share of the node
    budget keeps the emitted `children` and a `rest` bucket for the omitted
    siblings.

    `ignored=exclude` leaves gitignored entries out of `children` and `rest` and
    spends none of the budget on them; every total, tally, and breakdown is as with
    `include`, the default. `encoding=compact` writes each expanded directory's
    file children as `[name, size, mtime, ext, gitignored]` entries in its `files`
    array, with only directories in `children`, and says `"encoding": "compact"`
    in the envelope; `json`, the default, writes neither. A client derives a
    compact file's path as its folder's path, a `/`, and its name, which a Git
    pin's wire paths are not, so a pin always answers `json`. The shapes are
    `RollupDirNode` and `RollupCompactFile` in `wire_models.py`, and the folder
    aggregate helpers in `docs/plugins.md` describe them. A Git pin answers from
    recursive blob names and sizes and omits mtime.
    """

    require_source_capability("navigation")
    require_source_capability("index")
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
        ignored = cast(
            RollupIgnored,
            _query_choice(request, "ignored", "include", frozenset({"include", "exclude"})),
        )
        encoding = cast(
            RollupEncoding,
            _query_choice(request, "encoding", "json", frozenset({"json", "compact"})),
        )
    except ValueError as error:
        return JSONResponse(
            {"error": "This folder summary could not be made.", "detail": str(error)},
            status_code=400,
        )
    nodes = _query_bounded_int(
        request, "nodes", ROLLUP_DEFAULT_NODES, minimum=1, maximum=ROLLUP_MAX_NODES
    )

    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        from metabrowser.git.content_routes import git_revision_rollup

        return await git_revision_rollup(
            request,
            pin,
            RollupOptions(
                depth=depth,
                top=top,
                ext_top=ext_top,
                max_nodes=nodes,
                remaining_top=remaining_top,
                filename_top=filename_top,
                ext_rank=ext_rank,
                omit_mtime=True,
                ignored=ignored,
                # A pin's paths are wire tokens (``GitPath.to_wire``), not the folder's
                # path, a `/`, and the display name a compact entry carries, so a pin
                # answers the JSON encoding, and its envelope says no other.
                encoding="json",
            ),
        )

    require_filesystem_hooks()
    requested = request.query_params.get("path", "")
    subpath = parse_inventory_path(requested)
    if subpath is None or resolve_session_identity(subpath) is None:
        return JSONResponse({"error": "Not found"}, status_code=404)

    runtime = _inventory_runtime_for(request)
    preflight = await runtime.coordinator.read(
        ReadRequest(queries=(EntryQuery(query_id="rollup-parent", path=subpath),))
    )
    parent = preflight.result.completed_projection("rollup-parent")
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
        max_nodes=nodes,
        top=top,
        extension_top=ext_top,
        remaining_top=remaining_top,
        filename_top=filename_top,
        rank=ext_rank,
        ignored=ignored,
        encoding=encoding,
    )
    diagnostics = DiagnosticsQuery(query_id="rollup-diagnostics")
    request_shape = (
        f"{subpath}-{depth}.{top}.{nodes}.{ext_top}.{remaining_top}.{filename_top}."
        f"{ext_rank}.{ignored}.{encoding}"
    )

    def etag_for(version: HostVersion) -> str:
        engine = version.engine
        return build_scoped_etag(
            f"rollup-{session_filesystem_root()}-{engine.session}-{engine.sequence}-"
            f"{engine.scope_fingerprint}-{engine.semantic_fingerprint}-{request_shape}"
        )

    async def encode(*, at_version: EngineVersion | None = None) -> tuple[str, bytes]:
        coordinated = await runtime.coordinator.read(
            ReadRequest(
                queries=(query, diagnostics),
                at_version=at_version,
            )
        )
        rollup = coordinated.result.completed_projection("rollup")
        diagnostic = coordinated.result.completed_projection("rollup-diagnostics")
        if not isinstance(rollup, RollupProjection) or not isinstance(
            diagnostic, DiagnosticsProjection
        ):
            raise TypeError("the rollup read returned the wrong projections")
        payload = rollup.payload
        breakdown = payload.get("file_type_breakdown") if payload is not None else None
        state = coordinated.result.state
        indexed_files = diagnostic.payload.files_indexed
        status = _index_status_from_state(
            state.phase,
            complete=state.coverage.complete,
            budget=any(issue.code.value == "resource_budget" for issue in state.issues),
        )
        body = bytes(
            JSONResponse(
                {
                    "root": str(session_filesystem_root()),
                    "path": subpath,
                    **({"encoding": "compact"} if encoding == "compact" else {}),
                    "node": payload.get("node") if payload is not None else None,
                    "ext_tallies": (payload.get("ext_tallies", []) if payload is not None else []),
                    "file_type_breakdown": breakdown,
                    "file_type_legend": build_file_type_legend(breakdown),
                    "index_status": status,
                    "indexed_files": indexed_files,
                    "max_files": runtime.config.budget.max_files,
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
async def api_recent(request: Request) -> Response:
    """``GET /api/recent`` — top-N files by mtime within a
    rolling window (1h / 24h / 7d / 30d / all), filtered by
    the navigation filter vocabulary plus optional ``prefix`` and
    legacy ``ext`` query params, returned as flat leaves for browser
    clustering (see :mod:`metabrowser.recent`).
    """

    require_source_capability("recency")
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
    requested_filter = tree_filter_from_request(request)
    # `ext` predates the navigation vocabulary and remains useful for direct
    # CLI inspection. Merge it into `types` so one provider predicate decides
    # both spellings before the response cap is applied.
    types = parse_types((*requested_filter.types, *ext_filter))
    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        # A revision has no inventory: the newest files by the time of their last commit.
        from metabrowser.git.content_routes import git_revision_recent

        return await git_revision_recent(
            pin,
            window=window,
            limit=limit,
            types=types,
            min_size=requested_filter.min_size,
            prefix=prefix_filter,
        )
    recent_filter = TreeFilter(
        recency_seconds=int(RECENT_WINDOW_SECONDS[window] or 0),
        types=types,
        min_size=requested_filter.min_size,
        include_ignored=requested_filter.include_ignored,
    )
    require_filter_capabilities(
        recency=True,
        include_ignored=recent_filter.include_ignored,
    )
    as_of_ns = time.time_ns()
    selection = _inventory_filter(recent_filter, as_of_ns=as_of_ns)

    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(
            queries=(
                RecentQuery(
                    query_id="recent",
                    max_rows=limit,
                    as_of_ns=as_of_ns,
                    prefix=prefix_filter,
                    filter=selection,
                ),
            )
        )
    )
    projection = coordinated.result.completed_projection("recent")
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
            "root": str(session_filesystem_root()),
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
            "total_matching_exact": result.total_matching_exact,
            "truncated": result.truncated,
            "tally_cache_status": tally_cache_status,
        }
    )


def _markdown_frontmatter(ctx: FileContext, ext: str) -> tuple[dict[str, Any] | None, str | None]:
    """A Markdown file's frontmatter and the reason it has none, for a worker thread.

    ``FileContext.frontmatter`` is already the bounded, JSON-safe copy
    (:mod:`metabrowser.frontmatter_yaml`); parsing it can still take seconds at the
    byte bound (``FRONTMATTER_MAX_BYTES`` records how many), so callers run this off
    the event loop.
    """

    if ext != ".md":
        return None, None
    return ctx.frontmatter, ctx.frontmatter_parse_error


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
        # Serialization is the first half of the `encode` phase (metabrowser.server_timing).
        with server_timing.phase("encode"):
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


def _file_mtime(target: Path) -> float | None:
    """A served file's modification time in epoch seconds, or ``None`` if it cannot be read.

    The envelope's ``mtime`` is what a file's view header shows as its age, in the unit a
    folder envelope's ``dir.mtime`` and a tree row's ``mtime`` use.
    """

    try:
        return target.stat().st_mtime
    except OSError:
        return None


def _mtime_field(mtime: float | None) -> dict[str, float]:
    """``{"mtime": ...}``, or nothing when the time could not be read: never a null,
    which the browser reads as a value still on its way."""

    return {} if mtime is None else {"mtime": mtime}


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


def _jsonl_failure_message(exc: OSError | TypeError | ValueError) -> str:
    """The reader's sentence for a JSONL log that could not be parsed; the failure's own
    account is the answer's ``detail``."""
    if isinstance(exc, JsonlParseLimitError):
        return "This log is too large to show here."
    if isinstance(exc, ContentReadError):
        return exc.reader_message
    if isinstance(exc, OSError):
        return "This file cannot be read."
    return "This log could not be read."


def _api_file_internal_error_response(subpath: str, exc: Exception) -> JSONResponse:
    """Return a renderable file-error envelope instead of bubbling a 500."""
    target = resolve_session_identity(subpath)
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
            "error": "An unexpected error stopped this preview.",
            "detail": f"Internal error while rendering this file. {type(exc).__name__}: {exc}",
            "warning": (
                "Metabrowser returned a degraded error view instead of a server 500. "
                "Check the server log for the traceback."
            ),
        }
    )


def _folder_not_indexed(subpath: str, target: Path) -> str | None:
    """Why the inventory's scope leaves out this served folder, or None if it does not.

    *target* is already resolved, so a symlink anywhere on the path shows as a target
    other than the path's own spelling under the root.
    """

    if not is_visible_segment(subpath):
        return "hidden"
    native = native_inventory_path(subpath)
    if subpath and native is not None and target != _paths_safe.ROOT_DIR.resolve() / native:
        return "symlink"
    return None


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

    The inventory's scope leaves out hidden path components and does not follow
    symlinks, so a folder reached either way has no tree, no rollup, and aggregates
    that will never arrive. It still gets this envelope, so its page and README show;
    `dir.not_indexed` names which it is, so the page can say why rather than wait.
    """

    key = parse_inventory_path(subpath)
    if key is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    subpath = key
    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(queries=(EntryQuery(query_id="folder", path=subpath),))
    )
    projection = coordinated.result.completed_projection("folder")
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
        "views": (
            await asyncio.to_thread(_views_for_kind, "folder", target=target)
            if _FOLDER_OFFERS
            else _views_for_kind("folder")
        ),
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
    not_indexed = _folder_not_indexed(subpath, target)
    if not_indexed is not None:
        payload["dir"]["not_indexed"] = not_indexed
    return JSONResponse(payload, headers={"cache-control": "no-store"})


@log_async_calls(if_slower_than=0.1)
async def api_file(request: Request) -> JSONResponse | Response:
    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        from metabrowser.git.content_routes import git_revision_file

        return await git_revision_file(request, pin)
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
    native = native_inventory_path(subpath)
    requested = Path(native) if native is not None else Path()
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
    target = resolve_session_identity(subpath)
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
    file_mtime = _file_mtime(target)
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
                **_mtime_field(file_mtime),
                **_compression_identity_fields(artifact),
            }
        )

    try:
        # Validated compression scans must not run on the event loop.
        with server_timing.phase("read"):
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
                    **_mtime_field(file_mtime),
                    "error": exc.reader_message,
                    "detail": str(exc),
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
                **_mtime_field(file_mtime),
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
    default_text_limit = _TEXT_PREVIEW_CHUNK_BYTES
    if (
        requested_text_offset == 0
        and syntax_language_for_path(artifact.logical_name, ext)
        and _SYNTAX_HIGHLIGHT_MAX_BYTES > 0
    ):
        default_text_limit = min(default_text_limit, _SYNTAX_HIGHLIGHT_MAX_BYTES)
    text_limit = max(
        1,
        min(
            _query_int(request, "limit", default_text_limit),
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
                "error": "This part of the file is past what can be shown here.",
                "detail": "Requested preview window exceeds the decompression budget",
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

            with server_timing.phase("read"):
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
                    **_mtime_field(file_mtime),
                    "mtime_hash": mtime_hash,
                    **compression_fields,
                    **parsed,
                },
                headers=etag_headers,
            )
        except (OSError, TypeError, ValueError) as exc:
            return JSONResponse(
                {
                    "type": "error",
                    "kind": "error",
                    "views": [],
                    "path": subpath,
                    "error": _jsonl_failure_message(exc),
                    "detail": str(exc),
                }
            )

    if ext in BROWSER_IMAGE_EXTS:
        return JSONResponse(
            {
                "type": "image",
                "kind": "image",
                "views": _views_for_kind("image"),
                "path": subpath,
                "size": disk_size,
                **_mtime_field(file_mtime),
                "mtime_hash": mtime_hash,
                **compression_fields,
            },
            headers=etag_headers,
        )

    disk_prefix: bytes | None = None
    with server_timing.phase("read"):
        if ext in BROWSER_TEXT_EXTS:
            text_body = True
        else:
            text_body, disk_prefix = await asyncio.to_thread(_sniff_text_body, target)
    if text_body:
        try:
            content_has_more = False
            if (
                artifact.is_compressed
                or text_offset > 0
                or (logical_size is not None and logical_size > text_limit)
            ):
                with server_timing.phase("read"):
                    chunk = await asyncio.to_thread(
                        _read_artifact_text_chunk, artifact, text_offset, text_limit
                    )
                content, content_bytes, bytes_read, content_has_more = chunk
            else:
                with server_timing.phase("read"):
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
                        **_mtime_field(file_mtime),
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
                    **_mtime_field(file_mtime),
                    "error": exc.reader_message,
                    "detail": str(exc),
                    **compression_fields,
                }
            )
        except OSError:
            return JSONResponse(
                {
                    "type": "binary",
                    "path": subpath,
                    "size": disk_size,
                    **_mtime_field(file_mtime),
                    **compression_fields,
                }
            )

        if text_offset > 0:
            return JSONResponse(
                {
                    "type": "text_chunk",
                    "path": subpath,
                    "size": disk_size,
                    **_mtime_field(file_mtime),
                    "mtime_hash": mtime_hash,
                    "content": content,
                    "content_offset": text_offset,
                    "content_bytes": content_bytes,
                    "bytes_read": bytes_read,
                    "content_truncated": content_has_more
                    or (logical_size is not None and bytes_read < logical_size),
                    "content_preview_limit": text_limit,
                    "content_max_preview_limit": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
                    "highlight_disabled": (
                        _SYNTAX_HIGHLIGHT_MAX_BYTES <= 0 or bytes_read > _SYNTAX_HIGHLIGHT_MAX_BYTES
                    ),
                    **compression_fields,
                },
                headers=etag_headers,
            )

        # Build the FileContext once so frontmatter parsing + classification
        # share a cached result; plugin classification may consult frontmatter
        # for specialized document detection.
        ctx = FileContext(target, ext)

        # For .md files, expose parsed frontmatter so plugin renderers can
        # use it directly via ctx.frontmatter without re-parsing client-side.
        # Malformed YAML fences must NOT silently fall through to markdown;
        # surface the parse error on the response so the operator sees it
        # instead of quietly substituting an empty frontmatter object.
        def _classify_text_views() -> tuple[
            str, list[dict[str, Any]], dict[str, Any] | None, str | None
        ]:
            classified = _classify_with_plugins(target, ext, file_ctx=ctx)
            return (
                classified,
                _views_for_kind(classified, target=target),
                *_markdown_frontmatter(ctx, ext),
            )

        with server_timing.phase("read"):
            kind, views, frontmatter, frontmatter_error = await asyncio.to_thread(
                _classify_text_views
            )
        result: dict[str, Any] = {
            "type": "text",
            "kind": kind,
            "views": views,
            "path": subpath,
            "ext": ext,
            "size": disk_size,
            **_mtime_field(file_mtime),
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
                _SYNTAX_HIGHLIGHT_MAX_BYTES <= 0 or bytes_read > _SYNTAX_HIGHLIGHT_MAX_BYTES
            ),
            **compression_fields,
        }
        if frontmatter is not None:
            result["frontmatter"] = frontmatter
        result |= frontmatter_error_fields(frontmatter_error)
        # Rendered Markdown is fetched separately through the KPress route.
        # Keeping this payload source-only avoids duplicating the rendered
        # document in the normal file response.
        return JSONResponse(result, headers=etag_headers)

    # A plugin kind that claims a binary format by its magic number, whatever the
    # file's name, then a plugin's claim by path; the model stays the file's bytes.
    binary_kind = _magic_kind(disk_prefix) or _binary_kind(target, ext)
    return JSONResponse(
        {
            "type": "binary",
            "kind": binary_kind,
            "views": _views_for_kind(binary_kind),
            "path": subpath,
            "size": disk_size,
            **_mtime_field(file_mtime),
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


class _JsonRequestLimitError(ValueError):
    """Raised as soon as a streamed JSON request crosses its byte cap."""


async def _read_bounded_json_request(request: Request, max_bytes: int) -> Any:
    """Parse one JSON request without consuming or retaining bytes past *max_bytes*."""
    body = bytearray()
    async for chunk in request.stream():
        if len(chunk) > max_bytes - len(body):
            raise _JsonRequestLimitError(f"request body exceeds {max_bytes} bytes")
        body.extend(chunk)
    return await asyncio.to_thread(_json.loads, body)


# Transformed source can contain one six-byte JSON escape per source byte, plus
# bounded envelope fields. Export has no inline source, so one 64 KiB envelope
# leaves ample room for every supported path and option without an unbounded read.
_KPRESS_RENDER_REQUEST_MAX_BYTES = (_TEXT_PREVIEW_MAX_CHUNK_BYTES * 6) + (64 * 1024)
_KPRESS_EXPORT_REQUEST_MAX_BYTES = 64 * 1024
# The largest request body a route reads: KPress render's, 96 MiB by default, past
# export's and the pending-tally diagnostic's 64 KiB, a source route's 4 KiB, and the
# GitHub routes' 1 KiB (tests/test_cli_api_mode.py checks it). `metab --api --data`
# reads no more than this before it refuses, so a body no route takes is never held.
MAX_REQUEST_BODY_BYTES: Final = _KPRESS_RENDER_REQUEST_MAX_BYTES


def _kpress_render_refusal(detail: str) -> JSONResponse:
    """A render request the route cannot read: the reader's sentence, and *detail* for
    the request's author."""
    return JSONResponse(
        {
            "type": "kpress_render_error",
            "error": kpress_adapter.RENDER_FAILED_MESSAGE,
            "detail": detail,
        },
        status_code=400,
    )


def _unreadable_file(exc: OSError) -> JSONResponse:
    """A file that cannot be read; the operating system's words are the detail."""
    return JSONResponse({"error": "This file cannot be read.", "detail": str(exc)}, status_code=404)


def _frontmatter_detail(reason: str | None) -> dict[str, str]:
    """A render's ``frontmatter_error_detail``: why front matter KPress was told could not
    be read was refused, beside the reader's sentence its ``frontmatter_error`` holds."""
    return {} if reason is None else {"frontmatter_error_detail": reason}


@log_async_calls(if_slower_than=0.1)
async def api_kpress_render(request: Request) -> Response:
    """Render a safe served-root-relative file through the KPress adapter."""

    source_override: str | None = None
    if getattr(request, "method", "GET") == "POST":
        try:
            with server_timing.phase("read"):
                body = await _read_bounded_json_request(request, _KPRESS_RENDER_REQUEST_MAX_BYTES)
        except _JsonRequestLimitError:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                    "detail": "Render request exceeds safety limits",
                    "max_size": _KPRESS_RENDER_REQUEST_MAX_BYTES,
                },
                status_code=413,
            )
        except (_json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _kpress_render_refusal(f"Invalid JSON body: {exc}")
        if not isinstance(body, dict):
            return _kpress_render_refusal("Request body must be a JSON object")
        subpath = body.get("path", "")
        view = body.get("view", "document")
        profile_value = body.get("profile")
        source_override = body.get("source_text")
        # Same JSON-type contract as export: an absent or null profile means
        # the default, and a present one must be a string. `false` or `0` is a
        # malformed body, not a request for the default.
        if (
            not all(isinstance(value, str) for value in (subpath, view))
            or not isinstance(source_override, str)
            or (profile_value is not None and not isinstance(profile_value, str))
        ):
            return _kpress_render_refusal("Invalid render body fields")
        profile = profile_value or None
        try:
            source_size = len(source_override.encode())
        except UnicodeEncodeError as exc:
            return _kpress_render_refusal(f"Invalid transformed source encoding: {exc}")
        if source_size > _TEXT_PREVIEW_MAX_CHUNK_BYTES:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                    "detail": "Transformed source exceeds safety limits",
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
                "error": kpress_adapter.RENDER_FAILED_MESSAGE,
                "detail": f"Invalid toc: {include_toc!r}; expected 'auto', 'on', or 'off'",
                "diagnostics": [],
            },
            status_code=400,
        )

    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        from metabrowser.git.content_routes import git_revision_kpress_render

        return await git_revision_kpress_render(
            pin,
            request=request,
            subpath=subpath,
            view=view,
            profile=profile,
            source_override=source_override,
            include_toc=include_toc,
            max_bytes=_TEXT_PREVIEW_MAX_CHUNK_BYTES,
        )

    target = resolve_session_identity(subpath)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    artifact = ArtifactPath(target)
    ext = artifact.logical_ext
    content: str | None = source_override
    try:
        disk_size = artifact.disk_size
    except OSError as exc:
        return _unreadable_file(exc)

    try:
        if artifact.is_compressed and source_override is None:
            with server_timing.phase("read"):
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
                "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                "detail": "File is too large for full document rendering",
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
                "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                "detail": f"Compressed source exceeds safety limits: {exc}",
                "path": subpath,
                "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=413,
        )
    except ArtifactCompressionError as exc:
        if artifact.is_gzip:
            return JSONResponse({"error": exc.reader_message, "detail": str(exc)}, status_code=404)
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": exc.reader_message,
                "detail": f"Unable to read compressed source: {exc}",
                "path": subpath,
            },
            status_code=400,
        )
    except OSError as exc:
        return _unreadable_file(exc)
    if ext not in BROWSER_TEXT_EXTS and not await asyncio.to_thread(_prefers_text_body, target):
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": kpress_adapter.RENDER_TEXT_ONLY_MESSAGE,
                "detail": "KPress render supports text-like files only",
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
                "error": kpress_adapter.RENDER_TOO_LARGE_MESSAGE,
                "detail": "File is too large for full document rendering",
                "path": subpath,
                "size": disk_size,
                "logical_size": logical_size,
                "max_size": _TEXT_PREVIEW_MAX_CHUNK_BYTES,
            },
            status_code=413,
        )

    try:
        if content is None:
            with server_timing.phase("read"):
                content = await asyncio.to_thread(target.read_text, errors="replace")
    except OSError as exc:
        return _unreadable_file(exc)

    ctx = FileContext(target, ext)

    def _classify_markdown() -> tuple[str, dict[str, Any] | None, str | None]:
        return _classify_with_plugins(target, ext, file_ctx=ctx), *_markdown_frontmatter(ctx, ext)

    with server_timing.phase("read"):
        kind, frontmatter, frontmatter_error = await asyncio.to_thread(_classify_markdown)
    mtime_hash = file_mtime_hash(target)
    fence_origin = await read_fence_origin(subpath, mtime_hash, content, ext, view, profile)

    try:
        with server_timing.phase("render"):
            if get_capabilities().active_content:
                rendered = await asyncio.to_thread(
                    kpress_adapter.render_kpress_view,
                    source_text=content,
                    fence_origin=fence_origin,
                    source_path=subpath,
                    kind=kind,
                    view=view,
                    ext=ext,
                    mtime_hash=mtime_hash,
                    size=logical_size,
                    frontmatter=frontmatter,
                    frontmatter_error=shown_frontmatter_error(frontmatter_error),
                    profile=profile,
                    include_toc=include_toc,
                )
            else:
                # A document the reader does not trust renders inert, in the Markdown
                # child under its deadline (diff/markdown_projection_worker.py), and is
                # known by its text, which a folder's file has no other name for. A
                # client that goes away leaves the render to no one, and an abandoned
                # render must not hold the child.
                inert = await unless_disconnected(
                    request,
                    shared_worker().render_inert(
                        InertRender(
                            source_text=content,
                            fence_origin=fence_origin,
                            source_path=subpath,
                            identity=await asyncio.to_thread(text_identity, content),
                            kind=kind,
                            view=view,
                            ext=ext,
                            mtime_hash=mtime_hash,
                            size=logical_size,
                            frontmatter=frontmatter,
                            frontmatter_error=shown_frontmatter_error(frontmatter_error),
                            profile=profile,
                            include_toc=include_toc,
                        )
                    ),
                )
                if inert is None:
                    return Response(status_code=CLIENT_CLOSED)
                rendered = inert
    except InertRenderRefused as refused:
        return JSONResponse(
            kpress_refusal_payload(refused, subpath),
            status_code=refused.http_status,
            headers={"cache-control": "no-cache"},
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": kpress_adapter.RENDER_FAILED_MESSAGE,
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=400,
        )
    except kpress_adapter.KPressRenderError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": kpress_adapter.RENDER_FAILED_MESSAGE,
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=502,
        )
    # The version of each file the document embeds, which the page puts in that file's
    # /raw address, so a replaced image is a new address (_raw_versions). Read on every
    # render, which is never kept: a render names the files as they are when it is asked.
    # A new mapping: KPress keeps renders, and this one must not change what it keeps.
    with server_timing.phase("read"):
        raw_versions = await asyncio.to_thread(
            _raw_versions, str(rendered.get("html") or ""), subpath
        )
    return JSONResponse(
        {
            **rendered,
            **_frontmatter_detail(frontmatter_error),
            "raw_versions": raw_versions,
        },
        headers={"cache-control": "no-cache"},
    )


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

    require_source_capability("mutation")

    try:
        body = await _read_bounded_json_request(request, _KPRESS_EXPORT_REQUEST_MAX_BYTES)
    except _JsonRequestLimitError:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": "Export request exceeds safety limits",
                "max_size": _KPRESS_EXPORT_REQUEST_MAX_BYTES,
            },
            status_code=413,
        )
    except (_json.JSONDecodeError, UnicodeDecodeError) as exc:
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
    profile = body.get("profile", "document")
    export_mode = body.get("export_mode", "page")
    asset_mode = body.get("asset_mode", "linked")
    optimize = body.get("optimize", False)
    theme_mode = body.get("theme_mode", "system")

    string_fields = {
        "path": raw_path,
        "destination": raw_destination,
        "view": view,
        "profile": profile,
        "export_mode": export_mode,
        "asset_mode": asset_mode,
        "theme_mode": theme_mode,
    }
    invalid_fields = sorted(
        field for field, value in string_fields.items() if not isinstance(value, str)
    )
    if type(optimize) is not bool:
        invalid_fields.append("optimize")
    if invalid_fields:
        return JSONResponse(
            {
                "type": "kpress_export_error",
                "error": "Invalid export request field types",
                "fields": invalid_fields,
            },
            status_code=400,
        )

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

    source = resolve_session_identity(raw_path)
    if source is None or not source.is_file():
        return JSONResponse(
            {"type": "kpress_export_error", "error": "Source path not found or unsafe"},
            status_code=404,
        )

    if not raw_destination:
        return JSONResponse(
            {"type": "kpress_export_error", "error": "`destination` is required"},
            status_code=400,
        )
    destination = resolve_session_identity(raw_destination)
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
    """Serve KPress package assets through Metabrowser's safe asset route.

    Pages address them under ``@<digest>/``, a stamp of the KPress package's files
    (:func:`kpress_adapter.kpress_asset_url_prefix`), which is removed before KPress
    resolves the rest. Under the stamp that names the bytes served, CSS and JS are kept
    a year without revalidation, which the version-keyed address alone could not allow;
    see :mod:`metabrowser.asset_stamps`.
    """

    stamp_digest, rel = split_stamp(request.path_params.get("path", ""))

    def read() -> tuple[KPressAsset, bool]:
        asset = kpress_adapter.get_kpress_static_asset(rel)
        return asset, kpress_adapter.kpress_stamp_is_current(stamp_digest, asset.content)

    try:
        with server_timing.phase("read"):
            asset, current = await asyncio.to_thread(read)
    except kpress_adapter.KPressAssetNotFoundError:
        return PlainTextResponse(f"not found: {rel}", status_code=404)

    is_font = rel.rsplit(".", 1)[-1].lower() in {"woff2", "woff", "ttf", "otf"}
    # Immutable at the current stamp, and revalidated at an old one against the
    # content-addressed ETag: a 304 when unchanged, fresh bytes the moment an asset
    # changes. A font at an address with no stamp at all, the version-keyed one a KPress
    # past the stamping bound is named by, is still kept hard, as it always was: it is
    # large, stable for a KPress version, and never edited in development. Under an old
    # stamp it is not, or a page from before an in-place upgrade would keep the new font
    # under the old stamp's address (review C of #372, C4).
    headers = {
        "ETag": asset.etag,
        "Cache-Control": stamped_asset_cache_control(
            current=current or (is_font and stamp_digest is None)
        ),
    }
    if matches_if_none_match(request, asset.etag):
        return Response(status_code=304, headers=headers)
    if current:
        # Compressed once under the ETag, which is KPress's hash of these bytes (H115).
        # KPress reads the file itself, so the read above is still paid on each request.
        return EncodedAssetResponse(
            key=f"kpress:{asset.etag}",
            identity=asset.content,
            headers=headers,
            media_type=asset.media_type,
        )
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
    require_source_capability("activity")
    runtime = _inventory_runtime_for(request)
    active_files = await activity_snapshot(
        runtime.coordinator,
        config=runtime.config,
        root=session_filesystem_root(),
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


def _raw_target_from_request(request: Request) -> Path | None:
    """Resolve the file a raw request named.

    The query form is the existing public API and speaks inventory identities
    (the image renderer), resolved through the active session so the answer
    follows the subject rather than a remembered root. The path form is a
    document URL, so it uses the same filesystem address as ``/view``.
    """

    path_params = getattr(request, "path_params", {})
    if "path" in path_params:
        return _safe_path(str(path_params["path"]))
    return resolve_session_identity(request.query_params.get("path", ""))


def _raw_identity(mtime_hash: str, stat: os.stat_result, *, passthrough: bool) -> str:
    """What a ``/raw`` validator names: the file, the representation, and the trust profile.

    The file is named by its ``mtime_hash`` (name, size, modification time) with its change
    time and inode, so a same-size rewrite that restores the modification time -- npm
    unpacks every file at one fixed time -- still moves the tag. The response headers are
    the trust profile's, so the profile and the sandbox policy are named too; the build,
    which shapes both, is in every tag (``build_scoped_etag``).
    """
    active = get_capabilities().active_content
    profile = "active" if active else "inert"
    representation = "gzip" if passthrough else "identity"
    return (
        f"{mtime_hash}:{stat.st_ctime_ns}:{stat.st_ino}:{representation}:{profile}:"
        f"{raw_sandbox_csp(active_content=active)}"
    )


def _raw_version(target: Path, stat: os.stat_result) -> str:
    """The version a ``/raw`` address carries: the file as it is now, and the trust profile.

    A raster image at its versioned address is kept for a year without asking
    (``docs/project/architecture/arch-server-and-content.md``), so the version names
    everything that answer depends on: the file
    by its resolved path and by what a replacement moves -- size, modification and change
    times, inode, and device -- and the headers by the trust profile and the sandbox
    policy it sends. The build is folded in by
    :func:`metabrowser.http_caching.address_version`. The representation is not named: a
    gzip passthrough answer varies by ``Accept-Encoding``, which a browser keys it by.
    """
    active = get_capabilities().active_content
    return address_version(
        f"{os.fsencode(target)!r}:{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}:"
        f"{stat.st_ino}:{stat.st_dev}:{'active' if active else 'inert'}:"
        f"{raw_sandbox_csp(active_content=active)}"
    )


# How many resources of one render get a version, in document order. Past it a resource's
# address is unversioned and revalidated, and its image is not held (place-rendered.js).
# Each version costs what /raw's own resolver costs, a realpath and a stat, and a render
# is asked for on every entry. Measured 2026-11-14 on a laptop at a load average near 13,
# through _raw_versions on a document of 1,024 images in one folder, 12 path components
# deep, warm cache, 30 runs: 1,024 versions took a median of 71 ms, as long as KPress took
# to render that document uncached (68 ms); 256 took 19 ms, and 64 took 5.5 ms. A re-entry
# of that document in WebKit asked again for 224 images before they were held (#408), so
# 256 versions cover a screen of thumbnails, and an image past them loads lazily as KPress
# wrote it.
_MAX_RAW_VERSIONS = 256


def _raw_versions(rendered_html: str, source_path: str) -> dict[str, str]:
    """The version of each served file *rendered_html* embeds, by its ``/raw`` identity.

    Each identity is resolved as ``/raw`` resolves its ``path``, safe-path check included,
    so a version names the file that address serves; one that resolves to no regular file
    is left out. Runs in a worker thread: a ``stat`` per resource.
    """
    versions: dict[str, str] = {}
    for identity in embedded_raw_paths(rendered_html, source_path, limit=_MAX_RAW_VERSIONS):
        try:
            target = resolve_session_identity(identity)
            if target is None:
                continue
            stat = target.stat()
        except OSError:
            continue
        if S_ISREG(stat.st_mode):
            versions[identity] = _raw_version(target, stat)
    return versions


def _media_type_from_file(target: Path) -> str | None:
    """The media type *target*'s leading bytes give, from one bounded read, or None."""

    try:
        with target.open("rb") as stream:
            return media_type_from_prefix(stream.read(MEDIA_SIGNATURE_BYTES))
    except OSError:
        return None


async def raw_file(request: Request) -> Response:
    """Serve raw bytes for one file on the active subject.

    A pinned Git subject answers from the object store instead of the
    filesystem. Every response leaving this route, that one included, is
    sandboxed by ``_RawTrustHeaderMiddleware``, which owns the trust headers
    for the whole ``/raw`` path rather than any one branch here.
    """

    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        from metabrowser.git.content_routes import git_revision_raw

        # Said before anything is awaited: this answer is a pin's, whatever was served
        # when the request arrived and whatever is by the time it is sent.
        request.scope[_RAW_PINNED_SCOPE] = True
        return await git_revision_raw(request, pin)
    target = _raw_target_from_request(request)
    if target is None or not target.is_file():
        return PlainTextResponse("Not found", status_code=404)

    artifact = ArtifactPath(target)
    media_type = artifact.mime_type
    if media_type == "application/octet-stream" and not artifact.is_compressed:
        # A name that gives no type: the file's leading bytes may (media_type_from_prefix).
        media_type = await asyncio.to_thread(_media_type_from_file, target) or media_type
    accepts_gzip = _accepts_gzip(request.headers.get("accept-encoding", ""))

    # Uncompressed path: stream the file as-is. ``FileResponse`` streams in
    # fixed-size chunks rather than reading the whole file before the first
    # byte, so the event loop stays responsive and memory stays bounded
    # regardless of file size. ``_safe_path`` already rejected paths outside
    # ROOT_DIR.
    #
    # Passthrough: client accepts gzip → ship the on-disk bytes verbatim
    # with ``Content-Encoding: gzip`` so the browser decompresses
    # transparently. Zero server CPU. Starlette's ``GZipMiddleware``
    # skips responses with ``Content-Encoding`` already set, so we
    # don't double-wrap.
    passthrough = artifact.is_gzip and accepts_gzip
    if not artifact.is_compressed or passthrough:
        try:
            stat = target.stat()
            mtime_hash = file_mtime_hash(target)
        except OSError:
            return PlainTextResponse("Not found", status_code=404)
        etag = _etag_for(_raw_identity(mtime_hash, stat, passthrough=passthrough))
        # The body is the reader's file and its headers are the trust profile's
        # (_RawTrustHeaderMiddleware). A response a browser keeps without asking is
        # replayed without reaching this server, so no address can revoke it: one kept
        # while the trusted profile served would answer, with `allow-scripts`, a link to it
        # followed after the folder is served `--untrusted` on the same origin. So only an
        # answer whose execution policy is the same in both profiles, a raster image
        # (_PROFILE_INDEPENDENT_MEDIA_TYPES), is kept: for a year, at the query form's `v`
        # while it is the version the file has now (_raw_version). Every other answer, an
        # SVG or HTML document's at its current version included, is revalidated on every
        # use: a 304 answers only the tag, which names the profile; a date cannot, so
        # If-Modified-Since alone is answered in full. The path form is a document's
        # address, for its relative references, and is never versioned. See "Raw
        # Responses" in docs/project/architecture/arch-server-and-content.md.
        version = request.query_params.get("v")
        current = (
            version is not None
            and "path" not in getattr(request, "path_params", {})
            and _profile_independent(media_type)
            and version == _raw_version(target, stat)
        )
        headers = immutable_headers(etag) if current else etag_headers(etag)
        if _profile_independent(media_type):
            # By this route's choice of type, so every answer it gives the image -- a 304,
            # which carries no type, and a multipart range answer, whose type is
            # multipart/byteranges, as much as a 200 -- has the policy both profiles send
            # (review C of #426, C1).
            headers["Content-Security-Policy"] = raw_sandbox_csp(active_content=False)
        if passthrough:
            headers["Vary"] = "Accept-Encoding"
        # The tag alone: `*` names no profile, so it earns no 304 here.
        if matches_if_none_match(request, etag, wildcard=False):
            return Response(status_code=304, headers=headers)
        if passthrough:
            headers |= artifact.passthrough_headers()
        return FileResponse(target, media_type=media_type, headers=headers, stat_result=stat)

    # Validate every compressed identity response before StreamingResponse sends
    # successful headers. Without this scan, malformed or over-limit gzip data
    # can fail only after a 200 response and a partial body reach the client.
    try:
        await asyncio.to_thread(lambda: artifact.logical_size)
    except ArtifactCompressionError as exc:
        # A plain-text answer has no field for the detail, so the log keeps it.
        LOG.info("raw: a compressed file is not served: %s", exc)
        status = 413 if isinstance(exc, ArtifactDecompressionLimitError) else 400
        return PlainTextResponse(exc.reader_message, status_code=status)

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
    CONTENT_PREDICATE_MAX_BYTES,
    CompiledKindRule,
    build_classifier,
    classify_magic,
    collect_folder_markers,
)
from metabrowser.plugin_loader.discovery import (
    discover_plugins,
)
from metabrowser.plugin_loader.manifest import (
    merge_views,
    view_entry,
)
from metabrowser.plugin_loader.static_assets import (
    FileOffer,
    FolderOffer,
    build_plugin_routes,
    plugin_asset_prefix,
    plugin_asset_trees,
    resolve_file_offers,
    resolve_folder_offers,
)
from metabrowser.tree import (
    set_folder_markers,
)

# Honor the CLI's --plugins-dir flags (merged into METABROWSER_PLUGINS_DIRS
# by the CLI) and that variable when it is exported. A dotenv file cannot
# supply it (``metabrowser.dotenv.ALLOWED_KEYS``).
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
# The stamps the shell addresses each plugin's files under, shared with the route that
# serves them so it can tell a current stamp from an old one (metabrowser.asset_stamps).
_PLUGIN_ASSET_TREES = plugin_asset_trees(_LOADED_PLUGINS)


# Pre-compile plugin kind rules and view bindings for fast lookup at
# request time. Higher priority wins; within a priority, the plugin
# discovered first wins (``CompiledKindRule.sort_key``).
# A ``binary = true`` rule is asked only about a file already found to be binary, so it
# sits in its own list and no text classifier sees it.
_PLUGIN_KIND_RULES: list[CompiledKindRule] = []
_PLUGIN_BINARY_KIND_RULES: list[CompiledKindRule] = []
_PLUGIN_VIEWS_BY_KIND: dict[str, list[dict[str, Any]]] = {}
for _idx, _plugin in enumerate(_LOADED_PLUGINS):
    for _kr in _plugin.manifest.kind:
        (_PLUGIN_BINARY_KIND_RULES if _kr.binary else _PLUGIN_KIND_RULES).append(
            CompiledKindRule(rule=_kr, plugin_name=_plugin.name, discovery_index=_idx)
        )
    for _view in _plugin.manifest.view:
        _PLUGIN_VIEWS_BY_KIND.setdefault(_view.kind, []).append(view_entry(_view))

# Folder views a plugin offers only where its predicate accepts the folder, by view id.
_FOLDER_OFFERS: dict[str, FolderOffer | None] = resolve_folder_offers(_LOADED_PLUGINS)
# File views a plugin offers only where its predicate accepts the file's leading bytes,
# by kind and view id, and the kinds that have one.
_FILE_OFFERS: dict[tuple[str, str], FileOffer | None] = resolve_file_offers(_LOADED_PLUGINS)
_FILE_OFFER_KINDS: frozenset[str] = frozenset(kind for kind, _view in _FILE_OFFERS)

_PLUGIN_CLASSIFY = build_classifier(_PLUGIN_KIND_RULES)
_PLUGIN_CLASSIFY_BINARY = build_classifier(_PLUGIN_BINARY_KIND_RULES)
# Hand the tree renderer the folder-marker set so directories whose direct
# children include a known marker get a ``marker_basename`` field on their
# row. This is the only piece of plugin state that ``tree.py`` needs.
set_folder_markers(collect_folder_markers(_PLUGIN_KIND_RULES + _PLUGIN_BINARY_KIND_RULES))


def _classify_with_plugins(
    target: Path,
    ext: str,
    adapter: str | None = None,
    *,
    file_ctx: FileContext | None = None,
) -> str:
    """Classify a file. Plugin rules take precedence; legacy detector chain is the fallback.

    Returns the winning kind id. The legacy chain still drives the
    built-in kinds (markdown, text, binary, unknown-jsonl).

    *file_ctx* is optional — pass an existing :class:`FileContext` to
    avoid re-parsing frontmatter in callers that need both classification
    and frontmatter access (the api_file handler does this).
    """
    ctx = file_ctx if file_ctx is not None else FileContext(target, ext, adapter)
    plugin_kind = _PLUGIN_CLASSIFY(ctx)
    if plugin_kind is not None:
        return plugin_kind
    return classify_file_kind(target, ext, adapter)


def _magic_kind(disk_prefix: bytes | None) -> str | None:
    """The plugin kind whose ``magic`` bytes a file's leading bytes on disk hold.

    Checked only where a file would otherwise be ``binary``, from the sniff prefix the
    caller already read; None for no prefix (a compressed artifact) or no match.
    """
    if disk_prefix is None:
        return None
    return classify_magic(_PLUGIN_KIND_RULES, disk_prefix)


def _classify_content_kind(target: Path, ext: str) -> str:
    """The kind ``/api/file`` gives a file on the served folder, for a caller with no
    envelope of its own: an image extension, then text or JSONL through the plugin
    classifier, then a ``magic`` kind, a ``binary = true`` claim, or ``binary`` for bytes that sniff as binary."""
    if ext in BROWSER_IMAGE_EXTS:
        return "image"
    if ext != ".jsonl" and ext not in BROWSER_TEXT_EXTS:
        text_body, disk_prefix = _sniff_text_body(target)
        if not text_body:
            return _magic_kind(disk_prefix) or _binary_kind(target, ext)
    return _classify_with_plugins(target, ext)


def _binary_kind(target: Path, ext: str) -> str:
    """The kind of a served file found to be binary: a plugin's binary claim, or ``binary``.

    Path predicates only, so this reads nothing; ``_classify_with_plugins`` is never
    asked about a binary file, whose content its predicates would misread. A claim by a
    kind no loaded plugin gives a view keeps ``binary``, so the file keeps its Bytes view
    rather than reaching a page with nothing to show.
    """
    if not _PLUGIN_BINARY_KIND_RULES:
        return "binary"
    claimed = _PLUGIN_CLASSIFY_BINARY(FileContext(target, ext, None))
    return claimed if claimed is not None and _PLUGIN_VIEWS_BY_KIND.get(claimed) else "binary"


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
        target = resolve_session_identity(prefix)
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
        kind = _classify_content_kind(target, ext)
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


def _table_source_declarations() -> list[TableSourceDeclaration]:
    """Every ``[[table_source]]`` the server serves, in discovery order.

    An operator-directory plugin runs no Python, so its declarations are ignored with a
    log line, as its data hooks are (``build_plugin_routes``).
    """
    out: list[TableSourceDeclaration] = []
    for plugin in _LOADED_PLUGINS:
        if not plugin.manifest.table_source:
            continue
        if plugin.source.startswith("local:"):
            LOG.warning(
                "metabrowser local plugin '%s' declares table sources; operator-directory "
                "plugins are JavaScript-only, so they are ignored",
                plugin.name,
            )
            continue
        out.extend(
            TableSourceDeclaration(
                plugin=plugin.name, kind=spec.kind, adapter=spec.adapter, offer=spec.offer
            )
            for spec in plugin.manifest.table_source
        )
    return out


def _classify_served_file(ref: ContentRef) -> str | None:
    target = resolve_session_identity(ref.identity)
    if target is None or not target.is_file():
        return None
    return _classify_content_kind(target, ref.logical_ext)


async def _table_content_kind(ref: ContentRef) -> str | None:
    """The kind of the content a table route names, as ``/api/file`` classifies it.

    On a served folder it runs the plugin classifier and the fallback chain on the file;
    on a pin it applies the Git-blob subset of the rules (extension and basename), which
    is every rule a table source's kind uses.
    """
    if get_source_session().subject.filesystem_root is not None:
        # Resolving and statting the file runs off the event loop, with the classifier.
        return await asyncio.to_thread(_classify_served_file, ref)
    from metabrowser.git.content_routes import plugin_kind_for_git_wire, plugin_magic_kind

    kind = plugin_kind_for_git_wire(ref.identity)
    if kind is not None or ref.logical_ext in BROWSER_IMAGE_EXTS:
        return kind or "image"
    head = await read_content_window(ref, max_bytes=SNIFF_PREFIX_BYTES)
    content_class = classify_prefix(head.data)
    if content_class is ContentClass.BINARY or (
        ref.logical_ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT
    ):
        return plugin_magic_kind(head.data)
    return classify_by_ext(ref.logical_ext)


install_table_sources(
    _table_source_declarations(), _table_content_kind, container_kinds=_container_kinds()
)


def _views_for_kind(
    kind: str,
    *,
    target: Path | None = None,
    prefix: tuple[bytes, str] | None = None,
    active_content: bool | None = None,
) -> list[dict[str, Any]]:
    """Return the merged view list for a kind: built-in registry + plugin manifests.

    :func:`merge_views` owns the merge order and the override rule, and
    :func:`check_view_keys` the view key rule: a later view's duplicate or
    reserved key is dropped here and reported by ``metab --doctor``, and the
    view itself is still served. :func:`live_view_keys` runs last, so a list
    left with one view serves no key; a caller that filters the list further,
    as a Git folder does, applies it again.

    The html kind is the exception that still uses this merger: Preview is
    dropped when active content is off, and a bounded sniff may move the
    default tab to Source. *target* is the file being classified; omit it
    only when no file is in hand.

    For the folder kind *target* is the folder, and :func:`_offered_folder_views`
    keeps a plugin's offered view only where its predicate accepts the folder; with
    no folder in hand no offered view is kept. The predicates touch the disk, so a
    caller on the event loop runs this in a thread when :data:`_FOLDER_OFFERS` is
    not empty.

    For a file kind, :func:`_offered_file_views` keeps a plugin's offered view only
    where its predicate accepts the file's leading bytes: *prefix*, the bytes and the
    logical extension, when the caller holds them, as a pinned blob's does, or else
    read from *target*. Only a file served as text passes either, `/api/file`'s text
    answer and a pinned text blob's; an image, a binary, a JSONL log, or a container's
    entry passes neither, so its kind's offered views are never kept, and the first such
    answer logs a warning for the plugin's author. Reading *target* touches the disk, so
    a caller on the event loop that passes it runs this in a thread.
    """
    merged = merge_views(VIEW_REGISTRY.get(kind, []), _PLUGIN_VIEWS_BY_KIND.get(kind, []))
    out = check_view_keys(kind, merged).views
    if kind == "folder":
        if _FOLDER_OFFERS:
            out = _offered_folder_views(out, target)
        # The folder's tab strip groups the two data views before the Treemap.
        positions = {view["id"]: index for index, view in enumerate(out)}
        table = positions.get("table")
        treemap = positions.get("treemap")
        if table is not None and treemap is not None and table > treemap:
            out.insert(treemap, out.pop(table))
    elif kind in _FILE_OFFER_KINDS:
        if prefix is None and target is None:
            _warn_offers_never_read(kind)
        out = _offered_file_views(kind, out, prefix if prefix is not None else _file_prefix(target))
    if kind == "html":
        out = _html_kind_views(out, target, active_content=active_content)
    elif out and not any(v.get("default") for v in out):
        out[0] = {**out[0], "default": True}
    return live_view_keys(out)


def _offered_folder_views(views: list[dict[str, Any]], target: Path | None) -> list[dict[str, Any]]:
    """Keep each offered folder view only where its predicate accepts *target*.

    A predicate that raises is logged and its view left out, so one plugin cannot take
    every folder page down. An offered view that is a default becomes the only
    default, the first such one if several are offered: the folder is the plugin's
    subject, so its page opens there rather than on the Overview.
    """

    kept: list[dict[str, Any]] = []
    offered_default: str | None = None
    for view in views:
        view_id = view["id"]
        if view_id not in _FOLDER_OFFERS:
            kept.append(view)
            continue
        predicate = _FOLDER_OFFERS[view_id]
        if target is None or predicate is None:
            continue
        try:
            offered = bool(predicate(target))
        except Exception:
            LOG.exception("folder view %s offer failed; leaving the view out", view_id)
            continue
        if not offered:
            continue
        kept.append(view)
        if offered_default is None and view.get("default"):
            offered_default = view_id
    if offered_default is not None:
        kept = [{**view, "default": view["id"] == offered_default} for view in kept]
    return kept


@functools.cache
def _warn_offers_never_read(kind: str) -> None:
    """Say once that *kind*'s offered views are left out of an answer that reads no
    leading bytes, since an offer is decided only for a file served as text."""

    LOG.warning(
        "%s views declare an offer, but a %s file is not served as text, so no leading "
        "bytes are read and those views are never offered",
        kind,
        kind,
    )


def _file_prefix(target: Path | None) -> tuple[bytes, str] | None:
    """The leading logical bytes every file offer reads, one past the largest content
    predicate's cap, and the logical extension; None with no file in hand or none that
    can be read."""

    if target is None:
        return None
    artifact = ArtifactPath(target)
    try:
        with artifact.open_binary(max_output_bytes=CONTENT_PREDICATE_MAX_BYTES + 1) as source:
            data = source.read(CONTENT_PREDICATE_MAX_BYTES + 1)
    except (ArtifactCompressionError, OSError):
        return None
    return data, artifact.logical_ext


def _offered_file_views(
    kind: str, views: list[dict[str, Any]], prefix: tuple[bytes, str] | None
) -> list[dict[str, Any]]:
    """Keep each of *kind*'s offered views only where its predicate accepts *prefix*.

    A predicate that raises is logged and its view left out, as a folder's is. A view
    left out that was the default leaves the default to the caller's fallback, the
    first view.
    """

    kept: list[dict[str, Any]] = []
    for view in views:
        key = (kind, view["id"])
        if key not in _FILE_OFFERS:
            kept.append(view)
            continue
        predicate = _FILE_OFFERS[key]
        if prefix is None or predicate is None:
            continue
        try:
            offered = bool(predicate(*prefix))
        except Exception:
            LOG.exception("%s view %s offer failed; leaving the view out", kind, view["id"])
            continue
        if offered:
            kept.append(view)
    return kept


def _html_kind_views(
    views: list[dict[str, Any]], target: Path | None, *, active_content: bool | None = None
) -> list[dict[str, Any]]:
    """Apply the html kind's capability gate and default-tab sniff.

    *active_content* is the caller's subject's: a pin's routes pass false, since a pin is
    never trusted; a folder's leave it to the process's block.
    """

    if not (get_capabilities().active_content if active_content is None else active_content):
        remaining = [dict(view) for view in views if view["id"] != "preview"]
        if remaining and not any(view.get("default") for view in remaining):
            remaining[0] = {**remaining[0], "default": True}
        return remaining
    if target is not None and not sniff_full_page_html(target):
        return [{**view, "default": view["id"] == "source"} for view in views]
    if views and not any(view.get("default") for view in views):
        views[0] = {**views[0], "default": True}
    return views


def _plugin_asset_prefixes() -> dict[str, str]:
    """The path each plugin's assets are addressed under now, stamped where the tree is.

    Touches the disk for a live tree (``asset_stamps.StampedTree.stamp``); see
    :func:`_shell_asset_prefixes` for the caller on the event loop.
    """
    return {
        plugin.name: plugin_asset_prefix(plugin.name, _PLUGIN_ASSET_TREES.get(plugin.name))
        for plugin in _LOADED_PLUGINS
    }


def prepare_asset_stamps() -> None:
    """Stamp the static tree and every plugin's, so the first page reads none of them.

    Serve calls this before Uvicorn starts, beside ``kpress_adapter.prepare_browser_assets``.
    """
    _STATIC_TREE.stamp()
    _plugin_asset_prefixes()


async def _shell_asset_prefixes() -> tuple[dict[str, str], str]:
    """The plugin and KPress asset prefixes a shell names, and the static tree's stamp,
    without a walk on the event loop.

    A released tree is stamped once and answers at once. A live one -- an editable install
    or an operator's plugin directory -- takes its stamp again for every page, a ``stat``
    per file, so that page names what is on disk now; that walk runs in a thread.
    """

    def prefixes() -> tuple[dict[str, str], str]:
        _STATIC_TREE.stamp()
        return _plugin_asset_prefixes(), kpress_adapter.kpress_asset_url_prefix()

    settled = (
        _STATIC_TREE.settled
        and kpress_adapter.kpress_asset_prefix_settled()
        and all(tree.settled for tree in _PLUGIN_ASSET_TREES.values())
    )
    return prefixes() if settled else await asyncio.to_thread(prefixes)


def _build_plugin_asset_config_block(prefixes: Mapping[str, str]) -> str:
    """Configure manifest-owned assets by plugin, and the plugins each kind consumes.

    No plugin asset is an eager shell dependency. The private plugin host
    loads one plugin at most once, when ``app.js`` selects any kind in its
    manifest or code asks for its exports by name (``metabrowser.plugins.load``),
    which is how a plugin with no kind of its own is reached. Extra classic
    scripts retain manifest order before ``index.js``; styles load in parallel
    and settle before the plugin renderer mounts.

    Every URL is under the plugin's stamped prefix (*prefixes*, from
    :func:`_shell_asset_prefixes`, which takes them off the event loop), so its
    relative imports, worker, and stylesheet references inherit the stamp.
    """
    plugins: dict[str, dict[str, object]] = {}
    kinds: dict[str, list[str]] = {}
    for plugin in _LOADED_PLUGINS:
        prefix = prefixes.get(plugin.name, f"/plugin-static/{plugin.name}")
        styles: list[str] = []
        if plugin.static_root.joinpath("styles.css").is_file():
            styles.append(f"{prefix}/styles.css")
        for extra in plugin.manifest.plugin.extra_styles:
            url = f"{prefix}/{extra}"
            if url not in styles:
                styles.append(url)
        plugins[plugin.name] = {
            "name": plugin.name,
            "module": f"{prefix}/index.js",
            "scripts": [f"{prefix}/{extra}" for extra in plugin.manifest.plugin.extra_scripts],
            "styles": styles,
        }
        owned = {view.kind for view in plugin.manifest.view}
        owned.update(kind.id for kind in plugin.manifest.kind)
        for kind in sorted(owned):
            kinds.setdefault(kind, []).append(plugin.name)
    encoded = _json.dumps({"plugins": plugins, "kinds": kinds}).replace("<", "\\u003c")
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
    # A pin's index is its store's blob listing, not a provider the runtime opened, so
    # there are no provider counters to report: a typed refusal, not a 500.
    require_filesystem_hooks()
    runtime = _inventory_runtime_for(request)
    coordinated = await runtime.coordinator.read(
        ReadRequest(queries=(DiagnosticsQuery(query_id="debug-inventory"),))
    )
    diagnostic = coordinated.result.completed_projection("debug-inventory")
    if not isinstance(diagnostic, DiagnosticsProjection):
        raise TypeError("the inventory diagnostic returned the wrong projection")
    diagnostics = diagnostic.payload
    work = diagnostics.cumulative_work
    metrics = diagnostics.cumulative_metrics

    return JSONResponse(
        {
            "provider": diagnostics.provider,
            "contract": diagnostics.contract,
            "phase": coordinated.result.state.phase.value,
            "complete": coordinated.result.state.coverage.complete,
            "version": coordinated.version.engine.sequence,
            "work": {
                "read_requests": diagnostics.read_requests,
                "observations": work.observations,
                "unchanged": work.unchanged,
                "stale": work.stale,
                "resource_refused": work.resource_refused,
                "rows_visited": work.rows_visited,
                "rows_returned": work.rows_returned,
                "maintained_index_work": work.maintained_index_work,
                "commits_visited": work.commits_visited,
                "commits_returned": work.commits_returned,
                "directories_read": work.directories_read,
                "entries_visited": work.entries_visited,
                "files_visited": work.files_visited,
                "bytes_visited": work.bytes_visited,
                "binding_bytes_copied": metrics.bytes_copied,
                "lock_wait_ns": metrics.lock_wait_ns,
                "cpu_time_ns": metrics.cpu_time_ns,
                "wall_time_ns": metrics.wall_time_ns,
            },
        }
    )


async def api_routes(request: Request) -> JSONResponse:
    """List every route this build serves, so the surface is discoverable.

    An agent or script driving ``metab --api`` cannot know what exists
    otherwise. Reading ``app.routes`` at request time rather than a static
    list means plugin data hooks and the lazily-added inventory routes are
    included, and the answer cannot drift from what is actually mounted.
    """

    listed: list[dict[str, object]] = []
    for route in request.app.routes:
        path = getattr(route, "path", None)
        if not isinstance(path, str):
            continue
        # A Mount serves whatever its sub-application serves, so reporting a
        # method list for it would be a guess. Say so instead.
        declared = getattr(route, "methods", None)
        methods = sorted(declared) if declared else None
        if path.startswith("/api/"):
            kind = "api"
        elif path.startswith(("/static", "/kpress-static", "/plugin-static", "/raw")):
            kind = "asset"
        elif path.startswith("/_"):
            kind = "debug"
        else:
            kind = "browser"
        listed.append({"path": path, "methods": methods, "kind": kind})
    listed.sort(key=lambda entry: (str(entry["kind"]), str(entry["path"])))
    return JSONResponse({"routes": listed, "count": len(listed)})


# ── Starlette app ───────────────────────────────────────────────

routes = [
    Route("/", root_redirect),
    Route("/view/{path:path}", view_shell),
    Route("/commit/{rest:path}", commit_shell),
    Route("/pull/{rest:path}", pull_shell),
    Route("/stack/{rest:path}", stack_shell),
    Route("/pulls", pulls_shell),
    Route("/api/tree", api_tree),
    Route("/api/rollup", api_rollup),
    Route("/api/recent", api_recent),
    Route("/api/file", api_file),
    Route("/api/kpress/render", api_kpress_render, methods=["GET", "POST"]),
    Route("/api/kpress/export", api_kpress_export, methods=["POST"]),
    Route("/api/activity", api_activity),
    Route("/api/routes", api_routes),
    Route("/api/stream", api_stream),
    Route("/_debug/tasks", _debug_tasks),
    Route("/_debug/inventory", _debug_inventory),
    Route("/raw", raw_file),
    Route("/raw/{path:path}", raw_file),
    Route("/kpress-static/{path:path}", kpress_static_asset),
    Mount(
        "/static",
        app=StampedStaticFiles(
            directory=STATIC_DIR, tree=_STATIC_TREE, self_named=_SELF_NAMED_STATIC
        ),
        name="static",
    ),
    # Read-only git history, kept as its own collection in
    # ``metabrowser.git.routes``: separate wire model, separate failure
    # modes, separate resource bounds.
    *GIT_ROUTES,
    # Read-only logical cache state for CLI parity. The table imports the cache and
    # the application home only inside a cache request; see ``metabrowser.cache.routes``.
    *CACHE_ROUTES,
    # What this server serves: the subject and, on a pin, its commit, ref, and
    # freshness, plus the POST routes that refresh the mirror and switch the pin.
    *SOURCE_ROUTES,
    # What the served subject is called, as the shell's title and a native window say.
    *IDENTITY_ROUTES,
    # Where the event log is, and its records (metabrowser.event_log).
    *EVENT_LOG_ROUTES,
    # A page's github.com counterpart, which every View on GitHub control links to.
    *COUNTERPART_ROUTES,
    *build_plugin_routes(_LOADED_PLUGINS, asset_trees=_PLUGIN_ASSET_TREES),
]

# GZip every response above 1 KiB. This materially reduces tree and file
# payloads over an SSH tunnel. The level and the floor are in
# ``metabrowser.delivery``, which also decides who is sent gzip. A streamed
# ``FileResponse`` is compressed chunk by chunk like any other body; an asset at
# a current stamped address arrives already encoded (``encoded_assets``), and
# the middleware passes an answer with a ``Content-Encoding`` on unchanged.
middleware = [
    # Outermost, so a rejection written before routing — and a 500 an
    # inner layer never got to shape — still leaves ``/raw`` sandboxed.
    Middleware(_RawTrustHeaderMiddleware),
    Middleware(_HostValidationMiddleware),
    # Inside the origin checks: a page showing a pin the server has since switched away
    # from is refused with a typed pin_changed rather than answered from the new pin.
    Middleware(SourcePinGuard),
    Middleware(_SlowRequestLogMiddleware),
    # Starlette's, with the compression counted as the `encode` phase of Server-Timing.
    Middleware(
        server_timing.TimedGZipMiddleware,
        minimum_size=delivery.GZIP_MINIMUM_SIZE,
        compresslevel=delivery.GZIP_LEVEL,
    ),
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
        root = session_filesystem_root()
    except Exception:
        return None
    return root if str(root) and root != Path() else None


@asynccontextmanager  # pyright: ignore[reportDeprecated]
async def _lifespan(app: Starlette) -> AsyncIterator[None]:
    # A served pin attaches before the inventory opens, which reads the active
    # subject, and closes after it, so nothing still reads its Git processes. The
    # refresh jobs start once the pin is attached and are cancelled before it closes.
    # What a folder's server keeps for its checkout comes last, so it is left first: a
    # revision of the checkout still served at shutdown is closed while the rest is up.
    # The store a folder keeps of its checkout's origin needs the refresh jobs, and comes
    # before the checkout's revisions, whose `--ref` may name a ref read from it.
    # A served process's event log pings this loop, so a turn that blocks it is on record.
    event_log.watch_loop(asyncio.get_running_loop())
    async with (
        lifespan_subject(),
        build_lifespan(app=app, root_provider=_inventory_root_provider),
        lifespan_refresh(app),
        lifespan_checkout_store(app),
        lifespan_checkout(),
        lifespan_history_sessions(),
    ):
        history_preparation = None
        if getattr(app.state, "prepare_initial_history", False):
            # The in-process CLI also uses this application, after the serve has ended.
            app.state.prepare_initial_history = False
            history_preparation = asyncio.create_task(
                prepare_initial_history(), name="metabrowser-history-prepare"
            )
        try:
            if not get_capabilities().active_content:
                # Every document an untrusted session serves renders in the Markdown child,
                # a served pin's among them, so a served one starts it now rather than at
                # its first document, which would wait for it; a one-shot command starts
                # nothing it may not use. Inside the try, so the close below reaps it.
                start_for_pages()
            yield
        finally:
            try:
                if history_preparation is not None:
                    history_preparation.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await history_preparation
            finally:
                # The Markdown child belongs to this loop; a later one starts its own.
                await shared_worker().aclose()


async def _query_work_limit_response(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Expose an exhausted provider work bound without a misleading partial body."""

    if not isinstance(error, QueryWorkLimitError):  # pragma: no cover - Starlette dispatches it
        raise error
    limit = error.projection
    return JSONResponse(
        {
            "error": "Inventory query work limit exceeded",
            "code": "inventory_query_limit",
            "query": limit.query_kind.value,
            "max_work": limit.max_work,
            "rows_visited": limit.rows_visited,
        },
        status_code=503,
    )


async def _unsupported_source_response(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, UnsupportedSourceCapabilityError):  # pragma: no cover
        raise error
    return JSONResponse(unsupported_source_payload(error), status_code=409)


app = Starlette(
    routes=routes,
    middleware=middleware,
    lifespan=_lifespan,
    exception_handlers={
        QueryWorkLimitError: _query_work_limit_response,
        UnsupportedSourceCapabilityError: _unsupported_source_response,
    },
)
add_inventory_routes(app)


# ── CLI entry point ─────────────────────────────────────────────
