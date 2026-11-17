"""Bounded instrumentation for the fdu provider spike's temporary fallbacks.

Every place the spike adapter does work in Python that a native fdu projection should do
instead is recorded here, keyed by a fallback name. Each name maps to the fdu addition
that would remove it (`FALLBACK_REMEDIES`), so the evidence says what to build rather
than only what was slow.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from typing import Any

# The fdu addition that would remove each fallback. A fallback without an entry here is
# a bug in the spike: every one must name its remedy.
FALLBACK_REMEDIES: dict[str, str] = {
    "filtered_tree": (
        "native filtered-tree projection: one bounded selection and aggregation pass over "
        "portable_children with Metabrowser filter predicates (logical extension, exact "
        "name, registry family and display group, age band, minimum size, ignored pruning) "
        "returning level-ordered rows plus matching leaf/file/byte totals"
    ),
    "grouped_tree": (
        "native grouped filtered tree: the same pass with up to MAX_TREE_GROUPS group "
        "predicates (display group, age band) evaluated per leaf"
    ),
    "rollup": (
        "native File Rollup projection: DirectoryRollUp plus the maintained per-directory "
        "semantic type tallies, emitting the node/children, extension tallies, and "
        "file-type breakdown that Metabrowser's RollupResult carries"
    ),
    "navigation": (
        "native navigation projection derived from the maintained root partitions, "
        "semantic type tallies, declared exact-name tallies, and global recency order"
    ),
    "recent": (
        "native ranked-recency projection over the maintained global recency order "
        "(ignored last, mtime descending, path), with an Aggregate-style capped count"
    ),
    "directory_empty_probe": (
        "a leaf (file plus symlink) count in PartitionRollUpSummary, so `empty` is known "
        "for a directory holding no files without walking its subtree"
    ),
    "registry_downlevel": (
        "accept File Rollup registry schema 5 (the presentation-only `chroma_ratio` family "
        "field), which fdu's fingerprint already excludes"
    ),
    "catalog_offset_ledger": (
        "a flat continuation that carries the count of rows already emitted, or an "
        "Aggregate lower bound that includes them, so a continued catalog page can state "
        "its proven at-least count without adapter state"
    ),
    "page_chaining": (
        "a native page bound at least as large as Metabrowser's page requests (catalog "
        "pages are `budget.max_files` rows), or a provider page-size hint the host "
        "assembly honours; fdu 0.6.0 refuses a page limit above 4096"
    ),
    "continuation_identity_ledger": (
        "a Continue that carries (or validates) the resubmitted query, so a continuation "
        "presented with a different path, depth, or filter is refused natively"
    ),
}


@dataclass(slots=True)
class FallbackTotals:
    """Cumulative Python-side work for one fallback name."""

    invocations: int = 0
    native_calls: int = 0
    native_pages: int = 0
    materialized_rows: int = 0
    materialized_path_bytes: int = 0
    image_reuses: int = 0
    child_bucket_builds: int = 0
    full_result_sorts: int = 0
    aggregate_passes: int = 0
    rows_returned: int = 0
    wall_time_ns: int = 0
    cpu_time_ns: int = 0
    max_wall_time_ns: int = 0


@dataclass(slots=True)
class NativeTotals:
    """Cumulative work for projections answered by one native fdu projection."""

    invocations: int = 0
    native_calls: int = 0
    rows_returned: int = 0
    wall_time_ns: int = 0


@dataclass(slots=True)
class ProbeState:
    fallbacks: dict[str, FallbackTotals] = field(default_factory=dict)
    native: dict[str, NativeTotals] = field(default_factory=dict)
    change_polls: int = 0
    change_batches: int = 0
    refreshes: int = 0
    priorities: int = 0
    read_retries: int = 0
    extension_mismatches: int = 0
    extension_checks: int = 0
    extension_mismatch_examples: list[tuple[str, str, str]] = field(default_factory=list)
    typed_failures: dict[str, int] = field(default_factory=dict)


_MAX_EXAMPLES = 32


class AdapterProbe:
    """Thread-safe, constant-size evidence recorder shared by spike handles."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = ProbeState()

    def fallback(
        self,
        name: str,
        *,
        native_calls: int = 0,
        native_pages: int = 0,
        materialized_rows: int = 0,
        materialized_path_bytes: int = 0,
        image_reuses: int = 0,
        child_bucket_builds: int = 0,
        full_result_sorts: int = 0,
        aggregate_passes: int = 0,
        rows_returned: int = 0,
        wall_time_ns: int = 0,
        cpu_time_ns: int = 0,
    ) -> None:
        if name not in FALLBACK_REMEDIES:
            raise KeyError(f"fallback {name!r} names no fdu remedy")
        with self._lock:
            totals = self._state.fallbacks.setdefault(name, FallbackTotals())
            totals.invocations += 1
            totals.native_calls += native_calls
            totals.native_pages += native_pages
            totals.materialized_rows += materialized_rows
            totals.materialized_path_bytes += materialized_path_bytes
            totals.image_reuses += image_reuses
            totals.child_bucket_builds += child_bucket_builds
            totals.full_result_sorts += full_result_sorts
            totals.aggregate_passes += aggregate_passes
            totals.rows_returned += rows_returned
            totals.wall_time_ns += wall_time_ns
            totals.cpu_time_ns += cpu_time_ns
            totals.max_wall_time_ns = max(totals.max_wall_time_ns, wall_time_ns)

    def native(self, kind: str, *, rows_returned: int, wall_time_ns: int) -> None:
        with self._lock:
            totals = self._state.native.setdefault(kind, NativeTotals())
            totals.invocations += 1
            totals.native_calls += 1
            totals.rows_returned += rows_returned
            totals.wall_time_ns += wall_time_ns

    def count(self, name: str, amount: int = 1) -> None:
        with self._lock:
            setattr(self._state, name, getattr(self._state, name) + amount)

    def typed_failure(self, name: str) -> None:
        with self._lock:
            self._state.typed_failures[name] = self._state.typed_failures.get(name, 0) + 1

    def extension(self, path: str, native: str, oracle: str) -> None:
        with self._lock:
            self._state.extension_checks += 1
            if native != oracle:
                self._state.extension_mismatches += 1
                if len(self._state.extension_mismatch_examples) < _MAX_EXAMPLES:
                    self._state.extension_mismatch_examples.append((path, native, oracle))

    def reset(self) -> None:
        with self._lock:
            self._state = ProbeState()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self._state
            return {
                "fallbacks": {
                    name: {**asdict(totals), "remedy": FALLBACK_REMEDIES[name]}
                    for name, totals in sorted(state.fallbacks.items())
                },
                "native": {name: asdict(totals) for name, totals in sorted(state.native.items())},
                "change_polls": state.change_polls,
                "change_batches": state.change_batches,
                "refreshes": state.refreshes,
                "priorities": state.priorities,
                "read_retries": state.read_retries,
                "extension_checks": state.extension_checks,
                "extension_mismatches": state.extension_mismatches,
                "extension_mismatch_examples": list(state.extension_mismatch_examples),
                "typed_failures": dict(sorted(state.typed_failures.items())),
            }


__all__ = ["FALLBACK_REMEDIES", "AdapterProbe"]
