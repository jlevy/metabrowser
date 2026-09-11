"""The current filesystem engine behind the provider-neutral contract."""

from __future__ import annotations

import ast
import asyncio
import inspect
import os
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest

from metabrowser import inventory_rollup, walker
from metabrowser.fs_record import FsEntry
from metabrowser.inventory_engine import contract
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    ChangeBatch,
    CountKind,
    CountResult,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    DiscoveryBudget,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryClosedError,
    InventoryConfig,
    InventoryFilter,
    InventoryHandle,
    IssueCode,
    LifecyclePhase,
    NavigationProjection,
    NavigationQuery,
    PriorityRequest,
    ReadRequest,
    RecentProjection,
    RecentQuery,
    RefreshObservation,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.providers import python_inventory as python_provider
from metabrowser.inventory_engine.providers.python_inventory import (
    PythonInventoryBackend,
)
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)


async def _open_settled(
    root: Path,
    config: InventoryConfig | None = None,
) -> PythonInventoryStore:
    handle = cast(
        PythonInventoryStore,
        await PythonInventoryBackend().open(root, config or InventoryConfig()),
    )
    for _attempt in range(200):
        result = await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="state"),)))
        if result.state.phase in {
            LifecyclePhase.READY,
            LifecyclePhase.WATCHING,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }:
            return handle
        await asyncio.sleep(0.005)
    raise AssertionError("Python provider did not settle")


async def _python_provider_answers_one_coherent_bundled_read(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "b.md").write_text("bravo", encoding="utf-8")
    handle = await _open_settled(tmp_path)
    try:
        result = await handle.read(
            ReadRequest(
                queries=(
                    EntryQuery(query_id="entry", path="a.txt"),
                    DirectoryQuery(
                        query_id="tree",
                        path="",
                        max_depth=2,
                        max_rows=20,
                    ),
                    CatalogQuery(query_id="catalog", max_rows=1),
                    DiagnosticsQuery(query_id="diagnostics"),
                )
            )
        )
        assert result.version.session == result.cursor.session
        assert result.version.sequence == result.cursor.sequence

        entry = result.projection("entry")
        assert isinstance(entry, EntryProjection)
        assert entry.presence is EntryPresence.PRESENT
        assert entry.entry is not None and entry.entry.size == 5

        tree = result.projection("tree")
        assert isinstance(tree, DirectoryProjection)
        assert {row.path for row in tree.entries} == {"a.txt", "folder", "folder/b.md"}

        catalog = result.projection("catalog")
        assert isinstance(catalog, CatalogProjection)
        assert len(catalog.records) == 1
        assert catalog.total_matches == CountResult(CountKind.EXACT, 2)
        assert catalog.next_page is not None
        catalog_tail = await handle.read(
            ReadRequest(
                queries=(
                    CatalogQuery(
                        query_id="catalog",
                        max_rows=1,
                        after=catalog.next_page,
                    ),
                ),
                at_version=result.version,
            )
        )
        assert catalog_tail.work.entries_visited == 0

        diagnostics = result.projection("diagnostics")
        assert isinstance(diagnostics, DiagnosticsProjection)
        assert diagnostics.payload.provider == "python"
        assert diagnostics.payload.contract == "inventory-provider-v1"
        assert result.work.rows_returned >= 6
    finally:
        await handle.close()


async def _refresh_advances_version_and_emits_provider_change(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    handle = await _open_settled(tmp_path)
    try:
        before = await handle.read(ReadRequest(queries=(EntryQuery(query_id="a", path="a.txt"),)))
        changes = handle.changes(after=before.cursor)

        (tmp_path / "b.txt").write_text("bravo", encoding="utf-8")
        receipt = await handle.refresh(
            RefreshRequest(observations=(RefreshObservation(path="b.txt"),))
        )
        assert receipt.accepted_paths == ("b.txt",)
        assert receipt.version.session == before.version.session
        assert receipt.version.sequence > before.version.sequence

        for _attempt in range(4):
            batch = await asyncio.wait_for(anext(changes), timeout=1)
            if "b.txt" in batch.dirty_paths:
                break
        else:
            raise AssertionError("refresh did not emit the changed path")
        assert isinstance(batch, ChangeBatch)
        assert batch.version.sequence > before.version.sequence
        assert "b.txt" in batch.dirty_paths

        with pytest.raises(VersionUnavailableError):
            await handle.read(
                ReadRequest(
                    queries=(EntryQuery(query_id="old", path="a.txt"),),
                    at_version=before.version,
                )
            )
    finally:
        await handle.close()


async def _special_objects_stay_outside_the_provider_contract(tmp_path: Path) -> None:
    special = tmp_path / "pipe"
    os.mkfifo(special)
    handle = await _open_settled(tmp_path)
    try:
        boot = await handle.read(ReadRequest(queries=(EntryQuery(query_id="boot", path="pipe"),)))
        boot_entry = boot.projection("boot")
        assert isinstance(boot_entry, EntryProjection)
        assert boot_entry.presence is EntryPresence.ABSENT

        special.unlink()
        special.write_text("regular", encoding="utf-8")
        await handle.refresh(RefreshRequest(observations=(RefreshObservation(path="pipe"),)))
        regular = await handle.read(
            ReadRequest(queries=(EntryQuery(query_id="regular", path="pipe"),))
        )
        regular_entry = regular.projection("regular")
        assert isinstance(regular_entry, EntryProjection)
        assert regular_entry.entry is not None
        assert regular_entry.entry.type.value == "file"

        special.unlink()
        os.mkfifo(special)
        await handle.refresh(RefreshRequest(observations=(RefreshObservation(path="pipe"),)))
        refreshed = await handle.read(
            ReadRequest(queries=(EntryQuery(query_id="refreshed", path="pipe"),))
        )
        refreshed_entry = refreshed.projection("refreshed")
        assert isinstance(refreshed_entry, EntryProjection)
        assert refreshed_entry.presence is EntryPresence.ABSENT
    finally:
        await handle.close()


async def _close_is_idempotent_and_refuses_later_reads(tmp_path: Path) -> None:
    handle = await PythonInventoryBackend().open(tmp_path, InventoryConfig())
    assert isinstance(handle, InventoryHandle)
    await handle.close()
    await handle.close()
    with pytest.raises(InventoryClosedError):
        await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="state"),)))


async def _configured_hidden_allowlist_defines_provider_scope(tmp_path: Path) -> None:
    (tmp_path / ".included").mkdir()
    (tmp_path / ".included" / "kept.txt").write_text("kept", encoding="utf-8")
    (tmp_path / ".excluded").mkdir()
    (tmp_path / ".excluded" / "dropped.txt").write_text("dropped", encoding="utf-8")
    handle = await _open_settled(
        tmp_path,
        InventoryConfig(hidden_allowlist=(".included",), watch_mode="off"),
    )
    try:
        result = await handle.read(
            ReadRequest(queries=(DirectoryQuery(query_id="tree", max_depth=3, max_rows=20),))
        )
        projection = result.projection("tree")
        assert isinstance(projection, DirectoryProjection)
        paths = {entry.path for entry in projection.entries}
        assert {".included", ".included/kept.txt"} <= paths
        assert ".excluded" not in paths
        assert ".excluded/dropped.txt" not in paths
        receipt = await handle.refresh(
            RefreshRequest(observations=(RefreshObservation(path=".excluded/dropped.txt"),))
        )
        assert receipt.accepted_paths == ()
        assert receipt.rejected_paths == (".excluded/dropped.txt",)
    finally:
        await handle.close()


async def _python_provider_implements_every_projection(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('a')", encoding="utf-8")
    (tmp_path / "notes.md").write_text("notes", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "b.py").write_text("print('b')", encoding="utf-8")
    handle = await _open_settled(tmp_path)
    try:
        result = await handle.read(
            ReadRequest(
                queries=(
                    FilteredTreeQuery(
                        query_id="filtered",
                        max_depth=3,
                        max_rows=20,
                        filter=InventoryFilter(extensions=(".py",)),
                    ),
                    RollupQuery(query_id="rollup"),
                    NavigationQuery(query_id="navigation"),
                    RecentQuery(query_id="recent", max_rows=2, as_of_ns=10**30),
                )
            )
        )

        filtered = result.projection("filtered")
        assert isinstance(filtered, FilteredTreeProjection)
        assert {entry.path for entry in filtered.entries} == {
            "a.py",
            "folder",
            "folder/b.py",
        }
        assert filtered.matching_files == 2

        rollup = result.projection("rollup")
        assert isinstance(rollup, RollupProjection)
        assert rollup.payload is not None
        rollup_node = rollup.payload["node"]
        assert isinstance(rollup_node, dict)
        assert rollup_node["name"] == tmp_path.name

        navigation = result.projection("navigation")
        assert isinstance(navigation, NavigationProjection)
        navigation_summary = navigation.payload["summary"]
        assert isinstance(navigation_summary, dict)
        assert navigation_summary["files"] == 3

        recent = result.projection("recent")
        assert isinstance(recent, RecentProjection)
        assert recent.total_matches == CountResult(CountKind.EXACT, 3)
        assert len(recent.entries) == 2
        assert recent.truncated
    finally:
        await handle.close()


async def _targeted_read_reports_bounded_work(tmp_path: Path) -> None:
    for index in range(20):
        (tmp_path / f"{index}.txt").write_text(str(index), encoding="utf-8")
    handle = await _open_settled(tmp_path)
    try:
        result = await handle.read(ReadRequest(queries=(EntryQuery(query_id="one", path="7.txt"),)))
        assert result.work.rows_visited == 1
        assert result.work.rows_returned == 1
    finally:
        await handle.close()


async def _tree_continuations_reuse_the_first_projection(tmp_path: Path) -> None:
    file_count = 5
    page_rows = 2
    for index in range(file_count):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
    try:
        directory_query = DirectoryQuery(
            query_id="directory-page",
            max_depth=1,
            max_rows=page_rows,
        )
        first_directory = await handle.read(ReadRequest(queries=(directory_query,)))
        directory_page = first_directory.projection(directory_query.query_id)
        assert isinstance(directory_page, DirectoryProjection)
        assert directory_page.next_page is not None
        second_directory = await handle.read(
            ReadRequest(
                queries=(
                    DirectoryQuery(
                        query_id=directory_query.query_id,
                        max_depth=directory_query.max_depth,
                        max_rows=directory_query.max_rows,
                        after=directory_page.next_page,
                    ),
                ),
                at_version=first_directory.version,
            )
        )
        assert first_directory.work.rows_visited == file_count
        assert second_directory.work.rows_visited == page_rows

        filtered_query = FilteredTreeQuery(
            query_id="filtered-page",
            max_depth=1,
            max_rows=page_rows,
            filter=InventoryFilter(extensions=(".txt",)),
        )
        first_filtered = await handle.read(ReadRequest(queries=(filtered_query,)))
        filtered_page = first_filtered.projection(filtered_query.query_id)
        assert isinstance(filtered_page, FilteredTreeProjection)
        assert filtered_page.next_page is not None
        second_filtered = await handle.read(
            ReadRequest(
                queries=(
                    FilteredTreeQuery(
                        query_id=filtered_query.query_id,
                        max_depth=filtered_query.max_depth,
                        max_rows=filtered_query.max_rows,
                        after=filtered_page.next_page,
                        filter=filtered_query.filter,
                    ),
                ),
                at_version=first_filtered.version,
            )
        )
        assert first_filtered.work.rows_visited == file_count + 1
        assert second_filtered.work.rows_visited == page_rows
    finally:
        await handle.close()


async def _filtered_directory_newest_time_uses_regular_files(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    epoch_file = folder / "epoch.txt"
    epoch_file.write_text("epoch", encoding="utf-8")
    os.utime(epoch_file, ns=(0, 0))
    try:
        (folder / "link").symlink_to("epoch.txt")
    except OSError as error:  # pragma: no cover - unsupported Windows policy
        pytest.skip(f"symlinks are unavailable: {error}")

    handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
    try:
        result = await handle.read(
            ReadRequest(
                queries=(
                    FilteredTreeQuery(
                        query_id="filtered",
                        max_depth=2,
                        max_rows=20,
                    ),
                )
            )
        )
        projection = result.projection("filtered")
        assert isinstance(projection, FilteredTreeProjection)
        directory = next(entry for entry in projection.entries if entry.path == "folder")
        assert directory.total_files == 1
        assert directory.total_size == len("epoch")
        assert directory.newest_mtime_ns == 0
    finally:
        await handle.close()


async def _navigation_poll_reuses_one_coherent_read_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(20):
        (tmp_path / f"{index}.txt").write_text(str(index), encoding="utf-8")
    started = asyncio.Event()
    release = asyncio.Event()
    original_walk = python_provider.walk_tree

    async def blocked_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        seen = 0
        async for entry in original_walk(*args, **kwargs):
            yield entry
            seen += 1
            if seen == 5:
                started.set()
                await release.wait()

    monkeypatch.setattr(python_provider, "walk_tree", blocked_walk)
    handle = await PythonInventoryBackend().open(tmp_path, InventoryConfig())
    request = ReadRequest(
        queries=(
            EntryQuery(query_id="root", path=""),
            NavigationQuery(query_id="navigation"),
        )
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        first = await handle.read(request)
        first_navigation = first.projection("navigation")
        assert isinstance(first_navigation, NavigationProjection)
        first_summary = first_navigation.payload["summary"]
        assert isinstance(first_summary, dict)
        assert first.state.phase is LifecyclePhase.DISCOVERING
        assert first.work.rows_visited > 0

        (tmp_path / "new.txt").write_text("new", encoding="utf-8")
        await handle.refresh(RefreshRequest(observations=(RefreshObservation(path="new.txt"),)))
        cached = await handle.read(request)
        cached_navigation = cached.projection("navigation")
        assert isinstance(cached_navigation, NavigationProjection)
        assert cached.version == first.version
        assert cached.state == first.state
        assert cached.projection("root") == first.projection("root")
        assert cached_navigation.payload["summary"] == first_navigation.payload["summary"]
        assert cached.work.rows_visited < first.work.rows_visited

        monkeypatch.setattr(python_provider, "_NAVIGATION_TALLY_REFRESH_FLOOR_S", 0.0)
        await asyncio.sleep(0.02)
        refreshed = await handle.read(request)
        refreshed_navigation = refreshed.projection("navigation")
        assert isinstance(refreshed_navigation, NavigationProjection)
        assert refreshed.version.sequence > first.version.sequence
        refreshed_summary = refreshed_navigation.payload["summary"]
        assert isinstance(refreshed_summary, dict)
        assert refreshed_summary["files"] == first_summary["files"] + 1
        assert refreshed.work.rows_visited > first.work.rows_visited
    finally:
        release.set()
        await handle.close()


async def _expired_change_cursor_yields_reset(tmp_path: Path) -> None:
    handle = await _open_settled(
        tmp_path,
        InventoryConfig(change_queue_size=2),
    )
    try:
        before = await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="before"),)))
        for index in range(3):
            path = f"{index}.txt"
            (tmp_path / path).write_text(path, encoding="utf-8")
            await handle.refresh(RefreshRequest(observations=(RefreshObservation(path=path),)))

        batch = await asyncio.wait_for(anext(handle.changes(after=before.cursor)), timeout=1)
        assert batch.reset
        assert not batch.dirty_paths
        assert not batch.dirty_queries
    finally:
        await handle.close()


def test_python_provider_answers_one_coherent_bundled_read(tmp_path: Path) -> None:
    asyncio.run(_python_provider_answers_one_coherent_bundled_read(tmp_path))


def test_refresh_advances_version_and_emits_provider_change(tmp_path: Path) -> None:
    asyncio.run(_refresh_advances_version_and_emits_provider_change(tmp_path))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are unavailable")
def test_special_objects_stay_outside_the_provider_contract(tmp_path: Path) -> None:
    asyncio.run(_special_objects_stay_outside_the_provider_contract(tmp_path))


def test_close_is_idempotent_and_refuses_later_reads(tmp_path: Path) -> None:
    asyncio.run(_close_is_idempotent_and_refuses_later_reads(tmp_path))


def test_resource_budget_stop_and_close_both_join_the_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlapping shutdown owners cannot abandon the backend consumer."""

    import metabrowser.watch_backends as watch_backends

    async def run() -> None:
        saw_stop = asyncio.Event()
        permit_exit = asyncio.Event()
        finalized = asyncio.Event()

        async def controlled_awatch(
            *_args: object,
            stop_event: asyncio.Event | None = None,
            **_kwargs: object,
        ) -> AsyncIterator[set[object]]:
            assert stop_event is not None
            try:
                await stop_event.wait()
                saw_stop.set()
                await permit_exit.wait()
                yield set()
            finally:
                finalized.set()

        monkeypatch.setattr(watch_backends, "awatch", controlled_awatch)
        store = PythonInventoryStore(config=InventoryConfig(watch_mode="native"))
        store.start_watcher(tmp_path)
        await asyncio.wait_for(store.wait_until_watcher_started(), timeout=1.0)
        watcher = store._watcher_task
        assert watcher is not None

        budget_stop = asyncio.create_task(store._stop_watcher_for_resource_budget())
        close_task: asyncio.Task[None] | None = None
        try:
            await asyncio.wait_for(saw_stop.wait(), timeout=1.0)
            close_task = asyncio.create_task(store.close())
            for _attempt in range(10):
                await asyncio.sleep(0)
                if watcher.cancelling() >= 2:
                    break
            assert watcher.cancelling() >= 2
            # Let the second cancellation reach run_watcher's cooperative join.
            await asyncio.sleep(0)
            assert not watcher.done()
            assert not close_task.done()
            assert not finalized.is_set()

            permit_exit.set()
            await asyncio.wait_for(asyncio.gather(budget_stop, close_task), timeout=1.0)
            assert finalized.is_set()
            assert not any(
                task.get_name() == "metabrowser-watchfiles-consumer"
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
            )
        finally:
            permit_exit.set()
            pending = [budget_stop]
            if close_task is not None:
                pending.append(close_task)
            await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(run())


def test_configured_hidden_allowlist_defines_provider_scope(tmp_path: Path) -> None:
    asyncio.run(_configured_hidden_allowlist_defines_provider_scope(tmp_path))


def test_python_provider_implements_every_projection(tmp_path: Path) -> None:
    asyncio.run(_python_provider_implements_every_projection(tmp_path))


def test_filtered_directory_newest_time_uses_regular_files(tmp_path: Path) -> None:
    asyncio.run(_filtered_directory_newest_time_uses_regular_files(tmp_path))


def test_targeted_read_reports_bounded_work(tmp_path: Path) -> None:
    asyncio.run(_targeted_read_reports_bounded_work(tmp_path))


def test_rollup_collision_retries_once_and_reports_discarded_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    async def run() -> tuple[int, int, int, int]:
        handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
        build_started = Event()
        release_build = Event()
        build_calls = 0
        real_build = python_provider.build_rollup

        def gated_build(*args: Any, **kwargs: Any) -> Any:
            nonlocal build_calls
            build_calls += 1
            if build_calls == 1:
                build_started.set()
                assert release_build.wait(timeout=5.0)
            return real_build(*args, **kwargs)

        monkeypatch.setattr(python_provider, "build_rollup", gated_build)
        before_entries = len(handle._entries)
        read_task = asyncio.create_task(
            handle.read(ReadRequest(queries=(RollupQuery(query_id="rollup"),)))
        )
        try:
            assert await asyncio.to_thread(build_started.wait, 1.0)
            (tmp_path / "b.txt").write_text("b", encoding="utf-8")
            await handle.refresh(RefreshRequest(observations=(RefreshObservation(path="b.txt"),)))
            after_entries = len(handle._entries)
            release_build.set()
            result = await asyncio.wait_for(read_task, timeout=5.0)
            return (
                build_calls,
                result.work.rows_visited,
                result.work.maintained_index_work,
                before_entries + after_entries,
            )
        finally:
            release_build.set()
            await asyncio.gather(read_task, return_exceptions=True)
            await handle.close()

    calls, rows_visited, maintained_work, expected_work = asyncio.run(run())
    assert calls == 2
    assert rows_visited == maintained_work == expected_work


def test_tree_continuations_reuse_the_first_projection(tmp_path: Path) -> None:
    asyncio.run(_tree_continuations_reuse_the_first_projection(tmp_path))


def test_navigation_poll_reuses_one_coherent_read_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_navigation_poll_reuses_one_coherent_read_boundary(tmp_path, monkeypatch))


def test_catalog_predicates_are_applied_inside_the_provider(tmp_path: Path) -> None:
    logs = tmp_path / "runs" / "x" / ".logs"
    state = tmp_path / "runs" / "x" / ".state"
    logs.mkdir(parents=True)
    state.mkdir()
    (logs / "active.run.jsonl").write_text("active", encoding="utf-8")
    (logs / "too-large.jsonl").write_text("0123456789", encoding="utf-8")
    (state / "status.yaml").write_text("ok", encoding="utf-8")
    (tmp_path / "outside.yaml").write_text("outside", encoding="utf-8")

    async def run() -> tuple[set[str], int]:
        handle = await _open_settled(tmp_path)
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        CatalogQuery(
                            query_id="candidates",
                            max_rows=100,
                            include_ignored=True,
                            terminal_extensions=(".jsonl", ".yaml"),
                            ancestor_names=(".logs", ".state"),
                            size_less_than=10,
                        ),
                    )
                )
            )
            projection = result.projection("candidates")
            assert isinstance(projection, CatalogProjection)
            return {record.path for record in projection.records}, result.work.rows_visited
        finally:
            await handle.close()

    paths, visited = asyncio.run(run())
    assert paths == {
        "runs/x/.logs/active.run.jsonl",
        "runs/x/.state/status.yaml",
    }
    assert visited == 9


def test_priority_hint_returns_before_reference_refresh_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        handle = await _open_settled(tmp_path)
        release = asyncio.Event()
        started = asyncio.Event()

        async def blocked_refresh(*_args: object, **_kwargs: object) -> None:
            started.set()
            await release.wait()

        monkeypatch.setattr(handle, "_refresh_path", blocked_refresh)
        try:
            await asyncio.wait_for(
                handle.prioritize(PriorityRequest(paths=("later",), max_depth=1)),
                timeout=0.1,
            )
            await asyncio.wait_for(started.wait(), timeout=1)
        finally:
            release.set()
            await handle.close()

    asyncio.run(run())


def test_priority_hint_cannot_expand_a_budget_stopped_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled(
            tmp_path,
            InventoryConfig(
                budget=DiscoveryBudget(max_files=1),
                watch_mode="off",
            ),
        )
        refresh_started = asyncio.Event()

        async def unexpected_priority_refresh(*_args: object, **_kwargs: object) -> None:
            refresh_started.set()

        monkeypatch.setattr(
            handle,
            "_run_priority_refresh",
            unexpected_priority_refresh,
        )
        try:
            await handle.prioritize(PriorityRequest(paths=("b.txt",)))
            await asyncio.sleep(0)
            assert not refresh_started.is_set()
        finally:
            await handle.close()

    asyncio.run(run())


def test_refresh_builds_gitignore_checker_once_per_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    async def run() -> int:
        handle = await _open_settled(tmp_path)
        calls = 0

        def build_once(*_args: object, **_kwargs: object) -> None:
            nonlocal calls
            calls += 1
            return None

        monkeypatch.setattr(python_provider, "_build_gitignore_check_for", build_once)
        try:
            await handle.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(path="a.txt"),
                        RefreshObservation(path="b.txt"),
                    )
                )
            )
            return calls
        finally:
            await handle.close()

    assert asyncio.run(run()) == 1


def test_expired_change_cursor_yields_reset(tmp_path: Path) -> None:
    asyncio.run(_expired_change_cursor_yields_reset(tmp_path))


@pytest.mark.parametrize("path", ("../outside", "a//b", "a\\b"))
def test_refresh_rejects_noncanonical_paths_at_the_contract_boundary(path: str) -> None:
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        RefreshObservation(path=path)


def test_python_provider_installs_watcher_before_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> tuple[bool, bool]:
        watcher_entered = asyncio.Event()
        release_watcher = asyncio.Event()
        walk_started = asyncio.Event()
        real_walk = python_provider.walk_tree

        async def blocked_watcher(**kwargs: Any) -> None:
            watcher_entered.set()
            await release_watcher.wait()
            kwargs["on_status"](
                python_provider.WatcherStatus(
                    mode="native",
                    state="running",
                    reason="test",
                )
            )
            await asyncio.Event().wait()

        async def recording_walk(
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[FsEntry]:
            walk_started.set()
            async for entry in real_walk(*args, **kwargs):
                yield entry

        monkeypatch.setattr(python_provider, "run_watcher", blocked_watcher)
        monkeypatch.setattr(python_provider, "walk_tree", recording_walk)

        opening = asyncio.create_task(
            PythonInventoryBackend().open(
                tmp_path,
                InventoryConfig(watch_mode="native"),
            )
        )
        await asyncio.wait_for(watcher_entered.wait(), timeout=1.0)
        await asyncio.sleep(0)
        discovery_started_early = walk_started.is_set()
        release_watcher.set()
        handle = await asyncio.wait_for(opening, timeout=1.0)
        try:
            await asyncio.wait_for(walk_started.wait(), timeout=1.0)
            return discovery_started_early, walk_started.is_set()
        finally:
            await handle.close()

    assert asyncio.run(run()) == (False, True)


def test_python_walker_uses_a_timer_backed_yield_for_provider_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-delay yield can reacquire the GIL before a waiting read worker."""

    async def run() -> list[float]:
        real_sleep = asyncio.sleep
        delays: list[float] = []

        async def fixed_walk(*_args: Any, **_kwargs: Any) -> AsyncIterator[FsEntry]:
            for index in range(python_provider._WALKER_COOPERATIVE_YIELD_BATCH + 1):
                name = f"{index}.txt"
                yield FsEntry.for_observed_file(
                    path=name,
                    parent="",
                    name=name,
                    size=1,
                    mtime_ns=1,
                )

        async def record_sleep(delay: float) -> None:
            delays.append(delay)
            await real_sleep(0)

        monkeypatch.setattr(python_provider, "walk_tree", fixed_walk)
        monkeypatch.setattr(python_provider, "_build_gitignore_check_for", lambda *_a, **_kw: None)
        monkeypatch.setattr(python_provider.asyncio, "sleep", record_sleep)

        handle = cast(
            PythonInventoryStore,
            await PythonInventoryBackend().open(tmp_path, InventoryConfig(watch_mode="off")),
        )
        try:
            await handle.wait_until_done(timeout=1)
        finally:
            await handle.close()
        return delays

    assert asyncio.run(run()) == [python_provider._WALKER_COOPERATIVE_YIELD_S]


def test_python_provider_exposes_progressive_partial_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")

    async def run() -> tuple[str, bool, str | None, str, bool]:
        release = asyncio.Event()
        real_walk = python_provider.walk_tree

        async def blocked_walk(
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[FsEntry]:
            await release.wait()
            async for entry in real_walk(*args, **kwargs):
                yield entry

        monkeypatch.setattr(python_provider, "walk_tree", blocked_walk)
        handle = await PythonInventoryBackend().open(tmp_path, InventoryConfig())
        try:
            progressive = await handle.read(
                ReadRequest(queries=(DiagnosticsQuery(query_id="progressive"),))
            )
            release.set()
            for _attempt in range(200):
                settled = await handle.read(
                    ReadRequest(queries=(DiagnosticsQuery(query_id="settled"),))
                )
                if settled.state.phase is LifecyclePhase.WATCHING:
                    break
                await asyncio.sleep(0.005)
            else:
                raise AssertionError("Python provider did not finish after release")
            return (
                progressive.state.phase.value,
                progressive.state.coverage.complete,
                progressive.state.coverage.reason.value
                if progressive.state.coverage.reason
                else None,
                settled.state.phase.value,
                settled.state.coverage.complete,
            )
        finally:
            release.set()
            await handle.close()

    assert asyncio.run(run()) == ("discovering", False, "building", "watching", True)


def test_python_provider_surfaces_discovery_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> tuple[
        str,
        bool,
        str | None,
        tuple[IssueCode, ...],
        tuple[str, ...],
    ]:
        async def failing_walk(
            *_args: Any,
            **_kwargs: Any,
        ) -> AsyncIterator[contract.InventoryEntry]:
            if False:
                yield cast("contract.InventoryEntry", None)
            raise RuntimeError("contract failure sentinel")

        monkeypatch.setattr(python_provider, "walk_tree", failing_walk)
        handle = await _open_settled(tmp_path)
        try:
            result = await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="failed"),)))
            return (
                result.state.phase.value,
                result.state.coverage.complete,
                result.state.coverage.reason.value if result.state.coverage.reason else None,
                tuple(issue.code for issue in result.state.issues),
                tuple(issue.detail for issue in result.state.issues),
            )
        finally:
            await handle.close()

    phase, complete, reason, issue_codes, details = asyncio.run(run())
    assert (phase, complete, reason, issue_codes) == (
        "failed",
        False,
        "failed",
        (IssueCode.PROVIDER_FAILURE,),
    )
    assert "contract failure sentinel" in details[0]


def test_python_provider_surfaces_observation_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import metabrowser.watch_backends as watch_backends

    def failing_watch(*_args: object, **_kwargs: object) -> object:
        raise OSError("watch failure sentinel")

    monkeypatch.setattr(watch_backends, "awatch", failing_watch)

    async def run() -> tuple[LifecyclePhase, bool, str | None, str, tuple[IssueCode, ...], str]:
        handle = await _open_settled(
            tmp_path,
            InventoryConfig(watch_mode="native"),
        )
        try:
            for _attempt in range(100):
                result = await handle.read(
                    ReadRequest(queries=(DiagnosticsQuery(query_id="watch"),))
                )
                diagnostic = result.projection("watch")
                assert isinstance(diagnostic, DiagnosticsProjection)
                if any(issue.code is IssueCode.OBSERVATION_GAP for issue in result.state.issues):
                    reason = (
                        result.state.coverage.reason.value
                        if result.state.coverage.reason is not None
                        else None
                    )
                    return (
                        result.state.phase,
                        result.state.coverage.complete,
                        reason,
                        result.state.freshness.value,
                        tuple(issue.code for issue in result.state.issues),
                        diagnostic.payload.watch_state,
                    )
                await asyncio.sleep(0.005)
            raise AssertionError("provider did not surface the failed watcher")
        finally:
            await handle.close()

    phase, complete, reason, freshness, issue_codes, watch_state = asyncio.run(run())
    assert phase is LifecyclePhase.READY
    assert complete is True
    assert reason is None
    assert freshness == "stale"
    assert IssueCode.OBSERVATION_GAP in issue_codes
    assert watch_state == "failed"


@pytest.mark.parametrize("older_missing", [False, True])
def test_concurrent_refresh_cannot_replace_a_newer_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, older_missing: bool
) -> None:
    target = tmp_path / "changing.txt"
    target.write_text("old")
    observed = Event()
    release = Event()
    original_lstat = Path.lstat

    def delayed_lstat(path: Path) -> os.stat_result:
        if path == target and not observed.is_set():
            old = original_lstat(path)
            observed.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test did not release the older observation")
            if older_missing:
                raise FileNotFoundError(path)
            return old
        return original_lstat(path)

    async def run() -> None:
        handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
        monkeypatch.setattr(Path, "lstat", delayed_lstat)
        request = RefreshRequest(observations=(RefreshObservation(path=target.name),))
        older = asyncio.create_task(handle.refresh(request))
        try:
            assert await asyncio.to_thread(observed.wait, 5)
            target.write_text("the newer observation")
            newer = await handle.refresh(request)
            release.set()
            await older
            result = await handle.read(
                ReadRequest(queries=(EntryQuery(query_id="entry", path=target.name),))
            )
            entry = result.projection("entry")
            assert isinstance(entry, EntryProjection)
            assert entry.entry is not None
            assert entry.entry.size == target.stat().st_size
            assert result.version == newer.version
        finally:
            release.set()
            await asyncio.gather(older, return_exceptions=True)
            await handle.close()

    asyncio.run(run())


def test_scanner_and_reducer_do_not_depend_on_browser_events() -> None:
    for module in (walker, inventory_rollup):
        imported_modules: set[str] = set()
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.add(node.module)
        assert "metabrowser.events" not in imported_modules


def test_phase_one_contract_has_no_fdu_runtime_placeholder() -> None:
    sources = (
        inspect.getsource(contract),
        inspect.getsource(python_provider),
    )
    assert all("FduInventory" not in source for source in sources)


@pytest.mark.parametrize("external", [False, True])
def test_refresh_never_descends_through_symlink_ancestors(tmp_path: Path, external: bool) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "outside" if external else root / "inside"
    target.mkdir()
    (target / "secret.txt").write_text("not a child of the symlink")
    (target / "nested").mkdir()
    (target / "nested" / "child.txt").write_text("nested")
    (root / "link").symlink_to(target, target_is_directory=True)

    async def run() -> None:
        handle = await _open_settled(root, InventoryConfig(watch_mode="off"))
        try:
            paths = ("link/secret.txt", "link/nested")
            receipt = await handle.refresh(
                RefreshRequest(observations=tuple(RefreshObservation(path=p) for p in paths))
            )
            assert receipt.rejected_paths == paths
            await handle.prioritize(PriorityRequest(paths=paths))
            await asyncio.gather(*tuple(handle._priority_tasks))
            result = await handle.read(
                ReadRequest(queries=(EntryQuery(query_id="entry", path=paths[0]),))
            )
            entry = result.projection("entry")
            assert isinstance(entry, EntryProjection)
            assert entry.presence is not EntryPresence.PRESENT
        finally:
            await handle.close()

    asyncio.run(run())


def test_diagnostic_directory_count_includes_the_served_root(tmp_path: Path) -> None:
    (tmp_path / "child").mkdir()

    async def run() -> None:
        handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
        try:
            result = await handle.read(
                ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),))
            )
            diagnostic = result.projection("diagnostics")
            assert isinstance(diagnostic, DiagnosticsProjection)
            assert diagnostic.payload.directories_indexed == 2
            assert result.state.progress.directories_observed == 2
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["directory", "filtered_tree", "catalog"])
def test_retained_pages_remain_coherent_while_live_facts_advance(tmp_path: Path, kind: str) -> None:
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("old")

    async def run() -> None:
        handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
        query = {
            "directory": DirectoryQuery(query_id="page", max_rows=1),
            "filtered_tree": FilteredTreeQuery(query_id="page", max_rows=1),
            "catalog": CatalogQuery(query_id="page", max_rows=1),
        }[kind]
        try:
            first = await handle.read(ReadRequest(queries=(query,)))
            page = first.projection("page")
            assert isinstance(
                page, (DirectoryProjection, FilteredTreeProjection, CatalogProjection)
            )
            assert page.next_page is not None
            (tmp_path / "c.txt").write_text("newer contents")
            receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="c.txt"),))
            )
            assert receipt.version != first.version
            rows = list(page.records if isinstance(page, CatalogProjection) else page.entries)
            while page.next_page:
                later = await handle.read(
                    ReadRequest(
                        queries=(replace(query, after=page.next_page),), at_version=first.version
                    )
                )
                assert later.version == first.version
                assert later.state == first.state
                page = later.projection("page")
                assert isinstance(
                    page, (DirectoryProjection, FilteredTreeProjection, CatalogProjection)
                )
                rows.extend(page.records if isinstance(page, CatalogProjection) else page.entries)
            assert [(row.path, row.size) for row in rows] == [
                (name, 3) for name in ("a.txt", "b.txt", "c.txt")
            ]
        finally:
            await handle.close()

    asyncio.run(run())


def test_evicted_continuation_fails_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(python_provider, "_PAGE_MEMO_CAPACITY", 1)
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("x")

    async def run() -> None:
        handle = await _open_settled(tmp_path, InventoryConfig(watch_mode="off"))
        query = CatalogQuery(query_id="page", max_rows=1)
        try:
            first = await handle.read(ReadRequest(queries=(query,)))
            page = first.projection("page")
            assert isinstance(page, CatalogProjection)
            assert page.next_page is not None
            await handle.read(ReadRequest(queries=(query,)))
            with pytest.raises(VersionUnavailableError, match="cursor is unavailable"):
                await handle.read(
                    ReadRequest(
                        queries=(replace(query, after=page.next_page),), at_version=first.version
                    )
                )
        finally:
            await handle.close()

    asyncio.run(run())
