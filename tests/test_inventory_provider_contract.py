"""Contract-level tests for pluggable inventory providers."""

from __future__ import annotations

import ast
import asyncio
import inspect
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.inventory_engine.contract import (
    ALLOWED_PHASE_TRANSITIONS,
    QUERY_TYPE_BY_KIND,
    REGISTERED_QUERY_TYPES,
    CatalogProjection,
    CatalogQuery,
    ChangeBatch,
    ChangeCursor,
    Coverage,
    CoverageReason,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    EntryType,
    FilteredTreeProjection,
    FilteredTreeQuery,
    Freshness,
    IndexState,
    InventoryBackend,
    InventoryConfig,
    InventoryFilter,
    InventoryHandle,
    LifecyclePhase,
    MetadataProjection,
    MetadataQuery,
    NavigationProjection,
    NavigationQuery,
    PriorityRequest,
    QueryKind,
    ReadRequest,
    ReadResult,
    RecentProjection,
    RecentQuery,
    RefreshObservation,
    RefreshReceipt,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    SourceKind,
    WorkCounters,
)
from metabrowser.inventory_engine.providers.python import PythonInventoryBackend

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DOC = REPO_ROOT / "docs/project/architecture/arch-inventory-provider.md"

EXPECTED_QUERIES = {
    "entry": EntryQuery,
    "directory": DirectoryQuery,
    "filtered_tree": FilteredTreeQuery,
    "rollup": RollupQuery,
    "navigation": NavigationQuery,
    "recent": RecentQuery,
    "catalog": CatalogQuery,
    "metadata": MetadataQuery,
    "diagnostics": DiagnosticsQuery,
}

PROVIDER_FACTORIES: tuple[Any, ...] = (pytest.param(PythonInventoryBackend, id="python"),)


async def _open_settled_provider(
    factory: Callable[[], InventoryBackend],
    root: Path,
    *,
    config: InventoryConfig | None = None,
) -> InventoryHandle:
    handle = await factory().open(root, config or InventoryConfig())
    for _attempt in range(500):
        result = await handle.read(ReadRequest())
        if result.state.phase in {LifecyclePhase.WATCHING, LifecyclePhase.FAILED}:
            return handle
        await asyncio.sleep(0.005)
    await handle.close()
    raise AssertionError("inventory provider did not settle")


def _entry_semantics(entry: Any) -> tuple[object, ...]:
    return (
        entry.path,
        entry.type.value,
        entry.logical_extension,
        entry.size if entry.type is EntryType.FILE else None,
        entry.gitignored,
        entry.total_files,
        entry.total_size,
        entry.unignored_files,
        entry.unignored_size,
        entry.empty,
    )


def test_query_algebra_is_closed_and_registered_once() -> None:
    assert QUERY_TYPE_BY_KIND == EXPECTED_QUERIES
    assert tuple(QUERY_TYPE_BY_KIND.values()) == REGISTERED_QUERY_TYPES
    assert set(QueryKind) == {QueryKind(name) for name in EXPECTED_QUERIES}
    assert "kind" not in inspect.signature(EntryQuery).parameters


def test_architecture_document_lists_every_registered_query() -> None:
    document = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for kind, query_type in EXPECTED_QUERIES.items():
        assert f"| `{kind}` | `{query_type.__name__}` |" in document


def test_lifecycle_transition_graph_is_explicit_and_terminal() -> None:
    assert set(ALLOWED_PHASE_TRANSITIONS) == set(LifecyclePhase)
    assert ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.STOPPED] == frozenset()
    assert ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.FAILED] == frozenset({LifecyclePhase.STOPPED})
    for phase in set(LifecyclePhase) - {LifecyclePhase.STOPPED, LifecyclePhase.FAILED}:
        assert LifecyclePhase.STOPPED in ALLOWED_PHASE_TRANSITIONS[phase]
        assert LifecyclePhase.FAILED in ALLOWED_PHASE_TRANSITIONS[phase]


@pytest.mark.parametrize(
    ("query_type", "kwargs"),
    [
        (DirectoryQuery, {"max_depth": 0, "max_rows": 1}),
        (DirectoryQuery, {"max_depth": 1, "max_rows": 0}),
        (FilteredTreeQuery, {"max_depth": 1, "max_rows": 0}),
        (RollupQuery, {"max_depth": 1, "max_nodes": 0}),
        (NavigationQuery, {"max_rows": 0}),
        (RecentQuery, {"max_rows": 0, "as_of_ns": 1}),
        (CatalogQuery, {"max_rows": 0}),
    ],
)
def test_bounded_queries_reject_nonpositive_bounds(
    query_type: Callable[..., object], kwargs: dict[str, int]
) -> None:
    with pytest.raises(ValueError, match="positive"):
        query_type(query_id="q", **kwargs)


def test_read_request_defaults_to_a_checkpoint_and_rejects_duplicate_projection_ids() -> None:
    assert ReadRequest().queries == ()
    with pytest.raises(ValueError, match="unique"):
        ReadRequest(
            queries=(
                EntryQuery(query_id="same", path="a"),
                MetadataQuery(query_id="same"),
            )
        )


def test_catalog_predicates_are_canonical_and_bounded() -> None:
    with pytest.raises(ValueError, match="start with a dot"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=("jsonl",))
    with pytest.raises(ValueError, match="lowercase"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=(".JSONL",))
    with pytest.raises(ValueError, match="canonical terminal suffixes"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=(".run.jsonl",))
    with pytest.raises(ValueError, match="exact path-component"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=("runs/.logs",))
    with pytest.raises(ValueError, match="positive"):
        CatalogQuery(query_id="q", max_rows=1, size_less_than=0)


def test_state_requires_an_explanation_for_partial_coverage() -> None:
    assert "watcher_gap" not in {reason.value for reason in CoverageReason}
    with pytest.raises(ValueError, match="reason"):
        Coverage(complete=False)
    with pytest.raises(ValueError, match="complete"):
        Coverage(complete=True, reason=CoverageReason.BUILDING)


def test_configuration_and_command_bounds_are_enforced() -> None:
    with pytest.raises(ValueError, match="max_entries must be positive"):
        InventoryConfig(max_entries=0)
    with pytest.raises(ValueError, match="max_depth must be positive"):
        InventoryConfig(max_depth=0)
    with pytest.raises(ValueError, match="change_queue_size must be positive"):
        InventoryConfig(change_queue_size=0)
    with pytest.raises(ValueError, match="registry_fingerprint must not be empty"):
        InventoryConfig(registry_fingerprint="")
    with pytest.raises(ValueError, match="at most 1024"):
        RefreshRequest(
            observations=tuple(RefreshObservation(path=str(index)) for index in range(1_025))
        )
    with pytest.raises(ValueError, match="at most 1024"):
        PriorityRequest(paths=tuple(str(index) for index in range(1_025)))
    with pytest.raises(ValueError, match="nonnegative"):
        WorkCounters(entries_visited=-1)
    assert WorkCounters().cpu_time_ns is None
    assert WorkCounters(cpu_time_ns=0).cpu_time_ns == 0
    with pytest.raises(ValueError, match="nonnegative"):
        WorkCounters(cpu_time_ns=-1)
    with pytest.raises(ValueError, match="nonnegative"):
        RecentProjection(
            query_id="recent",
            entries=(),
            total_matches=-1,
            truncated=False,
        )


def test_change_batches_are_bounded_and_reset_dominates_dirtiness() -> None:
    version = EngineVersion(
        session="session-a",
        sequence=2,
        scope_fingerprint="scope",
        semantic_fingerprint="semantics",
    )
    state = IndexState(
        phase=LifecyclePhase.DISCOVERING,
        coverage=Coverage(complete=False, reason=CoverageReason.BUILDING),
        freshness=Freshness.PARTIAL,
        source=SourceKind.SCANNED,
    )
    cursor = ChangeCursor(session="session-a", sequence=2)
    with pytest.raises(ValueError, match="at most 1024"):
        ChangeBatch(
            version=version,
            cursor=cursor,
            state=state,
            dirty_paths=tuple(str(index) for index in range(1_025)),
        )
    with pytest.raises(ValueError, match="reset replaces"):
        ChangeBatch(
            version=version,
            cursor=cursor,
            state=state,
            reset=True,
            dirty_paths=("changed",),
        )


def test_version_and_cursor_share_a_session() -> None:
    version = EngineVersion(
        session="session-a",
        sequence=2,
        scope_fingerprint="scope",
        semantic_fingerprint="semantics",
    )
    state = IndexState(
        phase=LifecyclePhase.WATCHING,
        coverage=Coverage(complete=True),
        freshness=Freshness.FRESH,
        source=SourceKind.SCANNED,
    )
    with pytest.raises(ValueError, match="same session"):
        ReadResult(
            version=version,
            cursor=ChangeCursor(session="session-b", sequence=2),
            state=state,
            projections=(),
            work=WorkCounters(),
        )


class _Handle:
    async def read(self, request: ReadRequest) -> ReadResult:
        raise NotImplementedError

    async def changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]:
        if False:
            yield

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        return RefreshReceipt(accepted_paths=request.paths)

    async def prioritize(self, request: PriorityRequest) -> None:
        return None

    async def close(self) -> None:
        return None


class _Backend:
    async def open(self, root: Path, config: InventoryConfig) -> InventoryHandle:
        return _Handle()


def test_protocols_are_structural_and_provider_neutral() -> None:
    assert isinstance(_Handle(), InventoryHandle)
    assert isinstance(_Backend(), InventoryBackend)

    source = inspect.getsource(__import__("metabrowser.inventory_engine.contract", fromlist=["*"]))
    imported_modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    assert not imported_modules & {
        "starlette",
        "metabrowser.events",
        "metabrowser.inventory",
        "metabrowser.sse",
    }


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_checkpoint_read_returns_only_a_coherent_constant_work_envelope(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(provider_factory, tmp_path)
        try:
            checkpoint = await handle.read(ReadRequest())
            assert checkpoint.projections == ()
            assert checkpoint.version.session == checkpoint.cursor.session
            assert checkpoint.version.sequence == checkpoint.cursor.sequence
            assert checkpoint.state.phase is LifecyclePhase.WATCHING
            assert checkpoint.work.entries_visited == 0
            assert checkpoint.work.directories_visited == 0
            assert checkpoint.work.rows_returned == 0
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_paged_time_dependent_reads_reuse_one_as_of(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for index, mtime_ns in enumerate((210_000_000_000, 220_000_000_000, 230_000_000_000)):
        path = tmp_path / f"recent-{index}.txt"
        path.write_text(str(index), encoding="utf-8")
        os.utime(path, ns=(mtime_ns, mtime_ns))

    async def run() -> tuple[str, ...]:
        handle = await _open_settled_provider(provider_factory, tmp_path)
        try:
            as_of_ns = 300_000_000_000
            after: str | None = None
            version: EngineVersion | None = None
            paths: list[str] = []
            while True:
                result = await handle.read(
                    ReadRequest(
                        queries=(
                            FilteredTreeQuery(
                                query_id="recent-page",
                                max_depth=1,
                                max_rows=1,
                                after=after,
                                filter=InventoryFilter(
                                    recency_seconds=100,
                                    as_of_ns=as_of_ns,
                                ),
                            ),
                        ),
                        at_version=version,
                    )
                )
                if version is None:
                    version = result.version
                projection = cast(
                    "FilteredTreeProjection",
                    result.projection("recent-page"),
                )
                paths.extend(entry.path for entry in projection.entries)
                after = projection.next_page
                if after is None:
                    return tuple(paths)
        finally:
            await handle.close()

    assert asyncio.run(run()) == (
        "recent-0.txt",
        "recent-1.txt",
        "recent-2.txt",
    )


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_semantic_digest(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    """Every provider must produce the same normalized filesystem semantics."""

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    tracked = tmp_path / "tracked"
    tracked.mkdir()
    bundle = tracked / "bundle.min.js"
    bundle.write_text("code", encoding="utf-8")
    readme = tracked / "README"
    readme.write_text("readme", encoding="utf-8")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    cache = ignored / "cache.bin"
    cache.write_text("xxx", encoding="utf-8")
    os.utime(bundle, ns=(4_000_000_000, 4_000_000_000))
    os.utime(readme, ns=(3_000_000_000, 3_000_000_000))
    os.utime(cache, ns=(2_000_000_000, 2_000_000_000))
    try:
        (tmp_path / "bundle-link").symlink_to("tracked/bundle.min.js")
    except OSError as error:  # pragma: no cover - unsupported Windows policy
        pytest.skip(f"symlinks are unavailable: {error}")

    async def run() -> dict[str, object]:
        handle = await _open_settled_provider(provider_factory, tmp_path)
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        EntryQuery(query_id="link", path="bundle-link"),
                        DirectoryQuery(
                            query_id="directory",
                            max_depth=3,
                            max_rows=100,
                        ),
                        FilteredTreeQuery(
                            query_id="filtered",
                            max_depth=3,
                            max_rows=100,
                            filter=InventoryFilter(
                                extensions=(".min.js",),
                                include_ignored=False,
                            ),
                        ),
                        RollupQuery(
                            query_id="rollup",
                            max_depth=3,
                            max_nodes=100,
                            top=20,
                            extension_top=20,
                        ),
                        NavigationQuery(query_id="navigation", max_rows=20),
                        RecentQuery(
                            query_id="recent",
                            max_rows=20,
                            as_of_ns=10**30,
                            include_ignored=True,
                        ),
                        CatalogQuery(
                            query_id="catalog",
                            max_rows=20,
                            include_ignored=False,
                        ),
                        MetadataQuery(query_id="metadata"),
                    )
                )
            )
            link = cast("EntryProjection", result.projection("link"))
            directory = cast("DirectoryProjection", result.projection("directory"))
            filtered = cast("FilteredTreeProjection", result.projection("filtered"))
            rollup = cast("RollupProjection", result.projection("rollup"))
            navigation = cast("NavigationProjection", result.projection("navigation"))
            recent = cast("RecentProjection", result.projection("recent"))
            catalog = cast("CatalogProjection", result.projection("catalog"))
            metadata = cast("MetadataProjection", result.projection("metadata"))

            assert link.presence is EntryPresence.PRESENT
            assert link.entry is not None
            assert rollup.payload is not None
            rollup_node = cast("dict[str, object]", rollup.payload["node"])
            rollup_children = cast("list[dict[str, object]]", rollup_node["children"])
            navigation_summary = cast("dict[str, int]", navigation.payload["summary"])
            return {
                "state": (
                    result.state.phase.value,
                    result.state.coverage.complete,
                    result.state.freshness.value,
                    result.state.source.value,
                ),
                "link": _entry_semantics(link.entry),
                "directory": tuple(_entry_semantics(entry) for entry in directory.entries),
                "filtered": (
                    tuple(entry.path for entry in filtered.entries),
                    filtered.matching_files,
                    filtered.matching_bytes,
                ),
                "rollup": (
                    rollup_node["total_files"],
                    rollup_node["total_size"],
                    rollup_node["unignored_files"],
                    rollup_node["unignored_size"],
                    tuple(
                        (
                            child["name"],
                            child["type"],
                            child.get("total_files"),
                            child.get("total_size"),
                            child.get("unignored_files"),
                            child.get("unignored_size"),
                            child.get("gitignored", False),
                        )
                        for child in rollup_children
                    ),
                ),
                "navigation": navigation_summary,
                "recent": tuple(entry.path for entry in recent.entries),
                "catalog": tuple(
                    (record.path, record.logical_extension, record.size)
                    for record in catalog.records
                ),
                "metadata": (metadata.provider, metadata.contract),
            }
        finally:
            await handle.close()

    actual = asyncio.run(run())
    expected = {
        "state": ("watching", True, "fresh", "scanned"),
        "link": ("bundle-link", "symlink", "", None, False, None, None, None, None, None),
        "directory": (
            ("ignored", "dir", "", None, True, 1, 3, 0, 0, False),
            ("tracked", "dir", "", None, False, 2, 10, 2, 10, False),
            ("bundle-link", "symlink", "", None, False, None, None, None, None, None),
            ("ignored/cache.bin", "file", ".bin", 3, True, None, None, None, None, None),
            ("tracked/README", "file", "", 6, False, None, None, None, None, None),
            (
                "tracked/bundle.min.js",
                "file",
                ".min.js",
                4,
                False,
                None,
                None,
                None,
                None,
                None,
            ),
        ),
        "filtered": (("tracked", "tracked/bundle.min.js"), 1, 4),
        "rollup": (
            3,
            13,
            2,
            10,
            (
                ("tracked", "dir", 2, 10, 2, 10, False),
                ("ignored", "dir", 1, 3, 0, 0, True),
            ),
        ),
        "navigation": {
            "files": 2,
            "size": 10,
            "ignored_files": 1,
            "ignored_size": 3,
        },
        "recent": ("tracked/bundle.min.js", "tracked/README", "ignored/cache.bin"),
        "catalog": (
            ("tracked/README", "", 6),
            ("tracked/bundle.min.js", ".min.js", 4),
        ),
        "metadata": ("python", "inventory-provider-v1"),
    }
    assert actual == expected, actual


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_budget_stop_is_explicit_and_absence_remains_unknown(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for name in ("a.txt", "b.txt", "c.txt", "d.txt", "z.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    async def run() -> tuple[object, ...]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(max_entries=2),
        )
        try:
            result = await handle.read(
                ReadRequest(queries=(EntryQuery(query_id="missing", path="z.txt"),))
            )
            projection = cast("EntryProjection", result.projection("missing"))
            return (
                result.state.phase.value,
                result.state.coverage.complete,
                result.state.coverage.reason.value if result.state.coverage.reason else None,
                tuple(issue.code.value for issue in result.state.issues),
                projection.presence.value,
            )
        finally:
            await handle.close()

    assert asyncio.run(run()) == (
        "watching",
        False,
        "budget",
        ("resource_budget",),
        "unknown",
    )
