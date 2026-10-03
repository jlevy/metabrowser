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

Every build is measured in one bytecode state. A start that finds no compiled bytecode
compiles each module it imports, which is about three times the work of a start that
loads them compiled, so one build with bytecode beside one without measures the
compiler and not the builds. `run` reads the state of each build's environment before
the first round, refuses a series whose builds differ, and writes the state into every
record: see "One bytecode state" below.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

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


# ── One bytecode state ──────────────────────────────────────────────────────────
#
# Python compiles a module the first time it is imported and keeps the result beside the
# source, unless PYTHONDONTWRITEBYTECODE is set, and `uv pip install` compiles nothing
# unless asked. So an environment built and used under that variable, as some agent
# shells set it, never has bytecode, and every start in it compiles everything it
# imports. Measured 2026-10-01 on one wheel in two environments: 9,344M instructions
# from spawn to an accepted connection without bytecode, 2,805M with it. exp-037 took
# both builds without it; a control with bytecode beside a candidate without read 3.2x
# on `--show` for builds that differ by 1.03x.
#
# The state is read from the files: each source of the installed `metabrowser`
# distribution and of every distribution it requires, and whether the bytecode file
# beside it is one the interpreter loads without compiling; `_BYTECODE_PROBE` says
# exactly which. Two states can be measured, and a ratio is only taken inside one:
#
# - `cached`: every source has one. This is what an installation runs from its second
#   start, and the state a claim about a release is made in.
# - `uncached`: none has. Every start compiles its imports.
#
# Anything between is refused. It is what one earlier run leaves behind, and it differs
# by which modes that run happened to import.

BYTECODE_STATES: Final = ("cached", "uncached")
DONT_WRITE_BYTECODE: Final = "PYTHONDONTWRITEBYTECODE"

# Runs in the environment's own interpreter, with the standard library alone. A source
# the interpreter cannot compile is not counted: no start imports it, and no compile
# step can give it bytecode.
#
# A bytecode file counts when its 16-byte header passes the test the import system
# applies before it loads one (`SourceLoader.get_code`), at the interpreter's default
# `--check-hash-based-pycs`:
#
# - the magic number is this interpreter's;
# - a timestamp file records the source's modification time, in whole seconds, and its
#   size, both modulo 2**32;
# - a checked hash-based file records the hash of the source's bytes as they are now;
# - an unchecked hash-based file is loaded whatever the source holds, so it counts.
#
# The body of the file is not read, so one cut short after its header counts too.
_BYTECODE_PROBE: Final = r"""
import importlib.metadata as metadata, importlib.util as util
import json, os, re, struct, sys

def compiled(source):
    try:
        with open(util.cache_from_source(source), "rb") as handle:
            head = handle.read(16)
        if len(head) < 16 or head[:4] != util.MAGIC_NUMBER:
            return False
        (flags,) = struct.unpack("<L", head[4:8])
        if flags & 1:
            if not flags & 2:
                return True
            with open(source, "rb") as handle:
                return head[8:] == util.source_hash(handle.read())
        stat = os.stat(source)
        stamp = struct.pack("<LL", int(stat.st_mtime) & 0xFFFFFFFF, stat.st_size & 0xFFFFFFFF)
        return head[8:] == stamp
    except (OSError, ValueError, NotImplementedError):
        return False

def compilable(source):
    try:
        with open(source, "rb") as handle:
            compile(handle.read(), source, "exec", dont_inherit=True)
        return True
    except (OSError, SyntaxError, ValueError):
        return False

seen, queue, report, roots = set(), ["metabrowser"], {}, set()
while queue:
    name = re.sub(r"[-_.]+", "-", queue.pop()).lower()
    if name in seen:
        continue
    seen.add(name)
    try:
        distribution = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    sources = have = 0
    for entry in distribution.files or ():
        source = str(distribution.locate_file(entry))
        if not source.endswith(".py") or not os.path.isfile(source):
            continue
        if compiled(source):
            have += 1
        elif not compilable(source):
            continue
        sources += 1
    report[name] = [sources, have]
    roots.add(str(distribution.locate_file("")))
    queue += [re.match(r"[A-Za-z0-9._-]+", line)[0] for line in distribution.requires or ()]
json.dump(
    {
        "distributions": report,
        "roots": sorted(roots),
        "python": sys.version,
        "python_base": sys.base_prefix,
    },
    sys.stdout,
)
"""


@dataclass(frozen=True, slots=True)
class BytecodeState:
    """What bytecode one build's environment holds for the package and what it requires."""

    interpreter: Path
    sources: int
    compiled: int
    roots: tuple[str, ...]
    # `sys.version` and `sys.base_prefix` of the interpreter the build runs on. Its
    # standard library's bytecode is not read, so a record says which one it was.
    python: str
    python_base: str

    @property
    def state(self) -> str:
        if self.compiled == self.sources:
            return "cached"
        return "uncached" if self.compiled == 0 else "partial"

    def describe(self) -> str:
        return f"{self.state} ({self.compiled} of {self.sources} source files have bytecode)"

    @property
    def compile_command(self) -> str:
        return f"{self.interpreter} -m compileall -q {' '.join(self.roots)}"


def _without_bytecode_writes() -> dict[str, str]:
    # Reading a state, or asking a build its version, must not change the state.
    return {**os.environ, DONT_WRITE_BYTECODE: "1"}


def bytecode_state(metab: Path) -> BytecodeState:
    """Read the bytecode state of the environment *metab* is installed in."""

    interpreter = metab.parent / "python"
    if not interpreter.exists():
        raise SystemExit(
            f"{metab} has no interpreter beside it, so its environment's bytecode cannot be "
            "read. Give the console script inside the environment's bin directory."
        )
    result = subprocess.run(
        [str(interpreter), "-c", _BYTECODE_PROBE],
        capture_output=True,
        text=True,
        check=False,
        env=_without_bytecode_writes(),
    )
    if result.returncode != 0:
        raise SystemExit(f"could not read the bytecode state of {metab}: {result.stderr[-300:]}")
    report = cast("dict[str, Any]", json.loads(result.stdout))
    distributions = cast("dict[str, list[int]]", report["distributions"])
    if distributions.get("metabrowser", [0, 0])[0] == 0:
        raise SystemExit(
            f"the environment of {metab} holds no installed metabrowser source files. An "
            "editable install is not what a user runs: measure a wheel installed into an "
            "environment of its own."
        )
    return BytecodeState(
        interpreter=interpreter,
        sources=sum(counts[0] for counts in distributions.values()),
        compiled=sum(counts[1] for counts in distributions.values()),
        roots=tuple(cast("list[str]", report["roots"])),
        python=str(report["python"]),
        python_base=str(report["python_base"]),
    )


def compile_bytecode(state: BytecodeState) -> None:
    """Compile every source under the environment's package directories."""

    # Without the variable, though on CPython 3.14 `compileall` writes either way. Its
    # exit status is not read: it is nonzero when one file anywhere fails to compile,
    # and the caller reads the state again.
    environment = {key: value for key, value in os.environ.items() if key != DONT_WRITE_BYTECODE}
    subprocess.run(
        [str(state.interpreter), "-m", "compileall", "-q", *state.roots],
        capture_output=True,
        check=False,
        env=environment,
    )


def settle_bytecode(
    builds: dict[str, Path], *, compile_missing: bool
) -> tuple[str, dict[str, BytecodeState]]:
    """The one bytecode state every build is in, or a refusal that says how to get one.

    With *compile_missing*, an environment that is not `cached` is compiled first.
    Returns the state and what was read of each build.
    """

    states = {name: bytecode_state(path) for name, path in builds.items()}
    pythons = {state.python for state in states.values()}
    if len(pythons) > 1:
        # A different interpreter does different work to start, whatever it runs, and
        # brings a standard library whose bytecode this does not read.
        raise SystemExit(
            "the builds run on different Python versions, so a ratio between them would "
            "measure the interpreters:\n"
            + "\n".join(f"  {name}: {state.python}" for name, state in states.items())
            + "\nInstall every build into an environment made from one interpreter."
        )
    if compile_missing:
        for name, state in states.items():
            if state.state != "cached":
                print(
                    f"{name}: compiling {state.sources - state.compiled} source files", flush=True
                )
                compile_bytecode(state)
                states[name] = bytecode_state(builds[name])
    found = {state.state for state in states.values()}
    if len(found) == 1 and found <= set(BYTECODE_STATES):
        (state_name,) = found
        for name, state in states.items():
            print(f"{name}: bytecode {state.describe()}", flush=True)
        if state_name == "uncached":
            print(
                "every start in this series compiles its imports, which an installation does "
                "only on its first start; pass --compile-bytecode for the state a release "
                "claim is made in",
                flush=True,
            )
        return state_name, states
    lines = [
        "a ratio is taken only between builds in one bytecode state, all cached or all "
        "uncached, and these are not:"
    ]
    lines += [f"  {name}: {state.describe()}" for name, state in states.items()]
    lines.append(
        "A start without bytecode compiles what it imports, about three times the work of "
        "one that loads it compiled. Compile each environment that is not cached, and run "
        "again:"
    )
    commands = [state.compile_command for state in states.values() if state.state != "cached"]
    lines += [f"  {command}" for command in dict.fromkeys(commands)]
    lines.append("or pass --compile-bytecode, which does that before the first round.")
    raise SystemExit("\n".join(lines))


def _environment(home: Path) -> dict[str, str]:
    # A home of its own, so a build under test never reads or writes the developer's
    # cache, and a fixed hash seed, so set and dict ordering does not vary the work.
    # No measured process writes bytecode, so the state read before the first round is
    # the state of every round: without this, an `uncached` series would compile itself
    # into a cached one as it ran, the control first.
    return {
        **_without_bytecode_writes(),
        "METABROWSER_HOME": str(home),
        "PYTHONHASHSEED": "0",
    }


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
        [str(metab), "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        env=_without_bytecode_writes(),
    )
    return result.stdout.strip()


def cmd_run(args: argparse.Namespace) -> int:
    tree = Path(cast(str, args.tree)).resolve()
    out = Path(cast(str, args.out))
    if out.exists() and out.stat().st_size > 0:
        # Pair numbers start at zero in every run, so a second run's records would
        # share their keys with the first's, and a summary could not tell them apart.
        raise SystemExit(
            f"{out} already holds records. A run writes a file of its own: give a new "
            "path, or remove this one."
        )
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
    bytecode, environments = settle_bytecode(
        builds, compile_missing=cast(bool, args.compile_bytecode)
    )
    with tempfile.TemporaryDirectory(prefix="metab-startup-home-") as home_dir:
        home = Path(home_dir)
        with out.open("w", encoding="utf-8") as stream:
            for pair in range(cast(int, args.pairs)):
                for candidate in candidates:
                    for build in ("control", candidate):
                        load = os.getloadavg()[0]
                        record: dict[str, Any] = {
                            "pair": pair,
                            "candidate": candidate,
                            "build": build,
                            "version": versions[build],
                            "bytecode": bytecode,
                            "python": environments[build].python,
                            "python_base": environments[build].python_base,
                            "load1": load,
                            "recorded_at": time.time(),
                            **_measure(builds[build], tree, home),
                        }
                        stream.write(json.dumps(record) + "\n")
                        stream.flush()
                        print(f"pair {pair} [{candidate}] {build} load={load:.0f}", flush=True)
    return 0


_NOT_METRICS = {
    "pair",
    "candidate",
    "build",
    "version",
    "bytecode",
    "python",
    "python_base",
    "load1",
    "recorded_at",
}
# A record written before the state was read. Such a series may have been taken in
# either state, or across both.
BYTECODE_UNRECORDED: Final = "unrecorded"


def recorded_bytecode(rows: list[dict[str, Any]]) -> str:
    """The one bytecode state *rows* were measured in; refuse rows from more than one."""

    states = sorted({str(row.get("bytecode", BYTECODE_UNRECORDED)) for row in rows})
    if len(states) > 1:
        raise SystemExit(
            f"these records were measured in more than one bytecode state ({', '.join(states)}); "
            "a median across them is of no one condition. Summarize a file that holds one."
        )
    return states[0]


def cmd_summarize(args: argparse.Namespace) -> int:
    candidate = cast(str, args.candidate)
    suffix = cast(str, args.suffix)
    rows = [
        cast("dict[str, Any]", json.loads(line))
        for line in Path(cast(str, args.file)).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [row for row in rows if row["candidate"] == candidate]
    rounds: dict[int, dict[str, dict[str, Any]]] = {}
    versions: dict[str, set[str]] = {}
    for row in rows:
        pair, build = int(row["pair"]), str(row["build"])
        if build in rounds.setdefault(pair, {}):
            # What a second run written into the same file looks like. Keeping either
            # record would pair a measurement with one taken in another run.
            raise SystemExit(
                f"{args.file} holds more than one record for pair {pair} of {build!r} "
                f"against candidate {candidate!r}: it is not the output of one run."
            )
        rounds[pair][build] = row
        versions.setdefault(build, set()).add(str(row.get("version")))
    mixed = {build: sorted(found) for build, found in versions.items() if len(found) > 1}
    if mixed:
        raise SystemExit(
            "a build was recorded under more than one version, so these records are not "
            "one comparison: "
            + "; ".join(f"{build}: {', '.join(found)}" for build, found in sorted(mixed.items()))
        )
    complete = [
        halves
        for _, halves in sorted(rounds.items())
        if "control" in halves and candidate in halves
    ]
    if not complete:
        raise SystemExit(f"no complete pair for candidate {candidate!r}")
    loads = [float(halves[build]["load1"]) for halves in complete for build in halves]
    # Every record of this candidate, a half-finished last pair included.
    bytecode = recorded_bytecode(rows)
    print(
        f"candidate={candidate} pairs={len(complete)} bytecode={bytecode} "
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
    run.add_argument(
        "--compile-bytecode",
        action="store_true",
        help="compile each environment that lacks bytecode before the first round",
    )
    run.add_argument("--out", required=True, help="JSON Lines file to write; it must be new")
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
