"""Active-file tracker — background task that emits ``active``
flag changes on ``FsEntry`` records via the inventory event
plane, replacing client-side ``/api/activity`` polling.

Architecture:

* Periodically walks the inventory's known trackable files
  (``.logs/`` and ``.state/`` dirs, ``BROWSER_TRACKABLE_EXTS``
  extensions only).
* Calls :func:`metabrowser.activity.activity_tracker.poll`
  to fingerprint each file; the existing helper handles
  ``mtime`` + ``size`` change detection and PID-alive checks.
* For each file whose active state changed, replaces the
  ``FsEntry`` with a new instance carrying the updated
  ``active`` flag (and ``pid_alive`` label if applicable),
  then emits an ``fs.change`` op so the SPA's FileStore picks it
  up.

Why this lives here, not as part of the walker: the walker
finalizes structure/aggregates once. Active-file detection is a
recurring poll on a small subset of files. Splitting them keeps
the walker pure and lets active-tracker tune its cadence
independently while sharing a cadence with the compatibility
``/api/activity`` snapshot.

The output is the browser's live source of truth for "is this file
being written?" The compatibility ``/api/activity`` endpoint exposes
the same state as a snapshot for scripted callers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from pathlib import Path

from metabrowser.activity import activity_tracker
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.events import FsEntry, FsUpsert
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.inventory import InventoryIndex
from metabrowser.inventory import get_instance as get_inventory
from metabrowser.settings import (
    ACTIVE_TRACKER_INTERVAL_S,
    ACTIVE_TRACKER_QUIET_POLLS,
)

LOG = logging.getLogger(__name__)


def _is_trackable(entry: FsEntry) -> bool:
    """Match the ``_discover_trackable_files`` rules:
    ``BROWSER_TRACKABLE_EXTS`` files inside ``.logs`` /
    ``.state`` subtrees."""

    if entry.type != "file":
        return False
    name_lower = entry.name.lower()
    ext = ""
    if "." in name_lower:
        # Match against the simple extension; the inventory's
        # compound-tail ``ext`` field could be ``.tar.gz``,
        # which doesn't appear in BROWSER_TRACKABLE_EXTS.
        idx = name_lower.rfind(".")
        ext = name_lower[idx:]
    if ext not in BROWSER_TRACKABLE_EXTS:
        return False
    # Path-segment match — entry.path is relative to root, e.g.
    # "runs/x/.logs/foo.jsonl".
    anchored = "/" + entry.path
    return ("/" + LOGS_DIR + "/") in anchored or ("/" + STATE_DIR + "/") in anchored


def _resolved_abs(root: Path, entry: FsEntry) -> Path:
    """Map an inventory-relative entry to its absolute path."""
    return root / entry.path


def _compute_ops_sync(
    trackable: list[FsEntry],
    abs_paths: list[Path],
    active_set: set[str],
    quiet_counters: dict[str, int],
) -> list[FsUpsert]:
    """Per-entry comparison + per-jsonl pid-alive probe. All sync
    filesystem I/O lives here so the caller can run it via
    ``asyncio.to_thread`` and keep the event loop free."""

    ops: list[FsUpsert] = []
    for entry, abs_path in zip(trackable, abs_paths, strict=True):
        is_active_now = str(abs_path) in active_set
        prev_quiet = quiet_counters.get(entry.path, ACTIVE_TRACKER_QUIET_POLLS + 1)

        new_labels: dict[str, str] = dict(entry.labels)
        # Update PID-alive for .jsonl files in scope.
        if abs_path.suffix.lower() == ".jsonl":
            for pid_path in abs_path.parent.glob("*.pid"):
                alive = activity_tracker.check_pid_alive(pid_path)
                if alive is not None:
                    new_labels["pid_alive"] = "1" if alive else "0"
                    break

        new_active: bool
        if is_active_now:
            new_active = True
            quiet_counters[entry.path] = 0
        else:
            quiet_counters[entry.path] = prev_quiet + 1
            # Stay marked active until quiet_polls polls have
            # elapsed without a change. Smooths the badge so a
            # dispatcher pause-then-resume doesn't blink.
            new_active = entry.active and quiet_counters[entry.path] <= ACTIVE_TRACKER_QUIET_POLLS

        labels_tuple = tuple(sorted(new_labels.items()))
        if new_active != entry.active or labels_tuple != entry.labels:
            ops.append(
                FsUpsert(
                    entry=replace(
                        entry,
                        active=new_active,
                        labels=labels_tuple,
                    )
                )
            )
    return ops


async def _tick(inventory: InventoryIndex, root: Path, quiet_counters: dict[str, int]) -> None:
    """One poll cycle. Emits ``fs.change`` ops for every entry
    whose active state changed.

    The per-entry compare loop runs via ``asyncio.to_thread`` because
    the .jsonl branch glob()s ``*.pid`` siblings and reads them; with
    hundreds of trackable files, doing that on the event loop blocks
    every concurrent ``/api/file`` request for the duration of the
    sweep. The walker emit path (``_apply_walker_entry``) stays on the
    loop — it only manipulates dataclasses + asyncio queues.
    """

    trackable: list[FsEntry] = [e for e in inventory.entries(scope="all-known") if _is_trackable(e)]
    if not trackable:
        return

    # Use absolute paths for the tracker (it stat's filesystem).
    abs_paths = [_resolved_abs(root, e) for e in trackable]
    active_abs = await asyncio.to_thread(activity_tracker.poll, abs_paths)
    active_set = set(active_abs)

    ops = await asyncio.to_thread(
        _compute_ops_sync, trackable, abs_paths, active_set, quiet_counters
    )

    if ops:
        # Single batched apply so the SSE bus sees one ``fs.change``
        # per tick instead of N (where N is the count of active
        # files). Per-op emit through ``_apply_walker_entry`` would
        # push slow subscribers toward the queue-full drop path
        # during routine polling.
        inventory.apply_walker_entries([op.entry for op in ops])


async def run_active_tracker(
    *,
    root: Path,
    interval_s: float = ACTIVE_TRACKER_INTERVAL_S,
) -> None:
    """Long-running coroutine. Spawn from the lifespan hook;
    cancel on shutdown.

    Each tick reads the inventory's known trackable set, polls
    fingerprints, and emits ``fs.change`` ops for any file
    whose active state changed. Errors are logged and the loop
    keeps running — a transient OS-level failure shouldn't kill
    the badge surface.
    """

    quiet_counters: dict[str, int] = {}
    inventory = get_inventory()
    LOG.info("active tracker starting at %s", root)
    try:
        while True:
            try:
                await _tick(inventory, root, quiet_counters)
            except Exception:
                LOG.exception("active tracker tick failed; continuing")
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        LOG.info("active tracker cancelled")
        raise


__all__ = ["run_active_tracker"]
