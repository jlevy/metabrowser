"""Time an inventory provider alone: open to settled, then each query, with no server.

`devtools/bench_serving.py` measures a provider through the whole host, where routes,
serialization, the change relay, and the event loop take their share. An engine win
that does not appear there has been moved, not removed, and this harness is the layer
that says whether there was an engine win to move: it opens one provider handle on a
corpus through the sealed factory, waits for its first discovery to end, and times the
queries the folder view's routes issue, each read directly from the handle.

Each trial runs one provider in a fresh interpreter, so no provider inherits another's
imports or retained memory, and consecutive trials rotate the provider order, so drift
is not charged to whichever provider always ran second. Run at least as many trials as
providers, and pair the sides as `docs/development.md` (Measurement Discipline) says.

The end of discovery is waited for on the handle's own change stream, not by polling
reads: a read every few milliseconds competes with a Python walker for the interpreter
lock, and the floor stage of the fdu spike, which polled that way, slowed the walk it
was timing. Discovery has ended at the first state outside `DISCOVERY_PHASES`
(`inventory_engine/coordinator.py`), the definition the host's own discovery record
uses, so this layer and the server layer time the same thing.

Every query is read once cold and then `--repeats` more times at the same settled
version, and the report keeps both, because a provider that memoizes answers the first
read and the rest differently. A query that exhausts its work bound is reported as
``limit`` rather than timed.

Usage::

    uv --config-file uv.toml run --frozen python -m devtools.bench_engine \\
        .bench/corpus-100000 --provider python --trials 5 --json engine.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, cast

from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    ChangeCursor,
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryQuery,
    EntryQuery,
    FilteredTreeQuery,
    GroupedTreeQuery,
    IndexState,
    InventoryFilter,
    InventoryHandle,
    NavigationQuery,
    QueryLimitProjection,
    ReadQuery,
    ReadRequest,
    RecentQuery,
    RollupQuery,
)
from metabrowser.inventory_engine.coordinator import DISCOVERY_PHASES
from metabrowser.inventory_engine.factory import (
    InventoryProvider,
    create_inventory_backend,
    resolve_inventory_provider,
)
from metabrowser.inventory_engine.runtime import default_inventory_config
from metabrowser.settings import (
    INVENTORY_TREE_PAGE_ROWS,
    RECENT_DEFAULT_LIMIT,
    RECENT_WINDOW_SECONDS,
    ROLLUP_MAX_NODES,
)
from metabrowser.tree_groups import groups_for, inventory_group_filter

REPO = Path(__file__).resolve().parent.parent
# Timed reads of each query after its first, at the same version.
DEFAULT_REPEATS = 5
# Bounds one trial, so a provider that never settles is reported rather than waited for.
TRIAL_TIMEOUT_S = 1_800.0
WatchMode = Literal["auto", "native", "poll", "off"]
WATCH_MODES: tuple[WatchMode, ...] = ("auto", "native", "poll", "off")


def folder_view_queries(as_of_ns: int, max_files: int) -> dict[str, ReadQuery]:
    """The queries a folder view's first requests issue, in the shapes the routes use.

    Root tallies (`/api/tree?depth=0`), the first tree page, the Overview rollup, Recent,
    the first Quick File catalog page (`budget.max_files` rows, as the catalog route
    reads), a type-grouped tree, a filtered tree, one entry, and the diagnostics record.
    """

    return {
        "entry": EntryQuery(query_id="entry", path=""),
        "directory": DirectoryQuery(
            query_id="directory", max_depth=1, max_rows=INVENTORY_TREE_PAGE_ROWS
        ),
        "filtered_tree": FilteredTreeQuery(
            query_id="filtered_tree",
            max_depth=3,
            max_rows=INVENTORY_TREE_PAGE_ROWS,
            filter=InventoryFilter(include_ignored=False),
        ),
        "grouped_tree": GroupedTreeQuery(
            query_id="grouped_tree",
            groups=tuple(inventory_group_filter(group) for group in groups_for("type")),
            max_depth=2,
            max_rows=INVENTORY_TREE_PAGE_ROWS,
        ),
        "rollup": RollupQuery(
            query_id="rollup",
            max_depth=0,
            max_nodes=ROLLUP_MAX_NODES,
            top=0,
            extension_top=0,
            remaining_top=20,
            filename_top=20,
            rank="dual",
        ),
        "navigation": NavigationQuery(
            query_id="navigation",
            presets=tuple(
                (str(preset["id"]), tuple(str(value) for value in preset["values"]))
                for preset in FILTER_TYPE_PRESETS
            ),
            recency_windows=tuple(
                (key, seconds) for key, seconds in RECENT_WINDOW_SECONDS.items() if seconds
            ),
            as_of_ns=as_of_ns,
        ),
        "recent": RecentQuery(query_id="recent", max_rows=RECENT_DEFAULT_LIMIT, as_of_ns=as_of_ns),
        "catalog": CatalogQuery(query_id="catalog", max_rows=max_files),
        "diagnostics": DiagnosticsQuery(query_id="diagnostics"),
    }


async def _settled_state(handle: InventoryHandle) -> IndexState:
    """The first state past discovery, read from the handle's change stream."""

    checkpoint = await handle.read(ReadRequest())
    if checkpoint.state.phase not in DISCOVERY_PHASES:
        return checkpoint.state
    cursor: ChangeCursor = checkpoint.cursor
    changes = handle.changes(after=cursor)
    try:
        async for batch in changes:
            if batch.state.phase not in DISCOVERY_PHASES:
                return batch.state
    finally:
        close = getattr(changes, "aclose", None)
        if close is not None:
            await close()
    raise RuntimeError("the change stream ended before discovery did")


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 3)


async def _time_query(handle: InventoryHandle, query: ReadQuery, repeats: int) -> dict[str, Any]:
    samples: list[float] = []
    for _read in range(repeats + 1):
        started = time.perf_counter()
        result = await handle.read(ReadRequest(queries=(query,)))
        samples.append(time.perf_counter() - started)
        if isinstance(result.projection(query.query_id), QueryLimitProjection):
            return {"limit": True}
    repeated = samples[1:]
    return {
        "first_ms": _ms(samples[0]),
        "repeat_min_ms": _ms(min(repeated)) if repeated else None,
        "repeat_median_ms": _ms(statistics.median(repeated)) if repeated else None,
    }


async def measure(
    root: Path,
    provider: InventoryProvider,
    *,
    watch_mode: WatchMode | None = None,
    repeats: int = DEFAULT_REPEATS,
) -> dict[str, Any]:
    """One trial of *provider* on *root*, in this process."""

    config = default_inventory_config()
    if watch_mode is not None:
        config = replace(config, watch_mode=watch_mode)
    backend = create_inventory_backend(provider)
    cpu_started = time.process_time()
    started = time.perf_counter()
    handle = await backend.open(root, config)
    opened = time.perf_counter()
    try:
        state = await _settled_state(handle)
        settled = time.perf_counter()
        discovery_cpu_s = time.process_time() - cpu_started
        queries = folder_view_queries(time.time_ns(), config.budget.max_files)
        reads = {name: await _time_query(handle, query, repeats) for name, query in queries.items()}
        diagnostics = (
            await handle.read(ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),)))
        ).projection("diagnostics")
        if not isinstance(diagnostics, DiagnosticsProjection):
            raise TypeError("the diagnostics query returned the wrong projection")
    finally:
        closing = time.perf_counter()
        await handle.close()
        closed = time.perf_counter()
    return {
        "provider": provider.value,
        "contract": diagnostics.payload.contract,
        "watch_mode": config.watch_mode,
        "open_ms": _ms(opened - started),
        "settled_ms": _ms(settled - started),
        "close_ms": _ms(closed - closing),
        "discovery_cpu_s": round(discovery_cpu_s, 3),
        # ru_maxrss is KiB on Linux and bytes on macOS.
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        // (1024 if sys.platform == "darwin" else 1),
        "settled_phase": state.phase.value,
        "complete": state.coverage.complete,
        "files": diagnostics.payload.files_indexed,
        "directories": diagnostics.payload.directories_indexed,
        "reads": reads,
    }


def run_trial(
    root: Path, provider: InventoryProvider, watch_mode: WatchMode | None, repeats: int
) -> dict[str, Any]:
    """One trial in a fresh interpreter."""

    command = [
        sys.executable,
        "-m",
        "devtools.bench_engine",
        str(root),
        "--one",
        provider.value,
        "--repeats",
        str(repeats),
    ]
    if watch_mode is not None:
        command += ["--watch-mode", watch_mode]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
        env=os.environ.copy(),
        timeout=TRIAL_TIMEOUT_S,
    )
    if completed.returncode != 0:
        return {"provider": provider.value, "error": completed.stderr[-2000:]}
    loaded: Any = json.loads(completed.stdout.strip().splitlines()[-1])
    return cast("dict[str, Any]", loaded)


def rotated[T](items: list[T], trial: int) -> list[T]:
    """*items* starting from a different one on each trial."""

    shift = trial % len(items)
    return items[shift:] + items[:shift]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("root", type=Path, help="the corpus to open")
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="a provider to time; repeat to interleave several (default: python)",
    )
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument(
        "--watch-mode",
        choices=WATCH_MODES,
        help="override the application's watch mode, for example off to time discovery alone",
    )
    parser.add_argument("--json", type=Path, help="also write the results here")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = cast("Path", args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"{root} is not a directory")
    watch_mode = cast("WatchMode | None", args.watch_mode)
    repeats = cast("int", args.repeats)
    one = cast("str | None", args.one)
    if one is not None:
        result = asyncio.run(
            measure(root, resolve_inventory_provider(one), watch_mode=watch_mode, repeats=repeats)
        )
        print(json.dumps(result))
        return 0

    providers = [resolve_inventory_provider(name) for name in cast("list[str]", args.provider)] or [
        InventoryProvider.PYTHON
    ]
    runs: list[dict[str, Any]] = []
    for trial in range(cast("int", args.trials)):
        for provider in rotated(providers, trial):
            record = run_trial(root, provider, watch_mode, repeats)
            runs.append({"trial": trial, **record})
            settled = record.get("settled_ms", "error")
            print(f"trial {trial}  {provider.value:<10} settled {settled} ms", flush=True)
    report = {
        "root": str(root),
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "runs": runs,
    }
    output = cast("Path | None", args.json)
    if output is not None:
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 1 if any("error" in run for run in runs) else 0


if __name__ == "__main__":
    sys.exit(main())
