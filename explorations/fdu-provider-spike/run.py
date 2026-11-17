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

import adapter  # noqa: E402
import fdu as fdu_package  # noqa: E402
from adapter import FduInventoryBackend  # noqa: E402
from conformance import provider_cases, run_case, run_conformance  # noqa: E402
from probe import AdapterProbe  # noqa: E402
from rollup_corpus import run_corpus  # noqa: E402
from routes import SELECTED_2A, SELECTED_NEWER, run_selection  # noqa: E402

from metabrowser.inventory_engine.contract import (  # noqa: E402
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
from metabrowser.inventory_engine.coordinator import InventoryCoordinator  # noqa: E402
from metabrowser.inventory_engine.runtime import default_inventory_config  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FDU_REVISION = "4450be7"
FDU_VERSION = "0.6.0"
WHEEL_NAME = "fdu-0.6.0-cp312-abi3-manylinux_2_34_x86_64.whl"
WHEEL_SHA256 = "d4b9071b377be9201ad95dedaebc19328e0a255cd76dc072fe5fa0cc91fdac1f"

# (a) adapter bug, (b) fdu gap, (c) Metabrowser contract over-specification,
# (d) test reaches into Python-provider internals (or the spike's own injection).
CLASSIFIED: dict[str, tuple[str, str]] = {
    "test_provider_semantic_digest": (
        "d",
        "The test asserts diagnostics.provider == 'python'. Every filesystem fact, order, "
        "aggregate, filter, rollup, navigation, recent, and catalog value matches; the "
        "masked rerun (`semantic_digest_with_provider_identity_masked`) passes.",
    ),
    "test_provider_applies_work_bounds_to_continuation_pages": (
        "b",
        "Directory half only (catalog and filtered-tree halves pass with Python's exact "
        "work numbers). fdu's tree max_work is a soft budget (fdu plan: fdu-pokc, "
        "fdu-3v0d), so a max_work=1 continuation returns rows instead of a typed limit, "
        "and that read consumes the single-use continuation, so the retry is unavailable.",
    ),
    "test_provider_returns_typed_query_limits_without_partial_answers": (
        "b",
        "The directory query returns rows under max_work=2 for the same soft-budget reason; "
        "the five other kinds return the typed limit with rows_visited=2. The bundle's "
        "rows_visited total then differs from 12 because the directory rows were charged.",
    ),
    "test_provider_budget_stop_is_explicit_and_absence_remains_unknown": (
        "c",
        "The test assumes the 2-file budget admits a.txt and b.txt (Python's sorted "
        "admission). The contract orders traversal breadth-first but not admission within "
        "one directory; fdu admitted a different pair (readdir order), so z.txt is present "
        "and a.txt, never retained, is correctly rejected by refresh. Stopped phase, budget "
        "coverage, resource_budget issue, and watch_state/reason all match.",
    ),
    "test_provider_changes_resume_and_report_history_gaps_as_reset": (
        "c",
        "change_queue_size=1 asks for a gap after two batches. fdu budgets its journal in "
        "bytes with a 64 KiB floor (MIN_JOURNAL_CAPACITY_BYTES), so two small refreshes "
        "stay replayable and no reset is due. The contract should state capacity as a "
        "minimum a provider retains, not a maximum it must forget beyond.",
    ),
}
CLASSIFIED_ROUTES: dict[str, tuple[str, str]] = {
    "tests/test_browser_inventory_api.py::test_api_tree_uses_pending_inventory_without_filesystem_fallback": (
        "d",
        "Monkeypatches python_inventory.walk_tree to hold discovery open; fdu's native "
        "discovery has no such seam (same finding as 2A: needs a provider-owned scripted "
        "discovery barrier).",
    ),
    "tests/test_browser_lifespan_e2e.py::test_watcher_detects_new_file_after_walker_completes": (
        "b",
        "Uses watch_mode='poll'. fdu 0.6.0 has no polling observer; the adapter refuses it "
        "with a typed InventoryContractError rather than faking one.",
    ),
    "tests/test_browser_walk.py::test_tree_dump_honors_inventory_provider_selection": (
        "d",
        "Asserts the sealed factory rejects an unknown provider name; the spike's injection "
        "replaces that constructor, so the assertion cannot hold under injection.",
    ),
    "tests/test_api_folder_envelope.py::test_root_directory_envelope_and_pending_state": (
        "d",
        "Monkeypatches python_inventory.walk_tree to block discovery.",
    ),
    "tests/test_rollup_route.py::test_rollup_payload_and_etag_share_one_version": (
        "c",
        "Gates python_inventory.build_rollup (engaged only because the spike's rollup is the "
        "Python oracle) and asserts the host version holds right after refresh. fdu's "
        "refresh publishes three native commits (freshness->reconciling, insert, "
        "verified->fresh); the receipt names the terminal one, but the host relay can still "
        "be publishing the intermediate one when refresh returns. The contract permits "
        "sub-batches; the coordinator does not wait for its relay to reach the receipt.",
    ),
    "tests/test_catalog_feed_server.py::test_api_catalog_is_incomplete_while_discovery_is_blocked": (
        "d",
        "Monkeypatches python_inventory.walk_tree to block discovery.",
    ),
    "tests/test_catalog_feed_server.py::test_walker_completion_projects_capability_update": (
        "d",
        "Monkeypatches python_inventory.walk_tree to slow discovery and waits on it.",
    ),
    "tests/test_browser_events_route.py::test_api_index_progress_does_not_304_while_active": (
        "d",
        "Monkeypatches python_inventory.walk_tree to hold discovery active.",
    ),
}


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def provenance(wheel: Path, fdu_checkout: Path) -> dict[str, Any]:
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if wheel.name != WHEEL_NAME or digest != WHEEL_SHA256:
        raise RuntimeError(f"wheel {wheel.name} {digest} is not the reviewed {WHEEL_SHA256}")
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
        return {
            "corpus": "metabrowser-checkout" if corpus == REPO_ROOT else corpus.name,
            "settled_phase": settled.state.phase.value,
            "settle_s": round(time.monotonic() - settled_started, 3),
            "files": settled.state.progress.entries_observed,
            "bundle_wall_ms": round(wall_ms, 1),
            "bundle_python_peak_bytes": peak,
            "projection_rows": rows,
            "work": result.work.__dict__ if hasattr(result.work, "__dict__") else str(result.work),
            "rows_returned": result.work.rows_returned,
            "probe": probe.snapshot(),
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
    prefix = "metabrowser-fdu-spike-poll"
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
            "latency_ms": round(live_ms, 1),
        },
        "live_reread_presence": live_projection.presence.value,
        "refresh_accepted": list(receipt.accepted_paths),
        "replacement_presence": replacement.presence.value,
        "iterator_cancel_ms": round(cancel_ms, 1),
        "usable_after_iterator_cancel": usable.state.phase.value,
        "poll_workers_before": before,
        "poll_workers_after": after,
        "present": live_projection.presence is EntryPresence.PRESENT,
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
                    "directory_order": [entry.path for entry in getattr(directory, "entries")],
                    "catalog_order": [record.path for record in getattr(catalog, "records")],
                    "backslash_lookup": getattr(lookup, "presence").value,
                    "forty_entry_bundle_present": sum(
                        getattr(item, "presence") is EntryPresence.PRESENT
                        for item in many.projections
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


def _normalize(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {str(k): _normalize(v, key=str(k)) for k, v in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast("list[object] | tuple[object, ...]", value)
        return [_normalize(item) for item in sequence]
    if isinstance(value, str):
        text = value.replace(str(REPO_ROOT), "<METABROWSER>")
        text = text.replace(str(Path("/home/user/fdu")), "<FDU>")
        text = text.replace(str(Path.home()), "<HOME>")
        text = re.sub(r"/[^\s'\":]*/site-packages/", "<SITE_PACKAGES>/", text)
        text = re.sub(r"/tmp/[^\s'\":]*", "<TMP>", text)
        text = re.sub(r"fdu:[0-9a-f]{16}", "fdu:<SESSION>", text)
        text = re.sub(r"session='[0-9a-f]{32}'", "session='<SESSION>'", text)
        return text
    if key in {"wall_time_ms", "wall_time_s"} and isinstance(value, float):
        return round(value, 1)
    return value


def classify(rows: list[dict[str, Any]], table: dict[str, tuple[str, str]], key: str) -> None:
    for row in rows:
        failed = row["fdu_outcome"] == "failed"
        known = table.get(row[key])
        row["class"] = known[0] if failed and known else ("unclassified" if failed else None)
        row["root_cause"] = known[1] if failed and known else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--fdu-checkout", type=Path, default=Path("/home/user/fdu"))
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=HERE / "evidence" / "correctness.json")
    parser.add_argument("--skip-routes", action="store_true")
    args = parser.parse_args()

    record: dict[str, Any] = {"schema": "fdu-provider-spike-correctness-v1"}
    record["provenance"] = provenance(args.wheel.resolve(), args.fdu_checkout.resolve())
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
    record["conformance_probe"] = probe.snapshot()
    record["semantic_digest_with_provider_identity_masked"] = masked_digest()
    record["file_rollup_corpus"] = run_corpus(AdapterProbe())
    record["lifecycle"] = asyncio.run(lifecycle(AdapterProbe()))
    record["identity_and_bounds"] = asyncio.run(identity_and_bounds())
    record["representative_read"] = asyncio.run(representative(args.corpus.resolve(), probe))
    if not args.skip_routes:
        route_records: dict[str, Any] = {}
        for name, selection in (("selected_2a", SELECTED_2A), ("inventory_suites", SELECTED_NEWER)):
            outcome = run_selection(selection, AdapterProbe(), inject=True)
            rows = [
                {
                    "test": cast("str", row["test"]),
                    "fdu_outcome": cast("str", row["outcome"]),
                    "detail": cast("str", row["detail"])[-900:],
                }
                for row in cast("list[dict[str, object]]", outcome["results"])
            ]
            classify(rows, CLASSIFIED_ROUTES, "test")
            route_records[name] = {
                "selected": outcome["selected"],
                "fdu_backends_built": outcome["fdu_backends_built"],
                "passed": sum(row["fdu_outcome"] == "passed" for row in rows),
                "failed": sum(row["fdu_outcome"] == "failed" for row in rows),
                "skipped": sum(row["fdu_outcome"] == "skipped" for row in rows),
                "failures": [row for row in rows if row["fdu_outcome"] == "failed"],
            }
        record["routes"] = route_records
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
        subprocess.run([str(biome), "format", "--write", str(args.output)], cwd=REPO_ROOT, check=False)
    print(args.output)
    print("unclassified:", unclassified)
    return int(bool(unclassified))


if __name__ == "__main__":
    raise SystemExit(main())
