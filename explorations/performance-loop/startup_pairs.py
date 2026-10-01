#!/usr/bin/env python3
"""Start-up work of installed builds, in back-to-back pairs.

`run.py` measures what a reader sees once a tree is served, and `compare_builds`
measures the scan. Neither sees what a build does before either starts: importing
itself. That cost is paid by every mode, `--version` included, and it is small enough
that wall time on a busy machine cannot resolve it. This measures it in instructions
retired, which count the work the process did and are close to independent of what else
the machine is running, and records wall and CPU time beside them for a quiet machine.

Each round runs the control and then one candidate, so every ratio is between two
measurements taken next to each other:

    control, candidate-1, control, candidate-2, control, candidate-1, ...

Per build a round measures four one-shot commands (`--show`, `--api`, `--version`,
`--doctor`), then spawns a server, times it to its first `/api/routes` answer, and
fetches the shell once cold and nine times warm.

Usage:

    # Two wheels installed in two environments outside any work tree.
    startup_pairs.py run --tree /path/to/folder --pairs 9 --out pairs.jsonl \\
        --control /envs/release/bin/metab \\
        --candidate base=/envs/base/bin/metab --candidate after=/envs/after/bin/metab

    startup_pairs.py summarize pairs.jsonl --candidate after --suffix _instr --ratios

Instructions retired are read through macOS interfaces (`/usr/bin/time -l` for a
one-shot command, `proc_pid_rusage` for a live server). On another platform the
instruction columns are absent and only wall and CPU time are recorded.

Judge a tolerance on the pair ratios, never on one condition's worst run against the
other's: see "Judge a tolerance on back-to-back pairs" in this directory's README.
"""

from __future__ import annotations

import argparse
import ctypes
import gzip
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast

# Warm repetitions of the shell fetch. Nine gives a median that one slow response
# cannot move, and keeps a round short enough to take many of them.
WARM_REPS = 9
# Breaks a hung server; it is not a speed budget.
SERVER_READY_TIMEOUT_S = 600.0
# No proxy: the server is on loopback, and an inherited proxy setting would send the
# request elsewhere.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_MACOS = sys.platform == "darwin"

# `struct rusage_info_v4` is a 16-byte UUID followed by 36 64-bit counters;
# `ri_instructions` is the thirtieth of them.
_RUSAGE_INFO_V4 = 4
_RUSAGE_U64_FIELDS = 36
_RI_INSTRUCTIONS = 29


class _RusageInfoV4(ctypes.Structure):
    _fields_ = [
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("counters", ctypes.c_uint64 * _RUSAGE_U64_FIELDS),
    ]


def _instructions(pid: int) -> int | None:
    """Instructions retired by *pid* so far, or None where the platform cannot say."""

    if not _MACOS:
        return None
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    info = _RusageInfoV4()
    status = cast(int, libproc.proc_pid_rusage(pid, _RUSAGE_INFO_V4, ctypes.byref(info)))
    if status != 0:
        raise OSError(ctypes.get_errno(), "proc_pid_rusage failed")
    counters = cast("ctypes.Array[ctypes.c_uint64]", info.counters)
    return int(counters[_RI_INSTRUCTIONS])


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _fetch(url: str, *, timeout: float) -> tuple[float, int]:
    """Fetch *url* and return its wall time in milliseconds and its status."""

    request = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    started = time.perf_counter()
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            wire = cast(bytes, response.read())
            elapsed_ms = (time.perf_counter() - started) * 1000
            if response.headers.get("Content-Encoding") == "gzip":
                gzip.decompress(wire)
            return elapsed_ms, int(cast(int, response.status))
    except urllib.error.HTTPError as error:
        return (time.perf_counter() - started) * 1000, error.code


def _environment(home: Path) -> dict[str, str]:
    # A home of its own, so a build under test never reads or writes the developer's
    # cache, and a fixed hash seed, so set and dict ordering does not vary the work.
    return {**os.environ, "METABROWSER_HOME": str(home), "PYTHONHASHSEED": "0"}


def _measure_command(
    metrics: dict[str, float], name: str, metab: Path, args: list[str], home: Path
) -> None:
    """One CLI invocation: wall time, CPU time, instructions, and peak footprint."""

    command = [str(metab), *args]
    if _MACOS:
        command = ["/usr/bin/time", "-l", *command]
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=tempfile.gettempdir(),
        env=_environment(home),
        capture_output=True,
        text=True,
        check=False,
    )
    metrics[f"{name}_ms"] = (time.perf_counter() - started) * 1000
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} exited {result.returncode}: {result.stderr[-300:]}")
    times = re.search(r"([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys", result.stderr)
    if times:
        metrics[f"{name}_cpu_ms"] = (float(times[2]) + float(times[3])) * 1000
    instructions = re.search(r"(\d+)\s+instructions retired", result.stderr)
    if instructions:
        metrics[f"{name}_instr"] = float(instructions[1])
    peak = re.search(r"(\d+)\s+peak memory footprint", result.stderr)
    if peak:
        metrics[f"{name}_peak_mb"] = float(peak[1]) / 1e6


def _measure_server(metrics: dict[str, float], metab: Path, tree: Path, home: Path) -> None:
    """Spawn a server: time and work to its first `/api` answer, then the shell."""

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    spawned = time.perf_counter()
    process = subprocess.Popen(
        [str(metab), str(tree), "--port", str(port), "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=tempfile.gettempdir(),
        env=_environment(home),
    )
    try:
        deadline = spawned + SERVER_READY_TIMEOUT_S
        while True:
            try:
                _, status = _fetch(base + "/api/routes", timeout=5)
            except (urllib.error.URLError, OSError):
                status = 0
            if status == 200:
                break
            if process.poll() is not None:
                raise SystemExit(f"the server exited {process.returncode} before answering")
            if time.perf_counter() > deadline:
                raise SystemExit("the server never answered /api/routes")
            time.sleep(0.005)
        metrics["serve_first_api_ms"] = (time.perf_counter() - spawned) * 1000
        at_first_api = _instructions(process.pid)
        if at_first_api is not None:
            metrics["serve_first_api_instr"] = float(at_first_api)

        before = _instructions(process.pid)
        elapsed_ms, status = _fetch(base + "/", timeout=300)
        if status != 200:
            raise SystemExit(f"the shell answered {status}")
        metrics["shell_first_ms"] = elapsed_ms
        after = _instructions(process.pid)
        if before is not None and after is not None:
            metrics["shell_first_instr"] = float(after - before)

        before = _instructions(process.pid)
        warm = [_fetch(base + "/", timeout=300)[0] for _ in range(WARM_REPS)]
        after = _instructions(process.pid)
        metrics["shell_ms"] = statistics.median(warm)
        if before is not None and after is not None:
            metrics["shell_instr"] = (after - before) / WARM_REPS
    finally:
        process.terminate()
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _measure(metab: Path, tree: Path, home: Path) -> dict[str, float]:
    metrics: dict[str, float] = {}
    readme = next((name for name in ("README.md", "readme.md") if (tree / name).is_file()), None)
    if readme is None:
        raise SystemExit(f"{tree} has no README.md for --show to open")
    _measure_command(metrics, "cli_show", metab, [str(tree), "--show", readme], home)
    _measure_command(metrics, "cli_api_tree", metab, [str(tree), "--api", "/api/tree"], home)
    _measure_command(metrics, "cli_version", metab, ["--version"], home)
    _measure_command(metrics, "cli_doctor", metab, ["--doctor"], home)
    _measure_server(metrics, metab, tree, home)
    return metrics


def _version(metab: Path) -> str:
    result = subprocess.run(
        [str(metab), "--version"], capture_output=True, text=True, check=True, timeout=120
    )
    return result.stdout.strip()


def cmd_run(args: argparse.Namespace) -> int:
    tree = Path(cast(str, args.tree)).resolve()
    out = Path(cast(str, args.out))
    control = Path(cast(str, args.control)).resolve()
    candidates: dict[str, Path] = {}
    for spec in cast("list[str]", args.candidate):
        name, _, path = spec.partition("=")
        if not name or not path or name == "control":
            raise SystemExit(f"--candidate takes NAME=PATH, and not the name 'control': {spec!r}")
        candidates[name] = Path(path).resolve()
    builds = {"control": control, **candidates}
    # A build is identified by what it reports, so PATH order or a stale environment
    # cannot silently change the build under test.
    versions = {name: _version(path) for name, path in builds.items()}
    for name, version in versions.items():
        print(f"{name}: {version}", flush=True)
    with tempfile.TemporaryDirectory(prefix="metab-startup-home-") as home_dir:
        home = Path(home_dir)
        with out.open("a", encoding="utf-8") as stream:
            for pair in range(cast(int, args.pairs)):
                for candidate in candidates:
                    for build in ("control", candidate):
                        load = os.getloadavg()[0]
                        record: dict[str, Any] = {
                            "pair": pair,
                            "candidate": candidate,
                            "build": build,
                            "version": versions[build],
                            "load1": load,
                            "recorded_at": time.time(),
                            **_measure(builds[build], tree, home),
                        }
                        stream.write(json.dumps(record) + "\n")
                        stream.flush()
                        print(f"pair {pair} [{candidate}] {build} load={load:.0f}", flush=True)
    return 0


_NOT_METRICS = {"pair", "candidate", "build", "version", "load1", "recorded_at"}


def cmd_summarize(args: argparse.Namespace) -> int:
    candidate = cast(str, args.candidate)
    suffix = cast(str, args.suffix)
    rows = [
        cast("dict[str, Any]", json.loads(line))
        for line in Path(cast(str, args.file)).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rounds: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row["candidate"] == candidate:
            rounds.setdefault(int(row["pair"]), {})[str(row["build"])] = row
    complete = [
        halves
        for _, halves in sorted(rounds.items())
        if "control" in halves and candidate in halves
    ]
    if not complete:
        raise SystemExit(f"no complete pair for candidate {candidate!r}")
    loads = [float(halves[build]["load1"]) for halves in complete for build in halves]
    print(
        f"candidate={candidate} pairs={len(complete)} "
        f"load1 min={min(loads):.0f} median={statistics.median(loads):.0f} max={max(loads):.0f}"
    )
    print(
        f"{'metric':26s} {'control':>11s} {'candidate':>11s} {'ratio':>7s} "
        f"{'min':>6s} {'max':>6s} {'>1.05':>6s} {'>1.1':>6s} {'>1.3':>6s}"
    )
    for metric in complete[0]["control"]:
        if metric in _NOT_METRICS or not metric.endswith(suffix):
            continue
        both = [
            (float(halves["control"][metric]), float(halves[candidate][metric]))
            for halves in complete
            if metric in halves["control"] and metric in halves[candidate]
        ]
        if not both or min(control for control, _ in both) <= 0:
            continue
        ratios = [measured / control for control, measured in both]
        scale = 1e6 if metric.endswith("_instr") else 1.0
        print(
            f"{metric:26s} {statistics.median(c for c, _ in both) / scale:11.1f} "
            f"{statistics.median(m for _, m in both) / scale:11.1f} "
            f"{statistics.median(ratios):7.3f} {min(ratios):6.2f} {max(ratios):6.2f} "
            + " ".join(
                f"{sum(ratio > bound for ratio in ratios):3d}/{len(ratios):<2d}"
                for bound in (1.05, 1.1, 1.3)
            )
        )
        if cast(bool, args.ratios):
            print("    " + " ".join(f"{ratio:.2f}" for ratio in ratios))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start-up work of builds, in pairs.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="measure the control and each candidate in pairs")
    run.add_argument("--tree", required=True, help="folder to serve; it needs a README.md")
    run.add_argument("--control", required=True, help="the control build's metab script")
    run.add_argument(
        "--candidate",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="a candidate build's metab script; repeat for several",
    )
    run.add_argument("--pairs", type=int, default=9)
    run.add_argument("--out", required=True, help="JSON Lines file to append to")
    run.set_defaults(handler=cmd_run)

    summarize = commands.add_parser("summarize", help="pair ratios for one candidate")
    summarize.add_argument("file")
    summarize.add_argument("--candidate", required=True)
    summarize.add_argument(
        "--suffix",
        default="_instr",
        help="metric suffix: _instr (instructions, in millions), _ms, _cpu_ms, _peak_mb",
    )
    summarize.add_argument("--ratios", action="store_true", help="print every pair's ratio")
    summarize.set_defaults(handler=cmd_summarize)

    args = parser.parse_args()
    return cast(int, args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
