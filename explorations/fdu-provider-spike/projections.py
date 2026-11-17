"""Per-projection read latency at fresh versions, Python versus fdu, in one process.

Each sample first writes a marker file and refreshes it, so the provider is at a new
version and neither side answers from a per-version memo; then one query is read and
timed. Kinds and providers alternate sample by sample. A second record prices fdu's
binding: native flat pages per row (FULL and COMPACT shapes) and the adapter's per-row
conversion into the oracle's record, which every temporary fallback pays.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from adapter import FduInventoryBackend, FduInventoryHandle
from bench import OUT, host_record, summarize
from fdu import opened as fdu

from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    DiagnosticsQuery,
    DirectoryQuery,
    EntryQuery,
    FilteredTreeQuery,
    GroupedTreeQuery,
    InventoryFilter,
    LifecyclePhase,
    NavigationQuery,
    ReadQuery,
    ReadRequest,
    RecentQuery,
    RefreshObservation,
    RefreshRequest,
    RollupQuery,
    TreeGroupFilter,
)
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend
from metabrowser.inventory_engine.runtime import default_inventory_config

MARKER = "fdu-spike-projection-marker.tmp"


def queries(as_of_ns: int) -> dict[str, ReadQuery]:
    return {
        "entry_root": EntryQuery(query_id="q", path=""),
        "directory_depth2": DirectoryQuery(query_id="q", max_depth=2, max_rows=10_000),
        "catalog_page_10000": CatalogQuery(query_id="q", max_rows=10_000),
        "filtered_md_depth3": FilteredTreeQuery(
            query_id="q", max_depth=3, max_rows=10_000, filter=InventoryFilter(extensions=(".md",))
        ),
        "grouped_type_depth2": GroupedTreeQuery(
            query_id="q",
            max_depth=2,
            max_rows=10_000,
            groups=(
                TreeGroupFilter(key="code", type_group="code"),
                TreeGroupFilter(key="docs", type_group="docs"),
                TreeGroupFilter(key="other", type_group="other"),
            ),
        ),
        "rollup_overview": RollupQuery(
            query_id="q", max_depth=0, top=0, extension_top=0, rank="dual", max_work=1_000_000
        ),
        "rollup_treemap": RollupQuery(query_id="q", max_depth=3, max_work=1_000_000),
        "navigation": NavigationQuery(query_id="q", max_rows=200),
        "recent_200": RecentQuery(query_id="q", max_rows=200, as_of_ns=as_of_ns),
        "diagnostics": DiagnosticsQuery(query_id="q"),
    }


async def _open(factory: Any, root: Path) -> Any:
    config = default_inventory_config()
    from dataclasses import replace

    handle = await factory().open(root, replace(config, watch_mode="off"))
    while True:
        result = await handle.read(ReadRequest())
        if result.state.phase is not LifecyclePhase.DISCOVERING:
            return handle
        await asyncio.sleep(0.01)


async def latency(root: Path, samples: int) -> dict[str, Any]:
    handles = {
        "python": await _open(PythonInventoryBackend, root),
        "fdu": await _open(FduInventoryBackend, root),
    }
    marker = root / MARKER
    records: dict[str, dict[str, list[float]]] = {
        provider: {kind: [] for kind in queries(1)} for provider in handles
    }
    limits: dict[str, dict[str, int]] = {provider: {} for provider in handles}
    try:
        for sample in range(samples):
            as_of_ns = time.time_ns()
            for kind, query in queries(as_of_ns).items():
                order = list(handles) if sample % 2 == 0 else list(reversed(handles))
                for provider in order:
                    handle = handles[provider]
                    marker.write_text(f"{sample}-{kind}-{provider}", encoding="utf-8")
                    await handle.refresh(RefreshRequest(observations=(RefreshObservation(MARKER),)))
                    started = time.perf_counter()
                    result = await handle.read(ReadRequest(queries=(query,)))
                    elapsed = (time.perf_counter() - started) * 1000
                    projection = result.projections[0]
                    if type(projection).__name__ == "QueryLimitProjection":
                        limits[provider][kind] = limits[provider].get(kind, 0) + 1
                    records[provider][kind].append(elapsed)
    finally:
        marker.unlink(missing_ok=True)
        for handle in handles.values():
            await handle.close()
    return {
        "samples": samples,
        "ms": {
            provider: {kind: summarize(values) for kind, values in kinds.items()}
            for provider, kinds in records.items()
        },
        "query_limits": limits,
    }


async def binding(root: Path) -> dict[str, Any]:
    handle: FduInventoryHandle = await _open(FduInventoryBackend, root)
    try:
        index = handle._index
        result: dict[str, Any] = {}
        for shape in (fdu.RowShape.FULL, fdu.RowShape.COMPACT):
            page = fdu.Page(limit=4_096, max_work=1_000_000)
            projection: fdu.Projection = fdu.Flat(shape=shape, page=page)
            rows: list[fdu.Entry] = []
            calls = 0
            started = time.perf_counter()
            while True:
                calls += 1
                response = index.read(projection)
                flat = response.results[0]
                assert isinstance(flat, fdu.FlatResult)
                rows.extend(flat.value.rows)
                if flat.value.next is None:
                    break
                projection = fdu.Continue(continuation=flat.value.next, page=page)
            native_s = time.perf_counter() - started
            entry: dict[str, Any] = {
                "rows": len(rows),
                "native_calls": calls,
                "binding_us_per_row": round(native_s * 1e6 / max(1, len(rows)), 2),
                "binding_total_ms": round(native_s * 1000, 1),
            }
            if shape is fdu.RowShape.FULL:
                started = time.perf_counter()
                for row in rows:
                    handle._fs_entry(row, complete=True)
                convert_s = time.perf_counter() - started
                entry["adapter_convert_us_per_row"] = round(convert_s * 1e6 / max(1, len(rows)), 2)
                entry["adapter_convert_total_ms"] = round(convert_s * 1000, 1)
            result[shape.value] = entry
        return result
    finally:
        await handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    root = args.corpus.resolve()
    record = {
        "host": host_record(),
        "corpus": args.label,
        "binding": asyncio.run(binding(root)),
        "latency": asyncio.run(latency(root, args.samples)),
    }
    out = OUT / f"projections-{args.label}.json"
    out.write_text(json.dumps(record, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
