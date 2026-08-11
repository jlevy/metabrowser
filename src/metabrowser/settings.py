"""Centralized configuration constants for metabrowser.

Single source of truth for every tunable in the browser plane.
Importing from here (instead of defining constants inline in
the module that uses them) keeps the surface visible and makes
future env-var overrides a one-place change.

Convention for now: hard-coded defaults. If environment overrides become
useful, centralize their parsing here instead of scattering direct
``os.environ`` reads across the package.

The :func:`client_settings_dict` helper exposes the JS-relevant
subset to the client via the index template. The Python
constants below are the source; the client never duplicates a
value, it reads it from ``window.METABROWSER_SETTINGS``.
"""

from __future__ import annotations

from typing import Any

from metabrowser.file_type_filters import FILTER_TYPE_PRESETS

# ── Server port ──────────────────────────────────────────────

# Canonical port for metabrowser (serve + browse tunnel endpoint).
# Single source of truth — do not hardcode 8411 anywhere else.
DEFAULT_BROWSER_PORT = 8411

# ── Diagnostics ──────────────────────────────────────────────

# Shared cutoff for slow-request warnings and slow background-helper summaries.
# Routine details stay behind DEBUG without obscuring failures.
SLOW_OPERATION_LOG_SECONDS = 2.0

# ── InventoryIndex walker ────────────────────────────────────

INVENTORY_FIRST_RENDER_DEPTH = 2
INVENTORY_MAX_DEPTH = 20
# Hard ceiling on files indexed by the BFS walker at startup. The
# walker streams entries as it discovers them so /api/tree responds
# from a partial index immediately; this cap is just the point at
# which it stops. Tune up for large monorepos, down for memory-
# constrained hosts. Approx wall-clock at the cap on a local SSD
# is N/7 000 seconds (500k -> ~70 s on Linux ext4, longer on FUSE
# / NFS mounts). On truncation, partially-walked dirs still emit
# their accumulated totals so the UI shows usable numbers rather
# than skeletons.
INVENTORY_MAX_FILES = 500_000
# Refresh-TTL: re-walk an entry older than this on the walker's
# next idle pass. Bounds staleness when the active-tracker /
# watcher backends miss a change.
INVENTORY_REFRESH_TTL_S = 600.0

# Walker-emit batch size. The initial scan generates one upsert
# per file and dir; emitting them as individual fs.change events
# would produce ~500k events for a large repo and overflow every
# subscriber's queue. Batching ~256 ops per event keeps the
# event count to a few thousand while letting the UI still see
# the tree fill in incrementally.
INVENTORY_WALKER_EMIT_BATCH = 256

# ── /api/events SSE transport ────────────────────────────────

# Ring buffer holds ~5 minutes of typical write traffic. Resume
# below the head signals a gap and the client falls back to a
# fresh snapshot.
SSE_RING_BUFFER_CAPACITY = 5_000

# Per-connection bounded queue. Overflow replaces stale deltas with
# a resync marker, and the browser reconnects for a fresh snapshot.
# This bound protects one connection; bus-level fanout governs
# delivery across connections.
SSE_PER_CONNECTION_QUEUE_SIZE = 1_024

# The event bus subscribes to the inventory once and fans out to
# all connections. The walker batches its upserts, but large roots
# and watcher bursts can still fill this bounded queue. Overflow
# replaces stale deltas with one resync marker so browsers refresh
# from authoritative snapshots without losing live updates silently.
SSE_BUS_INVENTORY_QUEUE_SIZE = 4_096

# Heartbeat cadence — long enough to keep proxies alive; short
# enough that a stalled producer is noticed quickly client-side.
SSE_HEARTBEAT_INTERVAL_S = 15.0

# Worker-pool size for asyncio's default executor. Cache-served
# /api/tree and /api/recent calls run via asyncio.to_thread; the
# default pool (~12) queues them behind activity stat storms.
DEFAULT_EXECUTOR_WORKERS = 64

# ── Active-file tracker (replaces /api/activity polling) ─────

# Cadence at which the active-file tracker walks .logs/.state
# entries to refresh their fingerprint. The live stream and
# compatibility snapshot use the same activity cadence.
ACTIVE_TRACKER_INTERVAL_S = 5.0

# Files unchanged for this many polls drop their ``active=true``
# flag. ~30 s of inactivity tags a file as quiet again.
ACTIVE_TRACKER_QUIET_POLLS = 6

# ── Recent view ──────────────────────────────────────────────

# Cluster threshold as a fraction. A bucket clusters when
# (max_age - min_age) / max_age <= this. 5 % is tight enough
# that mixed-age dirs stay expanded but loose enough that the
# run-dir write-storm pattern collapses cleanly.
RECENT_CLUSTER_PCT = 0.05

# "Live" is the same recent-mtime window for every file. Specialized
# log tracking still owns active badges and live tailing, but it does
# not change filter membership.
LIVE_FILE_WINDOW_S = 90.0

# Window keys (UI choices) and their seconds-back values; ``None``
# means unbounded ("all"). Both the server endpoint and the
# browser read from this dict.
RECENT_WINDOW_SECONDS: dict[str, float | None] = {
    "live": LIVE_FILE_WINDOW_S,
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "all": None,
}

RECENT_DEFAULT_WINDOW = "24h"
# What bounds this is not first render — it is that the client
# re-clusters the whole result on every ``fs.change`` burst, debounced
# to ``RECENT_RECLUSTER_DEBOUNCE_MS``. Measured in a real browser on
# this tree (cluster + render, per burst):
#
#     2 000 →  10ms,  1.4MB HTML      10 000 →  44ms,  6.7MB
#     5 000 →  18ms,  3.4MB           20 000 →  58ms, 13.4MB
#
# At 5 000 a burst costs under a fifth of the debounce interval, so a
# dispatch writing a hundred files a second still leaves the main
# thread idle most of the time; 10 000 spends nearly half of it and
# the payload starts to matter. The cap also stopped being the thing
# that hides a user's own work once truncation learned to drop
# gitignored files first (see ``collect_recent_entries``) — it now
# only bounds how much build output rides along, so headroom here
# buys a large monorepo room for its *tracked* churn rather than more
# ``node_modules``.
RECENT_DEFAULT_LIMIT = 5_000
RECENT_MAX_LIMIT = 5_000

# Re-cluster the Recent panel at most this many times per
# second when fs.change ops are flowing. Caps render thrash on
# bursty workloads (a dispatch starting writes a hundred files
# per second).
RECENT_RECLUSTER_DEBOUNCE_MS = 100

# ── Index progress footer ────────────────────────────────────

# The left-nav crawl indicator polls a lightweight progress endpoint
# while the eager inventory walk is active. Keep the cadence human-
# visible but quiet; the server ETag buckets responses by the same
# file-count stride so unchanged buckets return 304.
INDEX_PROGRESS_POLL_MS = 1_000
INDEX_PROGRESS_UPDATE_FILES = 1_024

# Fallback first-paint row budget when the browser cannot measure the
# navigation viewport. Normal rendering derives the budget from the live pane.
TREE_AUTO_EXPAND_FALLBACK_ROWS = 24


# ── Git graph panel ──────────────────────────────────────────

# Every ``/api/git/`` handler spawns ``git`` on a request path, so each
# invocation is bounded twice: by wall clock and by how much stdout we
# are willing to buffer. A repository large enough to exceed either is
# reported as a failure rather than being allowed to stall the loop or
# grow the resident set without limit.
GIT_SUBPROCESS_TIMEOUT_S = 15.0
GIT_SUBPROCESS_MAX_BYTES = 32 * 1024 * 1024

# Commits per ``/api/git/log`` page. The default is sized so the first
# page fills a tall panel with room to scroll before the second request;
# the max is the clamp applied to a caller-supplied ``limit``.
GIT_LOG_DEFAULT_LIMIT = 250
GIT_LOG_MAX_LIMIT = 1_000

# Maximum commit rows retained and mounted by the browser. A navigation
# panel must not grow its DOM or client state with the lifetime of a
# repository. The panel discloses the cap instead of presenting the
# bounded list as complete.
GIT_HISTORY_MAX_ROWS = 500

# Largest ``--skip`` offset a page cursor may carry. Cursors are opaque
# and server-issued, and the panel stops paging at GIT_HISTORY_MAX_ROWS,
# so no legitimate cursor comes near this; it is ~400 pages at the default
# limit. Without the bound, a well-formed cursor carrying an arbitrary
# offset makes git walk and discard that whole prefix of history on every
# request, spending the subprocess timeout budget to return nothing.
GIT_LOG_MAX_SKIP = 100_000

# Changed files returned by ``/api/git/commit/{revision}``. A commit that
# touches more than this reports ``files_truncated`` rather than being
# silently shortened.
GIT_COMMIT_MAX_FILES = 1_000

# Repository identity (root, HEAD, capability) is stable between commits
# but must not go stale across a checkout. Short TTL, same shape as the
# gitignore checker cache in ``tree.py``. Unborn HEAD entries bypass the
# cache so the first commit appears immediately.
GIT_REPO_INFO_TTL_S = 5.0

# Client-side pacing for the hover card. The card is backed by the same
# commit-detail request the detail view uses, so a slow drag across the
# graph must not issue one request per row.
GIT_HOVER_DEBOUNCE_MS = 300

# Bounded client-side commit-detail cache, shared by the hover card and
# the detail view so hovering then selecting a row is one request.
GIT_DETAIL_CACHE_SIZE = 200


# ── Client settings export ───────────────────────────────────


def client_settings_dict() -> dict[str, Any]:
    """The subset of settings injected into the client via the
    index template. Reading from a single dict keeps the JS
    side from duplicating constants.

    Convention: keys here mirror the JS-side constant names
    (``RECENT_LIMIT``, ``RECENT_WINDOWS``, …); the client reads
    via ``window.METABROWSER_SETTINGS.RECENT_LIMIT`` etc.
    """

    return {
        "FILTER_TYPE_PRESETS": FILTER_TYPE_PRESETS,
        "RECENT_DEFAULT_WINDOW": RECENT_DEFAULT_WINDOW,
        "RECENT_LIMIT": RECENT_DEFAULT_LIMIT,
        "RECENT_WINDOW_SECONDS": RECENT_WINDOW_SECONDS,
        # Window keys in UI chip order. Server enforces same set.
        "RECENT_WINDOWS": list(RECENT_WINDOW_SECONDS.keys()),
        "RECENT_CLUSTER_PCT": RECENT_CLUSTER_PCT,
        "RECENT_RECLUSTER_DEBOUNCE_MS": RECENT_RECLUSTER_DEBOUNCE_MS,
        "INDEX_PROGRESS_POLL_MS": INDEX_PROGRESS_POLL_MS,
        "INDEX_PROGRESS_UPDATE_FILES": INDEX_PROGRESS_UPDATE_FILES,
        "TREE_AUTO_EXPAND_FALLBACK_ROWS": TREE_AUTO_EXPAND_FALLBACK_ROWS,
        "SSE_HEARTBEAT_INTERVAL_S": SSE_HEARTBEAT_INTERVAL_S,
        "GIT_LOG_LIMIT": GIT_LOG_DEFAULT_LIMIT,
        "GIT_HISTORY_MAX_ROWS": GIT_HISTORY_MAX_ROWS,
        "GIT_HOVER_DEBOUNCE_MS": GIT_HOVER_DEBOUNCE_MS,
        "GIT_DETAIL_CACHE_SIZE": GIT_DETAIL_CACHE_SIZE,
    }


__all__ = [
    "ACTIVE_TRACKER_INTERVAL_S",
    "ACTIVE_TRACKER_QUIET_POLLS",
    "DEFAULT_BROWSER_PORT",
    "DEFAULT_EXECUTOR_WORKERS",
    "GIT_COMMIT_MAX_FILES",
    "GIT_DETAIL_CACHE_SIZE",
    "GIT_HOVER_DEBOUNCE_MS",
    "GIT_HISTORY_MAX_ROWS",
    "GIT_LOG_DEFAULT_LIMIT",
    "GIT_LOG_MAX_LIMIT",
    "GIT_LOG_MAX_SKIP",
    "GIT_REPO_INFO_TTL_S",
    "GIT_SUBPROCESS_MAX_BYTES",
    "GIT_SUBPROCESS_TIMEOUT_S",
    "INVENTORY_FIRST_RENDER_DEPTH",
    "INVENTORY_MAX_DEPTH",
    "INVENTORY_MAX_FILES",
    "INVENTORY_REFRESH_TTL_S",
    "INVENTORY_WALKER_EMIT_BATCH",
    "INDEX_PROGRESS_POLL_MS",
    "INDEX_PROGRESS_UPDATE_FILES",
    "LIVE_FILE_WINDOW_S",
    "RECENT_CLUSTER_PCT",
    "RECENT_DEFAULT_LIMIT",
    "RECENT_DEFAULT_WINDOW",
    "RECENT_MAX_LIMIT",
    "RECENT_RECLUSTER_DEBOUNCE_MS",
    "RECENT_WINDOW_SECONDS",
    "SSE_BUS_INVENTORY_QUEUE_SIZE",
    "SSE_HEARTBEAT_INTERVAL_S",
    "SSE_PER_CONNECTION_QUEUE_SIZE",
    "SSE_RING_BUFFER_CAPACITY",
    "TREE_AUTO_EXPAND_FALLBACK_ROWS",
    "client_settings_dict",
]
