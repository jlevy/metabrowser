"""Tests for provider-neutral filesystem observation and watch selection."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from watchfiles import Change

from metabrowser.events import EventEnvelope, FsChange, FsUpsert
from metabrowser.inventory_engine.contract import (
    MAX_COMMAND_PATHS,
    DirectoryProjection,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    ReadRequest,
    RefreshReceipt,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
)
from metabrowser.watch_backends import (
    _NATIVE_FS_TYPES,
    _POLLING_FS_TYPES,
    WatcherStatus,
    _emit_batch,
    _emit_for_path,
    detect_fs_type,
    run_watcher,
    select_watch_mode,
)
from tests.inventory_harness import inventory_harness


def test_native_set_includes_ext4_apfs() -> None:
    assert {"ext4", "apfs", "btrfs", "tmpfs"} <= _NATIVE_FS_TYPES


def test_polling_set_includes_nfs_and_fuse() -> None:
    assert {"nfs", "nfs4", "fuse.gcsfuse"} <= _POLLING_FS_TYPES


def test_select_watch_mode_native_or_explained_fallback(tmp_path: Path) -> None:
    mode, reason = select_watch_mode(tmp_path)
    assert mode in ("native", "polling")
    assert reason


def test_select_watch_mode_polling_for_nfs_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.watch_backends.detect_fs_type", lambda _path: "nfs")
    assert select_watch_mode(Path("/anywhere")) == ("polling", "fs=nfs")


def test_select_watch_mode_polling_for_unknown_fs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.watch_backends.detect_fs_type", lambda _path: "weirdfs")
    mode, reason = select_watch_mode(Path("/anywhere"))
    assert mode == "polling"
    assert "weirdfs" in reason


def test_select_watch_mode_polling_when_detect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("metabrowser.watch_backends.detect_fs_type", lambda _path: "")
    assert select_watch_mode(Path("/anywhere")) == (
        "polling",
        "fs-type-unknown",
    )


def test_detect_fs_type_returns_string_on_real_path(tmp_path: Path) -> None:
    assert isinstance(detect_fs_type(tmp_path), str)


def test_backend_batch_is_deduplicated_and_submitted_once(tmp_path: Path) -> None:
    requests: list[RefreshRequest] = []

    async def refresh(request: RefreshRequest) -> RefreshReceipt:
        requests.append(request)
        return RefreshReceipt(accepted_paths=request.paths)

    asyncio.run(
        _emit_batch(
            refresh,
            tmp_path,
            {
                (Change.added, str(tmp_path / "a.txt")),
                (Change.modified, str(tmp_path / "a.txt")),
                (Change.added, str(tmp_path / "b.txt")),
            },
        )
    )

    assert len(requests) == 1
    assert requests[0].paths == ("a.txt", "b.txt")


def test_backend_batch_uses_the_opened_scope_hidden_allowlist(tmp_path: Path) -> None:
    requests: list[RefreshRequest] = []

    async def refresh(request: RefreshRequest) -> RefreshReceipt:
        requests.append(request)
        return RefreshReceipt(accepted_paths=request.paths)

    asyncio.run(
        _emit_batch(
            refresh,
            tmp_path,
            {
                (Change.added, str(tmp_path / ".included" / "kept.txt")),
                (Change.added, str(tmp_path / ".excluded" / "dropped.txt")),
            },
            hidden_allowlist=(".included",),
        )
    )

    assert [request.paths for request in requests] == [(".included/kept.txt",)]


def _build_fixture(root: Path) -> Path:
    (root / "runs" / "x").mkdir(parents=True)
    return root / "runs" / "x" / "new.jsonl"


def test_run_watcher_emits_fs_change_on_new_file(tmp_path: Path) -> None:
    new_file = _build_fixture(tmp_path)

    async def run() -> set[str]:
        async with inventory_harness(tmp_path) as harness:
            queue = harness.bus.attach_connection()
            envelopes: list[EventEnvelope] = []
            try:
                new_file.write_text('{"event":"start"}\n')
                deadline = asyncio.get_running_loop().time() + 4.0
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        envelopes.append(await asyncio.wait_for(queue.get(), timeout=0.1))
                    except TimeoutError:
                        continue
                    if any(
                        isinstance(envelope.event, FsChange)
                        and any(
                            isinstance(operation, FsUpsert)
                            and operation.entry.path == "runs/x/new.jsonl"
                            for operation in envelope.event.ops
                        )
                        for envelope in envelopes
                    ):
                        break
            finally:
                harness.bus.detach_connection(queue)
            seen = {
                operation.entry.path
                for envelope in envelopes
                if isinstance(envelope.event, FsChange)
                for operation in envelope.event.ops
                if isinstance(operation, FsUpsert)
            }
            return seen

    assert "runs/x/new.jsonl" in asyncio.run(run())


def test_stale_delete_event_reconciles_recreated_directory(tmp_path: Path) -> None:
    async def run() -> tuple[set[str], int]:
        artifacts = tmp_path / "dist"
        artifacts.mkdir()
        (artifacts / "old.whl").write_bytes(b"old")
        async with inventory_harness(tmp_path) as harness:
            (artifacts / "old.whl").unlink()
            artifacts.rmdir()
            artifacts.mkdir()
            (artifacts / "new.whl").write_bytes(b"new artifact")
            await _emit_for_path(
                harness.runtime.coordinator.refresh,
                tmp_path,
                str(artifacts),
                Change.deleted,
            )
            read = await harness.runtime.coordinator.read(
                ReadRequest(
                    queries=(
                        DirectoryQuery(
                            query_id="tree",
                            max_depth=harness.runtime.config.max_depth,
                            max_rows=harness.runtime.config.max_files,
                        ),
                        RollupQuery(
                            query_id="rollup",
                            path="dist",
                            max_depth=0,
                            top=0,
                            extension_top=10,
                        ),
                    )
                )
            )
            tree = read.result.projection("tree")
            rollup = read.result.projection("rollup")
            assert isinstance(tree, DirectoryProjection)
            assert isinstance(rollup, RollupProjection)
            assert rollup.payload is not None
            node = rollup.payload["node"]
            assert isinstance(node, dict)
            return {entry.path for entry in tree.entries}, int(node["total_files"])

    indexed_paths, total_files = asyncio.run(run())
    assert "dist/new.whl" in indexed_paths
    assert "dist/old.whl" not in indexed_paths
    assert total_files == 1


def test_stale_add_event_removes_now_absent_file(tmp_path: Path) -> None:
    async def run() -> tuple[bool, int]:
        target = tmp_path / "gone.txt"
        target.write_text("gone")
        async with inventory_harness(tmp_path) as harness:
            target.unlink()
            await _emit_for_path(
                harness.runtime.coordinator.refresh,
                tmp_path,
                str(target),
                Change.added,
            )
            read = await harness.runtime.coordinator.read(
                ReadRequest(
                    queries=(
                        EntryQuery(query_id="entry", path="gone.txt"),
                        RollupQuery(
                            query_id="rollup",
                            path="",
                            max_depth=0,
                            top=0,
                            extension_top=10,
                        ),
                    )
                )
            )
            entry = read.result.projection("entry")
            rollup = read.result.projection("rollup")
            assert isinstance(entry, EntryProjection)
            assert isinstance(rollup, RollupProjection)
            assert rollup.payload is not None
            node = rollup.payload["node"]
            assert isinstance(node, dict)
            return entry.presence is EntryPresence.ABSENT, int(node["total_files"])

    assert asyncio.run(run()) == (True, 0)


def test_watcher_announces_a_failed_watch_instead_of_dying_silently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import metabrowser.watch_backends as watch_backends

    def exploding_awatch(*_args: object, **_kwargs: object) -> object:
        raise OSError("inotify watch limit reached")

    monkeypatch.setattr(watch_backends, "awatch", exploding_awatch)

    async def run() -> list[WatcherStatus]:
        statuses: list[WatcherStatus] = []
        async with inventory_harness(tmp_path) as harness:
            await run_watcher(
                root=tmp_path,
                refresh=harness.runtime.coordinator.refresh,
                on_status=statuses.append,
                mode="native",
            )
        return statuses

    statuses = asyncio.run(run())
    assert any(status.state == "failed" for status in statuses)


def test_watcher_announces_a_failed_refresh_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import metabrowser.watch_backends as watch_backends

    async def yielding_awatch(*_args: object, **_kwargs: object):
        yield {(Change.added, str(tmp_path / "changed.txt"))}

    async def failing_refresh(_request: RefreshRequest) -> RefreshReceipt:
        raise OSError("refresh failed")

    monkeypatch.setattr(watch_backends, "awatch", yielding_awatch)

    async def run() -> list[WatcherStatus]:
        statuses: list[WatcherStatus] = []
        await run_watcher(
            root=tmp_path,
            refresh=failing_refresh,
            on_status=statuses.append,
            mode="native",
        )
        return statuses

    statuses = asyncio.run(run())
    assert statuses[-1].state == "failed"
    assert "refresh failed" in statuses[-1].detail


def test_watcher_announces_a_rejected_observation_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import metabrowser.watch_backends as watch_backends

    async def yielding_awatch(*_args: object, **_kwargs: object):
        yield {(Change.added, str(tmp_path / "changed.txt"))}

    async def rejecting_refresh(request: RefreshRequest) -> RefreshReceipt:
        return RefreshReceipt(accepted_paths=(), rejected_paths=request.paths)

    monkeypatch.setattr(watch_backends, "awatch", yielding_awatch)

    async def run() -> list[WatcherStatus]:
        statuses: list[WatcherStatus] = []
        await run_watcher(
            root=tmp_path,
            refresh=rejecting_refresh,
            on_status=statuses.append,
            mode="native",
        )
        return statuses

    statuses = asyncio.run(run())
    assert statuses[-1].state == "failed"
    assert "rejected 1 watcher observation" in statuses[-1].detail


def test_watcher_stops_after_a_middle_chunk_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import metabrowser.watch_backends as watch_backends

    changes = {
        (Change.added, str(tmp_path / f"changed-{index}.txt"))
        for index in range(MAX_COMMAND_PATHS * 2 + 1)
    }

    async def yielding_awatch(*_args: object, **_kwargs: object):
        yield changes

    requests: list[RefreshRequest] = []

    async def failing_middle_refresh(request: RefreshRequest) -> RefreshReceipt:
        requests.append(request)
        if len(requests) == 2:
            raise OSError("middle chunk failed")
        return RefreshReceipt(accepted_paths=request.paths)

    monkeypatch.setattr(watch_backends, "awatch", yielding_awatch)

    async def run() -> list[WatcherStatus]:
        statuses: list[WatcherStatus] = []
        await run_watcher(
            root=tmp_path,
            refresh=failing_middle_refresh,
            on_status=statuses.append,
            mode="native",
        )
        return statuses

    statuses = asyncio.run(run())
    assert [len(request.observations) for request in requests] == [
        MAX_COMMAND_PATHS,
        MAX_COMMAND_PATHS,
    ]
    assert statuses[-1].state == "failed"
    assert "middle chunk failed" in statuses[-1].detail
