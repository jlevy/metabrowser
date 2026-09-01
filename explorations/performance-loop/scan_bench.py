#!/usr/bin/env python3
"""Backend scan bench: how long the inventory takes to settle, and why.

The browser loop in `run.py` measures what a reader sees. This measures the
engine underneath it, because the inventory-provider refactor is a change to
that engine and the browser harness is too slow an instrument to iterate a
per-entry cost against.

Two modes, deliberately different in speed and in what they can conclude:

    inproc   Opens the runtime in this process and waits for discovery to reach
             a terminal phase. No server, no HTTP, no process startup, so a
             per-entry change shows up undiluted. This is the inner loop.

    binary   Spawns a `metab` console script against the same corpus and times
             a full scan through `--api /api/index/meta`, which waits for the
             index. Slower and noisier -- it carries interpreter startup -- but
             it is the only mode that can compare two *builds*, which is what a
             claim against `main` requires.

Neither mode is a release gate. `run.py` owns that. This one exists to answer
"did the thing I just changed help", quickly enough to ask it often.

Usage:

    # inner loop: is this working tree faster than it was?
    scan_bench.py inproc --files 60000 --runs 5

    # confirmatory: is this build faster than another one?
    scan_bench.py binary --files 60000 --runs 3 \\
        --binary main=/path/to/main/.venv/bin/metab \\
        --binary candidate=.venv/bin/metab

    # add --profile to inproc for the top frames behind the number
    scan_bench.py inproc --files 60000 --runs 1 --profile

The corpus is `bench_serving.build_corpus`, which reuses an existing tree when
its size and shape match, so repeated rounds measure the identical filesystem.
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import platform
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

REPO = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(REPO / "src"), str(REPO)]

DEFAULT_FILES = 60_000
DEFAULT_RUNS = 5
# Frames worth printing: the ones inside this package, plus the interpreter
# machinery a per-entry mistake shows up as (dataclass construction, attribute
# access, path handling).
PROFILE_INTEREST = ("metabrowser", "dataclasses", "pathlib", "posixpath")


def build_corpus(files: int, corpus_dir: Path) -> dict[str, Any]:
    from devtools.bench_serving import build_corpus as _build

    return _build(corpus_dir, files)


# Profiling slows the walk by several times, so the settle wait has to be
# generous enough that the instrument does not trip its own timeout.
SETTLE_TIMEOUT_S = 30.0
PROFILED_SETTLE_TIMEOUT_S = 300.0


async def _settle(root: Path, timeout_s: float) -> float:
    """One open-to-terminal-phase cycle, in milliseconds."""

    from tests.inventory_harness import inventory_harness, wait_until_settled

    started = time.perf_counter()
    async with inventory_harness(root, settle=False) as harness:
        await wait_until_settled(harness.runtime, timeout=timeout_s)
    return (time.perf_counter() - started) * 1000.0


def run_inproc(root: Path, runs: int, profile: bool) -> list[float]:
    if profile:
        profiler = cProfile.Profile()
        profiler.enable()
        elapsed = [asyncio.run(_settle(root, PROFILED_SETTLE_TIMEOUT_S))]
        profiler.disable()
        _print_profile(profiler)
        return elapsed
    return [asyncio.run(_settle(root, SETTLE_TIMEOUT_S)) for _ in range(runs)]


def _print_profile(profiler: cProfile.Profile) -> None:
    stats = pstats.Stats(profiler)
    # `pstats.Stats.stats` is undeclared in typeshed; its shape is
    # {(file, line, func): (calls, ncalls, tottime, cumtime, callers)}.
    raw = cast("dict[tuple[str, int, str], tuple[int, int, float, float, object]]", stats.stats)  # pyright: ignore[reportAttributeAccessIssue]
    rows: list[tuple[float, float, int, str]] = []
    for (filename, lineno, func), entry in raw.items():
        if not any(marker in filename for marker in PROFILE_INTEREST):
            continue
        _calls, ncalls, tottime, cumtime, _callers = entry
        rows.append((tottime, cumtime, ncalls, f"{Path(filename).name}:{lineno} {func}"))
    rows.sort(reverse=True)
    print(f"\n{'tottime':>8} {'cumtime':>8} {'ncalls':>10}  where")
    for tottime, cumtime, ncalls, where in rows[:20]:
        print(f"{tottime:8.3f} {cumtime:8.3f} {ncalls:10,}  {where}")


def run_binary(binary: str, root: Path, runs: int) -> list[float]:
    """Time a full scan through a route that waits for the index."""

    elapsed: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        completed = subprocess.run(
            [binary, str(root), "--api", "/api/index/meta"],
            capture_output=True,
            timeout=600,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(f"{binary} exited {completed.returncode}: {completed.stderr[-400:]!r}")
        elapsed.append((time.perf_counter() - started) * 1000.0)
    return elapsed


def summarize(label: str, samples: list[float]) -> dict[str, Any]:
    return {
        "label": label,
        "runs": len(samples),
        "median_ms": round(statistics.median(samples), 1),
        "range_ms": [round(min(samples), 1), round(max(samples), 1)],
        "samples_ms": [round(sample, 1) for sample in samples],
    }


def _overlapping(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Whether the ranges overlap, which is what forbids a speed claim."""

    return not (
        left["range_ms"][1] < right["range_ms"][0] or right["range_ms"][1] < left["range_ms"][0]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inproc", "binary"))
    parser.add_argument("--files", type=int, default=DEFAULT_FILES)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--corpus-dir", type=Path, default=None)
    parser.add_argument(
        "--binary",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="binary mode: a labelled metab console script; repeat for each build",
    )
    parser.add_argument("--profile", action="store_true", help="inproc: print the top frames")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    corpus_dir = args.corpus_dir or (REPO / ".bench" / f"scan-{args.files}")
    corpus_dir.parent.mkdir(parents=True, exist_ok=True)
    corpus = build_corpus(args.files, corpus_dir)
    print(f"corpus: {corpus.get('files')} files at {corpus_dir}")

    conditions: list[dict[str, Any]] = []
    if args.mode == "inproc":
        conditions.append(
            summarize("working tree", run_inproc(corpus_dir, args.runs, args.profile))
        )
    else:
        if not args.binary:
            raise SystemExit("binary mode needs at least one --binary LABEL=PATH")
        for spec in args.binary:
            label, _, path = spec.partition("=")
            if not path:
                raise SystemExit(f"--binary wants LABEL=PATH, got {spec!r}")
            conditions.append(summarize(label, run_binary(path, corpus_dir, args.runs)))

    print()
    for condition in conditions:
        print(
            f"  {condition['label']:<24} median {condition['median_ms']:9.1f} ms   "
            f"range {condition['range_ms'][0]:.1f}-{condition['range_ms'][1]:.1f}   "
            f"n={condition['runs']}"
        )
    if len(conditions) == 2:
        control, candidate = conditions
        change = (candidate["median_ms"] - control["median_ms"]) / control["median_ms"] * 100
        overlap = _overlapping(control, candidate)
        print(f"\n  change {change:+.1f}%   ranges {'overlap' if overlap else 'are disjoint'}")
        if overlap:
            print("  overlapping ranges are not a result; treat as no detectable effect")

    record = {
        "mode": args.mode,
        "corpus_files": corpus.get("files"),
        "corpus_dir": str(corpus_dir),
        "host_system": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "conditions": conditions,
    }
    if args.json:
        args.json.write_text(json.dumps(record, indent=2) + "\n")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
