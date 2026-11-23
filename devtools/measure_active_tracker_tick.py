"""Measure what one activity-tracker tick costs on a tree of trackable files.

The tracker (``metabrowser.active_tracker``) ticks every ``ACTIVE_TRACKER_INTERVAL_S``
for as long as a server runs, so a tick's CPU time is what an idle server pays. This
builds ``--runs`` run folders, each with a ``.logs`` of ``--logs`` JSONL files and one
pid file and a ``.state`` of four small files, opens the inventory on it as ``metab``
does, and runs ``--ticks`` ticks back to back.

It reports each tick's process CPU time (every thread, so the probes the tick hands to
worker threads count) and wall time. CPU time is the figure to compare: it does not
grow with the machine's load the way wall time does. ``--writers N`` appends to N logs
before every tick, which is the cost while runs are being written. ``--sweep N``
overrides ``ACTIVE_TRACKER_SWEEP_FILES``, and ``--profile`` runs the ticks with their
thread hops inline under cProfile and prints where the time goes.

    uv --config-file uv.toml run --frozen python devtools/measure_active_tracker_tick.py \
        --root /path/for/the/tree
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import os
import pstats
import statistics
import time
import types
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

_STATE_FILES = ("status.yaml", "plan.yaml", "state.json", "summary.json")


def _build(root: Path, runs: int, logs: int) -> list[Path]:
    """Create the tree once, and return the first log of every run."""

    first_logs: list[Path] = []
    for run in range(runs):
        logs_dir = root / "runs" / f"run-{run:04d}" / ".logs"
        state_dir = root / "runs" / f"run-{run:04d}" / ".state"
        first_logs.append(logs_dir / "step-0000.jsonl")
        if state_dir.is_dir():
            continue
        logs_dir.mkdir(parents=True, exist_ok=True)
        for n in range(logs):
            (logs_dir / f"step-{n:04d}.jsonl").write_text('{"event":"start"}\n')
        (logs_dir / "worker.pid").write_text(f"{os.getpid()}\n")
        state_dir.mkdir()
        for name in _STATE_FILES:
            (state_dir / name).write_text("state: done\n")
    return first_logs


async def _run(args: argparse.Namespace, first_logs: list[Path]) -> None:
    import metabrowser.active_tracker as active_tracker
    from metabrowser.activity import FileActivityTracker
    from metabrowser.inventory_engine.contract import LifecyclePhase
    from metabrowser.inventory_engine.runtime import InventoryRuntime, default_inventory_config

    config = replace(default_inventory_config(), watch_mode=args.watch)
    runtime = InventoryRuntime(config=config)
    await runtime.open(args.root)
    settled = {LifecyclePhase.READY, LifecyclePhase.WATCHING, LifecyclePhase.FAILED}
    while True:
        _cursor, _version, index = await runtime.coordinator.checkpoint()
        if index.phase in settled:
            break
        await asyncio.sleep(0.05)

    profile: cProfile.Profile | None = None
    if args.profile:

        async def inline[T](function: Callable[..., T], /, *a: object, **kw: object) -> T:
            return function(*a, **kw)

        inline_asyncio = types.ModuleType("asyncio")
        vars(inline_asyncio).update(vars(asyncio))
        inline_asyncio.to_thread = inline  # pyright: ignore[reportAttributeAccessIssue]
        active_tracker.asyncio = inline_asyncio  # pyright: ignore[reportAttributeAccessIssue]
        profile = cProfile.Profile()

    state = active_tracker._TrackerState()  # pyright: ignore[reportPrivateUsage]
    tracker = FileActivityTracker()
    sweep = {} if args.sweep is None else {"sweep_files": args.sweep}
    cpus: list[float] = []
    walls: list[float] = []
    active: list[int] = []
    try:
        for tick in range(args.ticks):
            for log in first_logs[: args.writers]:
                with log.open("a") as handle:
                    handle.write('{"event":"step"}\n')
            cpu = time.process_time()
            wall = time.perf_counter()
            if profile is not None and tick >= args.warmup:
                profile.enable()
            await active_tracker._tick(  # pyright: ignore[reportPrivateUsage]
                runtime.coordinator, args.root, runtime.config, state, tracker, **sweep
            )
            if profile is not None:
                profile.disable()
            cpus.append(time.process_time() - cpu)
            walls.append(time.perf_counter() - wall)
            active.append(len(state.active_paths))
            # Let the provider absorb the refresh hints a tick sent, outside the tick.
            await asyncio.sleep(args.pause)
    finally:
        await runtime.close()

    steady_cpu = cpus[args.warmup :]
    steady_wall = walls[args.warmup :]
    print(f"load average {os.getloadavg()[0]:.0f}; first tick {cpus[0] * 1000:.1f} ms CPU")
    print(
        f"steady tick, {len(steady_cpu)} ticks, {args.writers} writers: "
        f"median {statistics.median(steady_cpu) * 1000:.2f} ms CPU "
        f"(min {min(steady_cpu) * 1000:.2f}, max {max(steady_cpu) * 1000:.2f}), "
        f"median {statistics.median(steady_wall) * 1000:.2f} ms wall"
    )
    print("per tick ms CPU: " + " ".join(f"{cpu * 1000:.1f}" for cpu in cpus))
    print("active files after each tick: " + " ".join(str(count) for count in active))
    if profile is not None:
        pstats.Stats(profile).sort_stats("cumulative").print_stats(args.profile_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", type=Path, required=True, help="where the tree is built")
    parser.add_argument("--runs", type=int, default=300)
    parser.add_argument("--logs", type=int, default=95)
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=2, help="ticks left out of the median")
    parser.add_argument("--writers", type=int, default=0)
    parser.add_argument("--sweep", type=int, help="override ACTIVE_TRACKER_SWEEP_FILES")
    parser.add_argument("--pause", type=float, default=0.2)
    parser.add_argument("--watch", default="auto", choices=("auto", "native", "poll", "off"))
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-rows", type=int, default=30)
    args = parser.parse_args()

    args.root.mkdir(parents=True, exist_ok=True)
    first_logs = _build(args.root, args.runs, args.logs)
    print(f"{args.runs * (args.logs + 1 + len(_STATE_FILES))} trackable files at {args.root}")
    asyncio.run(_run(args, first_logs))


if __name__ == "__main__":
    main()
