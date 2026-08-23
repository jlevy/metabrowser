"""Contract-level tests for pluggable inventory providers."""

from __future__ import annotations

import ast
import inspect
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import (
    ALLOWED_PHASE_TRANSITIONS,
    QUERY_TYPE_BY_KIND,
    REGISTERED_QUERY_TYPES,
    CatalogQuery,
    ChangeBatch,
    ChangeCursor,
    Coverage,
    CoverageReason,
    DiagnosticsQuery,
    DirectoryQuery,
    EngineVersion,
    EntryQuery,
    FilteredTreeQuery,
    Freshness,
    IndexState,
    InventoryBackend,
    InventoryConfig,
    InventoryHandle,
    LifecyclePhase,
    MetadataQuery,
    NavigationQuery,
    PriorityRequest,
    QueryKind,
    ReadRequest,
    ReadResult,
    RecentProjection,
    RecentQuery,
    RefreshReceipt,
    RefreshRequest,
    RollupQuery,
    SourceKind,
    WorkCounters,
)

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


def test_read_request_rejects_empty_or_duplicate_projection_ids() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ReadRequest(queries=())

    with pytest.raises(ValueError, match="unique"):
        ReadRequest(
            queries=(
                EntryQuery(query_id="same", path="a"),
                MetadataQuery(query_id="same"),
            )
        )


def test_state_requires_an_explanation_for_partial_coverage() -> None:
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
    with pytest.raises(ValueError, match="at most 1024"):
        RefreshRequest(paths=tuple(str(index) for index in range(1_025)))
    with pytest.raises(ValueError, match="at most 1024"):
        PriorityRequest(paths=tuple(str(index) for index in range(1_025)))
    with pytest.raises(ValueError, match="nonnegative"):
        WorkCounters(entries_visited=-1)
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
        registry_fingerprint="registry",
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
        registry_fingerprint="registry",
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
