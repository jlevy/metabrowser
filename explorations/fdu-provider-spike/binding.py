"""Where fdu's per-row cost goes: native read, Python value rebuild, adapter conversion.

For each repetition and row shape, every page of a full-index ``Flat`` read is timed in
three parts: ``_native.read`` (the Rust engine plus PyO3 building its wire dictionaries),
``fdu.opened._read_response`` (rebuilding those dictionaries as the public dataclasses),
and, for the ``FULL`` shape, the adapter's conversion into the oracle's record. The
catalog and directory pages Metabrowser asks for are split the same way and set beside
each provider's whole answer at a fresh version (a marker file is refreshed first).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from adapter import FduInventoryBackend, FduInventoryHandle
from bench import OUT, host_record
from fdu import opened as fdu

from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    DirectoryQuery,
    LifecyclePhase,
    ReadQuery,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
)
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend
from metabrowser.inventory_engine.runtime import default_inventory_config

MARKER = "fdu-spike-binding-marker.tmp"


def _split(handle: FduInventoryHandle, first: fdu.Projection) -> dict[str, float]:
    """Time every page of one native read in its three parts."""

    native_index = handle._index._native
    projection = first
    native_s = convert_s = adapter_s = 0.0
    rows = pages = 0
    while True:
        pages += 1
        wire = [fdu._projection_wire(projection)]
        started = time.perf_counter()
        raw = native_index.read(wire, expected=None)
        native_s += time.perf_counter() - started
        started = time.perf_counter()
        response = fdu._read_response(raw)
        convert_s += time.perf_counter() - started
        result = response.results[0]
        page_rows: tuple[fdu.Entry, ...]
        if isinstance(result, fdu.FlatResult):
            page_rows, continuation = result.value.rows, result.value.next
        elif isinstance(result, fdu.TreeResult) and result.value.value is not None:
            page_rows, continuation = result.value.value.rows, result.value.value.next
        else:
            raise RuntimeError(f"unexpected native result {result.kind}")
        started = time.perf_counter()
        for row in page_rows:
            handle._fs_entry(row, complete=True)
        adapter_s += time.perf_counter() - started
        rows += len(page_rows)
        if continuation is None:
            break
        projection = fdu.Continue(continuation=continuation, page=fdu.Page(limit=4_096))
    per_row = 1e6 / max(1, rows)
    return {
        "rows": rows,
        "pages": pages,
        "native_read_ms": native_s * 1000,
        "python_rebuild_ms": convert_s * 1000,
        "adapter_convert_ms": adapter_s * 1000,
        "native_read_us_per_row": native_s * per_row,
        "python_rebuild_us_per_row": convert_s * per_row,
        "adapter_convert_us_per_row": adapter_s * per_row,
    }


def _stats(samples: list[dict[str, float]]) -> dict[str, Any]:
    keys = [key for key in samples[0] if key not in {"rows", "pages"}]
    return {
        "rows": samples[0]["rows"],
        "pages": samples[0]["pages"],
        "reps": len(samples),
        **{
            key: {
                "median": round(statistics.median(sample[key] for sample in samples), 3),
                "min": round(min(sample[key] for sample in samples), 3),
                "max": round(max(sample[key] for sample in samples), 3),
            }
            for key in keys
        },
    }


async def _open(factory: Any, root: Path) -> Any:
    config = replace(default_inventory_config(), watch_mode="off")
    handle = await factory().open(root, config)
    while True:
        if (await handle.read(ReadRequest())).state.phase is not LifecyclePhase.DISCOVERING:
            return handle
        await asyncio.sleep(0.01)


async def _whole(handle: Any, root: Path, query: ReadQuery, reps: int) -> dict[str, float]:
    times: list[float] = []
    for rep in range(reps):
        (root / MARKER).write_text(str(rep), encoding="utf-8")
        await handle.refresh(RefreshRequest(observations=(RefreshObservation(MARKER),)))
        started = time.perf_counter()
        await handle.read(ReadRequest(queries=(query,)))
        times.append((time.perf_counter() - started) * 1000)
    return {
        "median_ms": round(statistics.median(times), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
    }


async def measure(root: Path, reps: int) -> dict[str, Any]:
    handle: FduInventoryHandle = await _open(FduInventoryBackend, root)
    python = await _open(PythonInventoryBackend, root)
    catalog = CatalogQuery(query_id="q", max_rows=10_000)
    directory = DirectoryQuery(query_id="q", max_depth=2, max_rows=10_000)
    try:
        full_index = {
            shape.value: _stats(
                [
                    _split(handle, fdu.Flat(shape=shape, page=fdu.Page(limit=4_096)))
                    for _rep in range(reps)
                ]
            )
            for shape in (fdu.RowShape.FULL, fdu.RowShape.COMPACT)
        }
        catalog_split = _stats(
            [
                _split(
                    handle,
                    fdu.Flat(
                        selection=handle._catalog_selection(catalog),
                        shape=fdu.RowShape.COMPACT,
                        page=fdu.Page(limit=4_096),
                    ),
                )
                for _rep in range(reps)
            ]
        )
        directory_split = _stats(
            [
                _split(handle, fdu.Tree(path="", page=fdu.Page(limit=4_096), depth=2))
                for _rep in range(reps)
            ]
        )
        whole = {
            "catalog_10000": {
                "fdu": await _whole(handle, root, catalog, reps),
                "python": await _whole(python, root, catalog, reps),
            },
            "directory_depth2": {
                "fdu": await _whole(handle, root, directory, reps),
                "python": await _whole(python, root, directory, reps),
            },
        }
    finally:
        (root / MARKER).unlink(missing_ok=True)
        await handle.close()
        await python.close()
    return {
        "full_index": full_index,
        "catalog_page_split": catalog_split,
        "directory_page_split": directory_split,
        "whole_answer_at_fresh_version": whole,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    record = {
        "host": host_record(),
        "corpus": args.label,
        "binding_split": asyncio.run(measure(args.corpus.resolve(), args.reps)),
    }
    out = OUT / f"binding-{args.label}.json"
    out.write_text(json.dumps(record, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
