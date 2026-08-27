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

from metabrowser.file_extensions import (
    SYNTAX_LANGUAGE_BY_BASENAME,
    SYNTAX_LANGUAGE_BY_EXTENSION,
)
from metabrowser.file_type_filters import (
    FILTER_TYPE_PRESETS,
    serialize_distribution_colors,
    serialize_file_type_registry,
)

# ── Server port ──────────────────────────────────────────────

# Canonical port for metabrowser (serve + browse tunnel endpoint).
# Single source of truth — do not hardcode 8411 anywhere else.
DEFAULT_BROWSER_PORT = 8411

# ── Diagnostics ──────────────────────────────────────────────

# Shared cutoff for slow-request warnings and slow background-helper summaries.
# Routine details stay behind DEBUG without obscuring failures.
SLOW_OPERATION_LOG_SECONDS = 2.0

# ── Text preview chunking ────────────────────────────────────

# See docs/large-content-rendering.md for the cost model these come from.
#
# The source view puts real text in a `white-space: pre` surface, so the
# browser never searches for wrap opportunities and layout is proportional
# to line count. Measured in Chromium 141: scrolling stays at ~33 ms at every
# size tried, and a single 2M-character minified line paints in ~70 ms. The
# old 128 KiB chunk was therefore costing 31 clicks to open a 4 MiB source
# file for no measured benefit.
# A contiguous run of added or deleted lines longer than this folds
# behind an expander in the diff view, so one large rewrite cannot bury
# the changes around it. Measured on this project's own 65-file pull
# request (13,020 changed lines in 127 runs): at 40, 42 runs fold and
# 83% of the lines start hidden, while the 85 ordinary runs — most real
# changes — are untouched. Set to 0 to disable folding entirely.
DIFF_FOLD_THRESHOLD = 40
# Lines of the run shown above the expander, so a fold always starts by
# showing what the change is before offering the rest.
DIFF_FOLD_VISIBLE = 20

TEXT_PREVIEW_CHUNK_BYTES = 2 * 1024 * 1024
# Each Load more asks for twice the last chunk, capped here, so reaching a
# large file takes a handful of clicks while no single click stalls.
TEXT_PREVIEW_MAX_CHUNK_BYTES = 8 * 1024 * 1024
# Hard clamp on one request, which also bounds the decompression window for a
# compressed artifact.
TEXT_PREVIEW_REQUEST_MAX_BYTES = 16 * 1024 * 1024
# Highlight.js tokenization plus attached-DOM layout creates one span per token.
# Chromium 141 measurements in docs/large-content-rendering.md put representative
# 512 KiB sources at 0.34–1.14 s and 29k–170k spans; 2 MiB reaches 1.48–4.45 s
# and 117k–682k spans. The shell performs this work after first paint and keeps
# the loaded syntax-highlighted prefix at or below this bound.
SYNTAX_HIGHLIGHT_MAX_BYTES = 512 * 1024

# ── InventoryIndex walker ────────────────────────────────────

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

# Rendered directory totals should normally converge through the inventory
# event stream. If any remain pending this long, the browser records one
# correlated client/server diagnostic for that unresolved episode.
PENDING_TALLY_DIAGNOSTIC_DELAY_MS = 5_000
PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT = 20
PENDING_TALLY_DIAGNOSTIC_MAX_BODY_BYTES = 64 * 1_024

# Fallback first-paint row budget when the browser cannot measure the
# navigation viewport. Normal rendering derives the budget from the live pane.
TREE_AUTO_EXPAND_FALLBACK_ROWS = 24

# ── Folder rollup (/api/rollup) ──────────────────────────────

# Emitted-node bounds for the treemap rollup. Depth bounds the emitted
# tree only (totals stay full-subtree); ``top`` caps children per
# directory before the rest bucket; ``ext_top`` caps envelope
# extension-tally rows before the remainder row. The semantic breakdown
# independently caps No extension basenames and Other types extensions;
# the route clamps every query parameter to the corresponding maximum.
ROLLUP_DEFAULT_DEPTH = 3
ROLLUP_MAX_DEPTH = 6
ROLLUP_DEFAULT_TOP = 40
ROLLUP_MAX_TOP = 200
ROLLUP_DEFAULT_EXT_TOP = 12
ROLLUP_MAX_EXT_TOP = 32
ROLLUP_DEFAULT_EXT_RANK = "bytes"
ROLLUP_FILE_TYPE_FILENAME_LIMIT = 20
ROLLUP_FILE_TYPE_REMAINING_LIMIT = 20
FOLDER_DISCOVERY_MAX_ENTRIES = 4_096

# Global emission budget for one rollup response. ``top`` bounds a
# single directory; a balanced tree multiplies per level, so this cap
# is what actually bounds response size (nodes past it become
# children:null lazy sentinels or fold into rest buckets). The browser
# renders at most ~800 cells, so 1200 leaves headroom for hide-mode
# filtering without amplification.
ROLLUP_MAX_NODES = 1_200

# Trailing debounce for treemap refresh after inventory change events;
# read by the SDK's watchRollup.
ROLLUP_WATCH_DEBOUNCE_MS = 1_000

# Encoded rollup bodies retained for reuse, keyed by ETag. One open folder
# view asks for a handful of shapes at once (the Overview totals, the file-type
# breakdown, the treemap at its own depth), and several tabs on the same folder
# ask for the same ones, so a cache of a few entries covers the repeats.
#
# This bounds entries, not bytes. Measured on a 100k-file tree, the largest
# shape the browser asks for (depth 3, default bounds) encodes to ~200 KB, and
# a body is capped by ROLLUP_MAX_NODES regardless of tree size, so eight
# entries is a ceiling near 1.6 MB rather than something that grows with the
# root.
#
# This is a settled-index optimization. During a scan the revision has already
# moved by the time a body is stored, so every stored body is unreachable the
# moment it lands; the reuse shows up once the crawl finishes. Superseded
# bodies age out by insertion order rather than needing to be swept.
ROLLUP_BODY_CACHE_ENTRIES = 8


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

# Temporary v0.8 product-history ceiling retained until server replay is joined
# to bidirectional browser paging. Mounted rows are already bounded independently
# by ``GIT_HISTORY_WINDOW_MAX_ROWS``; this remaining ceiling is removed only when
# every evicted page can be recovered without a false end.
GIT_HISTORY_MAX_ROWS = 500

# Budgets for the v0.9 continuous-history implementation. The evidence and
# derivation live in ``explorations/git-history/README.md``. They are frozen
# before the continuation and virtual-window mechanisms so neither phase can
# choose a convenient unmeasured limit while it is being implemented.
GIT_HISTORY_WINDOW_MAX_ROWS = 256
GIT_HISTORY_WINDOW_OVERSCAN_ROWS = 64
GIT_HISTORY_PAGE_CACHE_PAGES = 8
GIT_HISTORY_SEGMENT_REBASE_PX = 8_000_000
GIT_HISTORY_SESSION_IDLE_TTL_S = 300.0
GIT_HISTORY_SESSION_MAX_ENTRIES = 8
GIT_HISTORY_SESSION_MAX_WALKS = 2
GIT_HISTORY_SESSION_PARSER_MAX_BYTES = 128 * 1024
GIT_HISTORY_SESSION_MAX_STORAGE_BYTES = 64 * 1024 * 1024

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


def client_settings_dict(
    *, syntax_highlight_max_bytes: int = SYNTAX_HIGHLIGHT_MAX_BYTES
) -> dict[str, Any]:
    """The subset of settings injected into the client via the
    index template. Reading from a single dict keeps the JS
    side from duplicating constants.

    Convention: keys here mirror the JS-side constant names
    (``RECENT_LIMIT``, ``RECENT_WINDOW_SECONDS``, …); the client reads
    via ``window.METABROWSER_SETTINGS.RECENT_LIMIT`` etc.
    """

    return {
        "FILE_TYPE_REGISTRY": serialize_file_type_registry(),
        "DISTRIBUTION_COLORS": serialize_distribution_colors(),
        "FILTER_TYPE_PRESETS": FILTER_TYPE_PRESETS,
        "RECENT_DEFAULT_WINDOW": RECENT_DEFAULT_WINDOW,
        "RECENT_LIMIT": RECENT_DEFAULT_LIMIT,
        "RECENT_WINDOW_SECONDS": RECENT_WINDOW_SECONDS,
        "RECENT_CLUSTER_PCT": RECENT_CLUSTER_PCT,
        "RECENT_RECLUSTER_DEBOUNCE_MS": RECENT_RECLUSTER_DEBOUNCE_MS,
        "INDEX_PROGRESS_POLL_MS": INDEX_PROGRESS_POLL_MS,
        "INDEX_PROGRESS_UPDATE_FILES": INDEX_PROGRESS_UPDATE_FILES,
        "PENDING_TALLY_DIAGNOSTIC_DELAY_MS": PENDING_TALLY_DIAGNOSTIC_DELAY_MS,
        "PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT": PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT,
        "TREE_AUTO_EXPAND_FALLBACK_ROWS": TREE_AUTO_EXPAND_FALLBACK_ROWS,
        "SSE_HEARTBEAT_INTERVAL_S": SSE_HEARTBEAT_INTERVAL_S,
        "GIT_LOG_LIMIT": GIT_LOG_DEFAULT_LIMIT,
        "GIT_HISTORY_MAX_ROWS": GIT_HISTORY_MAX_ROWS,
        "GIT_HISTORY_WINDOW_MAX_ROWS": GIT_HISTORY_WINDOW_MAX_ROWS,
        "GIT_HISTORY_WINDOW_OVERSCAN_ROWS": GIT_HISTORY_WINDOW_OVERSCAN_ROWS,
        "GIT_HISTORY_PAGE_CACHE_PAGES": GIT_HISTORY_PAGE_CACHE_PAGES,
        "GIT_HISTORY_SEGMENT_REBASE_PX": GIT_HISTORY_SEGMENT_REBASE_PX,
        "GIT_HOVER_DEBOUNCE_MS": GIT_HOVER_DEBOUNCE_MS,
        "GIT_DETAIL_CACHE_SIZE": GIT_DETAIL_CACHE_SIZE,
        "ROLLUP_DEFAULT_DEPTH": ROLLUP_DEFAULT_DEPTH,
        "ROLLUP_DEFAULT_TOP": ROLLUP_DEFAULT_TOP,
        "ROLLUP_DEFAULT_EXT_TOP": ROLLUP_DEFAULT_EXT_TOP,
        "ROLLUP_DEFAULT_EXT_RANK": ROLLUP_DEFAULT_EXT_RANK,
        "ROLLUP_FILE_TYPE_FILENAME_LIMIT": ROLLUP_FILE_TYPE_FILENAME_LIMIT,
        "ROLLUP_FILE_TYPE_REMAINING_LIMIT": ROLLUP_FILE_TYPE_REMAINING_LIMIT,
        "ROLLUP_WATCH_DEBOUNCE_MS": ROLLUP_WATCH_DEBOUNCE_MS,
        "DIFF_FOLD_THRESHOLD": DIFF_FOLD_THRESHOLD,
        "DIFF_FOLD_VISIBLE": DIFF_FOLD_VISIBLE,
        "SYNTAX_HIGHLIGHT_MAX_BYTES": syntax_highlight_max_bytes,
        "SYNTAX_LANGUAGE_BY_BASENAME": dict(SYNTAX_LANGUAGE_BY_BASENAME),
        "SYNTAX_LANGUAGE_BY_EXTENSION": dict(SYNTAX_LANGUAGE_BY_EXTENSION),
        "TEXT_PREVIEW_CHUNK_BYTES": TEXT_PREVIEW_CHUNK_BYTES,
        "TEXT_PREVIEW_MAX_CHUNK_BYTES": TEXT_PREVIEW_MAX_CHUNK_BYTES,
    }


__all__ = [
    "ACTIVE_TRACKER_INTERVAL_S",
    "ACTIVE_TRACKER_QUIET_POLLS",
    "DEFAULT_BROWSER_PORT",
    "DEFAULT_EXECUTOR_WORKERS",
    "FOLDER_DISCOVERY_MAX_ENTRIES",
    "GIT_COMMIT_MAX_FILES",
    "GIT_DETAIL_CACHE_SIZE",
    "GIT_HISTORY_MAX_ROWS",
    "GIT_HISTORY_PAGE_CACHE_PAGES",
    "GIT_HISTORY_SEGMENT_REBASE_PX",
    "GIT_HISTORY_SESSION_IDLE_TTL_S",
    "GIT_HISTORY_SESSION_MAX_ENTRIES",
    "GIT_HISTORY_SESSION_MAX_STORAGE_BYTES",
    "GIT_HISTORY_SESSION_MAX_WALKS",
    "GIT_HISTORY_SESSION_PARSER_MAX_BYTES",
    "GIT_HISTORY_WINDOW_MAX_ROWS",
    "GIT_HISTORY_WINDOW_OVERSCAN_ROWS",
    "GIT_HOVER_DEBOUNCE_MS",
    "GIT_LOG_DEFAULT_LIMIT",
    "GIT_LOG_MAX_LIMIT",
    "GIT_LOG_MAX_SKIP",
    "GIT_REPO_INFO_TTL_S",
    "GIT_SUBPROCESS_MAX_BYTES",
    "GIT_SUBPROCESS_TIMEOUT_S",
    "INDEX_PROGRESS_POLL_MS",
    "INDEX_PROGRESS_UPDATE_FILES",
    "INVENTORY_MAX_DEPTH",
    "INVENTORY_MAX_FILES",
    "INVENTORY_REFRESH_TTL_S",
    "INVENTORY_WALKER_EMIT_BATCH",
    "LIVE_FILE_WINDOW_S",
    "PENDING_TALLY_DIAGNOSTIC_DELAY_MS",
    "PENDING_TALLY_DIAGNOSTIC_MAX_BODY_BYTES",
    "PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT",
    "RECENT_CLUSTER_PCT",
    "RECENT_DEFAULT_LIMIT",
    "RECENT_DEFAULT_WINDOW",
    "RECENT_MAX_LIMIT",
    "RECENT_RECLUSTER_DEBOUNCE_MS",
    "RECENT_WINDOW_SECONDS",
    "ROLLUP_BODY_CACHE_ENTRIES",
    "ROLLUP_DEFAULT_DEPTH",
    "ROLLUP_DEFAULT_EXT_RANK",
    "ROLLUP_DEFAULT_EXT_TOP",
    "ROLLUP_DEFAULT_TOP",
    "ROLLUP_FILE_TYPE_FILENAME_LIMIT",
    "ROLLUP_FILE_TYPE_REMAINING_LIMIT",
    "ROLLUP_MAX_DEPTH",
    "ROLLUP_MAX_EXT_TOP",
    "ROLLUP_MAX_NODES",
    "ROLLUP_MAX_TOP",
    "ROLLUP_WATCH_DEBOUNCE_MS",
    "SSE_BUS_INVENTORY_QUEUE_SIZE",
    "SSE_HEARTBEAT_INTERVAL_S",
    "SSE_PER_CONNECTION_QUEUE_SIZE",
    "SSE_RING_BUFFER_CAPACITY",
    "SYNTAX_HIGHLIGHT_MAX_BYTES",
    "TEXT_PREVIEW_CHUNK_BYTES",
    "TEXT_PREVIEW_MAX_CHUNK_BYTES",
    "TEXT_PREVIEW_REQUEST_MAX_BYTES",
    "TREE_AUTO_EXPAND_FALLBACK_ROWS",
    "client_settings_dict",
]
