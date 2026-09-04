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

    # final baseline: the same comparison against a real tree, not a corpus
    scan_bench.py binary --root ~/wrk/aisw/trading --runs 3 \\
        --binary main=/path/to/main/.venv/bin/metab \\
        --binary candidate=.venv/bin/metab

    # add --profile to inproc for the top frames behind the number
    scan_bench.py inproc --files 60000 --runs 1 --profile

The corpus is `bench_serving.build_corpus`, which reuses an existing tree when
its size and shape match, so repeated rounds measure the identical filesystem.
`--root` measures an existing tree instead, which is the only way to see the
directory shapes, name lengths, and depth distribution real trees actually have;
a synthetic corpus is one shape by construction. It is a baseline, not a gate:
the tree is not version controlled by this harness, so a number is only
comparable to another number taken against the same tree in the same state.

Three things this harness does deliberately, because measuring builds against
each other is easy to get wrong:

* **Order alternates within a pass.** Interleaving alone still runs `builds[0]`
  first every time, which leaves page-cache and CPU-ramp effects confounded with
  the label. Odd passes run the builds in reverse.
* **A warmup pass is timed and discarded.** The first touch of a tree pays for
  the filesystem cache that every later run enjoys. Keeping it inflates the
  range, and the decision rule reads the range.
* **Every build records its commit and whether the tree was dirty.** A mode whose
  purpose is comparing two builds has to be able to say which two it compared.
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


def _time_one_scan(binary: str, root: Path) -> float:
    """One full scan through a route that waits for the index."""

    started = time.perf_counter()
    completed = subprocess.run(
        [binary, str(root), "--api", "/api/index/meta"],
        capture_output=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"{binary} exited {completed.returncode}: {completed.stderr[-400:]!r}")
    return (time.perf_counter() - started) * 1000.0


def describe_build(binary: str) -> dict[str, Any]:
    """Which build this is, so the record can say what it compared.

    Derived from the checkout the console script lives in (`<repo>/.venv/bin/metab`),
    because that is the tree whose source it imports. A dirty flag matters as much as
    the commit: an uncommitted edit is exactly the thing being measured, and a record
    that omits it cannot be reproduced later.
    """

    path = Path(binary).resolve()
    repo = path.parent.parent.parent
    info: dict[str, Any] = {"binary": str(path)}
    try:
        info["commit"] = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        info["dirty"] = bool(
            subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
        )
    except (subprocess.SubprocessError, OSError):
        # A binary outside a checkout is still measurable; it just cannot be attributed.
        info["commit"] = None
        info["dirty"] = None
    return info


def run_binaries(
    builds: list[tuple[str, str]], root: Path, runs: int, *, warmup: bool = True
) -> list[list[float]]:
    """Time every build, interleaved and order-alternated, one run of each per pass.

    Running a whole condition and then the next one lets anything that drifts
    over the measurement -- another process starting, thermal throttling, a
    filesystem cache filling -- land entirely on whichever went second, which is
    always the candidate. That is a difference the numbers cannot distinguish
    from the change under test. Interleaving spreads the drift across both.

    Interleaving alone is not enough. Running the builds in a fixed order within
    each pass leaves whatever depends on *position* -- the page cache the first
    run of a pass warms for the second, a CPU that has not ramped yet -- attached
    to the label rather than spread across it. Odd passes run the order reversed,
    so each build takes each position equally often.

    The warmup pass is timed and thrown away. The first scan of a tree pays for
    the filesystem cache every later scan reuses, and on a real tree that cost is
    large enough to dominate the range -- which is what the overlap rule reads.
    """

    if warmup:
        for _label, binary in builds:
            _time_one_scan(binary, root)
    samples: list[list[float]] = [[] for _ in builds]
    for pass_index in range(runs):
        order = list(range(len(builds)))
        if pass_index % 2:
            order.reverse()
        for index in order:
            samples[index].append(_time_one_scan(builds[index][1], root))
    return samples


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
        "--root",
        type=Path,
        default=None,
        help="measure this existing tree instead of building a synthetic corpus",
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="binary mode: keep the first (cold-cache) pass instead of discarding it",
    )
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

    if args.root is not None:
        corpus_dir = args.root.expanduser().resolve()
        if not corpus_dir.is_dir():
            raise SystemExit(f"--root {corpus_dir} is not a directory")
        corpus = {"files": None, "synthetic": False}
        print(f"tree: {corpus_dir} (real tree; not built or verified by this harness)")
    else:
        corpus_dir = args.corpus_dir or (REPO / ".bench" / f"scan-{args.files}")
        corpus_dir.parent.mkdir(parents=True, exist_ok=True)
        corpus = dict(build_corpus(args.files, corpus_dir))
        corpus["synthetic"] = True
        print(f"corpus: {corpus.get('files')} files at {corpus_dir}")

    conditions: list[dict[str, Any]] = []
    if args.mode == "inproc":
        conditions.append(
            summarize("working tree", run_inproc(corpus_dir, args.runs, args.profile))
        )
    else:
        if not args.binary:
            raise SystemExit("binary mode needs at least one --binary LABEL=PATH")
        builds: list[tuple[str, str]] = []
        for spec in args.binary:
            label, _, path = spec.partition("=")
            if not path:
                raise SystemExit(f"--binary wants LABEL=PATH, got {spec!r}")
            builds.append((label, path))
        for (label, path), samples in zip(
            builds,
            run_binaries(builds, corpus_dir, args.runs, warmup=not args.no_warmup),
            strict=True,
        ):
            condition = summarize(label, samples)
            condition["build"] = describe_build(path)
            conditions.append(condition)

    print()
    for condition in conditions:
        build = condition.get("build")
        stamp = ""
        if build is not None:
            commit = build.get("commit") or "unknown"
            stamp = f"   [{commit}{'+dirty' if build.get('dirty') else ''}]"
        print(
            f"  {condition['label']:<24} median {condition['median_ms']:9.1f} ms   "
            f"range {condition['range_ms'][0]:.1f}-{condition['range_ms'][1]:.1f}   "
            f"n={condition['runs']}{stamp}"
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
        "interleaved": args.mode == "binary",
        "order_alternated": args.mode == "binary",
        "warmup_discarded": args.mode == "binary" and not args.no_warmup,
        # A profiled run is several times slower than a measured one. Recording it
        # under the same key as a measurement is how a profile ends up quoted as a
        # number, so the record says which it is.
        "profiled": bool(args.profile) and args.mode == "inproc",
        "synthetic_corpus": bool(corpus.get("synthetic")),
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
