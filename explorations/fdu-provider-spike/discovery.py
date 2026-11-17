"""Open to first successful read, per projection kind, while discovery is running.

One fresh handle per (provider, kind) sample, opened with observation off. The kind's
query is read in a tight loop from the moment ``open`` returns; the record is the time
of the first answer that is not a typed limit, how many reads raised
``VersionUnavailableError`` first, and whether discovery had finished by then. For fdu
the fallback kinds need a multi-page image pinned to one version, which discovery keeps
moving, so this measures how long the temporary fallbacks leave a client waiting.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from adapter import FduInventoryBackend
from bench import OUT, host_record, summarize
from probe import AdapterProbe

from metabrowser.inventory_engine.contract import (
    DirectoryQuery,
    EntryQuery,
    LifecyclePhase,
    NavigationQuery,
    ReadQuery,
    ReadRequest,
    RollupQuery,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend
from metabrowser.inventory_engine.runtime import default_inventory_config

KINDS: dict[str, ReadQuery] = {
    "entry_root": EntryQuery(query_id="q", path=""),
    "directory_depth1": DirectoryQuery(query_id="q", max_depth=1, max_rows=500),
    "rollup_overview": RollupQuery(
        query_id="q", max_depth=0, top=0, extension_top=0, rank="dual", max_work=1_000_000
    ),
    "navigation": NavigationQuery(query_id="q", max_rows=200),
}


async def sample(provider: str, kind: str, root: Path) -> dict[str, Any]:
    probe = AdapterProbe()
    backend = FduInventoryBackend(probe=probe) if provider == "fdu" else PythonInventoryBackend()
    config = replace(default_inventory_config(), watch_mode="off")
    started = time.monotonic()
    handle = await backend.open(root, config)
    opened_s = time.monotonic() - started
    unavailable = 0
    reads = 0
    first_s: float | None = None
    phase_at_first: str | None = None
    try:
        while time.monotonic() - started < 300:
            reads += 1
            try:
                result = await handle.read(ReadRequest(queries=(KINDS[kind],)))
            except VersionUnavailableError:
                unavailable += 1
                continue
            if type(result.projections[0]).__name__ != "QueryLimitProjection":
                first_s = time.monotonic() - started
                phase_at_first = result.state.phase.value
                break
            await asyncio.sleep(0.001)
        settled_s: float | None = None
        while time.monotonic() - started < 300:
            state = (await handle.read(ReadRequest())).state
            if state.phase is not LifecyclePhase.DISCOVERING:
                settled_s = time.monotonic() - started
                break
            await asyncio.sleep(0.005)
    finally:
        await handle.close()
    return {
        "provider": provider,
        "kind": kind,
        "open_returned_s": round(opened_s, 4),
        "first_answer_s": round(first_s, 4) if first_s is not None else None,
        "phase_at_first_answer": phase_at_first,
        "reads": reads,
        "version_unavailable": unavailable,
        "retries_inside_adapter": probe.snapshot()["read_retries"],
        "settled_s_after_first": round(settled_s, 4) if settled_s is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    root = args.corpus.resolve()
    rows: list[dict[str, Any]] = []
    for trial in range(args.trials):
        for kind in KINDS:
            order = ("python", "fdu") if trial % 2 == 0 else ("fdu", "python")
            for provider in order:
                rows.append({"trial": trial, **asyncio.run(sample(provider, kind, root))})
    summary: dict[str, Any] = {}
    for provider in ("python", "fdu"):
        for kind in KINDS:
            mine = [row for row in rows if row["provider"] == provider and row["kind"] == kind]
            firsts = [row["first_answer_s"] * 1000 for row in mine if row["first_answer_s"]]
            summary[f"{provider}:{kind}"] = {
                "first_answer_ms": summarize(firsts),
                "phases_at_first_answer": sorted(
                    {str(row["phase_at_first_answer"]) for row in mine}
                ),
                "version_unavailable_total": sum(row["version_unavailable"] for row in mine),
                "adapter_retries_total": sum(row["retries_inside_adapter"] for row in mine),
            }
    out = OUT / f"discovery-{args.label}.json"
    out.write_text(
        json.dumps(
            {"host": host_record(), "corpus": args.label, "rows": rows, "summary": summary},
            indent=1,
        )
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
