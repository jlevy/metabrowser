"""Provider-neutral activity tracker and sparse-overlay behavior."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from metabrowser import server as proc_browser
from metabrowser.active_tracker import _is_trackable, _tick, _TrackerState
from metabrowser.activity import TRACKABLE_FILE_MAX_SIZE, FileActivityTracker
from metabrowser.events import CatalogChange, FsChange, FsUpsert
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    EntryQuery,
    ReadRequest,
    RollupProjection,
    RollupQuery,
)
from metabrowser.inventory_engine.overlay import (
    InventoryDecoration,
    InventoryDecorationPatch,
)
from metabrowser.settings import ACTIVE_TRACKER_QUIET_POLLS
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
            baseline, baseline_entry = await _entry(harness, "runs/x/.logs/foo.jsonl")
            assert not baseline_entry.decoration.active

            log.write_text('{"event":"start"}\n{"event":"step"}\n')
            await _tick(
                harness.runtime.coordinator,
                tmp_path,
                harness.runtime.config,
                state,
                tracker,
            )
            updated, updated_entry = await _entry(harness, "runs/x/.logs/foo.jsonl")
            assert updated_entry.decoration.active
            assert updated_entry.facts.size == log.stat().st_size
            assert updated.version.engine.sequence > baseline.version.engine.sequence

    asyncio.run(run())


def test_quiet_overlay_transition_preserves_engine_version_and_pid_label(
    tmp_path: Path,
) -> None:
    log = _setup_fixture(tmp_path, with_pid=True)

    async def run() -> None:
        async with inventory_harness(tmp_path) as harness:
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
            assert dict(seeded.decoration.labels)["pid_alive"] == "1"
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
            assert dict(quiet_entry.decoration.labels)["pid_alive"] == "1"
            assert quiet.version.engine == engine_after_write

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
                try:
                    pending = await asyncio.wait_for(queue.get(), timeout=0.05)
                except TimeoutError:
                    pass
                else:
                    assert not isinstance(pending.event, CatalogChange)
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
