"""Run the unchanged-contract fdu adapter spike and publish raw JSON evidence."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib
import json
import re
import resource
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tracemalloc
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import fdu as fdu_package
import pytest
from adapter import FduSpikeBackend

from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    DiagnosticsQuery,
    DirectoryProjection,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryConfig,
    InventoryFilter,
    LifecyclePhase,
    NavigationQuery,
    ReadRequest,
    RecentProjection,
    RecentQuery,
    RefreshObservation,
    RefreshRequest,
    RollupQuery,
)
from metabrowser.inventory_engine.coordinator import InventoryCoordinator

_METABROWSER_PR74_HEAD = "3183888808b366b5ba1c381dec1cbb18b49d969e"
_FDU_REVISION = "0583a1a"
_FDU_WHEEL_SHA256 = "80a077ba17f979a40f30a8dcfe59b2ceeba39285cf556543d78066b9dc5279c0"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FDU_CHECKOUT = _REPO_ROOT.parents[1]


def _wheel_provenance(wheel: Path) -> dict[str, object]:
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != _FDU_WHEEL_SHA256:
        raise RuntimeError(f"wheel digest {digest} does not match the reviewed {_FDU_WHEEL_SHA256}")
    package_path = Path(fdu_package.__file__).resolve()
    source_tree = (_FDU_CHECKOUT / "crates/fdu-py/python").resolve()
    if package_path.is_relative_to(source_tree):
        raise RuntimeError(f"fdu leaked from the sibling source tree: {package_path}")
    return {
        "fdu_revision": _FDU_REVISION,
        "metabrowser_contract_revision": _METABROWSER_PR74_HEAD,
        "wheel": wheel.name,
        "wheel_sha256": digest,
        "import_origin": "uv-managed installed wheel",
        "source_tree_import": False,
    }


def _normalize_text(value: str) -> str:
    """Remove machine paths and generated identities before artifact serialization."""

    normalized = value.replace(str(Path.home()), "<HOME>")
    normalized = normalized.replace(str(_REPO_ROOT), "<METABROWSER>")
    normalized = normalized.replace(str(_FDU_CHECKOUT), "<FDU>")
    normalized = re.sub(r"/[^\s:]+/site-packages/", "<SITE_PACKAGES>/", normalized)
    normalized = re.sub(r"SessionId\(\d+\)", "SessionId([GENERATED])", normalized)
    normalized = re.sub(r"fdu-contract-[A-Za-z0-9._-]+", "fdu-contract-[GENERATED]", normalized)
    return normalized


def _normalize_artifact(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {
            str(item_key): _normalize_artifact(item, key=str(item_key))
            for item_key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_normalize_artifact(item) for item in sequence]
    if key == "session":
        return "[GENERATED]"
    if isinstance(value, str):
        return _normalize_text(value)
    return value


def _run_conformance(probe: Any) -> list[dict[str, object]]:
    tests_path = str(_REPO_ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    suite = importlib.import_module("test_inventory_provider_contract")
    results: list[dict[str, object]] = []
    for name in sorted(suite.PROVIDER_CONFORMANCE_TESTS):
        factory = lambda: FduSpikeBackend(probe=probe)
        started = time.monotonic_ns()
        with tempfile.TemporaryDirectory(prefix="fdu-contract-") as raw_root:
            try:
                getattr(suite, name)(factory, Path(raw_root))
            except pytest.skip.Exception as error:
                outcome = "skipped"
                detail = str(error)
            except BaseException as error:
                outcome = "failed"
                detail = "".join(
                    traceback.format_exception(type(error), error, error.__traceback__, limit=8)
                )
            else:
                outcome = "passed"
                detail = ""
        results.append(
            {
                "test": name,
                "outcome": outcome,
                "detail": detail,
                "wall_time_ns": time.monotonic_ns() - started,
            }
        )
    return results


async def _settle_handle(handle: Any, *, timeout: float = 10.0) -> Any:
    async with asyncio.timeout(timeout):
        while True:
            result = await handle.read(ReadRequest())
            if result.state.phase in {
                LifecyclePhase.READY,
                LifecyclePhase.WATCHING,
                LifecyclePhase.FAILED,
                LifecyclePhase.STOPPED,
            }:
                return result
            await asyncio.sleep(0.005)


async def _representative_read(
    backend: FduSpikeBackend,
    corpus: Path,
) -> dict[str, object]:
    config = InventoryConfig(watch_mode="off")
    handle = await backend.open(corpus, config)
    try:
        settled = await _settle_handle(handle, timeout=30.0)
        as_of_ns = time.time_ns()
        tracemalloc.start()
        peak_rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result = await handle.read(
            ReadRequest(
                queries=(
                    EntryQuery(query_id="root", path=""),
                    DirectoryQuery(
                        query_id="directory",
                        max_depth=2,
                        max_rows=10_000,
                    ),
                    FilteredTreeQuery(
                        query_id="markdown",
                        max_depth=4,
                        max_rows=10_000,
                        filter=InventoryFilter(extensions=(".md",)),
                    ),
                    RollupQuery(query_id="rollup", max_depth=4, max_nodes=50_000),
                    NavigationQuery(query_id="navigation", max_rows=200),
                    RecentQuery(
                        query_id="recent",
                        max_rows=200,
                        as_of_ns=as_of_ns,
                        include_ignored=True,
                    ),
                    CatalogQuery(
                        query_id="catalog",
                        max_rows=10_000,
                        include_ignored=True,
                    ),
                    DiagnosticsQuery(query_id="diagnostics"),
                )
            )
        )
        _current, python_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        directory_projection = result.projection("directory")
        markdown_projection = result.projection("markdown")
        recent_projection = result.projection("recent")
        catalog_projection = result.projection("catalog")
        if not isinstance(directory_projection, DirectoryProjection):
            raise AssertionError("directory query returned the wrong projection")
        if not isinstance(markdown_projection, FilteredTreeProjection):
            raise AssertionError("filtered tree query returned the wrong projection")
        if not isinstance(recent_projection, RecentProjection):
            raise AssertionError("recent query returned the wrong projection")
        if not isinstance(catalog_projection, CatalogProjection):
            raise AssertionError("catalog query returned the wrong projection")
        return {
            "root": "metabrowser-repository" if corpus == _REPO_ROOT else corpus.name,
            "settled_phase": settled.state.phase.value,
            "version": asdict(result.version),
            "rows_returned": result.work.rows_returned,
            "python_peak_bytes": python_peak,
            "process_peak_rss_before": peak_rss_before,
            "process_peak_rss_after": peak_rss_after,
            "projection_rows": {
                "directory": len(directory_projection.entries),
                "markdown": len(markdown_projection.entries),
                "recent": len(recent_projection.entries),
                "catalog": len(catalog_projection.records),
            },
        }
    finally:
        await handle.close()


async def _next_matching_change(stream: Any, path: str, *, timeout: float = 10.0) -> Any:
    async with asyncio.timeout(timeout):
        async for change in stream:
            if change.reset or change.all_dirty or path in change.dirty_paths:
                return change
    raise AssertionError(f"no change arrived for {path}")


async def _lifecycle(backend: FduSpikeBackend) -> dict[str, object]:
    worker_prefix = "metabrowser-fdu-spike-poll"
    workers_before = sum(thread.name.startswith(worker_prefix) for thread in threading.enumerate())
    with (
        tempfile.TemporaryDirectory(prefix="fdu-lifecycle-a-") as first_raw,
        tempfile.TemporaryDirectory(prefix="fdu-lifecycle-b-") as second_raw,
    ):
        first_root = Path(first_raw)
        second_root = Path(second_raw)
        (first_root / "seed.txt").write_text("seed", encoding="utf-8")
        (second_root / "replacement.txt").write_text("replacement", encoding="utf-8")
        config = InventoryConfig()
        coordinator = InventoryCoordinator(backend=backend, config=config)
        try:
            await coordinator.open(first_root)
            first_read = await coordinator.read(
                ReadRequest(
                    queries=(
                        EntryQuery(query_id="root", path=""),
                        DirectoryQuery(query_id="useful", max_depth=2, max_rows=20),
                    )
                )
            )
            async with asyncio.timeout(10.0):
                while first_read.result.state.phase not in {
                    LifecyclePhase.READY,
                    LifecyclePhase.WATCHING,
                }:
                    await asyncio.sleep(0.01)
                    first_read = await coordinator.read(
                        ReadRequest(
                            queries=(
                                EntryQuery(query_id="root", path=""),
                                DirectoryQuery(
                                    query_id="useful",
                                    max_depth=2,
                                    max_rows=20,
                                ),
                            )
                        )
                    )
            checkpoint, _version, _state = await coordinator.checkpoint()
            host_stream = coordinator.changes(after=checkpoint)
            live_path = "live.txt"
            (first_root / live_path).write_text("live", encoding="utf-8")
            live_change = await _next_matching_change(host_stream, live_path)
            reread = await coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="live", path=live_path),))
            )
            live_projection = reread.result.projection("live")
            if not isinstance(live_projection, EntryProjection):
                raise AssertionError("live reread returned the wrong projection")
            if live_projection.presence is not EntryPresence.PRESENT:
                raise AssertionError("live reread did not observe the new file")

            refresh_path = "refresh.txt"
            (first_root / refresh_path).write_text("refresh", encoding="utf-8")
            receipt = await coordinator.refresh(
                RefreshRequest(observations=(RefreshObservation(path=refresh_path),))
            )
            if receipt.accepted_paths != (refresh_path,):
                raise AssertionError("refresh receipt did not preserve the request")
            await host_stream.aclose()

            replacement_version = await coordinator.replace_root(second_root)
            replacement = await coordinator.read(
                ReadRequest(queries=(EntryQuery(query_id="replacement", path="replacement.txt"),))
            )
            replacement_projection = replacement.result.projection("replacement")
            if not isinstance(replacement_projection, EntryProjection):
                raise AssertionError("replacement root returned the wrong projection")
            if replacement_projection.presence is not EntryPresence.PRESENT:
                raise AssertionError("replacement root was not visible")
        finally:
            await coordinator.close()

        cancellation_handle = await backend.open(
            first_root,
            InventoryConfig(watch_mode="off"),
        )
        await _settle_handle(cancellation_handle)
        cancellation_checkpoint = await cancellation_handle.read(ReadRequest())
        cancellation_stream = cancellation_handle.changes(after=cancellation_checkpoint.cursor)
        waiter = asyncio.ensure_future(anext(cancellation_stream))
        await asyncio.sleep(0.02)
        cancel_started = time.monotonic_ns()
        waiter.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await waiter
        cancellation_ns = time.monotonic_ns() - cancel_started
        usable_after_cancel = await cancellation_handle.read(ReadRequest())
        await asyncio.gather(cancellation_handle.close(), cancellation_handle.close())

    workers_after = sum(thread.name.startswith(worker_prefix) for thread in threading.enumerate())
    first_useful = first_read.result.projection("useful")
    if not isinstance(first_useful, DirectoryProjection):
        raise AssertionError("useful query returned the wrong projection")
    return {
        "first_phase": first_read.result.state.phase.value,
        "first_useful_rows": len(first_useful.entries),
        "live_change": {
            "reset": live_change.reset,
            "all_dirty": live_change.all_dirty,
            "dirty_paths": live_change.dirty_paths,
        },
        "refresh_version": asdict(receipt.version),
        "replacement_version": asdict(replacement_version.engine),
        "iterator_cancel_ns": cancellation_ns,
        "usable_after_iterator_cancel": usable_after_cancel.state.phase.value,
        "poll_workers_before": workers_before,
        "poll_workers_after": workers_after,
    }


class _RouteResultPlugin:
    def __init__(self, probe: Any) -> None:
        self.probe = probe
        self.results: list[dict[str, object]] = []

    def pytest_configure(self) -> None:
        runtime = importlib.import_module("metabrowser.inventory_engine.runtime")
        runtime.create_inventory_backend = lambda _provider: FduSpikeBackend(  # type: ignore[attr-defined]
            probe=self.probe
        )

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when != "call":
            return
        self.results.append(
            {
                "test": report.nodeid,
                "outcome": report.outcome,
                "detail": str(report.longrepr) if report.failed else "",
                "wall_time_s": report.duration,
            }
        )


def _run_route_tests(probe: Any) -> dict[str, object]:
    plugin = _RouteResultPlugin(probe)
    selected = (
        "tests/test_browser_inventory_api.py",
        "tests/test_browser_lifespan_e2e.py::test_full_lifespan_stack_serves_all_endpoints",
        "tests/test_browser_lifespan_e2e.py::test_recent_filter_includes_logs_state_files",
        "tests/test_e2e_filesystem_to_sse.py",
    )
    exit_code = pytest.main(["-q", "--tb=short", *selected], plugins=[plugin])
    return {
        "exit_code": int(exit_code),
        "selected": selected,
        "results": plugin.results,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=_REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("evidence.json"),
    )
    parser.add_argument("--skip-routes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    provenance = _wheel_provenance(args.wheel)
    backend = FduSpikeBackend()
    conformance = _run_conformance(backend.probe)
    representative = asyncio.run(_representative_read(backend, args.corpus.resolve()))
    try:
        lifecycle: dict[str, object] = {
            "outcome": "passed",
            "evidence": asyncio.run(_lifecycle(backend)),
        }
    except BaseException as error:
        lifecycle = {
            "outcome": "failed",
            "detail": "".join(
                traceback.format_exception(type(error), error, error.__traceback__, limit=12)
            ),
        }
    route_tests = {"skipped": True} if args.skip_routes else _run_route_tests(backend.probe)
    probe_snapshot = backend.probe.snapshot()
    observations = probe_snapshot["read_observations"]
    probe_snapshot["read_observations"] = [
        observation for observation in observations if observation["query_kinds"]
    ]
    probe_snapshot["omitted_checkpoint_observations"] = sum(
        not observation["query_kinds"] for observation in observations
    )
    artifact = _normalize_artifact(
        {
            "schema": "fdu-metabrowser-spike-v1",
            "provenance": provenance,
            "corpus": representative,
            "conformance": conformance,
            "lifecycle": lifecycle,
            "route_tests": route_tests,
            "probe": probe_snapshot,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    formatter = _REPO_ROOT / "node_modules/.bin/biome"
    if not formatter.is_file():
        raise RuntimeError("run `make install` before publishing spike evidence")
    subprocess.run(
        [str(formatter), "format", "--write", str(args.output)],
        cwd=_REPO_ROOT,
        check=True,
    )
    print(args.output.resolve())
    failures = sum(item["outcome"] == "failed" for item in conformance)
    if lifecycle["outcome"] == "failed":
        failures += 1
    if not args.skip_routes and route_tests["exit_code"] != 0:
        failures += 1
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
