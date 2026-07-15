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

# ── Server port ──────────────────────────────────────────────

# Canonical port for metabrowser (serve + browse tunnel endpoint).
# Single source of truth — do not hardcode 8411 anywhere else.
DEFAULT_BROWSER_PORT = 8411

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

# Per-connection bounded queue. Overflow disconnects that
# connection only; EventSource auto-reconnect drives a fresh
# snapshot. This bound protects one connection; bus-level fanout
# governs delivery across connections.
SSE_PER_CONNECTION_QUEUE_SIZE = 1_024

# The event bus subscribes to the inventory once and fans out to
# all connections. The walker batches its upserts (see
# INVENTORY_WALKER_EMIT_BATCH), so the burst is bounded at roughly
# (INVENTORY_MAX_FILES + dirs) / batch, about 2k-3k events for a
# 500k-file repo with typical directory density. If this queue
# overflows, the inventory drops the bus from its subscribers and
# the relay's defensive resubscribe (events_route._relay_loop)
# rebuilds the subscription.
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

# Window keys (UI chips) and their seconds-back values; ``None``
# means unbounded ("all"). Both the server endpoint and the
# client window-chip set read from this dict.
RECENT_WINDOW_SECONDS: dict[str, float | None] = {
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "all": None,
}

RECENT_DEFAULT_WINDOW = "24h"
RECENT_DEFAULT_LIMIT = 2_000
RECENT_MAX_LIMIT = 2_000

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
        "RECENT_DEFAULT_WINDOW": RECENT_DEFAULT_WINDOW,
        "RECENT_LIMIT": RECENT_DEFAULT_LIMIT,
        # Window keys in UI chip order. Server enforces same set.
        "RECENT_WINDOWS": list(RECENT_WINDOW_SECONDS.keys()),
        "RECENT_CLUSTER_PCT": RECENT_CLUSTER_PCT,
        "RECENT_RECLUSTER_DEBOUNCE_MS": RECENT_RECLUSTER_DEBOUNCE_MS,
        "INDEX_PROGRESS_POLL_MS": INDEX_PROGRESS_POLL_MS,
        "INDEX_PROGRESS_UPDATE_FILES": INDEX_PROGRESS_UPDATE_FILES,
        "SSE_HEARTBEAT_INTERVAL_S": SSE_HEARTBEAT_INTERVAL_S,
    }


__all__ = [
    "ACTIVE_TRACKER_INTERVAL_S",
    "ACTIVE_TRACKER_QUIET_POLLS",
    "DEFAULT_BROWSER_PORT",
    "DEFAULT_EXECUTOR_WORKERS",
    "INVENTORY_FIRST_RENDER_DEPTH",
    "INVENTORY_MAX_DEPTH",
    "INVENTORY_MAX_FILES",
    "INVENTORY_REFRESH_TTL_S",
    "INVENTORY_WALKER_EMIT_BATCH",
    "INDEX_PROGRESS_POLL_MS",
    "INDEX_PROGRESS_UPDATE_FILES",
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
    "client_settings_dict",
]
