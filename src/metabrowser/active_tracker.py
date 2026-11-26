"""Provider-neutral activity tracking on the sparse host overlay.

The inventory provider remains the sole owner of filesystem facts. The tracker keeps
the catalog's candidate set, the conventional runtime files, and rereads it only when
the engine version moves. Each tick probes three groups of candidates: the files it is
showing as active, the files whose catalog facts just changed, and the next
``ACTIVE_TRACKER_SWEEP_FILES`` of a rotating sweep over all of them. It sends verified
refresh hints for metadata mismatches and patches the activity-owned overlay fields of
the files whose activity changed. Decoration changes therefore reach the existing
filesystem event wire without changing provider versions, rollup validators, or catalog
cache keys.

An idle tick therefore costs the sweep and nothing that grows with the candidate set.
A write the provider's watcher reports lights its file on the next tick, as probing
every candidate did. A write nothing reports, because the watcher is off or the tree is
past the inventory cap, waits for the sweep: at most one tick where the candidates fit
in one sweep, and otherwise one tick for every ``ACTIVE_TRACKER_SWEEP_FILES``
candidates.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from metabrowser.activity import TRACKABLE_FILE_MAX_SIZE, ActivityPoll, FileActivityTracker
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.inventory_engine.contract import (
    MAX_COMMAND_PATHS,
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    EngineVersion,
    InventoryConfig,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshReason,
    RefreshRequest,
    native_inventory_path,
)
from metabrowser.inventory_engine.coordinator import InventoryConsistencyError, InventoryCoordinator
from metabrowser.inventory_engine.overlay import (
    InventoryDecoration,
    InventoryDecorationPatch,
)
from metabrowser.settings import (
    ACTIVE_TRACKER_INTERVAL_S,
    ACTIVE_TRACKER_QUIET_POLLS,
    ACTIVE_TRACKER_SWEEP_FILES,
)

LOG = logging.getLogger(__name__)
_ACTIVITY_LABEL = "pid_alive"
_SCOPED_DIRS = frozenset({LOGS_DIR, STATE_DIR})


@dataclass(slots=True)
class _TrackerState:
    """Mutable state owned by one lifespan tracker task."""

    # How many polls each active path has gone without a change.
    quiet_counters: dict[str, int] = field(default_factory=dict)
    active_paths: set[str] = field(default_factory=set)
    pending_refresh: dict[str, ObservationKind] = field(default_factory=dict)
    # The engine version the candidate set below was read at; None before the first read.
    catalog_version: EngineVersion | None = None
    # Every candidate's catalog ``(size, mtime_ns)``, in catalog order.
    fingerprints: dict[str, tuple[int, int]] = field(default_factory=dict)
    sweep_order: tuple[str, ...] = ()
    sweep_cursor: int = 0
    # Candidates whose catalog facts are new or changed and that no tick has probed yet.
    due: set[str] = field(default_factory=set)
    # Former candidates whose baselines and decorations the next tick clears.
    retired: set[str] = field(default_factory=set)


def _candidate_path(root: Path, path: str) -> str:
    """Cross from a provider identity to the platform name used by activity probes."""

    native = native_inventory_path(path)
    if native is None:
        raise InventoryConsistencyError("activity catalog returned a noncanonical path")
    return str(root / native)


def _is_trackable(record: CatalogRecord, *, root_is_scoped: bool = False) -> bool:
    """Whether one catalog file belongs to the bounded activity set."""

    # A canonical path is `/`-separated with no empty or dot segments, so string
    # splits name the same parts a path object would, without building one for every
    # record of a catalog read.
    folder, _separator, name = record.path.rpartition("/")
    if os.path.splitext(name)[1].lower() not in BROWSER_TRACKABLE_EXTS:
        return False
    if record.size >= TRACKABLE_FILE_MAX_SIZE:
        return False
    return root_is_scoped or not _SCOPED_DIRS.isdisjoint(folder.split("/"))


async def _read_candidates(
    coordinator: InventoryCoordinator,
    *,
    config: InventoryConfig,
    root: Path,
    include_decorations: bool = True,
) -> tuple[tuple[CatalogRecord, ...], dict[str, InventoryDecoration]]:
    """Read the bounded activity candidate set at the provider boundary."""

    root_is_scoped = root.name in _SCOPED_DIRS
    read = await coordinator.read(
        ReadRequest(
            queries=(
                CatalogQuery(
                    query_id="activity-candidates",
                    max_rows=config.budget.max_files,
                    include_ignored=True,
                    terminal_extensions=tuple(sorted(BROWSER_TRACKABLE_EXTS)),
                    ancestor_names=() if root_is_scoped else tuple(sorted(_SCOPED_DIRS)),
                    size_less_than=TRACKABLE_FILE_MAX_SIZE,
                ),
            )
        ),
        include_catalog_decorations=include_decorations,
    )
    projection = read.result.completed_projection("activity-candidates")
    if not isinstance(projection, CatalogProjection):
        raise TypeError("the activity catalog read returned the wrong projection")
    records = projection.records
    if any(not _is_trackable(record, root_is_scoped=root_is_scoped) for record in records):
        raise TypeError("the activity catalog returned a record outside its predicates")
    decorations = dict(read.decorations)
    return records, decorations


def _adopt_candidates(state: _TrackerState, records: tuple[CatalogRecord, ...]) -> None:
    """Replace the candidate set, noting what the catalog added, changed, and dropped."""

    previous = state.fingerprints
    fingerprints = {record.path: (record.size, record.mtime_ns) for record in records}
    state.due.intersection_update(fingerprints.keys())
    state.due.update(
        path for path, fingerprint in fingerprints.items() if previous.get(path) != fingerprint
    )
    state.retired.difference_update(fingerprints.keys())
    state.retired.update(previous.keys() - fingerprints.keys())
    state.fingerprints = fingerprints
    state.sweep_order = tuple(fingerprints)


async def _refresh_candidates(
    coordinator: InventoryCoordinator,
    *,
    config: InventoryConfig,
    root: Path,
    state: _TrackerState,
) -> None:
    """Reread the candidate set if the engine version moved since the last read.

    The version is the one the coordinator held before the read, so a change that
    lands during the read moves the version past it and the next tick reads again.
    """

    _cursor, version, _state = await coordinator.checkpoint()
    if state.catalog_version == version.engine:
        return
    records, _decorations = await _read_candidates(
        coordinator,
        config=config,
        root=root,
        include_decorations=False,
    )
    await asyncio.to_thread(_adopt_candidates, state, records)
    state.catalog_version = version.engine


def _select_probes(state: _TrackerState, sweep_files: int) -> tuple[str, ...]:
    """Choose this tick's probes and advance the sweep past the ones it takes."""

    order = state.sweep_order
    if len(order) <= sweep_files:
        swept = order
    else:
        start = state.sweep_cursor % len(order)
        end = start + sweep_files
        swept = order[start:end] + order[: max(0, end - len(order))]
        state.sweep_cursor = end % len(order)
    probes = dict.fromkeys(swept)
    known = state.fingerprints
    probes.update(dict.fromkeys(sorted(path for path in state.active_paths if path in known)))
    probes.update(dict.fromkeys(sorted(state.due)))
    return tuple(probes)


def _poll_candidates(
    root: Path,
    probes: Iterable[str],
    tracker: FileActivityTracker,
) -> tuple[dict[str, str], ActivityPoll]:
    """Probe *probes* off-loop, returning each one's absolute name with the poll."""

    paths = {_candidate_path(root, path): path for path in probes}
    return paths, tracker.poll_observations(paths)


def _pid_label(path: Path, tracker: FileActivityTracker) -> str | None:
    try:
        pid_paths = sorted(path.glob("*.pid"))
    except OSError:
        return None
    if not pid_paths:
        return None
    return "1" if tracker.check_pid_alive(pid_paths[0]) else "0"


def _compute_updates(
    *,
    root: Path,
    paths: dict[str, str],
    poll: ActivityPoll,
    tracker: FileActivityTracker,
    state: _TrackerState,
) -> dict[str, InventoryDecorationPatch]:
    """Derive refresh hints and ownership-safe decoration patches off-loop.

    *paths* maps each probed absolute name to its candidate. A patch is made only for
    a file that is active or just stopped being active, so a quiet candidate costs its
    probe and no more. The pid label is published with the active flag and cleared
    with it: the browser reads it only on an active file, and one process lookup per
    folder of active logs replaces one per JSONL candidate.
    """

    missing = {paths[absolute] for absolute in poll.missing if absolute in paths}
    for absolute, size, mtime_ns in poll.observed:
        path = paths.get(absolute)
        if path is None:
            continue
        if (size, mtime_ns) != state.fingerprints.get(path):
            state.pending_refresh[path] = ObservationKind.MODIFIED
    for path in missing:
        state.pending_refresh[path] = ObservationKind.DELETED

    cleared = InventoryDecorationPatch(active=False, labels=((_ACTIVITY_LABEL, None),))
    patches: dict[str, InventoryDecorationPatch] = {}
    for path in state.retired | missing:
        if path in state.active_paths:
            patches[path] = cleared
        state.quiet_counters.pop(path, None)
        state.active_paths.discard(path)
    tracker.forget(_candidate_path(root, path) for path in state.retired)
    state.retired.clear()

    recent = {paths[absolute] for absolute in poll.active if absolute in paths}
    pid_labels: dict[Path, str | None] = {}
    for absolute, path in paths.items():
        if path in missing:
            continue
        if path in recent:
            state.quiet_counters[path] = 0
            active = True
        elif path in state.active_paths:
            quiet = state.quiet_counters.get(path, 0) + 1
            state.quiet_counters[path] = quiet
            active = quiet <= ACTIVE_TRACKER_QUIET_POLLS
        else:
            continue
        if not active:
            state.active_paths.discard(path)
            state.quiet_counters.pop(path, None)
            patches[path] = cleared
            continue
        state.active_paths.add(path)
        label: str | None = None
        if absolute.lower().endswith(".jsonl"):
            folder = Path(absolute).parent
            if folder not in pid_labels:
                pid_labels[folder] = _pid_label(folder, tracker)
            label = pid_labels[folder]
        patches[path] = InventoryDecorationPatch(
            active=True,
            labels=((_ACTIVITY_LABEL, label),),
        )

    state.due.difference_update(paths.values())
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
    *,
    sweep_files: int = ACTIVE_TRACKER_SWEEP_FILES,
) -> None:
    """Run one bounded probe, refresh, and overlay-update cycle."""

    await _refresh_candidates(coordinator, config=config, root=root, state=state)
    probes = _select_probes(state, sweep_files)
    paths, poll = await asyncio.to_thread(_poll_candidates, root, probes, tracker)
    patches = await asyncio.to_thread(
        _compute_updates,
        root=root,
        paths=paths,
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
