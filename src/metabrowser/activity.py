"""File-activity tracking for the "is this file being written right now?" badge.

Discovers candidate files (JSONL/state/PID files inside ``.logs/`` and
``.state/`` trees), then on each poll re-stats them and reports which
ones changed within ``stale_after_s`` seconds.

Discovery is scoped to ``.logs/`` and ``.state/`` subtrees, where actively
written logs and state files commonly live. Bounding the candidate set prevents
repository size from turning each activity poll into a full-tree stat pass.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from time import monotonic
from time import monotonic as _mono
from typing import Any

from cachetools.func import ttl_cache
from funlog import log_calls

from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.paths_safe import _rel_path, register_root_callback
from metabrowser.settings import SLOW_OPERATION_LOG_SECONDS

LOG = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────

ACTIVITY_POLL_INTERVAL_MS = 5000
TRACKABLE_FILE_MAX_SIZE = 100 * 1024 * 1024
TRACKABLE_DISCOVERY_TTL_SECONDS = 30.0

# Trackable files only carry interesting "is it changing?" signal when
# they're one of these extensions; everything else is noise. Source of
# truth lives in ``metabrowser.file_extensions``; bound here for tests and
# callers that import ``_TRACKABLE_EXTS`` directly.
_TRACKABLE_EXTS = BROWSER_TRACKABLE_EXTS

# Activity tracking is scoped to conventional runtime subtrees. Searching
# the entire repo for changing files (the earlier
# behavior) burns one stat syscall per file per poll for no signal.
_ACTIVITY_SCOPED_DIRS = (LOGS_DIR, STATE_DIR)


# ── Tracker ──────────────────────────────────────────────────────


class FileActivityTracker:
    """Track which files are actively being written to via mtime+size change detection.

    Uses ``stat_result.st_mtime_ns`` directly (no filename hashing or
    ``clean_alphanum_hash`` round-trip) — ``(size, mtime_ns)`` is a
    perfectly good cheap fingerprint and avoids one round of string
    formatting per file per poll.
    """

    def __init__(self, stale_after_s: float = 30.0):
        self.stale_after_s: float = stale_after_s
        # path_str -> (last_fingerprint, last_changed_at_monotonic)
        self._state: dict[str, tuple[tuple[int, int], float]] = {}

    def poll(self, paths: list[Path]) -> list[str]:
        """Re-stat files and return paths that have changed recently."""
        now = monotonic()
        active: list[str] = []
        for p in paths:
            key = str(p)
            try:
                st = p.stat()
                fingerprint = (st.st_size, st.st_mtime_ns)
            except OSError:
                self._state.pop(key, None)
                continue

            prev = self._state.get(key)
            if prev is None:
                # First time seeing this file — seed without marking active.
                self._state[key] = (fingerprint, 0.0)
            elif prev[0] != fingerprint:
                self._state[key] = (fingerprint, now)

            _, last_changed = self._state[key]
            if now - last_changed < self.stale_after_s:
                active.append(key)

        return active

    def check_pid_alive(self, pid_path: Path) -> bool | None:
        """Check if a PID file's process is still running. Returns None if no PID file."""
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False


# Singleton tracker — module-level state intentionally; one tracker per
# server process.
activity_tracker = FileActivityTracker()


# ── Discovery ────────────────────────────────────────────────────


def _scoped_dirs(root: Path) -> list[Path]:
    """Return every ``.logs`` / ``.state`` directory under ``root``.

    Walks scope-relevant directories only (depth-first via scandir) so we
    aren't paying full-tree walk costs on each cache miss.
    """
    found: list[Path] = []
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    name = entry.name
                    if name.startswith(".") and name not in _ACTIVITY_SCOPED_DIRS:
                        continue
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if name in _ACTIVITY_SCOPED_DIRS:
                        found.append(Path(entry.path))
                    else:
                        stack.append(Path(entry.path))
        except (PermissionError, OSError, FileNotFoundError):
            continue
    return found


def _discover_trackable_files_from_inventory(root: Path) -> tuple[Path, ...] | None:
    """Try to read the trackable file set from
    :class:`InventoryIndex`. Returns ``None`` when the inventory
    has no data (walker hasn't reached anywhere yet) so the caller
    can fall back to the live walk.

    Reading the inventory keeps the request path from repeating a
    filesystem discovery walk. Per-file fingerprint checks in
    ``FileActivityTracker.poll`` remain unchanged.
    """

    inv = get_inventory()
    if not inv.entries(scope="all-known"):
        return None

    # The inventory tracks .logs/.state as visible dirs (matches
    # the `_is_visible` rule). Filter file entries whose path
    # contains a `/.logs/` or `/.state/` segment, OR whose top-
    # level dir is one of those (covers a served root that itself
    # *is* a .logs dir, though unusual).
    scoped_segments = ("/.logs/", "/.state/")
    trackable: list[Path] = []
    for entry in inv.entries(scope="all-known"):
        if entry.type != "file":
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        if ext not in _TRACKABLE_EXTS:
            continue
        if entry.size >= TRACKABLE_FILE_MAX_SIZE:
            continue
        # Path-prefix check. ``entry.path`` is relative to the
        # served root, e.g. "runs/x/.logs/foo.jsonl".
        anchored = "/" + entry.path
        if not (
            any(seg in anchored for seg in scoped_segments)
            or entry.parent in (".logs", ".state")
            or entry.parent.endswith("/.logs")
            or entry.parent.endswith("/.state")
        ):
            continue
        trackable.append(root / entry.path)
    return tuple(trackable)


@log_calls(
    level="info",
    show_args=False,
    show_return_value=False,
    if_slower_than=SLOW_OPERATION_LOG_SECONDS,
    include_module=False,
    log_func=LOG.info,
)
def _discover_trackable_files(root: Path) -> tuple[Path, ...]:
    """Collect files worth tracking for activity.

    Reads from :class:`InventoryIndex` when populated (the fast
    path); falls back to walking ``.logs/`` and ``.state/``
    subtrees only when the inventory has no data yet.
    """
    inventory_result = _discover_trackable_files_from_inventory(root)
    if inventory_result is not None:
        return inventory_result

    trackable: list[Path] = []
    for scope in _scoped_dirs(root):
        for dirpath, dirnames, filenames in os.walk(scope):
            # Skip nested hidden dirs (but keep walking into legitimate
            # subdirs of .logs/).
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") or d in _ACTIVITY_SCOPED_DIRS
            ]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _TRACKABLE_EXTS:
                    continue
                fpath = Path(dirpath) / fname
                try:
                    if fpath.stat().st_size < TRACKABLE_FILE_MAX_SIZE:
                        trackable.append(fpath)
                except OSError:
                    continue
    return tuple(trackable)


@ttl_cache(maxsize=64, ttl=TRACKABLE_DISCOVERY_TTL_SECONDS)
def _collect_trackable_files_cached(root: Path) -> tuple[Path, ...]:
    """Return a short-lived cached file discovery result for activity polling."""
    return _discover_trackable_files(root)


def _collect_trackable_files(root: Path) -> list[Path]:
    """Return cached activity candidates as a mutable list for the tracker."""
    return list(_collect_trackable_files_cached(root))


def _activity_snapshot(root: Path) -> list[dict[str, Any]]:
    """Build the browser activity payload."""

    started = _mono()
    paths = _collect_trackable_files(root)
    discovery_elapsed = _mono() - started
    poll_started = _mono()
    active_abs = activity_tracker.poll(paths)
    poll_elapsed = _mono() - poll_started

    active_files: list[dict[str, Any]] = []
    for abs_path_str in active_abs:
        abs_path = Path(abs_path_str)
        rel = _rel_path(abs_path_str)
        entry: dict[str, Any] = {"path": rel}

        if abs_path.suffix.lower() == ".jsonl":
            for pid_path in abs_path.parent.glob("*.pid"):
                alive = activity_tracker.check_pid_alive(pid_path)
                if alive is not None:
                    entry["pid_alive"] = alive
                    break

        active_files.append(entry)

    # DEBUG exposes per-poll work without flooding ordinary server output.
    LOG.debug(
        "_activity_snapshot tracked=%d active=%d discovery=%dms stat_poll=%dms",
        len(paths),
        len(active_files),
        int(discovery_elapsed * 1000),
        int(poll_elapsed * 1000),
    )
    return active_files


def _invalidate_caches() -> None:
    _collect_trackable_files_cached.cache_clear()
    # Reset per-file mtime fingerprints so a root swap doesn't carry
    # stale state forward — old paths from the previous root would
    # otherwise look "new" the first time we re-saw them.
    activity_tracker._state.clear()


register_root_callback(_invalidate_caches)
