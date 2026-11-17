"""Contract-level tests for pluggable inventory providers."""

from __future__ import annotations

import ast
import asyncio
import inspect
import itertools
import os
import re
import shutil
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from metabrowser.file_type_registry import load_file_type_registry_document
from metabrowser.inventory_engine.contract import (
    ALLOWED_PHASE_TRANSITIONS,
    DEFAULT_QUERY_MAX_WORK,
    MAX_ASSEMBLED_ROWS,
    MAX_COMMAND_PATHS,
    MAX_COUNT_CAP,
    MAX_INVENTORY_ISSUES,
    MAX_ISSUE_DETAIL_BYTES,
    MAX_TREE_GROUPS,
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
    GroupedTreeProjection,
    GroupedTreeQuery,
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
    PriorityRequest,
    ProjectionResult,
    QueryKind,
    QueryLimitProjection,
    QueryWorkLimitError,
    ReadRequest,
    ReadResult,
    RecentProjection,
    RecentQuery,
    RecentRecord,
    RefreshObservation,
    RefreshReceipt,
    RefreshRequest,
    RollupProjection,
    RollupQuery,
    SourceKind,
    TreeGroupFilter,
    TreeGroupProjection,
    VersionUnavailableError,
    WorkCounters,
    canonical_inventory_name,
    canonical_inventory_path,
    catalog_terminal_suffix,
    inventory_scope_fingerprint,
    native_inventory_name,
    require_canonical_inventory_path,
)
from metabrowser.inventory_engine.factory import InventoryProvider, create_inventory_backend
from metabrowser.inventory_engine.seams import DiscoveryGate, ProviderSeams
from metabrowser.wire_models import validate_rollup_result
from tests.inventory_harness import selected_inventory_provider
from tests.perturbed_provider import Perturbation, PerturbedBackend

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE_DOC = REPO_ROOT / "docs/project/architecture/arch-inventory-provider.md"
RESEARCH_DOC = REPO_ROOT / "docs/project/research/research-2026-11-17-fdu-backend-revisited.md"
GOLDEN_DIR = REPO_ROOT / "tests/golden"
# The statuses the architecture document's decisions table defines; an open one links
# the proposal that asks fdu to agree.
_FDU_PROPOSAL = "[jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)"
_DECISION_STATUSES = frozenset(
    {
        "Decided",
        "Method decided; values pending measurement",
        f"Intent decided; profile open, pending fdu ({_FDU_PROPOSAL})",
        f"Open, pending fdu ({_FDU_PROPOSAL})",
    }
)
# Bound transient watcher churn so this conformance case cannot hang.
_PROVIDER_PAGE_ATTEMPTS = 3

EXPECTED_QUERIES = {
    "entry": EntryQuery,
    "directory": DirectoryQuery,
    "filtered_tree": FilteredTreeQuery,
    "grouped_tree": GroupedTreeQuery,
    "rollup": RollupQuery,
    "navigation": NavigationQuery,
    "recent": RecentQuery,
    "catalog": CatalogQuery,
    "diagnostics": DiagnosticsQuery,
}

# The provider `METABROWSER_INVENTORY_PROVIDER` selects, built by the sealed factory, so
# the registry below runs against any shipped provider by setting that variable.
SELECTED_PROVIDER = selected_inventory_provider()


class ProviderFactory(Protocol):
    """Build one backend, passing the test seams a case asks for."""

    def __call__(self, *, seams: ProviderSeams | None = None) -> InventoryBackend: ...


def _selected_provider(*, seams: ProviderSeams | None = None) -> InventoryBackend:
    return create_inventory_backend(SELECTED_PROVIDER, seams=seams)


def _perturbed_provider(perturbation: Perturbation) -> ProviderFactory:
    def factory(*, seams: ProviderSeams | None = None) -> InventoryBackend:
        return PerturbedBackend(_selected_provider(seams=seams), perturbation)

    return factory


# The registry also runs against the selected provider behind `tests/perturbed_provider.py`,
# which changes only what the contract leaves to a provider: its name in diagnostics, and,
# in the second wrapping, its commit granularity, each data batch preceded by a state-only
# batch at a version of its own. A case that passes unwrapped and fails wrapped pins the
# provider's identity or granularity rather than the contract.
PROVIDER_FACTORIES: tuple[Any, ...] = (
    pytest.param(_selected_provider, id=SELECTED_PROVIDER.value),
    pytest.param(
        _perturbed_provider(Perturbation(provider_name="renamed")),
        id=f"{SELECTED_PROVIDER.value}-renamed",
    ),
    pytest.param(
        _perturbed_provider(Perturbation(provider_name="renamed", split_batches=True)),
        id=f"{SELECTED_PROVIDER.value}-renamed-split",
    ),
)
# Settled and serving: discovery has ended and nothing stopped or failed. Which of the two a
# provider reports depends on whether it has a live observer.
_SERVING_PHASES = frozenset({LifecyclePhase.READY, LifecyclePhase.WATCHING})
# Directory and filtered-tree pages, whose per-page work budget may be soft (D6); every
# other kind refuses at its work bound.
_TREE_KINDS = frozenset({QueryKind.DIRECTORY, QueryKind.FILTERED_TREE})

PROVIDER_CONFORMANCE_TESTS = frozenset(
    {
        "test_checkpoint_read_returns_only_a_coherent_constant_work_envelope",
        "test_paged_time_dependent_reads_reuse_one_as_of",
        "test_provider_semantic_digest",
        "test_provider_derives_registry_identity_from_supplied_content",
        "test_provider_uses_supplied_registry_content_for_classification",
        "test_provider_budget_stop_is_explicit_and_absence_remains_unknown",
        "test_provider_budget_counts_regular_files_and_stops_when_they_reach_it",
        "test_provider_counts_the_root_among_indexed_directories",
        "test_directory_pages_are_lossless_when_directories_outnumber_file_budget",
        "test_filtered_tree_and_recent_share_filter_semantics_before_caps",
        "test_grouped_tree_answers_each_group_as_its_filtered_tree",
        "test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks",
        "test_catalog_predicate_semantics_are_runtime_independent_and_exact",
        "test_catalog_pages_are_lossless_without_suffix_counts",
        "test_provider_applies_work_bounds_to_continuation_pages",
        "test_provider_returns_typed_query_limits_without_partial_answers",
        "test_provider_counts_are_exact_or_proven_lower_bounds",
        "test_provider_uses_canonical_portable_row_order",
        "test_provider_version_pins_fail_instead_of_moving",
        "test_provider_changes_resume_and_report_history_gaps_as_reset",
        "test_provider_dirty_paths_name_every_ancestor_whose_aggregates_changed",
        "test_provider_directory_times_are_their_newest_regular_file",
        "test_provider_answers_an_unlisted_directory_with_an_empty_final_page",
        "test_provider_allows_only_one_active_change_iterator",
        "test_provider_refresh_verifies_the_filesystem_instead_of_trusting_the_hint",
        "test_provider_change_stream_reaches_every_refresh_receipt_version",
        "test_provider_close_joins_change_delivery_and_is_idempotent",
        "test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session",
    }
)


async def _open_settled_provider(
    factory: ProviderFactory,
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


def _is_factory_parametrized(test: object) -> bool:
    return any(
        mark.name == "parametrize" and mark.args and mark.args[0] == "provider_factory"
        for mark in getattr(test, "pytestmark", ())
    )


def _documented_conformance_cases(document: str) -> set[str]:
    """The test names the architecture document's conformance table lists."""

    _before, _heading, section = document.partition("\n## Provider Conformance Registry\n")
    table, _next, _rest = section.partition("\n## ")
    return {
        line.removeprefix("| `").removesuffix("` |")
        for line in table.splitlines()
        if line.startswith("| `test_") and line.endswith("` |")
    }


def test_architecture_document_registers_every_provider_conformance_case() -> None:
    """The registry, the factory-parametrized cases, and the document's table agree.

    In both directions: a case parametrized over the provider factories but missing
    from the registry would run against every provider without being part of the
    adoption gate the document states, which is how one case once went unregistered.
    """

    document = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for test_name in PROVIDER_CONFORMANCE_TESTS:
        assert test_name in globals(), f"missing provider conformance test: {test_name}"
        assert _is_factory_parametrized(globals()[test_name]), (
            f"provider conformance test is not factory-parametrized: {test_name}"
        )
    parametrized = {
        name
        for name, value in globals().items()
        if name.startswith("test_") and _is_factory_parametrized(value)
    }
    assert parametrized - PROVIDER_CONFORMANCE_TESTS == set(), "unregistered conformance cases"
    assert _documented_conformance_cases(document) == PROVIDER_CONFORMANCE_TESTS


def _decision_rows(document: str, heading: str) -> list[tuple[str, ...]]:
    """The cells of each `D<n>` row in the table under *heading*, up to the next heading."""

    lines = document.splitlines()
    rows: list[tuple[str, ...]] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("#"):
            break
        if line.startswith("| D"):
            rows.append(tuple(cell.strip() for cell in line.strip().strip("|").split(" | ")))
    return rows


def test_architecture_document_records_every_decision() -> None:
    """The decisions table records each decision the research names, once and in order.

    Each row has one of the statuses the document defines, so every open one links the
    fdu proposal, and every test or test module the table names exists, so renaming one
    cannot leave a decision held by nothing.
    """

    research = _decision_rows(
        RESEARCH_DOC.read_text(encoding="utf-8"), "### Decisions Needed Before Parity Runs"
    )
    recorded = _decision_rows(
        ARCHITECTURE_DOC.read_text(encoding="utf-8"), "## Decisions for a Second Provider"
    )
    assert [row[0] for row in recorded] == [row[0] for row in research]
    test_sources = [path.read_text(encoding="utf-8") for path in (REPO_ROOT / "tests").glob("*.py")]
    defined = {
        name
        for source in test_sources
        for name in re.findall(r"^\s*(?:async )?def (test_\w+)\(", source, flags=re.MULTILINE)
    }
    for row in recorded:
        decision, _rule, status, held_by = row
        assert status in _DECISION_STATUSES, (decision, status)
        named_tests = set(re.findall(r"`(test_\w+)`", held_by))
        assert named_tests <= defined, (decision, named_tests - defined)
        for module in re.findall(r"`(tests/[\w/.-]+\.py)`", held_by):
            assert (REPO_ROOT / module).is_file(), (decision, module)


def _provider_pin_golden(provider: InventoryProvider) -> Path:
    return GOLDEN_DIR / f"cli-api-provider-{provider.value}.tryscript.md"


def test_each_shipped_provider_has_the_one_golden_that_pins_its_name() -> None:
    """The goldens match the provider as `[PROVIDER]`, so they pass against any provider.

    That leaves each name to one transcript per provider, which selects it and pins it.
    A literal name anywhere else would fail every run against another provider for a
    difference that is not a defect.
    """

    for provider in InventoryProvider:
        text = _provider_pin_golden(provider).read_text(encoding="utf-8")
        assert f'  METABROWSER_INVENTORY_PROVIDER: "{provider.value}"\n' in text
        assert f'  "provider": "{provider.value}",\n' in text
    pins = {_provider_pin_golden(provider) for provider in InventoryProvider}
    for path in sorted(GOLDEN_DIR.glob("*.tryscript.md")):
        if path in pins:
            continue
        text = path.read_text(encoding="utf-8")
        for provider in InventoryProvider:
            for literal in (f'"provider": "{provider.value}"', f'"provider":"{provider.value}"'):
                assert literal not in text, f"{path.name} pins {literal}; match [PROVIDER]"


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


def test_recent_filter_uses_the_query_observation_time() -> None:
    assert RecentQuery(query_id="default", max_rows=1, as_of_ns=1).filter == InventoryFilter(
        include_ignored=False
    )
    selection = InventoryFilter(recency_seconds=10, as_of_ns=2)
    assert (
        RecentQuery(
            query_id="recent",
            max_rows=1,
            as_of_ns=2,
            filter=selection,
        ).filter
        is selection
    )
    with pytest.raises(ValueError, match="filter as_of_ns must match"):
        RecentQuery(
            query_id="recent",
            max_rows=1,
            as_of_ns=1,
            filter=selection,
        )


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
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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
        RecentRecord(path=path, ext="", size=0, mtime_ns=0)
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


def test_the_canonical_path_is_total_and_injective() -> None:
    """Every name has a canonical form, and two names never collide on one.

    This replaced a contract in which a provider could report that some entries had no
    canonical form, with an omission count and bounded escaped examples, leaving the
    consumer to treat a directory as two populations. Totality removes the second
    population rather than describing it.
    """

    undecodable = b"x\xff.txt".decode("utf-8", "surrogateescape")
    assert canonical_inventory_name(undecodable) == "x%FF.txt"
    assert canonical_inventory_name("README.md") == "README.md"

    # `%` escapes too, or `x%FF.txt` on disk and the escape of `x\xff.txt` would be one
    # string, and the page could not say which file a row came from.
    assert canonical_inventory_name("x%FF.txt") == "x%25FF.txt"
    assert canonical_inventory_name(undecodable) != canonical_inventory_name("x%FF.txt")

    assert canonical_inventory_path(f"a/{undecodable}/b") == "a/x%FF.txt/b"

    # The point of escaping: the result is orderable. The raw name is not, because
    # encoding a surrogate as UTF-8 raises, so one such file made a whole directory
    # unlistable.
    assert canonical_inventory_name(undecodable).encode("utf-8") == b"x%FF.txt"
    with pytest.raises(UnicodeEncodeError):
        undecodable.encode("utf-8")

    # A canonical path is the escaped form, so the boundary rejects a raw platform name
    # rather than accepting one and ordering it inconsistently later.
    with pytest.raises(ValueError, match="escaped"):
        require_canonical_inventory_path(undecodable, "path", allow_root=False)
    require_canonical_inventory_path(
        canonical_inventory_name(undecodable), "path", allow_root=False
    )


def test_the_walker_escapes_on_the_way_in_and_the_boundary_passes_through() -> None:
    """The store keys the canonical identity; the read boundary has no encoding left.

    This is the reverse of the arrangement it replaced, where the store held raw platform
    names and the boundary escaped three fields of every row of every read. Escaping once
    per entry, in the walker, costs strictly less -- and, the reason it changed, it makes
    the store's keys the same strings the contract's queries carry, so an inbound lookup
    cannot silently miss the entry it names.

    Synthesised rather than written to disk, because APFS rejects a filename that is not
    valid UTF-8, so the case this covers cannot be created on the machine that most often
    runs these tests. It is reachable on Linux, which is where it would otherwise be found
    the hard way.
    """

    from metabrowser.inventory_engine.providers.python_inventory import (
        FsEntry,
        _semantic_entry,
    )

    undecodable = b"x\xff.txt".decode("utf-8", "surrogateescape")
    canonical = canonical_inventory_name(undecodable)
    assert canonical == "x%FF.txt"

    # What the walker stores, having escaped the name it got from `scandir`.
    stored = FsEntry(
        path=f"src/{canonical}",
        parent="src",
        name=canonical,
        type="file",
        ext=".txt",
        kind="file",
        size=1,
        mtime_ns=1,
        mtime_hash="",
        active=False,
    )

    row = _semantic_entry(stored)
    assert row.path == "src/x%FF.txt"
    assert row.name == "x%FF.txt"
    assert row.parent == "src"

    # Pass-through, not a second escape: escaping an already-canonical name again would
    # publish `x%25FF.txt`, an identity that names nothing.
    assert row.path is stored.path
    assert row.name is stored.name

    # And the identity inverts back to the platform name the filesystem answers to.
    assert native_inventory_name(row.name) == undecodable


def test_a_percent_in_a_filename_round_trips_through_the_identity() -> None:
    """A literal `%` is the plain-ASCII case that made the escape need an inverse.

    `report%20final.txt` is what a URL-derived download is called. It escapes to
    `report%2520final.txt`, and without an inverse that identity resolved to nothing:
    the folder listed, the entry expanded empty, and a refresh receipt reported
    `accepted` for a path it could not verify.
    """

    native = "report%20final.txt"
    canonical = canonical_inventory_name(native)
    assert canonical == "report%2520final.txt"
    assert native_inventory_name(canonical) == native

    # A tree may genuinely hold a file *named* `%41`. Its identity is `%2541`, so the
    # bare `%41` is not in the image of the escaper and must resolve to nothing rather
    # than to that file.
    assert canonical_inventory_name("%41") == "%2541"
    assert native_inventory_name("%41") is None


def test_lifecycle_issue_lists_are_bounded() -> None:
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
    with pytest.raises(ValueError, match="must also be dirty paths"):
        ChangeBatch(
            version=version,
            cursor=cursor,
            state=state,
            non_file_paths=("changed",),
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
    provider_factory: ProviderFactory,
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
            # Any settled serving phase: whether the observer is live is the provider's.
            assert checkpoint.state.phase in _SERVING_PHASES
            assert checkpoint.work.entries_visited == 0
            assert checkpoint.work.directories_read == 0
            assert checkpoint.work.rows_returned == 0
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_paged_time_dependent_reads_reuse_one_as_of(
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """Every provider must produce the same normalized filesystem semantics.

    The digest holds filesystem facts, not who answered: the provider's name and whether
    its observer is live are its own, and the Python provider's are pinned in
    `tests/test_python_inventory_provider.py`.
    """

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
                            filter=InventoryFilter(include_ignored=True),
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
            assert result.state.phase in _SERVING_PHASES
            assert diagnostics.payload.provider
            return {
                "state": (
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
                "contract": diagnostics.payload.contract,
            }
        finally:
            await handle.close()

    actual = asyncio.run(run())
    expected = {
        "state": (True, "fresh", "scanned"),
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
        "contract": "inventory-provider-v1",
    }
    assert actual == expected, actual


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_budget_stop_is_explicit_and_absence_remains_unknown(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """At its budget a provider stops, and what it did not reach stays unknown.

    The phase is `stopped`, coverage is partial for the budget, the state carries a
    `resource_budget` issue, exactly `max_files` regular files are readable, and every
    other path answers `unknown`, never `absent`. Which files a stop admits is
    unspecified (D17), so this reads them back rather than naming them; the Python
    store's are pinned in `tests/test_python_inventory_provider.py`. Refresh still
    verifies an admitted file and rejects one discovery never reached.
    """

    names = ("a.txt", "b.txt", "c.txt", "d.txt", "z.txt")
    max_files = 2
    for name in names:
        (tmp_path / name).write_text(name, encoding="utf-8")

    async def run() -> tuple[
        IndexState, set[str], int, dict[str, EntryPresence], RefreshReceipt, RefreshReceipt
    ]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(budget=DiscoveryBudget(max_files=max_files)),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        CatalogQuery(query_id="catalog", max_rows=len(names), include_ignored=True),
                        DiagnosticsQuery(query_id="diagnostics"),
                        *(EntryQuery(query_id=name, path=name) for name in names),
                    )
                )
            )
            catalog = cast("CatalogProjection", result.projection("catalog"))
            diagnostics = cast("DiagnosticsProjection", result.projection("diagnostics"))
            admitted = {record.path for record in catalog.records}
            presence = {
                name: cast("EntryProjection", result.projection(name)).presence for name in names
            }
            retained, unreached = min(admitted), min(set(names) - admitted)
            (tmp_path / retained).write_text("updated", encoding="utf-8")
            retained_receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path=retained),))
            )
            unreached_receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path=unreached),))
            )
            return (
                result.state,
                admitted,
                diagnostics.payload.files_indexed,
                presence,
                retained_receipt,
                unreached_receipt,
            )
        finally:
            await handle.close()

    state, admitted, files_indexed, presence, retained, unreached = asyncio.run(run())
    assert state.phase is LifecyclePhase.STOPPED
    assert state.coverage == Coverage(complete=False, reason=CoverageReason.BUDGET)
    assert IssueCode.RESOURCE_BUDGET in {issue.code for issue in state.issues}
    assert len(admitted) == files_indexed == max_files
    assert admitted <= set(names)
    assert presence == {
        name: EntryPresence.PRESENT if name in admitted else EntryPresence.UNKNOWN for name in names
    }
    assert (retained.accepted_paths, retained.rejected_paths) == ((min(admitted),), ())
    assert (unreached.accepted_paths, unreached.rejected_paths) == (
        (),
        (min(set(names) - admitted),),
    )


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_budget_counts_regular_files_and_stops_when_they_reach_it(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """Only regular files count against `max_files`, and reaching it is the stop.

    So a tree holding exactly `max_files` regular files reports a budget stop although
    discovery left nothing out, and the same tree under one more file of budget is
    complete. Directories and symlinks never count.
    """

    (tmp_path / "sub").mkdir()
    (tmp_path / "empty").mkdir()
    for path in ("a.txt", "sub/b.txt", "sub/c.txt"):
        (tmp_path / path).write_text(path, encoding="utf-8")
    try:
        (tmp_path / "link").symlink_to("a.txt")
    except OSError as error:  # pragma: no cover - unsupported Windows policy
        pytest.skip(f"symlinks are unavailable: {error}")

    async def run(max_files: int) -> tuple[IndexState, int, int]:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(budget=DiscoveryBudget(max_files=max_files), watch_mode="off"),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        DiagnosticsQuery(query_id="diagnostics"),
                        CatalogQuery(query_id="catalog", max_rows=10, include_ignored=True),
                    )
                )
            )
            diagnostics = cast("DiagnosticsProjection", result.projection("diagnostics"))
            catalog = cast("CatalogProjection", result.projection("catalog"))
            return result.state, diagnostics.payload.files_indexed, len(catalog.records)
        finally:
            await handle.close()

    at_budget, at_files, at_rows = asyncio.run(run(3))
    assert at_budget.phase is LifecyclePhase.STOPPED
    assert at_budget.coverage == Coverage(complete=False, reason=CoverageReason.BUDGET)
    assert IssueCode.RESOURCE_BUDGET in {issue.code for issue in at_budget.issues}
    assert at_files == at_rows == 3

    within, within_files, within_rows = asyncio.run(run(4))
    assert within.phase in _SERVING_PHASES
    assert within.coverage == Coverage(complete=True)
    assert IssueCode.RESOURCE_BUDGET not in {issue.code for issue in within.issues}
    assert within_files == within_rows == 3


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_counts_the_root_among_indexed_directories(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """`directories_indexed` counts every directory in scope, the served root included,
    and `files_indexed` counts regular files only; out-of-scope entries count as neither."""

    for directory in ("a/b", "empty", ".hidden"):
        (tmp_path / directory).mkdir(parents=True)
    for path in ("x.txt", "a/y.txt", "a/b/z.txt", ".hidden/secret.txt"):
        (tmp_path / path).write_text(path, encoding="utf-8")
    try:
        (tmp_path / "link").symlink_to("x.txt")
    except OSError as error:  # pragma: no cover - unsupported Windows policy
        pytest.skip(f"symlinks are unavailable: {error}")

    async def run() -> tuple[int, int]:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        try:
            result = await handle.read(
                ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),))
            )
            diagnostics = cast("DiagnosticsProjection", result.projection("diagnostics"))
            return diagnostics.payload.directories_indexed, diagnostics.payload.files_indexed
        finally:
            await handle.close()

    # The root, `a`, `a/b`, and `empty`; `.hidden` is outside the scope.
    assert asyncio.run(run()) == (4, 3)


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_directory_pages_are_lossless_when_directories_outnumber_file_budget(
    provider_factory: ProviderFactory,
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
def test_filtered_tree_and_recent_share_filter_semantics_before_caps(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """Both projections apply the shared file predicates to the full population."""

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("scope/ignored/\n", encoding="utf-8")
    scope = tmp_path / "scope"
    scope.mkdir()
    ignored = scope / "ignored"
    ignored.mkdir()

    files = {
        "00-wrong.txt": (b"wrong type", 99_000_000_000),
        "01-too-small.js": (b"tiny", 98_000_000_000),
        "02-too-old.js": (b"old enough", 89_000_000_000),
        "10-current.js": (b"exact", 91_000_000_000),
        "20-bundle.min.js": (b"compound", 92_000_000_000),
        "README": (b"basename", 93_000_000_000),
    }
    for name, (content, mtime_ns) in files.items():
        path = scope / name
        path.write_bytes(content)
        os.utime(path, ns=(mtime_ns, mtime_ns))
    ignored_path = ignored / "newest.js"
    ignored_path.write_bytes(b"ignored")
    os.utime(ignored_path, ns=(100_000_000_000, 100_000_000_000))

    as_of_ns = 100_000_000_000
    expected = {
        "scope/10-current.js",
        "scope/20-bundle.min.js",
        "scope/README",
    }

    async def run() -> tuple[FilteredTreeProjection, RecentProjection]:
        selection = InventoryFilter(
            extensions=(".JS",),
            filenames=("readme",),
            recency_seconds=10,
            minimum_size=5,
            include_ignored=False,
            as_of_ns=as_of_ns,
        )
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=(
                        FilteredTreeQuery(
                            query_id="filtered",
                            path="scope",
                            max_depth=2,
                            max_rows=len(expected),
                            filter=selection,
                        ),
                        RecentQuery(
                            query_id="recent",
                            prefix="scope/",
                            max_rows=len(expected),
                            count_cap=len(expected),
                            as_of_ns=as_of_ns,
                            filter=selection,
                        ),
                    )
                )
            )
            filtered = result.projection("filtered")
            recent = result.projection("recent")
            assert isinstance(filtered, FilteredTreeProjection)
            assert isinstance(recent, RecentProjection)
            return filtered, recent
        finally:
            await handle.close()

    filtered, recent = asyncio.run(run())
    filtered_paths = {entry.path for entry in filtered.entries if entry.type is EntryType.FILE}
    recent_paths = {entry.path for entry in recent.entries}
    assert filtered_paths == recent_paths == expected
    assert (filtered.matching_leaves, filtered.matching_files, filtered.matching_bytes) == (
        3,
        3,
        21,
    )
    assert filtered.next_page is None
    assert recent.total_matches == CountResult(CountKind.EXACT, 3)


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_catalog_predicate_semantics_are_runtime_independent_and_exact(
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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


type _PageQuery = DirectoryQuery | FilteredTreeQuery | CatalogQuery
type _Page = DirectoryProjection | FilteredTreeProjection | CatalogProjection


def _page_rows(page: _Page) -> tuple[InventoryEntry | CatalogRecord, ...]:
    return page.records if isinstance(page, CatalogProjection) else page.entries


async def _assemble_pages(
    handle: InventoryHandle,
    query: _PageQuery,
    first: _Page,
    version: EngineVersion,
    *,
    max_pages: int,
) -> list[InventoryEntry | CatalogRecord]:
    """Every row *first* and its continuations hold at *version*, under *query*'s bound.

    A page the bound refuses must leave its continuation usable, so the same token is
    retried at the same version with the default bound. A page the bound lets through
    must make progress and report the work it did: at least the rows it returned and,
    for any kind but a tree's, whose budget may be soft (D6), at most its bound. The
    walk must end within *max_pages*.
    """

    rows: list[InventoryEntry | CatalogRecord] = list(_page_rows(first))
    after = first.next_page
    for _page in range(max_pages):
        if after is None:
            return rows
        bounded = replace(query, after=after)
        result = await handle.read(ReadRequest(queries=(bounded,), at_version=version))
        page = result.projection(query.query_id)
        if isinstance(page, QueryLimitProjection):
            assert (page.query_kind, page.max_work) == (query.kind, query.max_work)
            assert result.work.rows_returned == 0
            bounded = replace(query, after=after, max_work=DEFAULT_QUERY_MAX_WORK)
            result = await handle.read(ReadRequest(queries=(bounded,), at_version=version))
            page = result.projection(query.query_id)
            assert not isinstance(page, QueryLimitProjection), "a typed limit consumed its page"
        assert isinstance(page, (DirectoryProjection, FilteredTreeProjection, CatalogProjection))
        page_rows = _page_rows(page)
        assert page_rows or page.next_page is None, "a page made no progress"
        assert result.work.rows_returned == len(page_rows)
        assert len(page_rows) <= result.work.rows_visited
        if query.kind not in _TREE_KINDS:
            assert result.work.rows_visited <= bounded.max_work, "a page passed its bound"
        rows.extend(page_rows)
        after = page.next_page
    raise AssertionError(f"the pages did not end within {max_pages}")


def _page_query(kind: QueryKind, query_id: str, **bounds: Any) -> _PageQuery:
    if kind is QueryKind.DIRECTORY:
        return DirectoryQuery(query_id=query_id, max_depth=1, **bounds)
    if kind is QueryKind.FILTERED_TREE:
        return FilteredTreeQuery(query_id=query_id, max_depth=1, **bounds)
    return CatalogQuery(query_id=query_id, **bounds)


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_applies_work_bounds_to_continuation_pages(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A continuation page carries its own work bound, and a refusal does not consume it.

    Under a bound too small for the page, a catalog page answers the typed limit and a
    tree page either does or, under a soft budget (D6, open pending fdu), makes progress.
    A typed limit leaves the continuation usable, so the same token at the same version
    succeeds with an adequate bound. However the pages fall, they end and assemble the
    unpaged answer. The Python store's exact charges are in
    `tests/test_python_inventory_provider.py`.
    """

    files = 6
    for index in range(files):
        (tmp_path / f"file-{index}.txt").write_text(str(index), encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            tmp_path,
            config=InventoryConfig(watch_mode="off"),
        )
        try:
            for kind in (QueryKind.DIRECTORY, QueryKind.FILTERED_TREE, QueryKind.CATALOG):
                first_query = _page_query(kind, kind, max_rows=2)
                whole_query = _page_query(kind, f"{kind}-whole", max_rows=100)
                first = await handle.read(ReadRequest(queries=(first_query, whole_query)))
                first_page = first.projection(kind)
                whole = first.projection(f"{kind}-whole")
                assert isinstance(
                    first_page, (DirectoryProjection, FilteredTreeProjection, CatalogProjection)
                )
                assert isinstance(
                    whole, (DirectoryProjection, FilteredTreeProjection, CatalogProjection)
                )
                assert whole.next_page is None
                assert first_page.next_page is not None
                rows = await _assemble_pages(
                    handle,
                    _page_query(kind, kind, max_rows=4, max_work=1),
                    first_page,
                    first.version,
                    max_pages=files + 1,
                )
                assert rows == list(_page_rows(whole)), kind
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_returns_typed_query_limits_without_partial_answers(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A query that cannot finish within `max_work` answers the typed limit, never a
    partial value of its ordinary type.

    Rollup, navigation, recent, and catalog must refuse here, because each needs every
    one of six files and its bound is two. A directory or filtered tree may instead
    answer a page that makes progress under a soft budget (D6, open pending fdu), and
    its pages then assemble the unpaged answer. The read reports the work it did, at
    least what its refusals charged and at most what its queries could visit. The Python
    store's hard tree limit and its exact charges are in
    `tests/test_python_inventory_provider.py`.
    """

    files = 6
    for index in range(files):
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
            charged = 0
            returned = 0
            for query in queries:
                projection = result.projection(query.query_id)
                if isinstance(projection, QueryLimitProjection):
                    assert (projection.query_kind, projection.max_work) == (query.kind, 2)
                    charged += projection.rows_visited
                    continue
                assert isinstance(query, (DirectoryQuery, FilteredTreeQuery)), (
                    f"{query.kind} answered past its work bound"
                )
                assert isinstance(projection, (DirectoryProjection, FilteredTreeProjection))
                returned += len(projection.entries)
                whole = await handle.read(
                    ReadRequest(
                        queries=(replace(query, max_work=DEFAULT_QUERY_MAX_WORK),),
                        at_version=result.version,
                    )
                )
                whole_page = whole.projection(query.query_id)
                assert isinstance(whole_page, (DirectoryProjection, FilteredTreeProjection))
                rows = await _assemble_pages(
                    handle, query, projection, result.version, max_pages=files + 1
                )
                assert rows == list(whole_page.entries), query.kind
            # Each query visits at most the six files and the root.
            assert charged <= result.work.rows_visited <= len(queries) * (files + 1)
            assert result.work.rows_returned == returned
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_counts_are_exact_or_proven_lower_bounds(
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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


async def _refresh_written(handle: InventoryHandle, root: Path, path: str) -> RefreshReceipt:
    """Write *path* under *root* and have *handle* verify it."""

    (root / path).write_text(path, encoding="utf-8")
    receipt = await handle.refresh(RefreshRequest(observations=(RefreshObservation(path=path),)))
    assert receipt.accepted_paths == (path,)
    return receipt


async def _changes_through(
    handle: InventoryHandle, *, after: ChangeCursor, through: EngineVersion
) -> list[ChangeBatch]:
    """The batches a stream resumed *after* delivers until one reaches *through*, or a reset.

    How many batches one change takes is the provider's own, so a case reads every batch
    up to the version it is waiting for rather than counting them.
    """

    stream = cast("AsyncGenerator[ChangeBatch, None]", handle.changes(after=after))
    batches: list[ChangeBatch] = []
    try:
        async with asyncio.timeout(5):
            async for batch in stream:
                batches.append(batch)
                if batch.reset or batch.cursor.sequence >= through.sequence:
                    return batches
    finally:
        await stream.aclose()
    raise AssertionError(f"the change stream ended before {through}: {batches}")


def _undirtied(batches: list[ChangeBatch], paths: set[str]) -> set[str]:
    """Which of *paths* no batch names dirty; an all-dirty batch names every path."""

    if any(batch.all_dirty for batch in batches):
        return set()
    return paths - {path for batch in batches for path in batch.dirty_paths}


def _assert_exact_replay(
    batches: list[ChangeBatch], *, after: ChangeCursor, paths: set[str]
) -> None:
    assert not any(batch.reset for batch in batches), batches
    assert {batch.cursor.session for batch in batches} == {after.session}
    sequences = [batch.cursor.sequence for batch in batches]
    assert sequences == sorted(set(sequences)) and sequences[0] > after.sequence, sequences
    assert not _undirtied(batches, paths), batches


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_changes_resume_and_report_history_gaps_as_reset(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A cursor inside the provider's replay capacity replays every change after it, in
    order; one outside it gets an explicit reset, never a suffix presented as complete
    (D8).

    Capacity is the provider's own budget, so how many batches a change takes, and so how
    many changes a capacity holds, is not pinned: two changes fit the default capacity,
    and three under a capacity of one either still replay exactly or reset. The Python
    store's capacity, counted in its own batches, is pinned in
    `tests/test_python_inventory_provider.py`.
    """

    inside_root = tmp_path / "inside"
    outside_root = tmp_path / "outside"
    inside_root.mkdir()
    outside_root.mkdir()

    async def inside() -> None:
        handle = await _open_settled_provider(
            provider_factory, inside_root, config=InventoryConfig(watch_mode="off")
        )
        try:
            initial = (await handle.read(ReadRequest())).cursor
            first = await _refresh_written(handle, inside_root, "first.txt")
            replayed = await _changes_through(handle, after=initial, through=first.version)
            _assert_exact_replay(replayed, after=initial, paths={"first.txt"})

            second = await _refresh_written(handle, inside_root, "second.txt")
            resumed_after = replayed[-1].cursor
            resumed = await _changes_through(handle, after=resumed_after, through=second.version)
            _assert_exact_replay(resumed, after=resumed_after, paths={"second.txt"})

            again = await _changes_through(handle, after=initial, through=second.version)
            _assert_exact_replay(again, after=initial, paths={"first.txt", "second.txt"})
        finally:
            await handle.close()

    async def outside() -> None:
        handle = await _open_settled_provider(
            provider_factory,
            outside_root,
            config=InventoryConfig(change_queue_size=1, watch_mode="off"),
        )
        try:
            initial = (await handle.read(ReadRequest())).cursor
            names = ("a.txt", "b.txt", "c.txt")
            receipts = [await _refresh_written(handle, outside_root, name) for name in names]
            replayed = await _changes_through(handle, after=initial, through=receipts[-1].version)
            if replayed[-1].reset:
                gap = replayed[-1]
                assert gap.cursor.session == initial.session
                assert gap.cursor.sequence > initial.sequence
            else:
                _assert_exact_replay(replayed, after=initial, paths=set(names))
        finally:
            await handle.close()

    asyncio.run(inside())
    asyncio.run(outside())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_dirty_paths_name_every_ancestor_whose_aggregates_changed(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A change dirties its path and every ancestor whose aggregates it moved, the root
    included, so a consumer that rereads only dirty paths sees current folder totals.

    Batch granularity is not pinned: the batches up to the refresh's version are read
    together, and an all-dirty batch names every path. What else a dirty path promises,
    and how a removed subtree is named, is D20, open pending fdu.
    """

    (tmp_path / "deep" / "a" / "b").mkdir(parents=True)
    (tmp_path / "deep" / "other").mkdir()
    (tmp_path / "deep" / "a" / "b" / "old.txt").write_bytes(b"old")
    (tmp_path / "deep" / "other" / "x.txt").write_bytes(b"x")
    ancestors = ("deep/a/b", "deep/a", "deep", "")

    async def totals(handle: InventoryHandle, paths: tuple[str, ...]) -> dict[str, object]:
        result = await handle.read(
            ReadRequest(queries=tuple(EntryQuery(query_id=f"/{path}", path=path) for path in paths))
        )
        answers: dict[str, object] = {}
        for path in paths:
            projection = cast("EntryProjection", result.projection(f"/{path}"))
            entry = projection.entry
            answers[path] = (
                projection.presence
                if entry is None
                else (entry.total_files, entry.total_size, entry.unignored_files)
            )
        return answers

    async def change(handle: InventoryHandle, path: str, *, dirty: set[str]) -> None:
        cursor = (await handle.read(ReadRequest())).cursor
        receipt = await handle.refresh(
            RefreshRequest(observations=(RefreshObservation(path=path),))
        )
        assert receipt.accepted_paths == (path,)
        batches = await _changes_through(handle, after=cursor, through=receipt.version)
        assert not any(batch.reset for batch in batches), batches
        assert not _undirtied(batches, dirty), (path, _undirtied(batches, dirty))

    async def run() -> list[dict[str, object]]:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        try:
            seen = [await totals(handle, ancestors)]
            (tmp_path / "deep" / "a" / "b" / "new.txt").write_bytes(b"added")
            await change(handle, "deep/a/b/new.txt", dirty={"deep/a/b/new.txt", *ancestors})
            seen.append(await totals(handle, ancestors))
            (tmp_path / "deep" / "a" / "b" / "old.txt").unlink()
            await change(handle, "deep/a/b/old.txt", dirty={"deep/a/b/old.txt", *ancestors})
            seen.append(await totals(handle, ancestors))
            shutil.rmtree(tmp_path / "deep" / "a" / "b")
            await change(handle, "deep/a/b", dirty=set(ancestors))
            seen.append(await totals(handle, ancestors))
            return seen
        finally:
            await handle.close()

    discovered, added, removed_file, removed_directory = asyncio.run(run())
    assert discovered == {
        "deep/a/b": (1, 3, 1),
        "deep/a": (1, 3, 1),
        "deep": (2, 4, 2),
        "": (2, 4, 2),
    }
    assert added == {
        "deep/a/b": (2, 8, 2),
        "deep/a": (2, 8, 2),
        "deep": (3, 9, 3),
        "": (3, 9, 3),
    }
    assert removed_file == {
        "deep/a/b": (1, 5, 1),
        "deep/a": (1, 5, 1),
        "deep": (2, 6, 2),
        "": (2, 6, 2),
    }
    assert removed_directory == {
        "deep/a/b": EntryPresence.ABSENT,
        "deep/a": (0, 0, 0),
        "deep": (1, 1, 1),
        "": (1, 1, 1),
    }


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_directory_times_are_their_newest_regular_file(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A directory's `mtime_ns` and `newest_mtime_ns` are the newest modification time of
    any regular file below it, at any depth, and 0 when it holds none.

    Neither a symlink's time nor the directory's own counts, which is why each is set
    newer than the file here. A live change moves `newest_mtime_ns` up the ancestors.
    `mtime_ns` is pinned at discovery only, because the Python store keeps a
    directory's discovered `mtime_ns` through a live change: an expected failure in
    `tests/test_python_inventory_provider.py`.
    """

    old_ns, new_ns = 100_000_000_000, 200_000_000_000
    (tmp_path / "d" / "sub").mkdir(parents=True)
    (tmp_path / "d" / "empty").mkdir()
    (tmp_path / "d" / "links").mkdir()
    old_file = tmp_path / "d" / "sub" / "old.txt"
    old_file.write_bytes(b"old")
    os.utime(old_file, ns=(old_ns, old_ns))
    try:
        (tmp_path / "d" / "link").symlink_to("sub/old.txt")
        (tmp_path / "d" / "links" / "link").symlink_to("../sub/old.txt")
    except OSError as error:  # pragma: no cover - unsupported Windows policy
        pytest.skip(f"symlinks are unavailable: {error}")
    for link in (tmp_path / "d" / "link", tmp_path / "d" / "links" / "link"):
        os.utime(link, ns=(900_000_000_000, 900_000_000_000), follow_symlinks=False)
    for directory in ("d/sub", "d/empty", "d/links", "d"):
        os.utime(tmp_path / directory, ns=(800_000_000_000, 800_000_000_000))
    paths = ("", "d", "d/sub", "d/empty", "d/links")

    async def times(handle: InventoryHandle) -> dict[str, tuple[int, int | None]]:
        result = await handle.read(
            ReadRequest(queries=tuple(EntryQuery(query_id=f"/{path}", path=path) for path in paths))
        )
        answers: dict[str, tuple[int, int | None]] = {}
        for path in paths:
            entry = cast("EntryProjection", result.projection(f"/{path}")).entry
            assert entry is not None, path
            answers[path] = (entry.mtime_ns, entry.newest_mtime_ns)
        return answers

    async def run() -> tuple[dict[str, tuple[int, int | None]], dict[str, tuple[int, int | None]]]:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        try:
            discovered = await times(handle)
            new_file = tmp_path / "d" / "sub" / "new.txt"
            new_file.write_bytes(b"new")
            os.utime(new_file, ns=(new_ns, new_ns))
            receipt = await handle.refresh(
                RefreshRequest(observations=(RefreshObservation(path="d/sub/new.txt"),))
            )
            assert receipt.accepted_paths == ("d/sub/new.txt",)
            return discovered, await times(handle)
        finally:
            await handle.close()

    discovered, changed = asyncio.run(run())
    assert discovered == {
        "": (old_ns, old_ns),
        "d": (old_ns, old_ns),
        "d/sub": (old_ns, old_ns),
        "d/empty": (0, 0),
        "d/links": (0, 0),
    }
    assert {path: newest for path, (_mtime, newest) in changed.items()} == {
        "": new_ns,
        "d": new_ns,
        "d/sub": new_ns,
        "d/empty": 0,
        "d/links": 0,
    }


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_answers_an_unlisted_directory_with_an_empty_final_page(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """While discovery has not listed a directory, a directory page for it, or for a path
    below it, is empty and has no continuation: neither an error nor a page that
    promises more. `/api/tree` relies on it while discovery runs.

    The discovery gate (`inventory_engine/seams.py`) holds the provider before it lists
    the directory; once released, the same page lists what the directory holds.
    """

    (tmp_path / "a" / "held" / "deeper").mkdir(parents=True)
    (tmp_path / "a" / "held" / "inside.txt").write_text("inside", encoding="utf-8")
    (tmp_path / "a" / "beside.txt").write_text("beside", encoding="utf-8")
    pages = (
        DirectoryQuery(query_id="held", path="a/held", max_depth=2, max_rows=10),
        DirectoryQuery(query_id="deeper", path="a/held/deeper", max_depth=1, max_rows=10),
    )

    async def run() -> tuple[IndexState, list[ProjectionResult], tuple[str, ...]]:
        gate = DiscoveryGate(before="a/held")
        backend = provider_factory(seams=ProviderSeams(discovery_gate=gate))
        handle = await backend.open(tmp_path, InventoryConfig(watch_mode="off"))
        try:
            await asyncio.wait_for(gate.wait_reached(), 5)
            held = await handle.read(ReadRequest(queries=pages))
            unlisted = [held.projection(page.query_id) for page in pages]
            gate.release()
            for _attempt in range(500):
                if (await handle.read(ReadRequest())).state.phase in _SERVING_PHASES:
                    break
                await asyncio.sleep(0.005)
            listed = await handle.read(ReadRequest(queries=pages[:1]))
            listed_page = cast("DirectoryProjection", listed.projection("held"))
            return held.state, unlisted, tuple(entry.path for entry in listed_page.entries)
        finally:
            gate.release()
            await handle.close()

    state, unlisted, listed = asyncio.run(run())
    assert state.phase is LifecyclePhase.DISCOVERING
    assert not state.coverage.complete
    assert unlisted == [
        DirectoryProjection(query_id="held", entries=(), next_page=None),
        DirectoryProjection(query_id="deeper", entries=(), next_page=None),
    ]
    assert listed == ("a/held/deeper", "a/held/inside.txt")


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_allows_only_one_active_change_iterator(
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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
def test_provider_change_stream_reaches_every_refresh_receipt_version(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A receipt names a version the change stream delivers, or one it already has.

    The coordinator returns a refresh only once its relay has published the receipt's
    version (R27), so a receipt ahead of every batch the stream will deliver would hang
    that wait. Each refresh here, one that changes nothing and one whose path vanished
    among them, must be followed by a batch at or past its receipt's version.
    """

    (tmp_path / "kept.txt").write_text("kept", encoding="utf-8")

    async def run() -> None:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        try:
            checkpoint = await handle.read(ReadRequest())
            stream = cast(
                "AsyncGenerator[ChangeBatch, None]", handle.changes(after=checkpoint.cursor)
            )
            delivered = checkpoint.version.sequence
            steps: tuple[tuple[str, ObservationKind, Callable[[], object]], ...] = (
                (
                    "new.txt",
                    ObservationKind.CREATED,
                    lambda: (tmp_path / "new.txt").write_text("n"),
                ),
                ("new.txt", ObservationKind.MODIFIED, lambda: None),
                (
                    "kept.txt",
                    ObservationKind.MODIFIED,
                    lambda: (tmp_path / "kept.txt").write_text("k2"),
                ),
                ("new.txt", ObservationKind.DELETED, lambda: (tmp_path / "new.txt").unlink()),
                ("never.txt", ObservationKind.CREATED, lambda: None),
            )
            for path, kind, mutate in steps:
                mutate()
                receipt = await handle.refresh(
                    RefreshRequest(observations=(RefreshObservation(path=path, kind=kind),))
                )
                async with asyncio.timeout(5):
                    while delivered < receipt.version.sequence:
                        delivered = (await anext(stream)).version.sequence
            await stream.aclose()
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_provider_close_joins_change_delivery_and_is_idempotent(
    provider_factory: ProviderFactory,
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
    provider_factory: ProviderFactory,
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
            states: list[IndexState] = []
            sessions: set[str] = set()
            for _attempt in range(500):
                result = await handle.read(ReadRequest())
                sessions.add(result.version.session)
                if not states or result.state.phase is not states[-1].phase:
                    states.append(result.state)
                if result.state.phase in {LifecyclePhase.READY, LifecyclePhase.FAILED}:
                    break
                await asyncio.sleep(0.005)
            assert states[-1].phase is LifecyclePhase.READY
            assert len(sessions) == 1
            # The contract's own check, which nothing applies at run time.
            for before, after in itertools.pairwise(states):
                assert before.can_transition_to(after), (before.phase, after.phase)
        finally:
            await handle.close()

    asyncio.run(run())


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """Group by's filter fields (metabrowser/tree_groups.py): an age band keeps an mtime
    exactly at its near edge and rejects one exactly at its far edge, so the bands
    partition mtimes; a type group classifies by name before extension; and a group,
    unlike a filter, keeps symlinks, by their own mtime for Age and in Other for type."""

    scope = tmp_path / "scope"
    scope.mkdir()
    as_of_ns = 100_000_000_000
    live_edge_ns = as_of_ns - 90_000_000_000
    files = {
        "at-edge.md": live_edge_ns,
        "just-newer.md": live_edge_ns + 1,
        "just-older.md": live_edge_ns - 1,
        "Makefile": live_edge_ns + 5,
        "notes.xyz": live_edge_ns + 5,
    }
    for name, mtime_ns in files.items():
        path = scope / name
        path.write_bytes(b"x")
        os.utime(path, ns=(mtime_ns, mtime_ns))
    link = scope / "link"
    try:
        link.symlink_to("at-edge.md")
    except OSError as error:
        pytest.skip(f"symlinks are unavailable: {error}")
    os.utime(link, ns=(live_edge_ns + 7, live_edge_ns + 7), follow_symlinks=False)

    live = InventoryFilter(band_within_seconds=90, as_of_ns=as_of_ns)
    past_hour = InventoryFilter(band_within_seconds=3600, older_than_seconds=90, as_of_ns=as_of_ns)
    selections = {
        "live": live,
        "past-hour": past_hour,
        "docs": InventoryFilter(type_group="docs"),
        "code": InventoryFilter(type_group="code"),
        "other": InventoryFilter(type_group="other"),
        # A filter still drops symlinks: the user's window, here, cuts the Live band.
        "live-in-window": InventoryFilter(
            recency_seconds=90, band_within_seconds=90, as_of_ns=as_of_ns
        ),
    }

    async def run() -> dict[str, set[str]]:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        try:
            result = await handle.read(
                ReadRequest(
                    queries=tuple(
                        FilteredTreeQuery(
                            query_id=name, path="scope", max_depth=1, filter=selection
                        )
                        for name, selection in selections.items()
                    )
                )
            )
            leaves: dict[str, set[str]] = {}
            for name in selections:
                projection = result.projection(name)
                assert isinstance(projection, FilteredTreeProjection)
                leaves[name] = {
                    entry.path.removeprefix("scope/")
                    for entry in projection.entries
                    if entry.type is not EntryType.DIRECTORY
                }
            return leaves
        finally:
            await handle.close()

    leaves = asyncio.run(run())
    assert leaves["live"] == {"at-edge.md", "just-newer.md", "Makefile", "notes.xyz", "link"}
    assert leaves["past-hour"] == {"just-older.md"}
    assert leaves["docs"] == {"at-edge.md", "just-newer.md", "just-older.md"}
    assert leaves["code"] == {"Makefile"}
    assert leaves["other"] == {"notes.xyz", "link"}
    assert leaves["live-in-window"] == {"at-edge.md", "just-newer.md", "Makefile", "notes.xyz"}


def test_group_filter_fields_are_validated() -> None:
    with pytest.raises(ValueError, match="band_within_seconds must be positive"):
        InventoryFilter(band_within_seconds=0, as_of_ns=1)
    with pytest.raises(ValueError, match="older_than_seconds must be positive"):
        InventoryFilter(older_than_seconds=0, as_of_ns=1)
    with pytest.raises(ValueError, match="requires as_of_ns"):
        InventoryFilter(band_within_seconds=1)
    with pytest.raises(ValueError, match="requires as_of_ns"):
        InventoryFilter(older_than_seconds=1)


_AS_OF_NS = 1_000_000_000_000_000_000
_TYPE_GROUPS = tuple(
    TreeGroupFilter(key=group_id, type_group=group_id)
    for group_id in ("docs", "code", "data", "archives", "media", "other")
)
_AGE_GROUPS = (
    TreeGroupFilter(key="live", band_within_seconds=90),
    TreeGroupFilter(key="1h", band_within_seconds=3_600, older_than_seconds=90),
    TreeGroupFilter(key="24h", band_within_seconds=86_400, older_than_seconds=3_600),
    TreeGroupFilter(key="older", older_than_seconds=86_400),
)


def _grouped_tree_fixture(root: Path) -> None:
    """Nested folders deeper than a listed tree, files of several type groups and ages,
    a file a name classifies, gitignored files, and symlinks."""

    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (root / ".gitignore").write_text("scope/build/\n", encoding="utf-8")
    ages = (10, 600, 7_200, 200_000)
    names = ("guide.md", "app.py", "data.json", "pack.zip", "photo.png", "blob.xyz", "Makefile")
    for index, folder in enumerate(
        ("scope", "scope/a", "scope/a/b", "scope/a/b/c/d", "scope/e", "scope/build/out")
    ):
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        for offset, name in enumerate(names):
            path = directory / name
            path.write_bytes(b"x" * (offset * 7 + index))
            mtime_ns = _AS_OF_NS - ages[(index + offset) % len(ages)] * 1_000_000_000
            os.utime(path, ns=(mtime_ns, mtime_ns))
    link = root / "scope" / "a" / "link"
    try:
        link.symlink_to("app.py")
    except OSError as error:
        pytest.skip(f"symlinks are unavailable: {error}")
    link_mtime_ns = _AS_OF_NS - 30_000_000_000
    os.utime(link, ns=(link_mtime_ns, link_mtime_ns), follow_symlinks=False)


@pytest.mark.parametrize("provider_factory", PROVIDER_FACTORIES)
def test_grouped_tree_answers_each_group_as_its_filtered_tree(
    provider_factory: ProviderFactory,
    tmp_path: Path,
) -> None:
    """A grouped tree's group is exactly its filtered tree (`GroupedTreeQuery.group_query`):
    the same rows, totals, and pages, read from one pass at one version, for each grouping,
    shared filter, depth, and page bound."""

    _grouped_tree_fixture(tmp_path)
    shared_filters = {
        "none": InventoryFilter(as_of_ns=_AS_OF_NS),
        "extensions": InventoryFilter(extensions=(".md", ".PY"), as_of_ns=_AS_OF_NS),
        "size-and-ignored": InventoryFilter(
            minimum_size=10, include_ignored=False, as_of_ns=_AS_OF_NS
        ),
        "recency": InventoryFilter(recency_seconds=7_200, as_of_ns=_AS_OF_NS),
    }
    cases = [
        (grouping, shared_name, path, max_depth, max_rows)
        for grouping in (_TYPE_GROUPS, _AGE_GROUPS)
        for shared_name in shared_filters
        for path, max_depth in (("", 2), ("scope", 1), ("scope", 3), ("scope/a", 2))
        for max_rows in (2, 4_096)
    ]

    async def pages(
        handle: InventoryHandle,
        first: tuple[InventoryEntry, ...],
        next_page: str | None,
        continuation: Callable[[str], FilteredTreeQuery],
        version: EngineVersion,
    ) -> list[InventoryEntry]:
        rows = list(first)
        while next_page is not None:
            query = continuation(next_page)
            result = await handle.read(ReadRequest(queries=(query,), at_version=version))
            page = result.projection(query.query_id)
            assert isinstance(page, FilteredTreeProjection)
            rows.extend(page.entries)
            next_page = page.next_page
        return rows

    async def run() -> int:
        handle = await _open_settled_provider(
            provider_factory, tmp_path, config=InventoryConfig(watch_mode="off")
        )
        compared = 0
        try:
            for grouping, shared_name, path, max_depth, max_rows in cases:
                grouped = GroupedTreeQuery(
                    query_id="grouped",
                    groups=grouping,
                    path=path,
                    max_depth=max_depth,
                    max_rows=max_rows,
                    filter=shared_filters[shared_name],
                )
                singles = [grouped.group_query(group) for group in grouping]
                result = await handle.read(ReadRequest(queries=(grouped, *singles)))
                answer = result.projection("grouped")
                assert isinstance(answer, GroupedTreeProjection)
                assert [group.key for group in answer.groups] == [group.key for group in grouping]
                for group, single, own in zip(grouping, singles, answer.groups, strict=True):
                    expected = result.projection(single.query_id)
                    assert isinstance(expected, FilteredTreeProjection)
                    label = (shared_name, path, max_depth, max_rows, group.key)
                    assert (own.matching_leaves, own.matching_files, own.matching_bytes) == (
                        expected.matching_leaves,
                        expected.matching_files,
                        expected.matching_bytes,
                    ), label
                    assert own.entries == expected.entries, label
                    assert (own.next_page is None) == (expected.next_page is None), label
                    own_rows = await pages(
                        handle,
                        own.entries,
                        own.next_page,
                        lambda after, grouped=grouped, group=group: grouped.group_query(
                            group, after=after
                        ),
                        result.version,
                    )
                    expected_rows = await pages(
                        handle,
                        expected.entries,
                        expected.next_page,
                        lambda after, single=single: replace(single, after=after),
                        result.version,
                    )
                    assert own_rows == expected_rows, label
                    compared += 1
        finally:
            await handle.close()
        return compared

    assert asyncio.run(run()) == sum(len(case[0]) for case in cases)


def test_grouped_tree_queries_are_validated() -> None:
    live = TreeGroupFilter(key="live", band_within_seconds=90)
    with pytest.raises(ValueError, match="selects by type group or by age band"):
        TreeGroupFilter(key="nothing")
    with pytest.raises(ValueError, match="older_than_seconds must be positive"):
        TreeGroupFilter(key="older", older_than_seconds=0)
    with pytest.raises(ValueError, match="at least one group"):
        GroupedTreeQuery(query_id="g", groups=())
    with pytest.raises(ValueError, match="unique"):
        GroupedTreeQuery(query_id="g", groups=(live, live), filter=InventoryFilter(as_of_ns=1))
    with pytest.raises(ValueError, match="at most"):
        GroupedTreeQuery(
            query_id="g",
            groups=tuple(
                TreeGroupFilter(key=str(index), type_group="docs")
                for index in range(MAX_TREE_GROUPS + 1)
            ),
        )
    with pytest.raises(ValueError, match="shared filter names no group"):
        GroupedTreeQuery(
            query_id="g",
            groups=(TreeGroupFilter(key="docs", type_group="docs"),),
            filter=InventoryFilter(type_group="code"),
        )
    with pytest.raises(ValueError, match="requires the shared filter's as_of_ns"):
        GroupedTreeQuery(query_id="g", groups=(live,))
    with pytest.raises(ValueError, match="max_rows must be positive"):
        GroupedTreeQuery(
            query_id="g", groups=(TreeGroupFilter(key="docs", type_group="docs"),), max_rows=0
        )
    with pytest.raises(ValueError, match="continuation requires a nonempty page"):
        TreeGroupProjection(
            key="docs",
            entries=(),
            matching_leaves=0,
            matching_files=0,
            matching_bytes=0,
            next_page="token",
        )
