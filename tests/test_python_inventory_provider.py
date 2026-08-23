"""The current filesystem engine behind the provider-neutral contract."""

from __future__ import annotations

import ast
import asyncio
import inspect
from pathlib import Path

import pytest

from metabrowser import inventory_rollup, walker
from metabrowser.inventory_engine import contract
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    ChangeBatch,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryClosedError,
    InventoryConfig,
    InventoryFilter,
    InventoryHandle,
    MetadataProjection,
    MetadataQuery,
    NavigationProjection,
    NavigationQuery,
    ReadRequest,
    RecentProjection,
    RecentQuery,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.providers import python as python_provider
from metabrowser.inventory_engine.providers.python import PythonInventoryBackend


async def _open_settled(
    root: Path,
    config: InventoryConfig | None = None,
) -> InventoryHandle:
    handle = await PythonInventoryBackend().open(root, config or InventoryConfig())
    for _attempt in range(200):
        result = await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="state"),)))
        if result.state.phase.value in {"watching", "failed"}:
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
                    MetadataQuery(query_id="metadata"),
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
        assert catalog.total_matches == 2
        assert catalog.next_page is not None

        metadata = result.projection("metadata")
        assert isinstance(metadata, MetadataProjection)
        assert metadata.provider == "python"
        assert metadata.contract == "inventory-provider-v1"

        diagnostics = result.projection("diagnostics")
        assert isinstance(diagnostics, DiagnosticsProjection)
        assert diagnostics.counters["provider"] == "python"
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
        receipt = await handle.refresh(RefreshRequest(paths=("b.txt",)))
        assert receipt.accepted_paths == ("b.txt",)

        batch = await asyncio.wait_for(anext(changes), timeout=1)
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


async def _close_is_idempotent_and_refuses_later_reads(tmp_path: Path) -> None:
    handle = await PythonInventoryBackend().open(tmp_path, InventoryConfig())
    assert isinstance(handle, InventoryHandle)
    await handle.close()
    await handle.close()
    with pytest.raises(InventoryClosedError):
        await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="state"),)))


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
        assert recent.total_matches == 3
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
        assert result.work.entries_visited == 1
        assert result.work.rows_returned == 1
    finally:
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
            await handle.refresh(RefreshRequest(paths=(path,)))

        batch = await asyncio.wait_for(anext(handle.changes(after=before.cursor)), timeout=1)
        assert batch.reset
        assert not batch.dirty_paths
        assert not batch.dirty_queries
    finally:
        await handle.close()


async def _refresh_rejects_noncanonical_paths(tmp_path: Path) -> None:
    handle = await _open_settled(tmp_path)
    try:
        receipt = await handle.refresh(RefreshRequest(paths=("../outside", "a//b", "a\\b")))
        assert receipt.accepted_paths == ()
        assert receipt.rejected_paths == ("../outside", "a//b", "a\\b")
    finally:
        await handle.close()


def test_python_provider_answers_one_coherent_bundled_read(tmp_path: Path) -> None:
    asyncio.run(_python_provider_answers_one_coherent_bundled_read(tmp_path))


def test_refresh_advances_version_and_emits_provider_change(tmp_path: Path) -> None:
    asyncio.run(_refresh_advances_version_and_emits_provider_change(tmp_path))


def test_close_is_idempotent_and_refuses_later_reads(tmp_path: Path) -> None:
    asyncio.run(_close_is_idempotent_and_refuses_later_reads(tmp_path))


def test_python_provider_implements_every_projection(tmp_path: Path) -> None:
    asyncio.run(_python_provider_implements_every_projection(tmp_path))


def test_targeted_read_reports_bounded_work(tmp_path: Path) -> None:
    asyncio.run(_targeted_read_reports_bounded_work(tmp_path))


def test_expired_change_cursor_yields_reset(tmp_path: Path) -> None:
    asyncio.run(_expired_change_cursor_yields_reset(tmp_path))


def test_refresh_rejects_noncanonical_paths(tmp_path: Path) -> None:
    asyncio.run(_refresh_rejects_noncanonical_paths(tmp_path))


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
