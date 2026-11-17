"""Correctness evidence for the fdu provider spike against the current contract.

Verifies the exact installed wheel, then runs every provider-parametrized conformance
case against Python and fdu, the File Rollup conformance corpus through fdu's native
classifier, the 2A route/SSE selection and the newer inventory route suites with fdu
injected, one bundled representative read with fallback counters, and an application
lifecycle probe. Every failure must match a classified root cause below, or the run
reports it as unclassified. Output: ``evidence/correctness.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("FDU_SPIKE_VERIFY_EXT", "1")

import adapter
import fdu as fdu_package
from adapter import FduInventoryBackend
from conformance import provider_cases, run_case, run_conformance
from probe import AdapterProbe
from rollup_corpus import run_corpus
from routes import SELECTED_2A, SELECTED_NEWER, run_selection

from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    ChangeBatch,
    DiagnosticsQuery,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    FilteredTreeQuery,
    GroupedTreeQuery,
    InventoryConfig,
    InventoryFilter,
    LifecyclePhase,
    NavigationQuery,
    ReadRequest,
    RecentQuery,
    RefreshObservation,
    RefreshRequest,
    RollupQuery,
    TreeGroupFilter,
)
from metabrowser.inventory_engine.coordinator import InventoryCoordinator
from metabrowser.inventory_engine.runtime import default_inventory_config

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FDU_CHECKOUT = REPO_ROOT.parent / "fdu"
FDU_REVISION = "4450be7"
FDU_VERSION = "0.6.0"
WHEEL_NAME = "fdu-0.6.0-cp312-abi3-manylinux_2_34_x86_64.whl"
WHEEL_SHA256 = "d4b9071b377be9201ad95dedaebc19328e0a255cd76dc072fe5fa0cc91fdac1f"

# (a) adapter bug, (b) fdu gap, (c) Metabrowser contract over-specification,
# (d) test reaches into Python-provider internals (or the spike's own injection).
# Each entry lists the failure modes it covers as (class, text the failing assertion or
# error must contain, root cause). A failure matching no listed mode is unclassified, so
# a test that starts failing somewhere else cannot inherit an old explanation.
type _Mode = tuple[str, str, str]
CLASSIFIED: dict[str, tuple[_Mode, ...]] = {
    "test_provider_semantic_digest": (
        (
            "d",
            "'diagnostics': ('fdu', 'inventory-provider-v1')",
            "Fails only at the provider name: the test asserts diagnostics.provider == "
            "'python'. Every filesystem fact, order, aggregate, filter, rollup, navigation, "
            "recent, and catalog value matches; the masked rerun "
            "(`semantic_digest_with_provider_identity_masked`) passes.",
        ),
    ),
    "test_provider_applies_work_bounds_to_continuation_pages": (
        (
            "b",
            "assert limited.projection(kind) == QueryLimitProjection(",
            "Fails in its first (directory) half, so the test never reaches the others; "
            "`work_bounds_by_half` runs each half on its own. fdu's tree max_work is a soft "
            "budget, so a max_work=1 continuation returns rows instead of a typed limit and "
            "consumes the single-use continuation, which makes the retry unavailable.",
        ),
    ),
    "test_provider_returns_typed_query_limits_without_partial_answers": (
        (
            "b",
            "assert projection == QueryLimitProjection(",
            "Fails at the first query, the directory one, for the same soft tree budget; "
            "`work_bounds_by_half.typed_limits` records every kind.",
        ),
    ),
    "test_provider_budget_stop_is_explicit_and_absence_remains_unknown": (
        (
            "c",
            "assert asyncio.run(run()) == (",
            "The test assumes the 2-file budget admits a.txt and b.txt (Python's sorted "
            "admission). The contract orders traversal breadth-first but not admission within "
            "one directory; fdu admits in readdir order (b.txt and z.txt here), so z.txt is "
            "present and a.txt, never retained, is rejected by refresh. Stopped phase, budget "
            "coverage, resource_budget issue, and watch facts match. Whether admission order "
            "should be deterministic is also an fdu design question.",
        ),
    ),
    "test_provider_changes_resume_and_report_history_gaps_as_reset": (
        (
            "c",
            "assert gap.reset is True",
            "change_queue_size=1 asks for a gap after two batches. fdu budgets its journal in "
            "bytes with a 64 KiB floor (MIN_JOURNAL_CAPACITY_BYTES), so two small refreshes "
            "stay replayable and no reset is due. The contract should state capacity as a "
            "minimum a provider retains, not a maximum it must forget beyond.",
        ),
    ),
}
_WALK_TREE = (
    "Monkeypatches python_inventory.walk_tree to hold or slow discovery; fdu has no such seam."
)
CLASSIFIED_ROUTES: dict[str, tuple[_Mode, ...]] = {
    "tests/test_browser_inventory_api.py::test_api_tree_uses_pending_inventory_without_filesystem_fallback": (
        ("d", "scanning", _WALK_TREE),
    ),
    "tests/test_browser_lifespan_e2e.py::test_watcher_detects_new_file_after_walker_completes": (
        (
            "b",
            "no polling observer",
            "Uses watch_mode='poll'. fdu 0.6.0 has no polling observer; the adapter refuses it "
            "with a typed InventoryContractError rather than faking one.",
        ),
    ),
    "tests/test_browser_walk.py::test_tree_dump_honors_inventory_provider_selection": (
        (
            "d",
            "DID NOT RAISE",
            "Asserts the sealed factory rejects an unknown provider name; the spike's "
            "injection replaces that constructor, so the assertion cannot hold under it.",
        ),
    ),
    "tests/test_api_folder_envelope.py::test_root_directory_envelope_and_pending_state": (
        ("d", 'body["dir"]["total_files"] is None', _WALK_TREE),
    ),
    "tests/test_rollup_route.py::test_rollup_payload_and_etag_share_one_version": (
        (
            "d",
            "assert first_files == 2",
            "Mode A. The test gates python_inventory.build_rollup, which engages only because "
            "the spike's rollup is the Python oracle. The gated build answers from the "
            "immutable image of the version the read began at, so the first body is that "
            "version's coherent rollup (one file) with that version's tag; the refresh made "
            "during the gate has already moved fdu on. The Python store is mutable, detects "
            "the move, and rereads, so its first body includes b.txt. Answering the older "
            "boundary is coherent and allowed; the test pins Python's reread policy.",
        ),
        (
            "c",
            "the version must hold",
            "Mode B. A native refresh is three commits (freshness to reconciling, insert, "
            "verified to fresh); the receipt names the last, but the host relay can still be "
            "publishing an earlier one when refresh() returns, so the served version moves "
            "between two reads. The contract permits sub-batches; the coordinator does not "
            "wait for its relay to reach the receipt's version.",
        ),
    ),
    "tests/test_e2e_filesystem_to_sse.py::test_rm_directory_coalesces_descendant_removals": (
        (
            "c",
            "assert change_count == 1",
            "Intermittent for both providers (counts in evidence/flake.json). With "
            "observation on, the live observer and the test's explicit refresh both verify "
            "one recursive removal, and whether that lands in one provider batch or two is "
            "timing; the host coalesces within a batch, against an assertion of exactly one "
            "envelope.",
        ),
    ),
    "tests/test_e2e_filesystem_to_sse.py::test_touch_existing_file_emits_one_upsert_path": (
        (
            "c",
            "'capability.update'",
            "Intermittent for fdu. A native refresh begins with a state-only commit "
            "(freshness fresh to reconciling); when a poll returns it alone, it is a "
            "state-only change batch, which the host projects as capability.update before "
            "the data batch. The contract allows state-only batches; the test asserts a "
            "verified refresh shows no state transition. It passed with the timed adapter "
            "only because that adapter wrongly took the state commit's paths as dirty data.",
        ),
    ),
    "tests/test_catalog_feed_server.py::test_api_catalog_is_incomplete_while_discovery_is_blocked": (
        ("d", "TimeoutError", _WALK_TREE),
    ),
    "tests/test_catalog_feed_server.py::test_walker_completion_projects_capability_update": (
        ("d", "TimeoutError", _WALK_TREE),
    ),
    "tests/test_browser_events_route.py::test_api_index_progress_does_not_304_while_active": (
        ("d", "assert status == 200", _WALK_TREE),
    ),
}


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def provenance(
    wheel: Path,
    fdu_checkout: Path,
    *,
    expected_name: str = WHEEL_NAME,
    expected_sha256: str = WHEEL_SHA256,
) -> dict[str, Any]:
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if wheel.name != expected_name or digest != expected_sha256:
        raise RuntimeError(f"wheel {wheel.name} {digest} is not the reviewed {expected_sha256}")
    package_path = Path(fdu_package.__file__).resolve()
    source_tree = (fdu_checkout / "crates/fdu-py/python").resolve()
    if package_path.is_relative_to(source_tree) or package_path.is_relative_to(fdu_checkout):
        raise RuntimeError(f"fdu leaked from the source checkout: {package_path}")
    if "site-packages" not in package_path.parts:
        raise RuntimeError(f"fdu was not imported from an installed wheel: {package_path}")
    native = sys.modules["fdu._native"]
    if getattr(native, "__version__", None) != FDU_VERSION:
        raise RuntimeError(f"fdu native version {getattr(native, '__version__', None)}")
    return {
        "fdu_revision": FDU_REVISION,
        "fdu_checkout_head": _git(fdu_checkout, "rev-parse", "HEAD"),
        "fdu_version": FDU_VERSION,
        "wheel": wheel.name,
        "wheel_sha256": digest,
        "import_origin": str(package_path),
        "source_tree_import": False,
        "metabrowser_head": _git(REPO_ROOT, "rev-parse", "HEAD"),
        "metabrowser_dirty_paths": _git(REPO_ROOT, "status", "--porcelain").splitlines(),
        "python": sys.version.split()[0],
        "platform": f"{os.uname().sysname} {os.uname().release} {os.uname().machine}",
        "cpus": os.cpu_count(),
    }


def masked_digest() -> dict[str, Any]:
    """Rerun the semantic digest with the adapter reporting the Python provider's name."""

    suite, _names = provider_cases()
    original = adapter.PROVIDER_ID
    adapter.PROVIDER_ID = "python"
    try:
        return run_case(suite, "test_provider_semantic_digest", lambda: FduInventoryBackend())
    finally:
        adapter.PROVIDER_ID = original


async def _settle(handle: Any, timeout: float = 120.0) -> Any:
    async with asyncio.timeout(timeout):
        while True:
            result = await handle.read(ReadRequest())
            if result.state.phase in {
                LifecyclePhase.READY,
                LifecyclePhase.WATCHING,
                LifecyclePhase.STOPPED,
                LifecyclePhase.FAILED,
            }:
                return result
            await asyncio.sleep(0.01)


async def representative(corpus: Path, probe: AdapterProbe) -> dict[str, Any]:
    """The 2A bundle on the same kind of corpus, plus the 2B-only grouped tree."""

    probe.reset()
    config = InventoryConfig(
        registry_document=default_inventory_config().registry_document,
        budget=default_inventory_config().budget,
        hidden_allowlist=default_inventory_config().hidden_allowlist,
        watch_mode="off",
    )
    handle = await FduInventoryBackend(probe=probe).open(corpus, config)
    try:
        settled_started = time.monotonic()
        settled = await _settle(handle)
        as_of_ns = time.time_ns()
        tracemalloc.start()
        started = time.monotonic_ns()
        result = await handle.read(
            ReadRequest(
                queries=(
                    EntryQuery(query_id="root", path=""),
                    DirectoryQuery(query_id="directory", max_depth=2, max_rows=10_000),
                    FilteredTreeQuery(
                        query_id="markdown",
                        max_depth=4,
                        max_rows=10_000,
                        filter=InventoryFilter(extensions=(".md",)),
                    ),
                    GroupedTreeQuery(
                        query_id="grouped",
                        groups=(
                            TreeGroupFilter(key="code", type_group="code"),
                            TreeGroupFilter(key="docs", type_group="docs"),
                        ),
                        max_depth=2,
                        max_rows=10_000,
                    ),
                    RollupQuery(query_id="rollup", max_depth=4, max_nodes=50_000),
                    NavigationQuery(query_id="navigation", max_rows=200),
                    RecentQuery(
                        query_id="recent",
                        max_rows=200,
                        as_of_ns=as_of_ns,
                        filter=InventoryFilter(include_ignored=True),
                    ),
                    CatalogQuery(query_id="catalog", max_rows=10_000, include_ignored=True),
                    DiagnosticsQuery(query_id="diagnostics"),
                )
            )
        )
        wall_ms = (time.monotonic_ns() - started) / 1e6
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows = {
            projection.query_id: len(
                getattr(projection, "entries", getattr(projection, "records", ()))
            )
            for projection in result.projections
        }
        counts, timings = _split_probe(probe.snapshot())
        return {
            "corpus": "metabrowser-checkout (live)" if corpus == REPO_ROOT else corpus.name,
            "settled_phase": settled.state.phase.value,
            # IndexProgress.entries_observed carries fdu's retained file count.
            "files": settled.state.progress.entries_observed,
            "projection_rows": rows,
            "rows_returned": result.work.rows_returned,
            "probe": counts,
            "volatile": {
                "settle_s": round(time.monotonic() - settled_started, 3),
                "bundle_wall_ms_under_tracemalloc": round(wall_ms, 1),
                "bundle_python_peak_bytes": peak,
                "probe_timings": timings,
            },
        }
    finally:
        await handle.close()


async def _next_matching(stream: Any, path: str, timeout: float = 10.0) -> ChangeBatch:
    async with asyncio.timeout(timeout):
        async for change in stream:
            if change.reset or change.all_dirty or path in change.dirty_paths:
                return cast("ChangeBatch", change)
    raise AssertionError(f"no change for {path}")


async def lifecycle(probe: AdapterProbe) -> dict[str, Any]:
    prefix = "metabrowser-fdu-spike-"  # the poll, read, and discovery-monitor threads
    before = sum(thread.name.startswith(prefix) for thread in threading.enumerate())
    backend = FduInventoryBackend(probe=probe)
    with (
        tempfile.TemporaryDirectory(prefix="fdu-spike-life-a-") as first_raw,
        tempfile.TemporaryDirectory(prefix="fdu-spike-life-b-") as second_raw,
    ):
        first_root, second_root = Path(first_raw), Path(second_raw)
        (first_root / "seed.txt").write_text("seed", encoding="utf-8")
        (second_root / "replacement.txt").write_text("replacement", encoding="utf-8")
        coordinator = InventoryCoordinator(backend=backend, config=InventoryConfig())
        try:
            await coordinator.open(first_root)
            async with asyncio.timeout(10):
                while True:
                    read = await coordinator.read(
                        ReadRequest(queries=(DirectoryQuery(query_id="useful", max_depth=2),))
                    )
                    if read.result.state.phase in {LifecyclePhase.READY, LifecyclePhase.WATCHING}:
                        break
                    await asyncio.sleep(0.01)
            first_phase = read.result.state.phase.value
            checkpoint, _version, _state = await coordinator.checkpoint()
            stream = coordinator.changes(after=checkpoint)
            written = time.monotonic()
            (first_root / "live.txt").write_text("live", encoding="utf-8")
            live = await _next_matching(stream, "live.txt")
            live_ms = (time.monotonic() - written) * 1000
            reread = await coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="live", path="live.txt"),))
            )
            live_projection = reread.result.projection("live")
            assert isinstance(live_projection, EntryProjection)
            (first_root / "refresh.txt").write_text("refresh", encoding="utf-8")
            receipt = await coordinator.refresh(
                RefreshRequest(observations=(RefreshObservation(path="refresh.txt"),))
            )
            await stream.aclose()
            await coordinator.replace_root(second_root)
            replaced = await coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="r", path="replacement.txt"),))
            )
            replacement = replaced.result.projection("r")
            assert isinstance(replacement, EntryProjection)
        finally:
            await coordinator.close()
        handle = await backend.open(first_root, InventoryConfig(watch_mode="off"))
        await _settle(handle)
        checkpoint_read = await handle.read(ReadRequest())
        iterator = handle.changes(after=checkpoint_read.cursor)
        waiter = asyncio.ensure_future(anext(iterator))
        await asyncio.sleep(0.05)
        cancel_started = time.monotonic_ns()
        waiter.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await waiter
        cancel_ms = (time.monotonic_ns() - cancel_started) / 1e6
        usable = await handle.read(ReadRequest())
        await asyncio.gather(handle.close(), handle.close())
    after = sum(thread.name.startswith(prefix) for thread in threading.enumerate())
    return {
        "first_phase": first_phase,
        "live_change": {
            "reset": live.reset,
            "all_dirty": live.all_dirty,
            "dirty_paths": list(live.dirty_paths),
        },
        "live_reread_presence": live_projection.presence.value,
        "refresh_accepted": list(receipt.accepted_paths),
        "replacement_presence": replacement.presence.value,
        "usable_after_iterator_cancel": usable.state.phase.value,
        "spike_threads_before": before,
        "spike_threads_after": after,
        "present": live_projection.presence is EntryPresence.PRESENT,
        "volatile": {
            "live_change_latency_ms": round(live_ms, 1),
            "iterator_cancel_ms": round(cancel_ms, 1),
        },
    }


async def identity_and_bounds() -> dict[str, Any]:
    """F2 (backslash identity and order) and the 16-projection / 64-priority caps."""

    from metabrowser.inventory_engine.contract import CatalogQuery as Catalog
    from metabrowser.inventory_engine.contract import PriorityRequest
    from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend

    async def one(factory: Any) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="fdu-spike-identity-") as raw:
            root = Path(raw)
            for name in ("a\\b.txt", "a.txt", "a]b.txt", "100%.txt"):
                (root / name).write_text(name, encoding="utf-8")
            for index in range(40):
                (root / f"f{index:02d}.txt").write_text(str(index), encoding="utf-8")
            handle = await factory().open(root, InventoryConfig(watch_mode="off"))
            try:
                await _settle(handle)
                read = await handle.read(
                    ReadRequest(
                        queries=(
                            DirectoryQuery(query_id="d", max_depth=1, max_rows=5),
                            Catalog(query_id="c", max_rows=5),
                            EntryQuery(query_id="b", path="a%5Cb.txt"),
                        )
                    )
                )
                many = await handle.read(
                    ReadRequest(
                        queries=tuple(
                            EntryQuery(query_id=f"q{index}", path=f"f{index:02d}.txt")
                            for index in range(40)
                        )
                    )
                )
                await handle.prioritize(
                    PriorityRequest(paths=tuple(f"p{index}" for index in range(100)))
                )
                directory = read.projection("d")
                catalog = read.projection("c")
                lookup = read.projection("b")
                return {
                    "directory_order": [entry.path for entry in directory.entries],
                    "catalog_order": [record.path for record in catalog.records],
                    "backslash_lookup": lookup.presence.value,
                    "forty_entry_bundle_present": sum(
                        item.presence is EntryPresence.PRESENT for item in many.projections
                    ),
                    "hundred_path_priority": "accepted",
                }
            finally:
                await handle.close()

    python = await one(PythonInventoryBackend)
    native = await one(FduInventoryBackend)
    return {
        "python": python,
        "fdu": native,
        "order_agrees": python["directory_order"] == native["directory_order"]
        and python["catalog_order"] == native["catalog_order"],
    }


_TIMING_KEYS = {"wall_time_ns", "cpu_time_ns", "max_wall_time_ns", "native_read_wall_ns"}


def _split_probe(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separate a probe snapshot's deterministic counts from its timings."""

    def strip(value: Any, timings: dict[str, Any], path: str) -> Any:
        if isinstance(value, dict):
            kept: dict[str, Any] = {}
            for key, item in cast("dict[str, Any]", value).items():
                if key in _TIMING_KEYS:
                    timings[f"{path}{key}"] = item
                else:
                    kept[key] = strip(item, timings, f"{path}{key}.")
            return kept
        return value

    timings: dict[str, Any] = {}
    return cast("dict[str, Any]", strip(snapshot, timings, "")), timings


_TEMP_ROOTS = tuple(
    sorted(
        {tempfile.gettempdir(), os.path.realpath(tempfile.gettempdir())},
        key=len,
        reverse=True,
    )
)


def _normalize(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {str(k): _normalize(v, key=str(k)) for k, v in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast("list[object] | tuple[object, ...]", value)
        return [_normalize(item) for item in sequence]
    if isinstance(value, str):
        text = value.replace(str(REPO_ROOT), "<METABROWSER>")
        text = text.replace(str(FDU_CHECKOUT), "<FDU>")
        text = text.replace(str(Path.home()), "<HOME>")
        text = re.sub(r"/[^\s'\":]*/site-packages/", "<SITE_PACKAGES>/", text)
        for temp_root in _TEMP_ROOTS:
            text = re.sub(re.escape(temp_root) + r"/[^\s'\":]*", "<TMP>", text)
        text = re.sub(r"(/private)?/var/folders/[^\s'\":]*", "<TMP>", text)
        text = re.sub(r"/tmp/[^\s'\":]*", "<TMP>", text)
        text = re.sub(r"fdu:[0-9a-f]{16}", "fdu:<SESSION>", text)
        text = re.sub(r"session='[0-9a-f]{32}'", "session='<SESSION>'", text)
        return text
    if key in {"wall_time_ms", "wall_time_s"} and isinstance(value, float):
        return round(value, 1)
    return value


def _failing_assertion(detail: str) -> str:
    """The test-file location and error line a failure stopped at."""

    locations = re.findall(r"(tests/test_[a-z_]+\.py):(\d+)", detail) or re.findall(
        r'(test_[a-z_]+\.py)", line (\d+)', detail
    )
    errors = [
        line.strip()
        for line in detail.splitlines()
        if line.strip().startswith(("E ", "assert", "AssertionError", "Failed"))
    ]
    where = f"{locations[-1][0]}:{locations[-1][1]}" if locations else "?"
    return f"{where} {errors[0] if errors else ''}"[:240]


def classify(rows: list[dict[str, Any]], table: dict[str, tuple[_Mode, ...]], key: str) -> None:
    for row in rows:
        row["class"] = None
        row["root_cause"] = ""
        if row["fdu_outcome"] != "failed":
            continue
        detail = str(row.get("detail") or row.get("fdu_detail") or "")
        row["failing_assertion"] = _failing_assertion(detail)
        for kind, needle, cause in table.get(row[key], ()):
            if needle in detail:
                row["class"], row["root_cause"] = kind, cause
                break
        else:
            row["class"] = "unclassified"


async def work_bounds_by_half() -> dict[str, Any]:
    """Each half of the continuation work-bound case, and every kind of the limits case.

    The registered case stops at its first failing half, so the halves it never reaches
    are run here on their own, against both providers, with the same fixture and bounds.
    """

    from metabrowser.inventory_engine.contract import QueryKind
    from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend

    def make(kind: Any, **bounds: Any) -> Any:
        if kind is QueryKind.DIRECTORY:
            return DirectoryQuery(query_id=kind, max_depth=1, **bounds)
        if kind is QueryKind.FILTERED_TREE:
            return FilteredTreeQuery(query_id=kind, max_depth=1, **bounds)
        return CatalogQuery(query_id=kind, **bounds)

    def shape(result: Any, query_id: str) -> dict[str, Any]:
        projection = result.projection(query_id)
        return {
            "projection": type(projection).__name__,
            "limit_rows_visited": getattr(projection, "rows_visited", None),
            "work_rows_visited": result.work.rows_visited,
            "work_rows_returned": result.work.rows_returned,
        }

    async def one(factory: Any) -> dict[str, Any]:
        halves: dict[str, Any] = {}
        for kind in (QueryKind.DIRECTORY, QueryKind.FILTERED_TREE, QueryKind.CATALOG):
            with tempfile.TemporaryDirectory(prefix="fdu-spike-bounds-") as raw:
                root = Path(raw)
                for index in range(6):
                    (root / f"file-{index}.txt").write_text(str(index), encoding="utf-8")
                handle = await factory().open(root, InventoryConfig(watch_mode="off"))
                try:
                    await _settle(handle)
                    first = await handle.read(ReadRequest(queries=(make(kind, max_rows=2),)))
                    after = first.projection(kind).next_page
                    entry: dict[str, Any] = {}
                    for label, max_work in (("limited", 1), ("retry", 4)):
                        try:
                            read = await handle.read(
                                ReadRequest(
                                    queries=(
                                        make(kind, max_rows=4, max_work=max_work, after=after),
                                    ),
                                    at_version=first.version,
                                )
                            )
                            entry[label] = shape(read, kind)
                        except Exception as error:
                            entry[label] = {"error": f"{type(error).__name__}: {error}"[:160]}
                    halves[kind.value] = entry
                finally:
                    await handle.close()
        with tempfile.TemporaryDirectory(prefix="fdu-spike-limits-") as raw:
            root = Path(raw)
            for index in range(6):
                (root / f"file-{index}.txt").write_text(str(index), encoding="utf-8")
            handle = await factory().open(root, InventoryConfig(watch_mode="off"))
            try:
                await _settle(handle)
                queries = (
                    DirectoryQuery(query_id="directory", max_depth=1, max_work=2),
                    FilteredTreeQuery(query_id="filtered", max_depth=1, max_work=2),
                    RollupQuery(query_id="rollup", max_work=2),
                    NavigationQuery(query_id="navigation", max_work=2),
                    RecentQuery(query_id="recent", max_rows=1, as_of_ns=1, max_work=2),
                    CatalogQuery(query_id="catalog", max_rows=1, max_work=2),
                )
                bundle = await handle.read(ReadRequest(queries=queries))
                limits = {
                    query.query_id: {
                        "projection": type(bundle.projection(query.query_id)).__name__,
                        "limit_rows_visited": getattr(
                            bundle.projection(query.query_id), "rows_visited", None
                        ),
                    }
                    for query in queries
                }
                limits["bundle_work"] = {
                    "rows_visited": bundle.work.rows_visited,
                    "rows_returned": bundle.work.rows_returned,
                }
            finally:
                await handle.close()
        return {"continuation_halves": halves, "typed_limits": limits}

    return {"python": await one(PythonInventoryBackend), "fdu": await one(FduInventoryBackend)}


def rollup_etag_modes(runs: int) -> dict[str, Any]:
    """Repeat the rollup/ETag route case in isolation and count where it fails."""

    test = "tests/test_rollup_route.py::test_rollup_payload_and_etag_share_one_version"
    modes: dict[str, dict[str, int]] = {"python": {}, "fdu": {}}
    for _run in range(runs):
        for provider in ("python", "fdu"):
            outcome = run_selection((test,), AdapterProbe(), inject=provider == "fdu")
            built = cast("int", outcome["fdu_backends_built"])
            if (provider == "fdu") != (built > 0):
                raise RuntimeError(f"the {provider} isolation run built {built} fdu backends")
            for row in cast("list[dict[str, Any]]", outcome["results"]):
                key = (
                    "passed"
                    if row["outcome"] == "passed"
                    else _failing_assertion(cast("str", row["detail"]))
                )
                modes[provider][key] = modes[provider].get(key, 0) + 1
    return {"test": test, "runs_per_provider": runs, "outcomes": modes}


def _route_record(outcome: dict[str, object]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = [
        {
            "test": cast("str", row["test"]),
            "fdu_outcome": cast("str", row["outcome"]),
            "fdu_backends_built": cast("int", row["fdu_backends_built"]),
            "detail": cast("str", row["detail"])[-900:],
        }
        for row in cast("list[dict[str, object]]", outcome["results"])
    ]
    classify(rows, CLASSIFIED_ROUTES, "test")
    passed = [row for row in rows if row["fdu_outcome"] == "passed"]
    return {
        "selected": outcome["selected"],
        "pytest_exit_code": outcome["exit_code"],
        "fdu_backends_built": outcome["fdu_backends_built"],
        "tests": len(rows),
        "passed": len(passed),
        "passed_with_an_fdu_backend": sum(row["fdu_backends_built"] > 0 for row in passed),
        "passed_without_an_fdu_backend": [
            row["test"] for row in passed if row["fdu_backends_built"] == 0
        ],
        "failed": sum(row["fdu_outcome"] == "failed" for row in rows),
        "skipped": sum(row["fdu_outcome"] == "skipped" for row in rows),
        "setup_or_teardown_failures": outcome["setup_or_teardown_failures"],
        "failures": [
            {key: value for key, value in row.items() if key != "detail"}
            | {"detail": row["detail"][-500:]}
            for row in rows
            if row["fdu_outcome"] == "failed"
        ],
        "backends_per_test": {row["test"]: row["fdu_backends_built"] for row in rows},
    }


def _baseline_record(outcome: dict[str, object]) -> dict[str, Any]:
    results = cast("list[dict[str, object]]", outcome["results"])
    if outcome["fdu_backends_built"] or any(row["fdu_backends_built"] for row in results):
        raise RuntimeError("the Python baseline built an fdu backend: the injection leaked")
    return {
        "pytest_exit_code": outcome["exit_code"],
        "tests": len(results),
        "passed": sum(row["outcome"] == "passed" for row in results),
        "failed": [row["test"] for row in results if row["outcome"] == "failed"],
        "setup_or_teardown_failures": outcome["setup_or_teardown_failures"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    # The fdu checkout the wheel was built from, conventionally beside this checkout.
    parser.add_argument("--fdu-checkout", type=Path, default=FDU_CHECKOUT)
    # The frozen copy the timed series measured, so counts do not move with the working
    # tree; the live checkout when no copy has been made.
    frozen = REPO_ROOT / ".bench" / "corpus-checkout"
    parser.add_argument("--corpus", type=Path, default=frozen if frozen.is_dir() else REPO_ROOT)
    suffix = "" if sys.platform.startswith("linux") else f"-{sys.platform}"
    parser.add_argument(
        "--output", type=Path, default=HERE / "evidence" / f"correctness{suffix}.json"
    )
    parser.add_argument("--skip-routes", action="store_true")
    parser.add_argument("--etag-runs", type=int, default=6)
    # A wheel built on another platform has its own name and digest; name both, so the
    # check stays exact rather than being skipped.
    parser.add_argument("--expect-wheel-name", default=WHEEL_NAME)
    parser.add_argument("--expect-wheel-sha256", default=WHEEL_SHA256)
    args = parser.parse_args()

    record: dict[str, Any] = {"schema": "fdu-provider-spike-correctness-v2"}
    record["provenance"] = provenance(
        args.wheel.resolve(),
        args.fdu_checkout.resolve(),
        expected_name=args.expect_wheel_name,
        expected_sha256=args.expect_wheel_sha256,
    )
    record["sources_sha256"] = {
        name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        for name in (
            "adapter.py",
            "probe.py",
            "run.py",
            "conformance.py",
            "routes.py",
            "rollup_corpus.py",
        )
    }
    record["adapter_modes"] = {
        "image_memo": adapter.IMAGE_MEMO,
        "verify_extensions": adapter.VERIFY_EXTENSIONS,
        "native_max_page_rows": adapter.NATIVE_MAX_PAGE_ROWS,
    }
    probe = AdapterProbe()
    conformance_rows = run_conformance(probe)
    table = [
        {
            "test": row["test"],
            "registered": row["registered"],
            "python_outcome": cast("dict[str, Any]", row["python"])["outcome"],
            "fdu_outcome": cast("dict[str, Any]", row["fdu"])["outcome"],
            "fdu_detail": str(cast("dict[str, Any]", row["fdu"])["detail"])[-1200:],
        }
        for row in conformance_rows
    ]
    classify(table, CLASSIFIED, "test")
    record["conformance"] = table
    record["conformance_probe"], conformance_timings = _split_probe(probe.snapshot())
    record["semantic_digest_with_provider_identity_masked"] = {
        "outcome": masked_digest()["outcome"]
    }
    record["work_bounds_by_half"] = asyncio.run(work_bounds_by_half())
    record["file_rollup_corpus"] = run_corpus(AdapterProbe())
    record["lifecycle"] = asyncio.run(lifecycle(AdapterProbe()))
    record["identity_and_bounds"] = asyncio.run(identity_and_bounds())
    record["representative_read"] = asyncio.run(representative(args.corpus.resolve(), probe))
    record["volatile"] = {"conformance_probe_timings": conformance_timings}
    if not args.skip_routes:
        route_records: dict[str, Any] = {}
        for name, selection in (("selected_2a", SELECTED_2A), ("inventory_suites", SELECTED_NEWER)):
            route_records[name] = _route_record(
                run_selection(selection, AdapterProbe(), inject=True)
            )
            route_records[name]["python_baseline"] = _baseline_record(
                run_selection(selection, AdapterProbe(), inject=False)
            )
        record["routes"] = route_records
        record["rollup_etag_modes"] = rollup_etag_modes(args.etag_runs)
    unclassified = [row["test"] for row in table if row["class"] == "unclassified"]
    for route in cast("dict[str, Any]", record.get("routes", {})).values():
        unclassified += [row["test"] for row in route["failures"] if row["class"] == "unclassified"]
    record["unclassified_failures"] = unclassified
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_normalize(record), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    biome = REPO_ROOT / "node_modules/.bin/biome"
    if biome.is_file():
        subprocess.run(
            [str(biome), "format", "--write", str(args.output)], cwd=REPO_ROOT, check=False
        )
    print(args.output)
    print("unclassified:", unclassified)
    return int(bool(unclassified))


if __name__ == "__main__":
    raise SystemExit(main())
