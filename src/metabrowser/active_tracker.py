"""Provider-neutral activity tracking on the sparse host overlay.

The inventory provider remains the sole owner of filesystem facts. Each tick reads a
bounded catalog image, probes only conventional runtime files, sends verified refresh
hints for metadata mismatches, and then patches the activity-owned overlay fields.
Decoration changes therefore reach the existing filesystem event wire without
changing provider versions, rollup validators, or catalog cache keys.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from metabrowser.activity import TRACKABLE_FILE_MAX_SIZE, ActivityPoll, FileActivityTracker
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.inventory_engine.contract import (
    MAX_COMMAND_PATHS,
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    InventoryConfig,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshReason,
    RefreshRequest,
)
from metabrowser.inventory_engine.coordinator import InventoryCoordinator
from metabrowser.inventory_engine.overlay import (
    InventoryDecoration,
    InventoryDecorationPatch,
)
from metabrowser.settings import ACTIVE_TRACKER_INTERVAL_S, ACTIVE_TRACKER_QUIET_POLLS

LOG = logging.getLogger(__name__)
_ACTIVITY_LABEL = "pid_alive"
_SCOPED_DIRS = frozenset({LOGS_DIR, STATE_DIR})


@dataclass(slots=True)
class _TrackerState:
    """Mutable state owned by one lifespan tracker task."""

    quiet_counters: dict[str, int] = field(default_factory=dict)
    active_paths: set[str] = field(default_factory=set)
    candidates: set[str] = field(default_factory=set)
    pending_refresh: dict[str, ObservationKind] = field(default_factory=dict)


def _is_trackable(record: CatalogRecord, *, root_is_scoped: bool = False) -> bool:
    """Whether one catalog file belongs to the bounded activity set."""

    path = PurePosixPath(record.path)
    if path.suffix.lower() not in BROWSER_TRACKABLE_EXTS:
        return False
    if record.size >= TRACKABLE_FILE_MAX_SIZE:
        return False
    return root_is_scoped or any(part in _SCOPED_DIRS for part in path.parts[:-1])


async def _read_candidates(
    coordinator: InventoryCoordinator,
    *,
    config: InventoryConfig,
    root: Path,
) -> tuple[tuple[CatalogRecord, ...], dict[str, InventoryDecoration]]:
    """Read the bounded activity candidate set at the provider boundary."""

    root_is_scoped = root.name in _SCOPED_DIRS
    read = await coordinator.read(
        ReadRequest(
            queries=(
                CatalogQuery(
                    query_id="activity-candidates",
                    max_rows=config.max_files,
                    include_ignored=True,
                    terminal_extensions=tuple(sorted(BROWSER_TRACKABLE_EXTS)),
                    ancestor_names=() if root_is_scoped else tuple(sorted(_SCOPED_DIRS)),
                    size_less_than=TRACKABLE_FILE_MAX_SIZE,
                ),
            )
        ),
        include_catalog_decorations=True,
    )
    projection = read.result.projection("activity-candidates")
    if not isinstance(projection, CatalogProjection):
        raise TypeError("the activity catalog read returned the wrong projection")
    records = projection.records
    if any(not _is_trackable(record, root_is_scoped=root_is_scoped) for record in records):
        raise TypeError("the activity catalog returned a record outside its predicates")
    decorations = dict(read.decorations)
    return records, decorations


def _pid_label(path: Path, tracker: FileActivityTracker) -> str | None:
    if path.suffix.lower() != ".jsonl":
        return None
    try:
        pid_paths = sorted(path.parent.glob("*.pid"))
    except OSError:
        return None
    if not pid_paths:
        return None
    return "1" if tracker.check_pid_alive(pid_paths[0]) else "0"


def _compute_updates(
    *,
    root: Path,
    records: tuple[CatalogRecord, ...],
    poll: ActivityPoll,
    tracker: FileActivityTracker,
    state: _TrackerState,
) -> dict[str, InventoryDecorationPatch]:
    """Derive refresh hints and ownership-safe decoration patches off-loop."""

    by_absolute = {str(root / record.path): record for record in records}
    missing_absolute = set(poll.missing)
    missing_relative = {
        record.path for absolute, record in by_absolute.items() if absolute in missing_absolute
    }

    for absolute, size, mtime_ns in poll.observed:
        record = by_absolute.get(absolute)
        if record is None:
            continue
        if (size, mtime_ns) != (record.size, record.mtime_ns):
            state.pending_refresh[record.path] = ObservationKind.MODIFIED
    for path in missing_relative:
        state.pending_refresh[path] = ObservationKind.DELETED

    active_absolute = set(poll.active)
    current = {record.path for record in records} - missing_relative
    stale = state.candidates - current
    patches: dict[str, InventoryDecorationPatch] = {
        path: InventoryDecorationPatch(
            active=False,
            labels=((_ACTIVITY_LABEL, None),),
        )
        for path in stale | missing_relative
    }

    for record in records:
        if record.path in missing_relative:
            continue
        absolute = root / record.path
        is_recent = str(absolute) in active_absolute
        previous_quiet = state.quiet_counters.get(
            record.path,
            ACTIVE_TRACKER_QUIET_POLLS + 1,
        )
        if is_recent:
            active = True
            state.quiet_counters[record.path] = 0
        else:
            quiet = previous_quiet + 1
            state.quiet_counters[record.path] = quiet
            active = record.path in state.active_paths and quiet <= ACTIVE_TRACKER_QUIET_POLLS
        if active:
            state.active_paths.add(record.path)
        else:
            state.active_paths.discard(record.path)
        patches[record.path] = InventoryDecorationPatch(
            active=active,
            labels=((_ACTIVITY_LABEL, _pid_label(absolute, tracker)),),
        )

    for path in stale | missing_relative:
        state.quiet_counters.pop(path, None)
        state.active_paths.discard(path)
    state.candidates = current
    return patches


async def _submit_pending_refreshes(
    coordinator: InventoryCoordinator,
    state: _TrackerState,
) -> None:
    """Submit bounded refresh batches, retaining any failed work for retry."""

    pending = tuple(state.pending_refresh.items())
    for offset in range(0, len(pending), MAX_COMMAND_PATHS):
        batch = pending[offset : offset + MAX_COMMAND_PATHS]
        receipt = await coordinator.refresh(
            RefreshRequest(
                observations=tuple(
                    RefreshObservation(path=path, kind=kind) for path, kind in batch
                ),
                reason=RefreshReason.ACTIVITY_OBSERVATION,
            )
        )
        for path in receipt.accepted_paths:
            state.pending_refresh.pop(path, None)
        if receipt.rejected_paths:
            LOG.warning(
                "activity refresh rejected %d provider-derived path(s)",
                len(receipt.rejected_paths),
            )


async def _tick(
    coordinator: InventoryCoordinator,
    root: Path,
    config: InventoryConfig,
    state: _TrackerState,
    tracker: FileActivityTracker,
) -> None:
    """Run one bounded probe, refresh, and overlay-update cycle."""

    records, _decorations = await _read_candidates(
        coordinator,
        config=config,
        root=root,
    )
    absolute_paths = [root / record.path for record in records]
    poll = await asyncio.to_thread(tracker.poll_observations, absolute_paths)
    patches = await asyncio.to_thread(
        _compute_updates,
        root=root,
        records=records,
        poll=poll,
        tracker=tracker,
        state=state,
    )

    refresh_error: Exception | None = None
    try:
        await _submit_pending_refreshes(coordinator, state)
    except Exception as error:
        refresh_error = error
    if patches:
        await coordinator.patch_decorations(patches)
    if refresh_error is not None:
        raise refresh_error


async def activity_snapshot(
    coordinator: InventoryCoordinator,
    *,
    config: InventoryConfig,
    root: Path,
) -> list[dict[str, object]]:
    """Return the existing activity wire snapshot from one coherent host read."""

    records, decorations = await _read_candidates(coordinator, config=config, root=root)
    active_files: list[dict[str, object]] = []
    for record in records:
        decoration = decorations.get(record.path)
        if decoration is None or not decoration.active:
            continue
        item: dict[str, object] = {"path": record.path}
        labels = dict(decoration.labels)
        pid_alive = labels.get(_ACTIVITY_LABEL)
        if pid_alive is not None:
            item["pid_alive"] = pid_alive == "1"
        active_files.append(item)
    return active_files


async def run_active_tracker(
    *,
    coordinator: InventoryCoordinator,
    config: InventoryConfig,
    root: Path,
    interval_s: float = ACTIVE_TRACKER_INTERVAL_S,
) -> None:
    """Poll until lifespan cancellation, isolating transient tick failures."""

    state = _TrackerState()
    tracker = FileActivityTracker()
    LOG.debug("activity tracker starting at %s", root)
    try:
        while True:
            try:
                await _tick(coordinator, root, config, state, tracker)
            except Exception:
                LOG.exception("activity tracker tick failed; continuing")
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        LOG.debug("activity tracker cancelled")
        raise


__all__ = ["activity_snapshot", "run_active_tracker"]
