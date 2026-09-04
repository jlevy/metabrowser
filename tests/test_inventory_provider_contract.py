"""Contract-level tests for pluggable inventory providers."""

from __future__ import annotations

import ast
import asyncio
import inspect
import itertools
import os
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.file_type_registry import load_file_type_registry_document
from metabrowser.inventory_engine.contract import (
    ALLOWED_PHASE_TRANSITIONS,
    MAX_ASSEMBLED_ROWS,
    MAX_COMMAND_PATHS,
    MAX_COUNT_CAP,
    MAX_INVENTORY_ISSUES,
    MAX_ISSUE_DETAIL_BYTES,
    MAX_PORTABLE_PATH_EXAMPLE_BYTES,
    MAX_PORTABLE_PATH_EXAMPLES,
    QUERY_TYPE_BY_KIND,
    REGISTERED_QUERY_TYPES,
    AdmittedObjectKind,
    BoundaryMetrics,
    CatalogProjection,
    CatalogQuery,
    CatalogRecord,
    ChangeBatch,
    ChangeCursor,
    ChangeStreamBusyError,
    CountKind,
    CountResult,
    Coverage,
    CoverageReason,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    DiscoveryBudget,
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
    InventoryClosedError,
    InventoryConfig,
    InventoryEntry,
    InventoryFilter,
    InventoryHandle,
    InventoryIssue,
    IssueCode,
    LifecyclePhase,
    NavigationProjection,
    NavigationQuery,
    ObservationKind,
    PortablePathEncoding,
    PortablePathExample,
    PortablePathIssue,
    PriorityRequest,
    QueryKind,
    QueryLimitProjection,
    QueryWorkLimitError,
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
    VersionUnavailableError,
    WorkCounters,
    catalog_terminal_suffix,
    inventory_scope_fingerprint,
)
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend
from metabrowser.wire_models import validate_rollup_result

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DOC = REPO_ROOT / "docs/project/architecture/arch-inventory-provider.md"
# Bound transient watcher churn so this conformance case cannot hang.
_PROVIDER_PAGE_ATTEMPTS = 3

EXPECTED_QUERIES = {
    "entry": EntryQuery,
    "directory": DirectoryQuery,
    "filtered_tree": FilteredTreeQuery,
    "rollup": RollupQuery,
    "navigation": NavigationQuery,
    "recent": RecentQuery,
    "catalog": CatalogQuery,
    "diagnostics": DiagnosticsQuery,
}

PROVIDER_FACTORIES: tuple[Any, ...] = (pytest.param(PythonInventoryBackend, id="python"),)

PROVIDER_CONFORMANCE_TESTS = frozenset(
    {
        "test_checkpoint_read_returns_only_a_coherent_constant_work_envelope",
        "test_paged_time_dependent_reads_reuse_one_as_of",
        "test_provider_semantic_digest",
        "test_provider_derives_registry_identity_from_supplied_content",
        "test_provider_uses_supplied_registry_content_for_classification",
        "test_provider_budget_stop_is_explicit_and_absence_remains_unknown",
        "test_directory_pages_are_lossless_when_directories_outnumber_file_budget",
        "test_catalog_predicate_semantics_are_runtime_independent_and_exact",
        "test_catalog_pages_are_lossless_without_suffix_counts",
        "test_provider_applies_work_bounds_to_continuation_pages",
        "test_provider_returns_typed_query_limits_without_partial_answers",
        "test_provider_counts_are_exact_or_proven_lower_bounds",
        "test_provider_uses_canonical_portable_row_order",
        "test_provider_version_pins_fail_instead_of_moving",
        "test_provider_changes_resume_and_report_history_gaps_as_reset",
        "test_provider_allows_only_one_active_change_iterator",
        "test_provider_refresh_verifies_the_filesystem_instead_of_trusting_the_hint",
        "test_provider_close_joins_change_delivery_and_is_idempotent",
        "test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session",
    }
)


async def _open_settled_provider(
    factory: Callable[[], InventoryBackend],
    root: Path,
    *,
    config: InventoryConfig | None = None,
) -> InventoryHandle:
    handle = await factory().open(root, config or InventoryConfig())
    for _attempt in range(500):
        result = await handle.read(ReadRequest())
        if result.state.phase in {
            LifecyclePhase.READY,
            LifecyclePhase.WATCHING,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }:
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


def test_architecture_document_registers_every_provider_conformance_case() -> None:
    document = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for test_name in PROVIDER_CONFORMANCE_TESTS:
        assert test_name in globals(), f"missing provider conformance test: {test_name}"
        marks = getattr(globals()[test_name], "pytestmark", ())
        assert any(
            mark.name == "parametrize" and mark.args and mark.args[0] == "provider_factory"
            for mark in marks
        ), f"provider conformance test is not factory-parametrized: {test_name}"
        assert f"| `{test_name}` |" in document


def test_lifecycle_transition_graph_is_explicit_and_terminal() -> None:
    assert set(ALLOWED_PHASE_TRANSITIONS) == set(LifecyclePhase)
    assert ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.STOPPED] == frozenset()
    assert ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.FAILED] == frozenset({LifecyclePhase.STOPPED})
    assert LifecyclePhase.READY in ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.DISCOVERING]
    assert LifecyclePhase.READY in ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.RECONCILING]
    assert LifecyclePhase.READY in ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.WATCHING]
    assert LifecyclePhase.WATCHING in ALLOWED_PHASE_TRANSITIONS[LifecyclePhase.READY]
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
                DiagnosticsQuery(query_id="same"),
            )
        )
    with pytest.raises(ValueError, match="exact provider version"):
        ReadRequest(queries=(DirectoryQuery(query_id="page", after="opaque-continuation"),))


@pytest.mark.parametrize(
    "factory",
    (
        lambda: DirectoryProjection(query_id="directory", entries=(), next_page="next"),
        lambda: FilteredTreeProjection(
            query_id="filtered",
            entries=(),
            matching_leaves=0,
            matching_files=0,
            matching_bytes=0,
            next_page="next",
        ),
        lambda: CatalogProjection(
            query_id="catalog",
            records=(),
            total_matches=CountResult(CountKind.EXACT, 1),
            next_page="next",
        ),
    ),
)
def test_paged_projection_continuations_require_nonempty_pages(
    factory: Callable[[], object],
) -> None:
    with pytest.raises(ValueError, match="continuation"):
        factory()


def test_catalog_predicates_are_canonical_and_bounded() -> None:
    with pytest.raises(ValueError, match="start with a dot"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=("jsonl",))
    with pytest.raises(ValueError, match="lowercase"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=(".JSONL",))
    with pytest.raises(ValueError, match="canonical terminal suffixes"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=(".run.jsonl",))
    with pytest.raises(ValueError, match="unique"):
        CatalogQuery(query_id="q", max_rows=1, terminal_extensions=(".jsonl", ".jsonl"))
    with pytest.raises(ValueError, match="exact path-component"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=("runs/.logs",))
    with pytest.raises(ValueError, match="exact path-component"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=("runs\\logs",))
    with pytest.raises(ValueError, match="exact path-component"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=(".",))
    with pytest.raises(ValueError, match="exact path-component"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=("..",))
    with pytest.raises(ValueError, match="unique"):
        CatalogQuery(query_id="q", max_rows=1, ancestor_names=("runs", "runs"))
    with pytest.raises(ValueError, match="positive"):
        CatalogQuery(query_id="q", max_rows=1, size_less_than=0)


def test_catalog_terminal_suffix_has_one_explicit_cross_provider_rule() -> None:
    assert catalog_terminal_suffix("notes.txt") == ".txt"
    assert catalog_terminal_suffix("archive.tar.gz") == ".gz"
    assert catalog_terminal_suffix("..foo") == ".foo"
    assert catalog_terminal_suffix(".foo") == ""
    assert catalog_terminal_suffix("foo.") == ""


def test_catalog_records_preserve_signed_filesystem_mtimes() -> None:
    record = CatalogRecord(
        path="old.txt",
        logical_extension=".txt",
        size=1,
        mtime_ns=-1,
    )
    assert record.mtime_ns == -1


def test_state_vocabularies_match_the_native_contract_exactly() -> None:
    assert {phase.value for phase in LifecyclePhase} == {
        "opening",
        "discovering",
        "reconciling",
        "ready",
        "watching",
        "stopped",
        "failed",
    }
    assert {reason.value for reason in CoverageReason} == {
        "building",
        "budget",
        "cancelled",
        "inaccessible",
        "failed",
    }
    assert {freshness.value for freshness in Freshness} == {
        "fresh",
        "reconciling",
        "stale",
        "partial",
    }
    assert {source.value for source in SourceKind} == {
        "scanned",
        "revalidated",
        "journal_scoped",
        "cached",
    }
    assert {code.value for code in IssueCode} == {
        "permission",
        "disappeared",
        "invalid_metadata",
        "resource_budget",
        "observation_gap",
        "provider_failure",
    }


def test_state_requires_an_explanation_for_partial_coverage() -> None:
    with pytest.raises(ValueError, match="reason"):
        Coverage(complete=False)
    with pytest.raises(ValueError, match="complete"):
        Coverage(complete=True, reason=CoverageReason.BUILDING)


def test_configuration_and_command_bounds_are_enforced() -> None:
    with pytest.raises(ValueError, match="max_files must be a positive integer"):
        DiscoveryBudget(max_files=0)
    with pytest.raises(ValueError, match="max_files must be a positive integer"):
        DiscoveryBudget(max_files=cast(Any, True))
    with pytest.raises(ValueError, match="budget"):
        InventoryConfig(budget=cast(Any, 10))
    with pytest.raises(ValueError, match="change_queue_size must be positive"):
        InventoryConfig(change_queue_size=0)
    with pytest.raises(ValueError, match="registry"):
        InventoryConfig(registry_document="")
    with pytest.raises(ValueError, match="registry"):
        InventoryConfig(registry_document=cast(Any, None))
    with pytest.raises(ValueError, match="symlink"):
        InventoryConfig(follow_symlinks=True)
    with pytest.raises(ValueError, match="scope flags"):
        InventoryConfig(include_hidden=cast(Any, 0))
    with pytest.raises(ValueError, match="filesystem"):
        InventoryConfig(one_filesystem=True)
    with pytest.raises(ValueError, match="object kinds"):
        InventoryConfig(admitted_object_kinds=(AdmittedObjectKind.FILE,))
    with pytest.raises(ValueError, match="object kinds"):
        InventoryConfig(
            admitted_object_kinds=cast(
                Any,
                ("file", "directory", "symlink"),
            )
        )
    with pytest.raises(ValueError, match="hidden_allowlist"):
        InventoryConfig(hidden_allowlist=cast(Any, [".metabrowser"]))
    with pytest.raises(ValueError, match="watch_mode"):
        InventoryConfig(watch_mode=cast(Any, "sometimes"))
    for invalid_hidden_name in ("visible", ".", "..", ".nested/name", ".bad\\name", ".bad\x00name"):
        with pytest.raises(ValueError, match="exact hidden path-component"):
            InventoryConfig(hidden_allowlist=(invalid_hidden_name,))
    with pytest.raises(ValueError, match="at most 1024"):
        RefreshRequest(
            observations=tuple(RefreshObservation(path=str(index)) for index in range(1_025))
        )
    with pytest.raises(ValueError, match="at most 1024"):
        PriorityRequest(paths=tuple(str(index) for index in range(1_025)))
    with pytest.raises(ValueError, match="at most 1024"):
        ReadRequest(
            queries=tuple(
                EntryQuery(query_id=f"entry-{index}", path=str(index)) for index in range(1_025)
            )
        )
    with pytest.raises(ValueError, match="unique"):
        PriorityRequest(paths=("same", "same"))
    with pytest.raises(ValueError, match="nonnegative"):
        WorkCounters(entries_visited=-1)
    assert BoundaryMetrics().cpu_time_ns is None
    assert BoundaryMetrics(cpu_time_ns=0).cpu_time_ns == 0
    with pytest.raises(ValueError, match="nonnegative"):
        BoundaryMetrics(cpu_time_ns=-1)
    with pytest.raises(ValueError, match="nonnegative"):
        CountResult(CountKind.EXACT, -1)


def test_query_work_and_count_bounds_are_enforced() -> None:
    query_factories: tuple[Callable[[int], object], ...] = (
        lambda value: DirectoryQuery(query_id="directory", max_work=value),
        lambda value: FilteredTreeQuery(query_id="filtered", max_work=value),
        lambda value: RollupQuery(query_id="rollup", max_work=value),
        lambda value: NavigationQuery(query_id="navigation", max_work=value),
        lambda value: RecentQuery(
            query_id="recent",
            max_rows=1,
            as_of_ns=1,
            max_work=value,
        ),
        lambda value: CatalogQuery(query_id="catalog", max_rows=1, max_work=value),
    )
    for factory in query_factories:
        with pytest.raises(ValueError, match="positive"):
            factory(0)
        with pytest.raises(ValueError, match="at most"):
            factory(MAX_ASSEMBLED_ROWS + 1)

    for count_cap in (0, MAX_COUNT_CAP + 1):
        with pytest.raises(ValueError, match="count_cap"):
            RecentQuery(
                query_id="recent",
                max_rows=1,
                as_of_ns=1,
                count_cap=count_cap,
            )
        with pytest.raises(ValueError, match="count_cap"):
            CatalogQuery(query_id="catalog", max_rows=1, count_cap=count_cap)


def test_inventory_scope_fingerprint_is_portable_and_semantic() -> None:
    first = InventoryConfig(
        budget=DiscoveryBudget(max_files=10),
        hidden_allowlist=(".z", ".a"),
    )
    reordered = InventoryConfig(
        budget=DiscoveryBudget(max_files=20),
        hidden_allowlist=(".a", ".z"),
        admitted_object_kinds=(
            AdmittedObjectKind.SYMLINK,
            AdmittedObjectKind.DIRECTORY,
            AdmittedObjectKind.FILE,
        ),
    )
    changed = InventoryConfig(
        budget=DiscoveryBudget(max_files=10),
        hidden_allowlist=(".a", ".雪"),
    )
    reformatted_registry = InventoryConfig(
        registry_document=f"{load_file_type_registry_document()}\n",
        hidden_allowlist=(".a", ".z"),
    )

    digest = inventory_scope_fingerprint(first)
    assert digest == inventory_scope_fingerprint(reordered)
    assert digest != inventory_scope_fingerprint(changed)
    assert digest == inventory_scope_fingerprint(reformatted_registry)
    assert inventory_scope_fingerprint(changed) == (
        "9e6928332861f2f6a485dcffabfac6a6c8a1f0ecb4e080684f7dcddce28dfdcd"
    )
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_derives_registry_identity_from_supplied_content(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    registry_document = load_file_type_registry_document()
    changed_registry = registry_document.replace(
        "registry_revision = 3",
        "registry_revision = 4",
        1,
    )

    async def identity(config: InventoryConfig) -> EngineVersion:
        handle = await _open_settled_provider(provider_factory, tmp_path, config=config)
        try:
            return (await handle.read(ReadRequest())).version
        finally:
            await handle.close()

    baseline = asyncio.run(identity(InventoryConfig(watch_mode="off")))
    reformatted = asyncio.run(
        identity(
            InventoryConfig(
                registry_document=f"{registry_document}\n",
                watch_mode="off",
            )
        )
    )
    changed = asyncio.run(
        identity(
            InventoryConfig(
                registry_document=changed_registry,
                watch_mode="off",
            )
        )
    )

    assert baseline.scope_fingerprint == reformatted.scope_fingerprint
    assert baseline.semantic_fingerprint == reformatted.semantic_fingerprint
    assert baseline.scope_fingerprint == changed.scope_fingerprint
    assert baseline.semantic_fingerprint != changed.semantic_fingerprint


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_uses_supplied_registry_content_for_classification(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    (tmp_path / "note.md").write_text("# Note\n", encoding="utf-8")
    registry_document = load_file_type_registry_document()
    changed_registry = registry_document.replace(
        'id = "python"\nfamily = "python"\ncontent_family = "code"',
        'id = "python"\nfamily = "markdown"\ncontent_family = "code"',
        1,
    ).replace(
        'id = "markdown"\nfamily = "markdown"\ncontent_family = "markup"',
        'id = "markdown"\nfamily = "python"\ncontent_family = "markup"',
        1,
    )
    assert changed_registry != registry_document

    async def markdown_group(config: InventoryConfig) -> str:
        handle = await _open_settled_provider(provider_factory, tmp_path, config=config)
        try:
            read = await handle.read(
                ReadRequest(
                    queries=(
                        RollupQuery(
                            query_id="rollup",
                            max_depth=2,
                            max_nodes=20,
                            top=20,
                            extension_top=20,
                        ),
                    )
                )
            )
            projection = cast("RollupProjection", read.projection("rollup"))
            assert projection.payload is not None
            breakdown = cast("dict[str, object]", projection.payload["file_type_breakdown"])
            groups = cast("list[dict[str, object]]", breakdown["groups"])
            for group in groups:
                families = cast("list[dict[str, object]]", group["families"])
                for family in families:
                    extensions = cast("list[dict[str, object]]", family["extensions"])
                    if any(extension["extension"] == ".md" for extension in extensions):
                        return cast(str, group["id"])
            raise AssertionError("the Markdown extension is absent from the rollup")
        finally:
            await handle.close()

    baseline = asyncio.run(markdown_group(InventoryConfig(watch_mode="off")))
    changed = asyncio.run(
        markdown_group(
            InventoryConfig(
                registry_document=changed_registry,
                watch_mode="off",
            )
        )
    )

    assert baseline == "docs"
    assert changed == "code"


@pytest.mark.parametrize("path", ("/absolute", "a//b", "a/./b", "a/../b", "a\\b", "a\x00b"))
def test_path_bearing_contract_records_reject_noncanonical_paths(path: str) -> None:
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        EntryQuery(query_id="entry", path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        DirectoryQuery(query_id="directory", path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        FilteredTreeQuery(query_id="filtered", path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        RollupQuery(query_id="rollup", path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        RefreshObservation(path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        PriorityRequest(paths=(path,))
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        CatalogRecord(path=path, logical_extension="", size=0, mtime_ns=0)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        InventoryEntry(
            path=path,
            parent="",
            name="entry",
            type=EntryType.FILE,
            ext="",
            size=0,
            mtime_ns=0,
        )
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        InventoryIssue(code=IssueCode.PROVIDER_FAILURE, detail="failed", path=path)
    with pytest.raises(ValueError, match="canonical POSIX-relative"):
        RecentProjection(
            query_id="recent",
            entries=(),
            total_matches=CountResult(CountKind.EXACT, 0),
            gitignored_directories=(path,),
        )


def test_entry_identity_and_refresh_receipts_are_self_consistent() -> None:
    version = EngineVersion(
        session="session-a",
        sequence=1,
        scope_fingerprint="scope",
        semantic_fingerprint="semantics",
    )
    with pytest.raises(ValueError, match="one identity"):
        InventoryEntry(
            path="directory/file.txt",
            parent="wrong",
            name="file.txt",
            type=EntryType.FILE,
            ext=".txt",
            size=0,
            mtime_ns=0,
        )
    with pytest.raises(ValueError, match="both accepted and rejected"):
        RefreshReceipt(
            version=version,
            accepted_paths=("same",),
            rejected_paths=("same",),
        )
    with pytest.raises(ValueError, match="at most"):
        RefreshReceipt(
            version=version,
            accepted_paths=tuple(f"path-{index}" for index in range(MAX_COMMAND_PATHS + 1)),
        )


def test_lifecycle_diagnostics_are_bounded_before_crossing_provider_boundaries() -> None:
    with pytest.raises(ValueError, match="UTF-8 bytes"):
        InventoryIssue(
            code=IssueCode.PROVIDER_FAILURE,
            detail="x" * (MAX_ISSUE_DETAIL_BYTES + 1),
        )


def test_portable_path_loss_is_bounded_and_losslessly_encoded() -> None:
    example = PortablePathExample(
        encoding=PortablePathEncoding.UNIX_BYTES,
        encoded_hex="ff00",
        truncated=False,
    )
    assert PortablePathIssue(omitted=1, examples=(example,)).omitted == 1
    with pytest.raises(ValueError, match="positive"):
        PortablePathIssue(omitted=0)
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        PortablePathExample(
            encoding=PortablePathEncoding.UNIX_BYTES,
            encoded_hex="FF",
            truncated=False,
        )
    with pytest.raises(ValueError, match="encoded-byte bound"):
        PortablePathExample(
            encoding=PortablePathEncoding.PLATFORM_BYTES,
            encoded_hex="aa" * (MAX_PORTABLE_PATH_EXAMPLE_BYTES + 1),
            truncated=True,
        )
    with pytest.raises(ValueError, match="at most"):
        PortablePathIssue(
            omitted=MAX_PORTABLE_PATH_EXAMPLES + 1,
            examples=(example,) * (MAX_PORTABLE_PATH_EXAMPLES + 1),
        )

    issue = InventoryIssue(code=IssueCode.PROVIDER_FAILURE, detail="failed")
    with pytest.raises(ValueError, match="at most"):
        IndexState(
            phase=LifecyclePhase.FAILED,
            coverage=Coverage(complete=False, reason=CoverageReason.FAILED),
            freshness=Freshness.PARTIAL,
            source=SourceKind.SCANNED,
            issues=(issue,) * (MAX_INVENTORY_ISSUES + 1),
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
    assert version.cursor == ChangeCursor.from_version(version)

    limited = ReadResult(
        version=version,
        cursor=version.cursor,
        state=state,
        projections=(
            QueryLimitProjection(
                query_id="catalog",
                query_kind=QueryKind.CATALOG,
                max_work=10,
                rows_visited=10,
            ),
        ),
        work=WorkCounters(rows_visited=10),
    )
    with pytest.raises(QueryWorkLimitError, match="catalog query"):
        limited.completed_projection("catalog")


def test_recent_truncation_is_derived_from_the_projection_rows() -> None:
    complete = RecentProjection(
        query_id="complete",
        entries=(),
        total_matches=CountResult(CountKind.EXACT, 0),
    )
    truncated = RecentProjection(
        query_id="truncated",
        entries=(),
        total_matches=CountResult(CountKind.EXACT, 1),
    )
    capped = RecentProjection(
        query_id="capped",
        entries=(),
        total_matches=CountResult(CountKind.AT_LEAST, 0),
    )
    assert complete.truncated is False
    assert truncated.truncated is True
    assert capped.truncated is True


class _Handle:
    async def read(self, request: ReadRequest) -> ReadResult:
        raise NotImplementedError

    async def changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]:
        if False:
            yield

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt:
        return RefreshReceipt(
            version=EngineVersion(
                session="protocol",
                sequence=0,
                scope_fingerprint="scope",
                semantic_fingerprint="semantics",
            ),
            accepted_paths=request.paths,
        )

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
    # `metabrowser.inventory` was the pre-refactor singleton and no longer
    # exists, so guarding that name guards nothing. What the rule is actually
    # for is that the contract must not name a concrete provider or the
    # delivery layer.
    assert not imported_modules & {
        "starlette",
        "metabrowser.events",
        "metabrowser.inventory_engine.factory",
        "metabrowser.inventory_engine.providers.python_inventory",
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
            assert checkpoint.work.directories_read == 0
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
            for _attempt in range(_PROVIDER_PAGE_ATTEMPTS):
                after: str | None = None
                version: EngineVersion | None = None
                paths: list[str] = []
                try:
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
                except VersionUnavailableError:
                    continue
            raise AssertionError("the provider version moved during all page attempts")
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
                        DiagnosticsQuery(query_id="diagnostics"),
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
            diagnostics = cast(
                "DiagnosticsProjection",
                result.projection("diagnostics"),
            )

            assert link.presence is EntryPresence.PRESENT
            assert link.entry is not None
            assert rollup.payload is not None
            assert set(rollup.payload) == {
                "node",
                "ext_tallies",
                "file_type_breakdown",
            }
            validate_rollup_result(rollup.payload)
            assert set(navigation.payload) == {
                "summary",
                "file_type_registry",
                "extensions",
                "canonical_extensions",
                "type_families",
                "type_presets",
                "recency_tallies",
                "oldest_mtime_ns",
                "newest_mtime_ns",
            }
            rollup_node = cast("dict[str, object]", rollup.payload["node"])
            rollup_children = cast("list[dict[str, object]]", rollup_node["children"])
            navigation_summary = navigation.payload["summary"]
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
                "diagnostics": (
                    diagnostics.payload.provider,
                    diagnostics.payload.contract,
                ),
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
        "diagnostics": ("python", "inventory-provider-v1"),
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
            config=InventoryConfig(budget=DiscoveryBudget(max_files=2)),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        EntryQuery(query_id="missing", path="z.txt"),
                        DiagnosticsQuery(query_id="diagnostics"),
                    )
                )
            )
            projection = cast("EntryProjection", result.projection("missing"))
            diagnostics = cast("DiagnosticsProjection", result.projection("diagnostics"))
            (tmp_path / "a.txt").write_text("updated", encoding="utf-8")
            retained_receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="a.txt"),))
            )
            unknown_receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="z.txt"),))
            )
            return (
                result.state.phase.value,
                result.state.coverage.complete,
                result.state.coverage.reason.value if result.state.coverage.reason else None,
                tuple(issue.code.value for issue in result.state.issues),
                projection.presence.value,
                diagnostics.payload.watch_state,
                diagnostics.payload.watch_reason,
                retained_receipt.accepted_paths,
                unknown_receipt.rejected_paths,
            )
        finally:
            await handle.close()

    assert asyncio.run(run()) == (
        "stopped",
        False,
        "budget",
        ("resource_budget",),
        "unknown",
        "off",
        "resource_budget",
        ("a.txt",),
        ("z.txt",),
    )


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_directory_pages_are_lossless_when_directories_outnumber_file_budget(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    expected = {f"directory-{index}" for index in range(7)}
    for path in expected:
        (tmp_path / path).mkdir()

    async def run() -> set[str]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(
                budget=DiscoveryBudget(max_files=1),
                watch_mode="off",
            ),
        )
        try:
            seen: set[str] = set()
            after: str | None = None
            pinned: EngineVersion | None = None
            while True:
                result = await handle.read(
                    ReadRequest(
                        queries=(
                            DirectoryQuery(
                                query_id="tree",
                                max_depth=2,
                                max_rows=2,
                                after=after,
                            ),
                        ),
                        at_version=pinned,
                    )
                )
                projection = result.projection("tree")
                assert isinstance(projection, DirectoryProjection)
                pinned = result.version if pinned is None else pinned
                assert result.version == pinned
                assert not (seen & {entry.path for entry in projection.entries})
                seen.update(entry.path for entry in projection.entries)
                after = projection.next_page
                if after is None:
                    return seen
        finally:
            await handle.close()

    assert asyncio.run(run()) == expected


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_catalog_predicate_semantics_are_runtime_independent_and_exact(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for name in (".foo", "..foo", "foo.", "plain.foo"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    async def run() -> set[str]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(
                hidden_allowlist=(".foo", "..foo"),
                watch_mode="off",
            ),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        CatalogQuery(
                            query_id="catalog",
                            max_rows=10,
                            terminal_extensions=(".foo",),
                        ),
                    )
                )
            )
            projection = result.projection("catalog")
            assert isinstance(projection, CatalogProjection)
            return {record.path for record in projection.records}
        finally:
            await handle.close()

    assert asyncio.run(run()) == {"..foo", "plain.foo"}


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_catalog_pages_are_lossless_without_suffix_counts(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    expected = {f"file-{index}.txt" for index in range(7)}
    for path in expected:
        (tmp_path / path).write_text(path, encoding="utf-8")

    async def run() -> set[str]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(
                budget=DiscoveryBudget(max_files=10),
                watch_mode="off",
            ),
        )
        try:
            seen: set[str] = set()
            after: str | None = None
            pinned: EngineVersion | None = None
            while True:
                result = await handle.read(
                    ReadRequest(
                        queries=(
                            CatalogQuery(
                                query_id="catalog",
                                max_rows=2,
                                after=after,
                            ),
                        ),
                        at_version=pinned,
                    )
                )
                projection = result.projection("catalog")
                assert isinstance(projection, CatalogProjection)
                pinned = result.version if pinned is None else pinned
                assert result.version == pinned
                assert not (seen & {record.path for record in projection.records})
                seen.update(record.path for record in projection.records)
                after = projection.next_page
                if after is None:
                    return seen
        finally:
            await handle.close()

    assert asyncio.run(run()) == expected


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_applies_work_bounds_to_continuation_pages(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for index in range(6):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            for kind in (QueryKind.DIRECTORY, QueryKind.FILTERED_TREE, QueryKind.CATALOG):
                if kind is QueryKind.DIRECTORY:
                    first_query = DirectoryQuery(query_id=kind, max_depth=1, max_rows=2)
                elif kind is QueryKind.FILTERED_TREE:
                    first_query = FilteredTreeQuery(query_id=kind, max_depth=1, max_rows=2)
                else:
                    first_query = CatalogQuery(query_id=kind, max_rows=2)
                first = await handle.read(ReadRequest(queries=(first_query,)))
                first_projection = first.projection(kind)
                assert isinstance(
                    first_projection,
                    (DirectoryProjection, FilteredTreeProjection, CatalogProjection),
                )
                after = first_projection.next_page
                assert after is not None

                if kind is QueryKind.DIRECTORY:
                    limited_query = DirectoryQuery(
                        query_id=kind,
                        max_depth=1,
                        max_rows=4,
                        max_work=1,
                        after=after,
                    )
                    retry_query = DirectoryQuery(
                        query_id=kind,
                        max_depth=1,
                        max_rows=4,
                        max_work=4,
                        after=after,
                    )
                elif kind is QueryKind.FILTERED_TREE:
                    limited_query = FilteredTreeQuery(
                        query_id=kind,
                        max_depth=1,
                        max_rows=4,
                        max_work=1,
                        after=after,
                    )
                    retry_query = FilteredTreeQuery(
                        query_id=kind,
                        max_depth=1,
                        max_rows=4,
                        max_work=4,
                        after=after,
                    )
                else:
                    limited_query = CatalogQuery(
                        query_id=kind,
                        max_rows=4,
                        max_work=1,
                        after=after,
                    )
                    retry_query = CatalogQuery(
                        query_id=kind,
                        max_rows=4,
                        max_work=4,
                        after=after,
                    )

                limited = await handle.read(
                    ReadRequest(queries=(limited_query,), at_version=first.version)
                )
                assert limited.projection(kind) == QueryLimitProjection(
                    query_id=kind,
                    query_kind=kind,
                    max_work=1,
                    rows_visited=1,
                )
                assert limited.work.rows_visited == 1
                assert limited.work.rows_returned == 0

                retry = await handle.read(
                    ReadRequest(queries=(retry_query,), at_version=first.version)
                )
                assert not isinstance(retry.projection(kind), QueryLimitProjection)
                assert retry.work.rows_visited == 4
                assert retry.work.rows_returned == 4
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_returns_typed_query_limits_without_partial_answers(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for index in range(6):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        queries = (
            DirectoryQuery(query_id="directory", max_depth=1, max_work=2),
            FilteredTreeQuery(query_id="filtered", max_depth=1, max_work=2),
            RollupQuery(query_id="rollup", max_work=2),
            NavigationQuery(query_id="navigation", max_work=2),
            RecentQuery(query_id="recent", max_rows=1, as_of_ns=1, max_work=2),
            CatalogQuery(query_id="catalog", max_rows=1, max_work=2),
        )
        try:
            result = await handle.read(ReadRequest(queries=queries))
            for query in queries:
                projection = result.projection(query.query_id)
                assert projection == QueryLimitProjection(
                    query_id=query.query_id,
                    query_kind=query.kind,
                    max_work=2,
                    rows_visited=2,
                )
            assert result.work.rows_visited == 12
            assert result.work.rows_returned == 0
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_counts_are_exact_or_proven_lower_bounds(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for index in range(8):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        RecentQuery(
                            query_id="recent",
                            max_rows=2,
                            as_of_ns=1,
                            count_cap=3,
                        ),
                        CatalogQuery(query_id="catalog", max_rows=2, count_cap=3),
                    )
                )
            )
            recent = result.projection("recent")
            catalog = result.projection("catalog")
            assert isinstance(recent, RecentProjection)
            assert isinstance(catalog, CatalogProjection)
            assert recent.total_matches == CountResult(CountKind.AT_LEAST, 3)
            assert catalog.total_matches == CountResult(CountKind.AT_LEAST, 3)
            assert catalog.next_page is not None
            tail = await handle.read(
                ReadRequest(
                    queries=(
                        CatalogQuery(
                            query_id="catalog",
                            max_rows=6,
                            count_cap=3,
                            after=catalog.next_page,
                        ),
                    ),
                    at_version=result.version,
                )
            )
            tail_catalog = tail.projection("catalog")
            assert isinstance(tail_catalog, CatalogProjection)
            assert tail_catalog.total_matches == CountResult(CountKind.AT_LEAST, 8)
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_uses_canonical_portable_row_order(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for name in ("é-dir", "A-dir"):
        (tmp_path / name).mkdir()
    for name in ("中.txt", "z.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    async def run() -> tuple[tuple[str, ...], tuple[str, ...]]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        DirectoryQuery(query_id="directory", max_depth=1),
                        CatalogQuery(query_id="catalog", max_rows=10),
                    )
                )
            )
            directory = result.projection("directory")
            catalog = result.projection("catalog")
            assert isinstance(directory, DirectoryProjection)
            assert isinstance(catalog, CatalogProjection)
            assert directory.portable_issue is None
            assert catalog.portable_issue is None
            return (
                tuple(entry.path for entry in directory.entries),
                tuple(record.path for record in catalog.records),
            )
        finally:
            await handle.close()

    directory_paths, catalog_paths = asyncio.run(run())
    assert directory_paths == ("A-dir", "é-dir", "z.txt", "中.txt")
    assert catalog_paths == ("z.txt", "中.txt")


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_version_pins_fail_instead_of_moving(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            pinned = await handle.read(ReadRequest())
            (tmp_path / "later.txt").write_text("later", encoding="utf-8")
            receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="later.txt"),))
            )
            assert receipt.accepted_paths == ("later.txt",)
            assert receipt.version.session == pinned.version.session
            assert receipt.version.sequence > pinned.version.sequence
            with pytest.raises(VersionUnavailableError):
                await handle.read(ReadRequest(at_version=pinned.version))
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_changes_resume_and_report_history_gaps_as_reset(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(change_queue_size=1, watch_mode="off"),
        )
        try:
            initial = await handle.read(ReadRequest())
            (tmp_path / "first.txt").write_text("first", encoding="utf-8")
            await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="first.txt"),))
            )
            first_stream = cast(
                "AsyncGenerator[ChangeBatch, None]",
                handle.changes(after=initial.cursor),
            )
            first = await asyncio.wait_for(anext(first_stream), timeout=1)
            assert first.reset is False
            assert "first.txt" in first.dirty_paths
            assert first.cursor.session == initial.cursor.session
            await first_stream.aclose()

            (tmp_path / "second.txt").write_text("second", encoding="utf-8")
            await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="second.txt"),))
            )
            resumed_stream = cast(
                "AsyncGenerator[ChangeBatch, None]",
                handle.changes(after=first.cursor),
            )
            resumed = await asyncio.wait_for(anext(resumed_stream), timeout=1)
            assert resumed.reset is False
            assert "second.txt" in resumed.dirty_paths
            await resumed_stream.aclose()

            gap_stream = cast(
                "AsyncGenerator[ChangeBatch, None]",
                handle.changes(after=initial.cursor),
            )
            gap = await asyncio.wait_for(anext(gap_stream), timeout=1)
            assert gap.reset is True
            assert gap.cursor.session == initial.cursor.session
            assert gap.cursor.sequence >= resumed.cursor.sequence
            await gap_stream.aclose()
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_allows_only_one_active_change_iterator(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        first_stream: AsyncGenerator[ChangeBatch, None] | None = None
        try:
            checkpoint = await handle.read(ReadRequest())
            first_stream = cast(
                "AsyncGenerator[ChangeBatch, None]",
                handle.changes(after=checkpoint.cursor),
            )
            first_change = asyncio.ensure_future(anext(first_stream))
            await asyncio.sleep(0)

            second_stream = handle.changes(after=checkpoint.cursor)
            with pytest.raises(ChangeStreamBusyError):
                await anext(second_stream)

            (tmp_path / "changed.txt").write_text("changed", encoding="utf-8")
            await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="changed.txt"),))
            )
            assert (await asyncio.wait_for(first_change, timeout=1)).reset is False
        finally:
            if first_stream is not None:
                await first_stream.aclose()
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_refresh_verifies_the_filesystem_instead_of_trusting_the_hint(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            (tmp_path / "observed.txt").write_text("present", encoding="utf-8")
            (tmp_path / "also-observed.txt").write_text("also present", encoding="utf-8")
            receipt = await handle.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="observed.txt",
                            kind=ObservationKind.DELETED,
                        ),
                        RefreshObservation(
                            path="also-observed.txt",
                            kind=ObservationKind.DELETED,
                        ),
                    )
                )
            )
            assert receipt.accepted_paths == ("observed.txt", "also-observed.txt")
            result = await handle.read(
                ReadRequest(
                    queries=(
                        EntryQuery(query_id="observed", path="observed.txt"),
                        EntryQuery(query_id="also-observed", path="also-observed.txt"),
                    )
                )
            )
            assert result.version == receipt.version
            for query_id in ("observed", "also-observed"):
                projection = result.projection(query_id)
                assert isinstance(projection, EntryProjection)
                assert projection.presence is EntryPresence.PRESENT
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_close_joins_change_delivery_and_is_idempotent(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    async def run() -> None:
        handle = await _open_settled_provider(provider_factory, tmp_path)
        checkpoint = await handle.read(ReadRequest())
        stream = handle.changes(after=checkpoint.cursor)
        waiting = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0)
        await asyncio.gather(handle.close(), handle.close())

        async def wait_for_stream_end() -> None:
            try:
                await waiting
            except StopAsyncIteration:
                return
            async for _queued_batch in stream:
                pass

        await asyncio.wait_for(wait_for_stream_end(), timeout=1)
        with pytest.raises(InventoryClosedError):
            await handle.read(ReadRequest())

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session(
    provider_factory: Callable[[], InventoryBackend],
    tmp_path: Path,
) -> None:
    for index in range(50):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    async def run() -> None:
        handle = await provider_factory().open(
            tmp_path,
            InventoryConfig(watch_mode="off"),
        )
        try:
            phases: list[LifecyclePhase] = []
            sessions: set[str] = set()
            for _attempt in range(500):
                result = await handle.read(ReadRequest())
                sessions.add(result.version.session)
                if not phases or result.state.phase is not phases[-1]:
                    phases.append(result.state.phase)
                if result.state.phase in {LifecyclePhase.READY, LifecyclePhase.FAILED}:
                    break
                await asyncio.sleep(0.005)
            assert phases[-1] is LifecyclePhase.READY
            assert len(sessions) == 1
            for before, after in itertools.pairwise(phases):
                assert after in ALLOWED_PHASE_TRANSITIONS[before]
        finally:
            await handle.close()

    asyncio.run(run())
