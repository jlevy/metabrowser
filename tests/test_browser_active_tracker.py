"""Provider-neutral activity tracker and sparse-overlay behavior."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from metabrowser import active_tracker
from metabrowser import server as proc_browser
from metabrowser.active_tracker import _is_trackable, _tick, _TrackerState
from metabrowser.activity import TRACKABLE_FILE_MAX_SIZE, ActivityPoll, FileActivityTracker
from metabrowser.events import CatalogChange, FsChange, FsUpsert
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    EntryQuery,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshReason,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
)
from metabrowser.inventory_engine.overlay import (
    InventoryDecoration,
    InventoryDecorationPatch,
)
from metabrowser.inventory_engine.runtime import default_inventory_config
from metabrowser.settings import ACTIVE_TRACKER_QUIET_POLLS, ACTIVE_TRACKER_SWEEP_FILES
from tests.inventory_harness import InventoryHarness, inventory_harness


def _record(path: str, *, size: int = 10) -> CatalogRecord:
    return CatalogRecord(
        path=path,
        logical_extension=Path(path).suffix,
        size=size,
        mtime_ns=1,
    )


def test_trackable_catalog_records_are_scoped_bounded_and_uncompressed() -> None:
    assert _is_trackable(_record("runs/x/.logs/foo.jsonl"))
    assert _is_trackable(_record("runs/x/.state/status.yaml"))
    assert not _is_trackable(_record("docs/notes.md"))
    assert not _is_trackable(_record("runs/x/.logs/archive.jsonl.gz"))
    assert not _is_trackable(_record("runs/x/.logs/huge.jsonl", size=TRACKABLE_FILE_MAX_SIZE))
    assert _is_trackable(_record("live.jsonl"), root_is_scoped=True)


def _setup_fixture(root: Path, *, with_pid: bool = False) -> Path:
    logs = root / "runs" / "x" / ".logs"
    logs.mkdir(parents=True)
    log = logs / "foo.jsonl"
    log.write_text('{"event":"start"}\n')
    if with_pid:
        (logs / "worker.pid").write_text(f"{os.getpid()}\n")
    return log


async def _entry(harness: InventoryHarness, path: str):
    read = await harness.runtime.coordinator.read(
        ReadRequest(queries=(EntryQuery(query_id="entry", path=path),))
    )
    return read, read.entries[path]


def test_tick_refreshes_facts_then_marks_the_overlay_active(tmp_path: Path) -> None:
    log = _setup_fixture(tmp_path)
    renamed = log.with_name("progress%20.jsonl")
    log.rename(renamed)
    log = renamed

    async def run() -> None:
        async with inventory_harness(tmp_path) as harness:
            state = _TrackerState()
            tracker = FileActivityTracker(stale_after_s=60.0)
            await _tick(
                harness.runtime.coordinator,
                tmp_path,
                harness.runtime.config,
                state,
                tracker,
            )
            baseline, baseline_entry = await _entry(harness, "runs/x/.logs/progress%2520.jsonl")
            assert not baseline_entry.decoration.active

            log.write_text('{"event":"start"}\n{"event":"step"}\n')
            await _tick(
                harness.runtime.coordinator,
                tmp_path,
                harness.runtime.config,
                state,
                tracker,
            )
            updated, updated_entry = await _entry(harness, "runs/x/.logs/progress%2520.jsonl")
            assert updated_entry.decoration.active
            assert updated_entry.facts.size == log.stat().st_size
            assert updated.version.engine.sequence > baseline.version.engine.sequence

    asyncio.run(run())


def test_quiet_overlay_transition_preserves_engine_version_and_clears_pid_label(
    tmp_path: Path,
) -> None:
    log = _setup_fixture(tmp_path, with_pid=True)

    async def run() -> None:
        # This assertion isolates overlay writes. A delayed native watch event for
        # the earlier file write may legitimately advance the engine version.
        config = replace(default_inventory_config(), watch_mode="off")
        async with inventory_harness(tmp_path, config=config) as harness:
            state = _TrackerState()
            tracker = FileActivityTracker(stale_after_s=1e-9)
            await _tick(
                harness.runtime.coordinator,
                tmp_path,
                harness.runtime.config,
                state,
                tracker,
            )
            baseline, seeded = await _entry(harness, "runs/x/.logs/foo.jsonl")
            assert "pid_alive" not in dict(seeded.decoration.labels)
            assert baseline.version.engine.sequence == baseline.result.version.sequence

            log.write_text('{"event":"step"}\n')
            await _tick(
                harness.runtime.coordinator,
                tmp_path,
                harness.runtime.config,
                state,
                tracker,
            )
            changed, active = await _entry(harness, "runs/x/.logs/foo.jsonl")
            assert active.decoration.active
            assert dict(active.decoration.labels)["pid_alive"] == "1"
            engine_after_write = changed.version.engine

            for _ in range(ACTIVE_TRACKER_QUIET_POLLS + 1):
                await _tick(
                    harness.runtime.coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                )
            quiet, quiet_entry = await _entry(harness, "runs/x/.logs/foo.jsonl")
            assert not quiet_entry.decoration.active
            assert "pid_alive" not in dict(quiet_entry.decoration.labels)
            assert quiet.version.engine == engine_after_write

    asyncio.run(run())


# Small enough that a test tree is several sweeps long.
_SWEEP = 4
_LOGS = 3 * _SWEEP + 1


class _CountingTracker(FileActivityTracker):
    """Record which paths each poll probed."""

    def __init__(self) -> None:
        super().__init__(stale_after_s=60.0)
        self.polls: list[tuple[str, ...]] = []

    def poll_observations(self, paths: Iterable[str]) -> ActivityPoll:
        probed = tuple(paths)
        self.polls.append(probed)
        return super().poll_observations(probed)


def _setup_many_logs(root: Path) -> list[Path]:
    logs_dir = root / "runs" / "x" / ".logs"
    logs_dir.mkdir(parents=True)
    logs = [logs_dir / f"step-{n:02d}.jsonl" for n in range(_LOGS)]
    for log in logs:
        log.write_text('{"event":"start"}\n')
    return logs


def _count_catalog_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    reads: list[int] = []
    real_read = active_tracker._read_candidates

    async def counted(*args: Any, **kwargs: Any) -> Any:
        reads.append(1)
        return await real_read(*args, **kwargs)

    monkeypatch.setattr(active_tracker, "_read_candidates", counted)
    return reads


def test_tick_sweeps_by_the_documented_default() -> None:
    default = inspect.signature(_tick).parameters["sweep_files"].default
    assert default == ACTIVE_TRACKER_SWEEP_FILES


def test_idle_tick_probes_one_sweep_and_rereads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An idle tick's work is the sweep, however many candidates there are."""

    logs = _setup_many_logs(tmp_path)
    reads = _count_catalog_reads(monkeypatch)

    async def run() -> None:
        config = replace(default_inventory_config(), watch_mode="off")
        async with inventory_harness(tmp_path, config=config) as harness:
            state = _TrackerState()
            tracker = _CountingTracker()

            async def tick() -> None:
                await _tick(
                    harness.runtime.coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                    sweep_files=_SWEEP,
                )

            # The first tick reads the candidates and gives each its baseline.
            await tick()
            assert len(reads) == 1
            assert len(tracker.polls[0]) == _LOGS

            idle_ticks = 2 * _LOGS
            for _ in range(idle_ticks):
                await tick()
            idle_polls = tracker.polls[1:]
            assert len(reads) == 1, "an idle tick reread the catalog"
            assert [len(poll) for poll in idle_polls] == [_SWEEP] * idle_ticks
            # The sweep reaches every candidate in the fewest ticks that can hold them.
            one_pass = -(-_LOGS // _SWEEP)
            swept = {path for poll in idle_polls[:one_pass] for path in poll}
            assert swept == {str(log) for log in logs}
            assert not state.active_paths and not state.quiet_counters

    asyncio.run(run())


def test_unreported_write_is_found_by_the_sweep_then_probed_every_tick(tmp_path: Path) -> None:
    """With no watcher, a cold file's write waits at most one pass of the sweep."""

    logs = _setup_many_logs(tmp_path)
    written = logs[-1]

    async def run() -> None:
        config = replace(default_inventory_config(), watch_mode="off")
        async with inventory_harness(tmp_path, config=config) as harness:
            state = _TrackerState()
            tracker = _CountingTracker()

            async def tick() -> bool:
                await _tick(
                    harness.runtime.coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                    sweep_files=_SWEEP,
                )
                _read, entry = await _entry(harness, "runs/x/.logs/" + written.name)
                return entry.decoration.active

            assert not await tick()
            written.write_text('{"event":"start"}\n{"event":"step"}\n')
            one_pass = -(-_LOGS // _SWEEP)
            ticks = 1
            while not await tick():
                ticks += 1
                assert ticks <= one_pass, "a full pass of the sweep missed the write"

            # Once active it is probed on every tick, not once a pass.
            before = len(tracker.polls)
            for _ in range(one_pass):
                assert await tick()
            assert all(str(written) in poll for poll in tracker.polls[before:])

    asyncio.run(run())


def test_catalog_reported_write_is_probed_on_the_next_tick(tmp_path: Path) -> None:
    """A write the provider learned of, as its watcher reports one, skips the sweep."""

    logs = _setup_many_logs(tmp_path)

    async def run() -> None:
        config = replace(default_inventory_config(), watch_mode="off")
        async with inventory_harness(tmp_path, config=config) as harness:
            coordinator = harness.runtime.coordinator
            state = _TrackerState()
            tracker = _CountingTracker()

            async def tick() -> None:
                await _tick(
                    coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                    sweep_files=_SWEEP,
                )

            await tick()
            await tick()
            # The next sweep starts where the last one ended, so the file the sweep
            # just passed is the one it would reach last.
            written = Path(tracker.polls[-1][0])
            assert str(written) not in {str(log) for log in logs[2 * _SWEEP :]}
            written.write_text('{"event":"start"}\n{"event":"step"}\n')
            path = "runs/x/.logs/" + written.name
            receipt = await coordinator.refresh(
                RefreshRequest(
                    observations=(RefreshObservation(path=path, kind=ObservationKind.MODIFIED),),
                    reason=RefreshReason.ACTIVITY_OBSERVATION,
                )
            )
            assert receipt.accepted_paths == (path,)

            await tick()
            assert str(written) in tracker.polls[-1]
            assert len(tracker.polls[-1]) == _SWEEP + 1
            _read, entry = await _entry(harness, path)
            assert entry.decoration.active

    asyncio.run(run())


def test_activity_patch_preserves_other_fields_and_cache_inputs(tmp_path: Path) -> None:
    _setup_fixture(tmp_path)

    async def read_products(harness: InventoryHarness):
        read = await harness.runtime.coordinator.read(
            ReadRequest(
                queries=(
                    CatalogQuery(query_id="catalog", max_rows=100),
                    RollupQuery(query_id="rollup"),
                )
            )
        )
        catalog = read.result.projection("catalog")
        rollup = read.result.projection("rollup")
        assert isinstance(catalog, CatalogProjection)
        assert isinstance(rollup, RollupProjection)
        return read, catalog, rollup

    async def run() -> None:
        async with inventory_harness(tmp_path) as harness:
            path = "runs/x/.logs/foo.jsonl"
            await harness.runtime.coordinator.replace_decoration(
                path,
                InventoryDecoration(
                    views=("source",),
                    labels=(("plugin_state", "ready"),),
                ),
            )
            before, before_catalog, before_rollup = await read_products(harness)
            await harness.runtime.coordinator.patch_decorations(
                {
                    path: InventoryDecorationPatch(
                        active=True,
                        labels=(("pid_alive", "1"),),
                    )
                }
            )
            after, after_catalog, after_rollup = await read_products(harness)
            _read, decorated = await _entry(harness, path)

            assert after.version.engine == before.version.engine
            assert after.version.overlay_revision > before.version.overlay_revision
            assert after_catalog.records == before_catalog.records
            assert after_rollup.payload == before_rollup.payload
            assert decorated.decoration.views == ("source",)
            assert dict(decorated.decoration.labels) == {
                "pid_alive": "1",
                "plugin_state": "ready",
            }

    asyncio.run(run())


def test_decoration_change_emits_fs_upsert_without_catalog_delta(tmp_path: Path) -> None:
    _setup_fixture(tmp_path)

    async def run() -> None:
        async with inventory_harness(tmp_path) as harness:
            path = "runs/x/.logs/foo.jsonl"
            queue = harness.bus.attach_connection()
            try:
                await harness.runtime.coordinator.patch_decorations(
                    {path: InventoryDecorationPatch(active=True)}
                )
                envelope = await asyncio.wait_for(queue.get(), timeout=2.0)
                assert isinstance(envelope.event, FsChange)
                upserts = [
                    operation for operation in envelope.event.ops if isinstance(operation, FsUpsert)
                ]
                assert len(upserts) == 1
                assert upserts[0].entry.path == path
                assert upserts[0].entry.active
                # A second change is the marker. A catalog delta is queued right after
                # the change it belongs to, so reading up to the marker sees whatever
                # the first change emitted; a pause could only see nothing yet.
                await harness.runtime.coordinator.patch_decorations(
                    {path: InventoryDecorationPatch(active=False)}
                )
                async with asyncio.timeout(5):
                    while True:
                        envelope = await queue.get()
                        assert not isinstance(envelope.event, CatalogChange)
                        if isinstance(envelope.event, FsChange):
                            break
                (marker,) = envelope.event.ops
                assert isinstance(marker, FsUpsert)
                assert marker.entry.path == path and not marker.entry.active
            finally:
                harness.bus.detach_connection(queue)

    asyncio.run(run())


def test_api_activity_reads_the_same_overlay_snapshot(tmp_path: Path) -> None:
    _setup_fixture(tmp_path)

    async def run() -> dict[str, object]:
        async with inventory_harness(tmp_path) as harness:
            await harness.runtime.coordinator.patch_decorations(
                {
                    "runs/x/.logs/foo.jsonl": InventoryDecorationPatch(
                        active=True,
                        labels=(("pid_alive", "1"),),
                    )
                }
            )
            request = SimpleNamespace(app=harness.app)
            response = await proc_browser.api_activity(cast(Any, request))
            return cast(dict[str, object], json.loads(bytes(response.body)))

    body = asyncio.run(run())
    assert body == {
        "active_files": [{"path": "runs/x/.logs/foo.jsonl", "pid_alive": True}],
        "poll_interval_ms": 5_000,
    }
