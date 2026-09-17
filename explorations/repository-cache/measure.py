"""Phase 0 repository-cache measurements.

Measures the questions the repository-library plan leaves to evidence:
acquisition strategy and store layout, worktree-free reads, lazy-fetch
behavior, concurrent readers and fetches, cancellation, maintenance, and
the platform primitives the lock and publication state machines rely on.

Run from the repository root, one suite at a time::

    uv --config-file uv.toml run --frozen python explorations/repository-cache/measure.py \
        --scratch "$TMPDIR/mb-repository-cache" environment

Every suite writes ``results/<suite>.json`` beside this file, with the
scratch directory and home directory replaced by placeholders. Clones and
temporary repositories live only under ``--scratch``; each suite deletes the
stores it created unless ``--keep`` is given.

Git runs with an isolated configuration (no system or global config, no
prompts, no inherited ``GIT_*`` variables) so a developer's own settings —
credential helpers, filter drivers, maintenance schedules — cannot change a
result. Nothing here is imported by the package.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import platform
import random
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, cast

from metabrowser.git.log import LOG_FORMAT

# JSON-serializable values; json.dumps validates them at write time.
type Json = object

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

SMALL = ("flask", "https://github.com/pallets/flask")
MEDIUM = ("mypy", "https://github.com/python/mypy")

# Metadata fields of `git show` in metabrowser.git.detail, in the same order.
SHOW_FORMAT = "\x1f".join(["%H", "%h", "%an", "%ae", "%at", "%ct", "%P", "%D", "%B"])

# Transport allowlist applied on the command line of every acquisition.
PROTOCOL_ARGS = (
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.https.allow=always",
    "-c",
    "protocol.file.allow=always",
)

# Store configuration written at creation. Disabling automatic maintenance is
# the finding of the maintenance suite, not an assumption: every fetch,
# including each implicit lazy fetch, otherwise spawns a detached
# `git maintenance run --auto`.
STORE_CONFIG = (
    "maintenance.auto=false",
    "gc.auto=0",
    "fetch.recurseSubmodules=false",
    "transfer.bundleURI=false",
    "core.hooksPath=/dev/null",
)

ERROR_CLASSES = (
    ("remote_corruption", "possible repository corruption on the remote side"),
    ("bitmap_closure", "have full closure"),
    ("not_our_ref", "not our ref"),
    ("mailmap_blob_unavailable", "mailmap"),
    ("commit_graph_race", "in the commit graph file but not in the object database"),
    ("promisor_fetch_failed", "from promisor remote"),
    ("lazy_fetch_disabled", "lazy fetching disabled"),
    ("filter_ignored", "filtering not recognized by server"),
    ("cannot_lock_ref", "cannot lock ref"),
    ("unable_to_lock", "Unable to create"),
    ("connection_refused", "Connection refused"),
    ("operation_timeout", "timed out"),
    ("low_speed", "Operation too slow"),
    ("bad_object", "bad object"),
    ("not_valid_object", "not a valid object"),
    ("missing_object", "missing"),
)


# ----------------------------------------------------------------------------
# Process, trace, and statistics primitives


def git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Isolated environment: no inherited GIT_* variables, config, or prompts."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GCM_INTERACTIVE": "never",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class TraceCounts:
    lazy_fetches: int
    maintenance_spawns: int
    remote_helpers: int
    children: int

    def as_json(self) -> dict[str, Json]:
        return {
            "lazy_fetches": self.lazy_fetches,
            "maintenance_spawns": self.maintenance_spawns,
            "remote_helpers": self.remote_helpers,
            "children": self.children,
        }


def parse_trace(path: Path) -> TraceCounts:
    lazy = maintenance = helpers = children = 0
    if not path.exists():
        return TraceCounts(0, 0, 0, 0)
    for line in path.read_text(errors="replace").splitlines():
        if '"child_start"' not in line:
            continue
        with contextlib.suppress(ValueError):
            event = cast(dict[str, object], json.loads(line))
            if event.get("event") != "child_start":
                continue
            argv = [str(part) for part in cast(list[object], event.get("argv", []))]
            children += 1
            if "fetch" in argv and "--stdin" in argv and "fetch.negotiationAlgorithm=noop" in argv:
                lazy += 1
            if "maintenance" in argv or ("gc" in argv and "--auto" in argv):
                maintenance += 1
            if argv[:2] == ["git", "remote-https"] or argv[:2] == ["git", "remote-http"]:
                helpers += 1
    return TraceCounts(lazy, maintenance, helpers, children)


@dataclass
class Outcome:
    argv: list[str]
    wall_s: float
    returncode: int | None
    stdout: bytes
    stderr: str
    timed_out: bool
    trace: TraceCounts | None

    def error_class(self) -> str:
        if self.timed_out:
            return "harness_timeout"
        if self.returncode == 0:
            return ""
        return classify(self.stderr)


def classify(text: str) -> str:
    for name, needle in ERROR_CLASSES:
        if needle in text:
            return name
    return "other" if text.strip() else ""


_TRACE_SEQ = iter(range(1_000_000_000))


def git(
    args: Sequence[str],
    *,
    git_dir: Path | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    timeout: float = 900.0,
    trace_dir: Path | None = None,
    umask: int = -1,
) -> Outcome:
    argv = ["git"]
    if git_dir is not None:
        argv += ["--git-dir", str(git_dir)]
    argv += list(args)
    run_env = dict(env) if env is not None else git_env()
    trace_path: Path | None = None
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"trace-{os.getpid()}-{next(_TRACE_SEQ)}.json"
        run_env["GIT_TRACE2_EVENT"] = str(trace_path)
    started = time.perf_counter()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=run_env,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        umask=umask,
    )
    timed_out = False
    try:
        out, err = process.communicate(input=stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate()
    wall = time.perf_counter() - started
    counts = parse_trace(trace_path) if trace_path is not None else None
    if trace_path is not None:
        trace_path.unlink(missing_ok=True)
    return Outcome(
        argv=argv,
        wall_s=wall,
        returncode=None if timed_out else process.returncode,
        stdout=out,
        stderr=err.decode(errors="replace")[-4000:],
        timed_out=timed_out,
        trace=counts,
    )


def must(outcome: Outcome) -> Outcome:
    if outcome.returncode != 0:
        raise RuntimeError(f"{' '.join(outcome.argv)} failed: {outcome.stderr[-800:]}")
    return outcome


def text(outcome: Outcome) -> str:
    return must(outcome).stdout.decode().strip()


def stats(values: Sequence[float]) -> dict[str, Json]:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0}
    result: dict[str, Json] = {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
    }
    if len(ordered) > 1:
        mean = statistics.fmean(ordered)
        spread = statistics.stdev(ordered)
        result["stdev"] = round(spread, 4)
        result["cv"] = round(spread / mean, 3) if mean else None
    return result


def percentiles(values: Sequence[float]) -> dict[str, Json]:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0}

    def pick(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]

    return {
        "n": len(ordered),
        "p50_ms": round(pick(0.5) * 1000, 3),
        "p95_ms": round(pick(0.95) * 1000, 3),
        "p99_ms": round(pick(0.99) * 1000, 3),
        "max_ms": round(ordered[-1] * 1000, 3),
    }


def disk_usage(path: Path) -> dict[str, Json]:
    apparent = allocated = files = 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            with contextlib.suppress(FileNotFoundError):
                info = os.lstat(os.path.join(root, name))
                apparent += info.st_size
                allocated += info.st_blocks * 512
                files += 1
    return {"apparent_bytes": apparent, "allocated_bytes": allocated, "files": files}


def count_objects(git_dir: Path) -> dict[str, Json]:
    raw = text(git(["count-objects", "-v"], git_dir=git_dir))
    values: dict[str, Json] = {}
    for line in raw.splitlines():
        key, _, value = line.partition(": ")
        with contextlib.suppress(ValueError):
            values[key.replace("-", "_")] = int(value)
    packs = git_dir / "objects" / "pack"
    values["promisor_packs"] = len(list(packs.glob("*.promisor"))) if packs.exists() else 0
    return values


_RECEIVED = re.compile(r"Receiving objects:\s+100% \((\d+)/\d+\), ([\d.]+) (bytes|KiB|MiB|GiB)")
_UNITS = {"bytes": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}


def received(stderr: str) -> dict[str, Json]:
    matches = _RECEIVED.findall(stderr.replace("\r", "\n"))
    if not matches:
        return {"objects": None, "bytes": None}
    objects, amount, unit = cast(tuple[str, str, str], matches[-1])
    return {"objects": int(objects), "bytes": round(float(amount) * _UNITS[unit])}


def remove(path: Path) -> None:
    def make_writable(function: Callable[..., object], name: str, _exc: BaseException) -> None:
        os.chmod(name, 0o700)
        function(name)

    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, onexc=make_writable)
    elif path.exists() or path.is_symlink():
        path.unlink()


def copy_store(source: Path, destination: Path) -> Path:
    remove(destination)
    shutil.copytree(source, destination, symlinks=True)
    return destination


class Recorder:
    """Collects rows and writes one normalized JSON result file."""

    def __init__(self, suite: str, scratch: Path, parameters: dict[str, Json]) -> None:
        self.suite = suite
        self.scratch = scratch
        self.parameters = parameters
        self.rows: list[dict[str, Json]] = []
        self.started = datetime.now(UTC)

    def add(self, **row: Json) -> None:
        self.rows.append(dict(row))
        summary = {key: value for key, value in row.items() if not isinstance(value, (dict, list))}
        print(json.dumps(self._normalize(summary), sort_keys=True), flush=True)

    def _normalize(self, value: Json) -> Json:
        if isinstance(value, str):
            normalized = value.replace(str(self.scratch.resolve()), "<SCRATCH>")
            normalized = normalized.replace(str(self.scratch), "<SCRATCH>")
            return normalized.replace(str(Path.home()), "<HOME>")
        if isinstance(value, list):
            return [self._normalize(item) for item in cast(list[object], value)]
        if isinstance(value, dict):
            return {
                str(key): self._normalize(item)
                for key, item in cast(dict[object, object], value).items()
            }
        return value

    def write(self) -> Path:
        RESULTS.mkdir(parents=True, exist_ok=True)
        document: dict[str, Json] = {
            "schema": "metabrowser-repository-cache-measurement-v1",
            "suite": self.suite,
            "started_at": self.started.isoformat(timespec="seconds"),
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "environment": environment(),
            "parameters": self.parameters,
            "rows": self.rows,
        }
        path = RESULTS / f"{self.suite}.json"
        path.write_text(json.dumps(self._normalize(document), indent=2, sort_keys=True) + "\n")
        return path


def environment() -> dict[str, Json]:
    def command(*argv: str) -> str:
        with contextlib.suppress(OSError, subprocess.CalledProcessError):
            return subprocess.run(argv, capture_output=True, text=True, check=True).stdout.strip()
        return ""

    return {
        "git_version": text(git(["version"])),
        "git_build_options": command("git", "version", "--build-options").splitlines()[1:6],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": command("sysctl", "-n", "machdep.cpu.brand_string") or platform.processor(),
        "logical_cpus": os.cpu_count(),
        "memory_bytes": int(command("sysctl", "-n", "hw.memsize") or 0),
        "python": platform.python_version(),
    }


# ----------------------------------------------------------------------------
# Repository preparation


@dataclass(frozen=True)
class Origin:
    name: str
    url: str


def clone_args(*, layout: str, strategy: str, url: str, destination: Path) -> list[str]:
    args = [*PROTOCOL_ARGS, "clone", "--progress", "--template="]
    for item in STORE_CONFIG:
        args += ["--config", item]
    args.append("--bare" if layout == "bare" else "--no-checkout")
    if strategy == "blobless":
        args.append("--filter=blob:none")
    return [*args, "--", url, str(destination)]


def store_git_dir(destination: Path, layout: str) -> Path:
    return destination / ".git" if layout == "no-checkout" else destination


def local_origin(scratch: Path, name: str, url: str) -> Path:
    """A full bare mirror that serves filtered fetches like a hosting provider."""
    origin = scratch / "origins" / f"{name}.git"
    if not (origin / "HEAD").exists():
        origin.parent.mkdir(parents=True, exist_ok=True)
        must(git([*PROTOCOL_ARGS, "clone", "--bare", "--template=", "--", url, str(origin)]))
    for item in ("uploadpack.allowFilter", "uploadpack.allowAnySHA1InWant"):
        must(git(["config", item, "true"], git_dir=origin))
    return origin


def file_url(path: Path) -> str:
    return f"file://{path.resolve()}"


@dataclass(frozen=True)
class Subjects:
    head: str
    first_parent: list[str]
    wide_base: str
    other_tip: str
    paths: list[str]
    blobs: list[str]
    other_blobs: list[str]


def tree_blobs(git_dir: Path, commit: str) -> list[tuple[str, str]]:
    raw = must(git(["ls-tree", "-r", "-z", "--full-tree", commit], git_dir=git_dir)).stdout
    entries: list[tuple[str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        _mode, kind, oid = meta.decode().split(" ")
        if kind == "blob":
            entries.append((oid, path.decode(errors="replace")))
    return entries


def select_subjects(git_dir: Path) -> Subjects:
    head = text(git(["rev-parse", "HEAD"], git_dir=git_dir))
    first_parent = text(
        git(["rev-list", "--first-parent", "--max-count=20", head], git_dir=git_dir)
    ).split()
    wide_base = text(git(["rev-parse", f"{head}~50"], git_dir=git_dir))
    tips = text(
        git(
            ["for-each-ref", "--sort=-committerdate", "--format=%(objectname)", "refs/heads"],
            git_dir=git_dir,
        )
    ).split()
    other_tip = head
    for tip in tips:
        if tip == head:
            continue
        ancestor = git(["merge-base", "--is-ancestor", tip, head], git_dir=git_dir)
        if ancestor.returncode == 1:
            other_tip = tip
            break
    blobs = tree_blobs(git_dir, head)
    rng = random.Random(0)
    paths = [path for _oid, path in rng.sample(blobs, min(20, len(blobs)))]
    head_oids = {oid for oid, _path in blobs}
    other_blobs = [oid for oid, _path in tree_blobs(git_dir, other_tip) if oid not in head_oids]
    return Subjects(
        head=head,
        first_parent=first_parent,
        wide_base=wide_base,
        other_tip=other_tip,
        paths=paths,
        blobs=[oid for oid, _path in blobs],
        other_blobs=other_blobs,
    )


# ----------------------------------------------------------------------------
# Suite: environment


def suite_environment(scratch: Path, _args: argparse.Namespace) -> None:
    recorder = Recorder("environment", scratch, {})
    probes: dict[str, list[str]] = {
        "no_lazy_fetch_option": ["--no-lazy-fetch", "version"],
        "backfill_help": ["backfill", "-h"],
        "cat_file_batch_command": ["cat-file", "-h"],
        "ls_tree_format": ["ls-tree", "-h"],
    }
    for name, argv in probes.items():
        outcome = git(argv)
        combined = outcome.stdout.decode(errors="replace") + outcome.stderr
        recorder.add(
            probe=name,
            returncode=outcome.returncode,
            mentions_batch_command="--batch-command" in combined,
            mentions_format="--format" in combined,
            first_line=combined.strip().splitlines()[0] if combined.strip() else "",
        )
    print(recorder.write())


# ----------------------------------------------------------------------------
# Suite: acquire


def layout_facts(git_dir: Path, destination: Path) -> dict[str, Json]:
    refs = text(git(["for-each-ref", "--format=%(refname)"], git_dir=git_dir)).splitlines()
    fetch_spec = git(["config", "--get-all", "remote.origin.fetch"], git_dir=git_dir)
    return {
        "core_bare": text(git(["config", "--get", "core.bare"], git_dir=git_dir)),
        "has_index": (git_dir / "index").exists(),
        "has_reflogs": (git_dir / "logs").exists(),
        "worktree_entries": (
            len([p for p in destination.iterdir() if p.name != ".git"])
            if destination != git_dir
            else None
        ),
        "fetch_refspec": fetch_spec.stdout.decode().strip() or None,
        "local_heads": sum(1 for ref in refs if ref.startswith("refs/heads/")),
        "remote_tracking": sum(1 for ref in refs if ref.startswith("refs/remotes/")),
        "tags": sum(1 for ref in refs if ref.startswith("refs/tags/")),
        "promisor": fetch_value(git_dir, "remote.origin.promisor"),
        "partial_clone_filter": fetch_value(git_dir, "remote.origin.partialclonefilter"),
        "maintenance_auto": fetch_value(git_dir, "maintenance.auto"),
    }


def fetch_value(git_dir: Path, key: str) -> str | None:
    outcome = git(["config", "--get", key], git_dir=git_dir)
    return outcome.stdout.decode().strip() if outcome.returncode == 0 else None


def acquire_init_fetch(url: str, destination: Path, strategy: str, traces: Path) -> Outcome:
    """`init --bare` plus explicit config and one fetch: the controlled layout."""
    remove(destination)
    started = time.perf_counter()
    must(git(["init", "--bare", "--template=", "-q", str(destination)]))
    for item in STORE_CONFIG:
        key, _, value = item.partition("=")
        must(git(["config", key, value], git_dir=destination))
    must(git(["config", "remote.origin.url", url], git_dir=destination))
    fetch = [*PROTOCOL_ARGS, "fetch", "--progress", "--no-write-fetch-head"]
    if strategy == "blobless":
        fetch.append("--filter=blob:none")
    fetch += ["origin", "+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*"]
    outcome = git(fetch, git_dir=destination, trace_dir=traces)
    head = git([*PROTOCOL_ARGS, "ls-remote", "--symref", "origin", "HEAD"], git_dir=destination)
    outcome.wall_s = time.perf_counter() - started
    outcome.stderr += head.stderr
    return outcome


def suite_acquire(scratch: Path, args: argparse.Namespace) -> None:
    reps = cast(int, args.reps)
    origins = [Origin(SMALL[0] + "-https", SMALL[1]), Origin(MEDIUM[0] + "-https", MEDIUM[1])]
    medium_origin = local_origin(scratch, MEDIUM[0], MEDIUM[1])
    origins.append(Origin(MEDIUM[0] + "-file", file_url(medium_origin)))
    if cast(str, args.only):
        origins = [origin for origin in origins if origin.name in cast(str, args.only).split(",")]
    recorder = Recorder(
        "acquire",
        scratch,
        {
            "reps": reps,
            "origins": [origin.url for origin in origins],
            "layouts": ["bare", "no-checkout", "init-fetch"],
            "strategies": ["full", "blobless", "blobless+backfill"],
            "store_config": list(STORE_CONFIG),
        },
    )
    work = scratch / "acquire"
    traces = scratch / "traces"
    plan = [
        (layout, strategy)
        for layout in ("bare", "no-checkout", "init-fetch")
        for strategy in ("full", "blobless")
    ]
    for rep in range(reps):
        order = plan if rep % 2 == 0 else list(reversed(plan))
        for origin in origins:
            for layout, strategy in order:
                destination = work / f"{origin.name}-{layout}-{strategy}"
                remove(destination)
                if layout == "init-fetch":
                    outcome = acquire_init_fetch(origin.url, destination, strategy, traces)
                else:
                    outcome = git(
                        clone_args(
                            layout=layout,
                            strategy=strategy,
                            url=origin.url,
                            destination=destination,
                        ),
                        cwd=work if work.exists() else None,
                        trace_dir=traces,
                    )
                git_dir = store_git_dir(destination, layout)
                row: dict[str, Json] = {
                    "origin": origin.name,
                    "layout": layout,
                    "strategy": strategy,
                    "rep": rep,
                    "acquire_s": round(outcome.wall_s, 3),
                    "returncode": outcome.returncode,
                    "error_class": outcome.error_class(),
                    "filter_ignored": "filtering not recognized" in outcome.stderr,
                    "received": received(outcome.stderr),
                    "trace": outcome.trace.as_json() if outcome.trace else None,
                    "disk": disk_usage(git_dir),
                    "objects": count_objects(git_dir),
                }
                if rep == 0:
                    row["layout_facts"] = layout_facts(git_dir, destination)
                if strategy == "blobless" and outcome.returncode == 0:
                    backfill = git(["backfill"], git_dir=git_dir, trace_dir=traces)
                    row["backfill_s"] = round(backfill.wall_s, 3)
                    row["backfill_returncode"] = backfill.returncode
                    row["backfill_error_class"] = backfill.error_class()
                    row["backfill_trace"] = backfill.trace.as_json() if backfill.trace else None
                    row["disk_after_backfill"] = disk_usage(git_dir)
                    row["objects_after_backfill"] = count_objects(git_dir)
                recorder.add(**row)
                if not args.keep:
                    remove(destination)
    # A file:// origin that has not opted in to filtering, like most user repositories.
    if any(origin.name.endswith("-file") for origin in origins):
        must(git(["config", "uploadpack.allowFilter", "false"], git_dir=medium_origin))
        destination = work / "file-origin-without-allow-filter"
        outcome = git(
            clone_args(
                layout="bare",
                strategy="blobless",
                url=file_url(medium_origin),
                destination=destination,
            )
        )
        recorder.add(
            origin=MEDIUM[0] + "-file-no-allow-filter",
            layout="bare",
            strategy="blobless",
            rep=0,
            acquire_s=round(outcome.wall_s, 3),
            returncode=outcome.returncode,
            filter_ignored="filtering not recognized" in outcome.stderr,
            promisor=fetch_value(destination, "remote.origin.promisor"),
            objects=count_objects(destination),
        )
        must(git(["config", "uploadpack.allowFilter", "true"], git_dir=medium_origin))
        remove(destination)
    print(recorder.write())


# ----------------------------------------------------------------------------
# Suite: read


def missing_frames(output: bytes) -> int:
    """Count `<oid> missing` frames in `cat-file --batch` output, skipping bodies.

    A substring count also matches blob bodies that happen to contain the
    text, which is how results/read.json came to report a few "missing" rows
    for full stores; that file predates this parser.
    """
    missing = 0
    offset = 0
    while offset < len(output):
        end = output.index(b"\n", offset)
        header = output[offset:end].split(b" ")
        offset = end + 1
        if len(header) == 2 and header[1] == b"missing":
            missing += 1
        elif len(header) == 3:
            offset += int(header[2]) + 1
    return missing


def batch_read(git_dir: Path, oids: Sequence[str], env: dict[str, str]) -> Outcome:
    return git(
        ["cat-file", "--batch"], git_dir=git_dir, env=env, stdin=("\n".join(oids) + "\n").encode()
    )


def batch_command_latency(
    git_dir: Path, oids: Sequence[str], env: dict[str, str]
) -> dict[str, Json]:
    """One persistent `cat-file --batch-command --buffer` actor: info, then contents."""
    started = time.perf_counter()
    process = subprocess.Popen(
        ["git", "--git-dir", str(git_dir), "cat-file", "--batch-command", "--buffer"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    stdin = cast(IO[bytes], process.stdin)
    stdout = cast(IO[bytes], process.stdout)
    latencies: list[float] = []
    first_response_s: float | None = None
    missing = 0
    body_bytes = 0
    for oid in oids:
        request = time.perf_counter()
        stdin.write(f"info {oid}\nflush\n".encode())
        stdin.flush()
        header = stdout.readline().decode().split()
        if first_response_s is None:
            first_response_s = time.perf_counter() - started
        if len(header) < 3:
            missing += 1
            latencies.append(time.perf_counter() - request)
            continue
        size = int(header[2])
        stdin.write(f"contents {oid}\nflush\n".encode())
        stdin.flush()
        stdout.readline()
        body_bytes += len(stdout.read(size + 1)) - 1
        latencies.append(time.perf_counter() - request)
    stdin.close()
    process.wait()
    return {
        "requests": len(oids),
        "missing": missing,
        "body_bytes": body_bytes,
        "first_response_ms": round((first_response_s or 0) * 1000, 3),
        "latency": percentiles(latencies),
    }


@dataclass
class OpResult:
    walls: list[float]
    returncodes: list[int | None]
    lazy_fetches: int
    maintenance_spawns: int
    error_classes: list[str]
    output_bytes: int


def run_op(
    commands: Sequence[tuple[list[str], bytes | None]],
    git_dir: Path,
    env: dict[str, str],
    traces: Path,
    timeout: float,
) -> OpResult:
    result = OpResult([], [], 0, 0, [], 0)
    for argv, stdin in commands:
        outcome = git(
            argv, git_dir=git_dir, env=env, stdin=stdin, trace_dir=traces, timeout=timeout
        )
        result.walls.append(outcome.wall_s)
        result.returncodes.append(outcome.returncode)
        result.output_bytes += len(outcome.stdout)
        if outcome.trace:
            result.lazy_fetches += outcome.trace.lazy_fetches
            result.maintenance_spawns += outcome.trace.maintenance_spawns
        error = outcome.error_class()
        if error:
            result.error_classes.append(error)
    return result


type Commands = list[tuple[list[str], bytes | None]]


def command(argv: list[str], stdin: bytes | None = None) -> tuple[list[str], bytes | None]:
    return (argv, stdin)


def route_commands(subjects: Subjects) -> dict[str, Commands]:
    """The argument vectors the v0.10 routes issue, bound to full object IDs."""
    commits = subjects.first_parent
    pairs = [(f"{commit}^", commit) for commit in commits[:-1]]
    pairs.append((subjects.wide_base, subjects.head))
    rename_flags = ["-M50", "-C", "--diff-merges=first-parent"]
    commands: dict[str, Commands] = {
        "inventory_ls_tree": [command(["ls-tree", "-r", "-z", "--full-tree", subjects.head])],
        "inventory_ls_tree_long": [
            command(["ls-tree", "-r", "-z", "-l", "--full-tree", subjects.head])
        ],
        "path_identity_ls_tree": [
            command(["ls-tree", "-z", "--full-tree", subjects.head, "--", path])
            for path in subjects.paths
        ],
        "path_identity_rev_parse": [
            command(["rev-parse", "--verify", f"{subjects.head}:{path}"]) for path in subjects.paths
        ],
        "history_scope_refs": [
            command(["for-each-ref", "--format=%(refname)%00%(objecttype)%00%(objectname)", "refs"])
        ],
        "history_page": [
            command(
                [
                    "log",
                    "-z",
                    f"--format={LOG_FORMAT}",
                    "--decorate=full",
                    "--date-order",
                    "--max-count=250",
                    "--stdin",
                ],
                f"{subjects.head}\n".encode(),
            )
        ],
        "history_count": [command(["rev-list", "--count", subjects.head])],
        "commit_detail_raw_only": [
            command(["show", "-z", "--raw", "--no-abbrev", f"--format={SHOW_FORMAT}", commit])
            for commit in commits
        ],
        "commit_detail": [
            command(
                [
                    "show",
                    "-z",
                    "--raw",
                    "--numstat",
                    "-M",
                    "-C",
                    "--diff-merges=first-parent",
                    f"--format={SHOW_FORMAT}",
                    commit,
                ]
            )
            for commit in commits
        ],
        "comparison_manifest": [
            command(["diff", "--raw", "-z", "--no-abbrev", *rename_flags, left, right])
            for left, right in pairs
        ]
        + [
            command(["diff", "--numstat", "-z", *rename_flags, left, right])
            for left, right in pairs
        ],
        "deferred_patches": [
            command(["diff", *rename_flags, left, right]) for left, right in pairs
        ],
    }
    return commands


def changed_blobs(git_dir: Path, subjects: Subjects, env: dict[str, str]) -> list[str]:
    oids: list[str] = []
    for commit in subjects.first_parent[:-1]:
        raw = must(
            git(
                ["diff", "--raw", "-z", "--no-abbrev", f"{commit}^", commit],
                git_dir=git_dir,
                env=env,
            )
        ).stdout
        for token in raw.split(b"\0"):
            if token.startswith(b":"):
                new_oid = token.decode().split(" ")[3]
                if set(new_oid) != {"0"}:
                    oids.append(new_oid)
    return oids


def suite_read(scratch: Path, args: argparse.Namespace) -> None:
    reps = cast(int, args.reps)
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "read"
    repositories = [SMALL, MEDIUM]
    if cast(str, args.only):
        repositories = [repo for repo in repositories if repo[0] in cast(str, args.only).split(",")]
    recorder = Recorder("read", scratch, {"reps": reps, "timeout_s": timeout})
    lazy = git_env()
    no_lazy = git_env({"GIT_NO_LAZY_FETCH": "1"})
    for name, url in repositories:
        origin = local_origin(scratch, name, url)
        full = work / f"{name}-full.git"
        blobless = work / f"{name}-blobless.git"
        backfilled = work / f"{name}-backfilled.git"
        for destination, strategy in ((full, "full"), (blobless, "blobless")):
            remove(destination)
            must(
                git(
                    clone_args(
                        layout="bare",
                        strategy=strategy,
                        url=file_url(origin),
                        destination=destination,
                    )
                )
            )
        copy_store(blobless, backfilled)
        backfill = must(git(["backfill"], git_dir=backfilled, trace_dir=traces))
        subjects = select_subjects(full)
        commands = route_commands(subjects)
        content_oids = changed_blobs(full, subjects, lazy)
        commands["revision_content"] = [command(["cat-file", "blob", oid]) for oid in content_oids]
        recorder.add(
            repository=name,
            op="subjects",
            head=subjects.head,
            other_tip=subjects.other_tip,
            head_tree_blobs=len(subjects.blobs),
            other_tip_unique_blobs=len(subjects.other_blobs),
            first_parent_commits=len(subjects.first_parent),
            revision_content_blobs=len(content_oids),
            backfill_s=round(backfill.wall_s, 3),
            objects_full=count_objects(full),
            objects_blobless=count_objects(blobless),
            objects_backfilled=count_objects(backfilled),
        )
        variants: list[tuple[str, Path, dict[str, str], bool]] = [
            ("full", full, lazy, False),
            ("blobless_lazy", blobless, lazy, True),
            ("blobless_no_lazy", blobless, no_lazy, False),
            ("backfilled_lazy", backfilled, lazy, True),
            ("backfilled_no_lazy", backfilled, no_lazy, False),
        ]
        for variant, store, env, fresh in variants:
            for op, op_commands in commands.items():
                walls: list[float] = []
                first: OpResult | None = None
                for rep in range(reps if not fresh else 1):
                    target = store
                    if fresh:
                        target = copy_store(store, work / f"{name}-{variant}-scratch.git")
                    before = count_objects(target)["in_pack"] if fresh else None
                    result = run_op(op_commands, target, env, traces, timeout)
                    walls.append(sum(result.walls))
                    if rep == 0:
                        first = result
                        if fresh and before is not None:
                            after = count_objects(target)["in_pack"]
                            recorder.add(
                                repository=name,
                                variant=variant,
                                op=op,
                                invocations=len(op_commands),
                                wall=stats(walls),
                                returncodes_nonzero=sum(
                                    1 for code in result.returncodes if code != 0
                                ),
                                lazy_fetches=result.lazy_fetches,
                                maintenance_spawns=result.maintenance_spawns,
                                objects_fetched=cast(int, after) - cast(int, before),
                                error_classes=sorted(set(result.error_classes)),
                                output_bytes=result.output_bytes,
                            )
                            remove(target)
                if not fresh and first is not None:
                    recorder.add(
                        repository=name,
                        variant=variant,
                        op=op,
                        invocations=len(op_commands),
                        wall=stats(walls),
                        returncodes_nonzero=sum(1 for code in first.returncodes if code != 0),
                        lazy_fetches=first.lazy_fetches,
                        maintenance_spawns=first.maintenance_spawns,
                        error_classes=sorted(set(first.error_classes)),
                        output_bytes=first.output_bytes,
                    )
            # Whole-tree batched reads and a persistent actor.
            if variant.endswith("no_lazy") or variant == "full":
                walls = []
                outcome: Outcome | None = None
                for _rep in range(reps):
                    outcome = batch_read(store, subjects.blobs, env)
                    walls.append(outcome.wall_s)
                assert outcome is not None
                missing = missing_frames(outcome.stdout)
                recorder.add(
                    repository=name,
                    variant=variant,
                    op="batch_read_head_tree",
                    blobs=len(subjects.blobs),
                    output_bytes=len(outcome.stdout),
                    missing=missing,
                    wall=stats(walls),
                    blobs_per_s=round(len(subjects.blobs) / statistics.median(walls)),
                )
                other = batch_read(store, subjects.other_blobs, env)
                recorder.add(
                    repository=name,
                    variant=variant,
                    op="batch_read_other_branch_unique",
                    blobs=len(subjects.other_blobs),
                    missing=missing_frames(other.stdout),
                    wall=stats([other.wall_s]),
                )
                sample = random.Random(1).sample(subjects.blobs, min(500, len(subjects.blobs)))
                recorder.add(
                    repository=name,
                    variant=variant,
                    op="batch_command_actor",
                    **batch_command_latency(store, sample, env),
                )
        # Explicit subject-scoped prefetch of the other branch's missing blobs.
        target = copy_store(blobless, work / f"{name}-prefetch-scratch.git")
        check = git(
            ["cat-file", "--batch-check"],
            git_dir=target,
            env=no_lazy,
            stdin=("\n".join(tree_oids(full, subjects.other_tip)) + "\n").encode(),
        )
        missing_oids = [
            line.split()[0]
            for line in check.stdout.decode().splitlines()
            if line.endswith(" missing")
        ]
        before = count_objects(target)["in_pack"]
        prefetch = git(
            [
                *PROTOCOL_ARGS,
                "-c",
                "fetch.negotiationAlgorithm=noop",
                "fetch",
                "origin",
                "--no-tags",
                "--no-write-fetch-head",
                "--recurse-submodules=no",
                "--filter=blob:none",
                "--stdin",
            ],
            git_dir=target,
            env=lazy,
            stdin=("\n".join(missing_oids) + "\n").encode(),
            trace_dir=traces,
        )
        after = count_objects(target)["in_pack"]
        recorder.add(
            repository=name,
            variant="blobless",
            op="explicit_tree_prefetch_other_tip",
            missing_before=len(missing_oids),
            wall=stats([prefetch.wall_s]),
            returncode=prefetch.returncode,
            objects_fetched=cast(int, after) - cast(int, before),
            trace=prefetch.trace.as_json() if prefetch.trace else None,
        )
        remove(target)
        if not args.keep:
            for store in (full, blobless, backfilled):
                remove(store)
    print(recorder.write())


def tree_oids(git_dir: Path, commit: str) -> list[str]:
    return [oid for oid, _path in tree_blobs(git_dir, commit)]


# ----------------------------------------------------------------------------
# Suite: lazy (network-facing lazy fetch, bounded and unbounded)


class Blackhole:
    """Accepts HTTP connections and never answers."""

    def __init__(self) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(16)
        self.port = cast(int, self.server.getsockname()[1])
        self.connections: list[socket.socket] = []
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self) -> None:
        with contextlib.suppress(OSError):
            while True:
                connection, _address = self.server.accept()
                self.connections.append(connection)

    def close(self) -> None:
        for connection in self.connections:
            connection.close()
        self.server.close()


def closed_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = cast(int, probe.getsockname()[1])
    probe.close()
    return port


def suite_lazy(scratch: Path, args: argparse.Namespace) -> None:
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "lazy"
    recorder = Recorder("lazy", scratch, {"timeout_s": timeout})
    name, url = SMALL
    https_blobless = work / f"{name}-https-blobless.git"
    remove(https_blobless)
    must(git(clone_args(layout="bare", strategy="blobless", url=url, destination=https_blobless)))
    full = work / f"{name}-full.git"
    remove(full)
    must(
        git(
            clone_args(
                layout="bare",
                strategy="full",
                url=file_url(local_origin(scratch, name, url)),
                destination=full,
            )
        )
    )
    subjects = select_subjects(full)
    readme = text(git(["rev-parse", f"{subjects.head}:README.md"], git_dir=full))

    # 1. Per-object lazy fetch latency against the real hosting provider.
    commands = route_commands(subjects)
    for op in (
        "commit_detail",
        "comparison_manifest",
        "deferred_patches",
        "inventory_ls_tree_long",
    ):
        target = copy_store(https_blobless, work / "https-scratch.git")
        before = count_objects(target)["in_pack"]
        result = run_op(commands[op][:10], target, git_env(), traces, timeout)
        after = count_objects(target)["in_pack"]
        total = sum(result.walls)
        recorder.add(
            case="https_lazy_fetch",
            op=op,
            invocations=len(commands[op][:10]),
            wall_s=round(total, 3),
            lazy_fetches=result.lazy_fetches,
            s_per_lazy_fetch=round(total / result.lazy_fetches, 3) if result.lazy_fetches else None,
            objects_fetched=cast(int, after) - cast(int, before),
            returncodes_nonzero=sum(1 for code in result.returncodes if code != 0),
            error_classes=sorted(set(result.error_classes)),
            maintenance_spawns=result.maintenance_spawns,
        )
        remove(target)

    # 2. Unreachable, refusing, and stalled promisor remotes.
    hole = Blackhole()
    cases: list[tuple[str, str, list[str], dict[str, str]]] = [
        ("stalled_remote_default", f"http://127.0.0.1:{hole.port}/r.git", [], {}),
        (
            "stalled_remote_low_speed_3s",
            f"http://127.0.0.1:{hole.port}/r.git",
            ["-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=3"],
            {},
        ),
        ("refused_remote", f"http://127.0.0.1:{closed_port()}/r.git", [], {}),
        (
            "stalled_remote_no_lazy_env",
            f"http://127.0.0.1:{hole.port}/r.git",
            [],
            {"GIT_NO_LAZY_FETCH": "1"},
        ),
        (
            "stalled_remote_no_lazy_option",
            f"http://127.0.0.1:{hole.port}/r.git",
            ["--no-lazy-fetch"],
            {},
        ),
        (
            "stalled_remote_promisor_false",
            f"http://127.0.0.1:{hole.port}/r.git",
            ["-c", "remote.origin.promisor=false"],
            {},
        ),
    ]
    for case, remote, prefix, extra in cases:
        target = copy_store(https_blobless, work / "stall-scratch.git")
        must(git(["config", "remote.origin.url", remote], git_dir=target))
        outcome = git(
            [*PROTOCOL_ARGS, "-c", "protocol.http.allow=always", *prefix, "cat-file", "-p", readme],
            git_dir=target,
            env=git_env(extra),
            timeout=min(timeout, 20.0),
            trace_dir=traces,
        )
        recorder.add(
            case=case,
            op="cat_file_missing_blob",
            wall_s=round(outcome.wall_s, 3),
            timed_out=outcome.timed_out,
            returncode=outcome.returncode,
            error_class=outcome.error_class(),
            lazy_fetches=outcome.trace.lazy_fetches if outcome.trace else None,
        )
        remove(target)
    hole.close()

    # 3. The batch actor stays framed when an object is missing and lazy fetch is disabled.
    target = copy_store(https_blobless, work / "frame-scratch.git")
    requests = f"info {readme}\ncontents {readme}\ninfo {subjects.head}\n".encode()
    framed = git(
        ["cat-file", "--batch-command"],
        git_dir=target,
        env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        stdin=requests,
    )
    recorder.add(
        case="batch_command_missing_frame",
        op="cat_file_batch_command",
        returncode=framed.returncode,
        stdout=framed.stdout.decode(errors="replace"),
    )
    remove(target)
    if not args.keep:
        remove(https_blobless)
        remove(full)
    print(recorder.write())


# ----------------------------------------------------------------------------
# Suite: concurrency


def drain_digest(stream: IO[bytes], sink: dict[str, str], key: str) -> None:
    digest = hashlib.sha256()
    while chunk := stream.read(1 << 16):
        digest.update(chunk)
    sink[key] = digest.hexdigest()


def batch_process(git_dir: Path, oids: Sequence[str]) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        ["git", "--git-dir", str(git_dir), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=git_env(),
    )
    payload = ("\n".join(oids) + "\n").encode()

    def feed() -> None:
        stdin = cast(IO[bytes], process.stdin)
        with contextlib.suppress(BrokenPipeError):
            stdin.write(payload)
            stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    return process


def parallel_batch(git_dir: Path, groups: Sequence[Sequence[str]]) -> tuple[float, list[str]]:
    digests: dict[str, str] = {}
    started = time.perf_counter()
    processes = [batch_process(git_dir, group) for group in groups]
    threads = [
        threading.Thread(
            target=drain_digest, args=(cast(IO[bytes], process.stdout), digests, str(index))
        )
        for index, process in enumerate(processes)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for process in processes:
        process.wait()
    return time.perf_counter() - started, [digests[str(index)] for index in range(len(groups))]


def add_origin_commits(origin: Path, prefix: str, count: int, blob_bytes: int) -> list[str]:
    """Commits with fresh random blobs on new branches, written directly into a bare origin."""
    head = text(git(["rev-parse", "HEAD"], git_dir=origin))
    tree = text(git(["rev-parse", "HEAD^{tree}"], git_dir=origin))
    rng = random.Random(prefix)
    refs: list[str] = []
    for index in range(count):
        blob = text(
            git(["hash-object", "-w", "--stdin"], git_dir=origin, stdin=rng.randbytes(blob_bytes))
        )
        entries = must(git(["ls-tree", "-z", tree], git_dir=origin)).stdout
        entries += f"100644 blob {blob}\tmeasure-{prefix}-{index}.bin\0".encode()
        new_tree = text(git(["mktree", "-z"], git_dir=origin, stdin=entries))
        env = git_env(
            {
                "GIT_AUTHOR_NAME": "Measure",
                "GIT_AUTHOR_EMAIL": "measure@example.invalid",
                "GIT_COMMITTER_NAME": "Measure",
                "GIT_COMMITTER_EMAIL": "measure@example.invalid",
            }
        )
        commit = text(
            git(["commit-tree", new_tree, "-p", head, "-m", prefix], git_dir=origin, env=env)
        )
        ref = f"refs/heads/measure/{prefix}/{index}"
        must(git(["update-ref", ref, commit], git_dir=origin))
        refs.append(ref)
    return refs


class ReaderLoad:
    """Reader threads that list a random historical tree and batch-read its blobs."""

    def __init__(self, store: Path, commits: Sequence[str], readers: int) -> None:
        self.store = store
        self.commits = list(commits)
        self.tallies: dict[str, int] = {"iterations": 0, "failures": 0, "missing": 0}
        self.failure_classes: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._run, args=(seed,)) for seed in range(readers)
        ]
        for thread in self._threads:
            thread.start()

    def _run(self, seed: int) -> None:
        rng = random.Random(seed)
        while not self._stop.is_set():
            commit = rng.choice(self.commits)
            listing = git(["ls-tree", "-r", "-z", "--full-tree", commit], git_dir=self.store)
            oids = [
                record.split(b"\t")[0].split(b" ")[2].decode()
                for record in listing.stdout.split(b"\0")
                if b" blob " in record
            ]
            reads = git(
                ["cat-file", "--batch"],
                git_dir=self.store,
                stdin=("\n".join(rng.sample(oids, min(50, len(oids)))) + "\n").encode(),
            )
            with self._lock:
                self.tallies["iterations"] += 1
                if listing.returncode != 0 or reads.returncode != 0:
                    self.tallies["failures"] += 1
                    self.failure_classes.add(classify(listing.stderr + reads.stderr))
                self.tallies["missing"] += missing_frames(reads.stdout)

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join()


def suite_concurrency(scratch: Path, args: argparse.Namespace) -> None:
    reps = cast(int, args.reps)
    work = scratch / "concurrency"
    recorder = Recorder("concurrency", scratch, {"reps": reps})
    name, url = MEDIUM
    origin = local_origin(scratch, name, url)
    store = work / f"{name}-full.git"
    remove(store)
    must(git(clone_args(layout="bare", strategy="full", url=file_url(origin), destination=store)))
    subjects = select_subjects(store)
    old = text(git(["rev-list", "--max-count=1", "--skip=3000", subjects.head], git_dir=store))
    tree_a = tree_oids(store, subjects.head)
    tree_b = tree_oids(store, old)

    # 1. Two readers on different full OIDs: sequential versus concurrent, byte-identical.
    for rep in range(reps):
        order = ["sequential", "concurrent"] if rep % 2 == 0 else ["concurrent", "sequential"]
        results: dict[str, tuple[float, list[str]]] = {}
        for mode in order:
            if mode == "sequential":
                first = parallel_batch(store, [tree_a])
                second = parallel_batch(store, [tree_b])
                results[mode] = (first[0] + second[0], first[1] + second[1])
            else:
                results[mode] = parallel_batch(store, [tree_a, tree_b])
        recorder.add(
            case="two_readers_different_oids",
            rep=rep,
            blobs=[len(tree_a), len(tree_b)],
            sequential_s=round(results["sequential"][0], 3),
            concurrent_s=round(results["concurrent"][0], 3),
            identical_bytes=results["sequential"][1] == results["concurrent"][1],
        )

    # 2. Reader pool scaling over one large tree.
    for rep in range(reps):
        sizes = [1, 2, 4, 8] if rep % 2 == 0 else [8, 4, 2, 1]
        for size in sizes:
            groups = [tree_a[index::size] for index in range(size)]
            wall, _digests = parallel_batch(store, groups)
            recorder.add(
                case="reader_pool_scaling",
                rep=rep,
                pool=size,
                blobs=len(tree_a),
                wall_s=round(wall, 3),
                blobs_per_s=round(len(tree_a) / wall),
            )

    # 3. Persistent actors under contention.
    sample_a = random.Random(2).sample(tree_a, min(400, len(tree_a)))
    sample_b = random.Random(3).sample(tree_b, min(400, len(tree_b)))
    single = batch_command_latency(store, sample_a, git_env())
    shared: dict[str, dict[str, Json]] = {}

    def actor(key: str, oids: Sequence[str]) -> None:
        shared[key] = batch_command_latency(store, oids, git_env())

    threads = [
        threading.Thread(target=actor, args=("a", sample_a)),
        threading.Thread(target=actor, args=("b", sample_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    recorder.add(
        case="actor_latency", single=single, concurrent_a=shared["a"], concurrent_b=shared["b"]
    )

    # 4. Actor restart cost after poisoning.
    starts: list[float] = []
    for _rep in range(max(reps, 10)):
        started = time.perf_counter()
        process = subprocess.Popen(
            ["git", "--git-dir", str(store), "cat-file", "--batch-command", "--buffer"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=git_env(),
        )
        stdin = cast(IO[bytes], process.stdin)
        stdin.write(f"info {tree_a[0]}\nflush\n".encode())
        stdin.flush()
        cast(IO[bytes], process.stdout).readline()
        starts.append(time.perf_counter() - started)
        stdin.close()
        process.wait()
    recorder.add(case="actor_restart_first_response", latency=percentiles(starts))

    # 5. Cancellation latency of a streaming batch reader.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        exits: list[float] = []
        for _rep in range(max(reps, 5)):
            process = batch_process(store, tree_a)
            stdout = cast(IO[bytes], process.stdout)
            stdout.read(1 << 20)
            sent = time.perf_counter()
            process.send_signal(sig)
            with contextlib.suppress(OSError, ValueError):
                while stdout.read(1 << 16):
                    pass
            process.wait()
            exits.append(time.perf_counter() - sent)
        recorder.add(case="batch_reader_cancellation", signal=sig.name, latency=percentiles(exits))

    # 6. Cancelled acquisition: exit latency and what is left behind.
    for strategy in ("full", "blobless"):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            destination = work / f"cancel-{strategy}.git"
            remove(destination)
            process = subprocess.Popen(
                [
                    "git",
                    *clone_args(
                        layout="bare", strategy=strategy, url=MEDIUM[1], destination=destination
                    ),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=git_env(),
                start_new_session=True,
            )
            time.sleep(1.5)
            sent = time.perf_counter()
            os.killpg(process.pid, sig)
            process.wait()
            exit_s = time.perf_counter() - sent
            residue = disk_usage(destination) if destination.exists() else None
            locks = (
                sorted(str(path.relative_to(destination)) for path in destination.rglob("*.lock"))
                if destination.exists()
                else []
            )
            temp_packs = len(list(destination.rglob("tmp_pack_*"))) if destination.exists() else 0
            recorder.add(
                case="acquisition_cancellation",
                strategy=strategy,
                signal=sig.name,
                exit_ms=round(exit_s * 1000, 1),
                destination_exists=destination.exists(),
                residue=residue,
                lock_files=locks,
                temp_packs=temp_packs,
            )
            time.sleep(0.5)
            remove(destination)

    # 7. Readers during repack and gc of the same store.
    subjects_pool = text(
        git(["rev-list", "--max-count=200", "--skip=100", subjects.head], git_dir=store)
    ).split()
    for maintenance in (["repack", "-a", "-d"], ["gc", "--prune=now"]):
        target = copy_store(store, work / "maintenance-scratch.git")
        long_lived = subprocess.Popen(
            ["git", "--git-dir", str(target), "cat-file", "--batch-command", "--buffer"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=git_env(),
        )
        stdin = cast(IO[bytes], long_lived.stdin)
        stdout = cast(IO[bytes], long_lived.stdout)
        stdin.write(f"contents {tree_b[0]}\nflush\n".encode())
        stdin.flush()
        warm = stdout.readline().split()
        stdout.read(int(warm[2]) + 1)
        load = ReaderLoad(target, subjects_pool, readers=4)
        time.sleep(0.5)
        outcome = git(maintenance, git_dir=target)
        time.sleep(0.5)
        load.stop()
        survived = 0
        for oid in tree_b[:200]:
            stdin.write(f"info {oid}\nflush\n".encode())
            stdin.flush()
            if not stdout.readline().endswith(b"missing\n"):
                survived += 1
        stdin.close()
        long_lived.wait()
        recorder.add(
            case="readers_during_maintenance",
            maintenance=" ".join(maintenance),
            maintenance_s=round(outcome.wall_s, 3),
            maintenance_returncode=outcome.returncode,
            reader_iterations=load.tallies["iterations"],
            reader_failures=load.tallies["failures"],
            reader_missing_objects=load.tallies["missing"],
            failure_classes=sorted(load.failure_classes),
            long_lived_actor_found=survived,
            long_lived_actor_queried=len(tree_b[:200]),
        )
        remove(target)
    if not args.keep:
        remove(store)
    print(recorder.write())


ZERO_OID = "0" * 40
JOB_REFSPEC = "+refs/heads/measure/*:refs/metabrowser/jobs/{job}/measure/*"


def stderr_lines(text_value: str, limit: int = 3) -> list[str]:
    """First distinct diagnostic lines, with object IDs elided."""
    lines: list[str] = []
    for line in text_value.replace("\r", "\n").splitlines():
        cleaned = re.sub(r"\b[0-9a-f]{40}\b", "<oid>", line.strip())
        if (
            cleaned
            and not cleaned.startswith(
                (
                    "Receiving",
                    "remote:",
                    "Resolving",
                    "Counting",
                    "Compressing",
                    "Enumerating",
                    "Total",
                    "Writing",
                    "Delta",
                    "Expanding",
                )
            )
            and cleaned not in lines
        ):
            lines.append(cleaned)
        if len(lines) >= limit:
            break
    return lines


def direct_fetch_job(git_dir: Path, job: str) -> subprocess.Popen[bytes]:
    """A network job: fetch from the promisor remote into job-private refs, no store lock."""
    return subprocess.Popen(
        [
            "git",
            "--git-dir",
            str(git_dir),
            *PROTOCOL_ARGS,
            "fetch",
            "--progress",
            "--no-tags",
            "--no-write-fetch-head",
            "origin",
            JOB_REFSPEC.format(job=job),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=git_env(),
    )


def finish_jobs(processes: Sequence[subprocess.Popen[bytes]]) -> tuple[list[int], list[str], int]:
    codes: list[int] = []
    errors: list[str] = []
    received_bytes = 0
    for process in processes:
        _out, err = process.communicate()
        message = err.decode(errors="replace")
        codes.append(process.returncode)
        received_bytes += cast(int | None, received(message)["bytes"]) or 0
        if process.returncode != 0:
            errors.append(classify(message))
    return codes, errors, received_bytes


def ref_values(git_dir: Path, prefix: str) -> dict[str, str]:
    raw = text(git(["for-each-ref", "--format=%(refname) %(objectname)", prefix], git_dir=git_dir))
    return dict(line.split(" ", 1) for line in raw.splitlines() if line)


def publish_job(git_dir: Path, job: str, base: dict[str, str]) -> tuple[str, float]:
    """Compare-and-swap the public refs from one job's refs, then delete the job refs.

    The expected old value is what the job observed before its network work; a
    mismatch means a newer publication won, which is success when it published
    the same object IDs and a conflict otherwise.
    """
    job_prefix = f"refs/metabrowser/jobs/{job}/"
    started = time.perf_counter()
    jobs = ref_values(git_dir, job_prefix)
    lines = ["start"]
    for name, oid in sorted(jobs.items()):
        public = "refs/remotes/origin/" + name.removeprefix(job_prefix)
        lines.append(f"update {public} {oid} {base.get(public, ZERO_OID)}")
        lines.append(f"delete {name} {oid}")
    lines += ["prepare", "commit"]
    outcome = git(
        ["update-ref", "--stdin"], git_dir=git_dir, stdin=("\n".join(lines) + "\n").encode()
    )
    if outcome.returncode == 0:
        return "published", time.perf_counter() - started
    current = ref_values(git_dir, "refs/remotes/origin/")
    same = all(
        current.get("refs/remotes/origin/" + name.removeprefix(job_prefix)) == oid
        for name, oid in jobs.items()
    )
    cleanup = [
        "start",
        *[f"delete {name} {oid}" for name, oid in sorted(jobs.items())],
        "prepare",
        "commit",
    ]
    must(
        git(["update-ref", "--stdin"], git_dir=git_dir, stdin=("\n".join(cleanup) + "\n").encode())
    )
    return ("already_published" if same else "conflict"), time.perf_counter() - started


def pack_counts(git_dir: Path) -> dict[str, Json]:
    packs = git_dir / "objects" / "pack"
    names = {path.stem for path in packs.glob("*.pack")}
    promisor = {path.stem for path in packs.glob("*.promisor")}
    return {
        "packs": len(names),
        "promisor_packs": len(names & promisor),
        "non_promisor_packs": len(names - promisor),
        "bitmaps": len(list(packs.glob("*.bitmap"))),
        "pack_bytes": sum(path.stat().st_size for path in packs.glob("*.pack")),
    }


def maintenance_outcome(git_dir: Path) -> dict[str, Json]:
    """Run the two maintenance commands whose failures the staged design exposed."""
    missing_before = missing_reachable(git_dir, ["--all"])
    gc = git(["gc", "--prune=now"], git_dir=git_dir)
    repack = git(["repack", "-a", "-d"], git_dir=git_dir)
    return {
        "gc_returncode": gc.returncode,
        "gc_stderr": stderr_lines(gc.stderr),
        "repack_returncode": repack.returncode,
        "repack_stderr": stderr_lines(repack.stderr),
        "after": pack_counts(git_dir),
        "fsck_ok": git(["fsck", "--connectivity-only", "--no-dangling"], git_dir=git_dir).returncode
        == 0,
        "missing_reachable_before": missing_before,
        "missing_reachable_after": missing_reachable(git_dir, ["--all"]),
    }


def suite_fetches(scratch: Path, args: argparse.Namespace) -> None:
    """Same-ref fetches into a blobless store: direct jobs, CAS publication, then maintenance."""
    reps = cast(int, args.reps)
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "fetches"
    recorder = Recorder("fetches", scratch, {"reps": reps})
    origin = work / "origin.git"
    base = work / "base.git"
    remove(origin)
    remove(base)
    must(
        git(
            [
                *PROTOCOL_ARGS,
                "clone",
                "--bare",
                "--template=",
                "--no-local",
                "--",
                str(local_origin(scratch, SMALL[0], SMALL[1])),
                str(origin),
            ]
        )
    )
    for item in ("uploadpack.allowFilter", "uploadpack.allowAnySHA1InWant"):
        must(git(["config", item, "true"], git_dir=origin))
    must(
        git(clone_args(layout="bare", strategy="blobless", url=file_url(origin), destination=base))
    )
    head = text(git(["rev-parse", "HEAD"], git_dir=base))
    must(prefetch_oids(base, tree_oids(base, head), traces, timeout))
    recorder.add(case="base", head=head, **pack_counts(base))
    for rep in range(reps):
        add_origin_commits(origin, f"direct{rep}", count=60, blob_bytes=16 * 1024)
        modes = [("coalesced", 1), ("concurrent_direct", 4)]
        for mode, jobs in modes if rep % 2 == 0 else list(reversed(modes)):
            target = copy_store(base, work / "target.git")
            before = pack_counts(target)
            base_refs = ref_values(target, "refs/remotes/origin/")
            started = time.perf_counter()
            codes, errors, received_bytes = finish_jobs(
                [direct_fetch_job(target, f"job{index}") for index in range(jobs)]
            )
            network_s = time.perf_counter() - started
            outcomes: list[str] = []
            publish_ms: list[float] = []
            for index in range(jobs):
                outcome, wall = publish_job(target, f"job{index}", base_refs)
                outcomes.append(outcome)
                publish_ms.append(round(wall * 1000, 2))
            after_fetch = pack_counts(target)
            tips = list(ref_values(target, "refs/remotes/origin/measure/").values())
            wanted = sorted({oid for tip in tips for oid in tree_oids(target, tip)})
            check = git(
                ["cat-file", "--batch-check"],
                git_dir=target,
                env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
                stdin=("\n".join(wanted) + "\n").encode(),
            )
            missing = [
                line.split()[0]
                for line in check.stdout.decode().splitlines()
                if line.endswith(" missing")
            ]
            prefetches = [
                subprocess.Popen(
                    [
                        "git",
                        "--git-dir",
                        str(target),
                        *PROTOCOL_ARGS,
                        "-c",
                        "fetch.negotiationAlgorithm=noop",
                        "fetch",
                        "origin",
                        "--no-tags",
                        "--no-write-fetch-head",
                        "--recurse-submodules=no",
                        "--filter=blob:none",
                        "--stdin",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    env=git_env(),
                )
                for _job in range(jobs)
            ]
            for process in prefetches:
                cast(IO[bytes], process.stdin).write(("\n".join(missing) + "\n").encode())
                cast(IO[bytes], process.stdin).close()
            prefetch_codes = [process.wait() for process in prefetches]
            after_prefetch = pack_counts(target)
            recorder.add(
                case="direct_job_fetches",
                rep=rep,
                mode=mode,
                jobs=jobs,
                network_s=round(network_s, 3),
                failures=sum(1 for code in codes if code != 0),
                error_classes=sorted(set(errors)),
                received_bytes=received_bytes,
                publication=outcomes,
                publish_ms=publish_ms,
                job_refs_left=len(ref_values(target, "refs/metabrowser/jobs/")),
                refs_published=len(tips),
                before=before,
                after_fetch=after_fetch,
                blob_prefetch_wanted=len(missing),
                blob_prefetch_failures=sum(1 for code in prefetch_codes if code != 0),
                after_prefetch=after_prefetch,
                maintenance=maintenance_outcome(target),
            )
            remove(target)
        # The rejected design: stage in a separate repository with the store as an alternate.
        for variant in ("staged_filtered_import", "staged_unfiltered_import"):
            target = copy_store(base, work / "target.git")
            stage = work / "stage.git"
            remove(stage)
            must(git(["init", "--bare", "--template=", "-q", str(stage)]))
            (stage / "objects" / "info").mkdir(parents=True, exist_ok=True)
            (stage / "objects" / "info" / "alternates").write_text(f"{target / 'objects'}\n")
            stage_fetch = [*PROTOCOL_ARGS, "fetch", "--no-tags", "--no-write-fetch-head"]
            if variant == "staged_filtered_import":
                stage_fetch.append("--filter=blob:none")
            staged = git(
                [*stage_fetch, file_url(origin), "+refs/heads/measure/*:refs/staged/*"],
                git_dir=stage,
            )
            imported = git(
                [
                    "fetch",
                    "--no-tags",
                    "--no-write-fetch-head",
                    str(stage),
                    "+refs/staged/*:refs/remotes/origin/measure/*",
                ],
                git_dir=target,
            )
            recorder.add(
                case="staged_alternates_import",
                rep=rep,
                variant=variant,
                stage_returncode=staged.returncode,
                import_returncode=imported.returncode,
                import_error_class=imported.error_class(),
                import_stderr=stderr_lines(imported.stderr),
                after_import=pack_counts(target),
                maintenance=maintenance_outcome(target) if imported.returncode == 0 else None,
            )
            remove(stage)
            remove(target)
    if not args.keep:
        remove(origin)
        remove(base)
    print(recorder.write())


IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "Measure",
    "GIT_AUTHOR_EMAIL": "measure@example.invalid",
    "GIT_AUTHOR_DATE": "1700000000 +0000",
    "GIT_COMMITTER_NAME": "Measure",
    "GIT_COMMITTER_EMAIL": "measure@example.invalid",
    "GIT_COMMITTER_DATE": "1700000000 +0000",
}
BLOB_MODES = frozenset({"100644", "100755", "120000"})
STORE_READ_CONFIG = ("-c", "mailmap.blob=", "-c", "mailmap.file=")


def tiny_origin(path: Path) -> Path:
    remove(path)
    must(git(["init", "--bare", "--template=", "-q", str(path)]))
    must(git(["config", "uploadpack.allowFilter", "true"], git_dir=path))
    return path


def write_blob(origin: Path, data: bytes) -> str:
    return text(git(["hash-object", "-w", "--stdin"], git_dir=origin, stdin=data))


def write_tree(origin: Path, files: dict[str, tuple[str, str]]) -> str:
    """Build nested trees from `path -> (mode, oid)`; mode 160000 is a gitlink."""
    children: dict[str, dict[str, tuple[str, str]]] = {}
    entries: list[bytes] = []
    for path, (mode, oid) in files.items():
        head_name, _, rest = path.partition("/")
        if rest:
            children.setdefault(head_name, {})[rest] = (mode, oid)
        else:
            kind = "commit" if mode == "160000" else "blob"
            entries.append(f"{mode} {kind} {oid}\t{head_name}".encode())
    for name, nested in children.items():
        entries.append(f"040000 tree {write_tree(origin, nested)}\t{name}".encode())
    return text(git(["mktree", "-z"], git_dir=origin, stdin=b"\0".join(entries) + b"\0"))


def write_commit(
    origin: Path,
    tree: str,
    parents: Sequence[str],
    message: str,
    author: tuple[str, str] | None = None,
) -> str:
    identity = dict(IDENTITY_ENV)
    if author is not None:
        identity["GIT_AUTHOR_NAME"], identity["GIT_AUTHOR_EMAIL"] = author
    argv = ["commit-tree", tree, "-m", message]
    for parent in parents:
        argv += ["-p", parent]
    return text(git(argv, git_dir=origin, env=git_env(identity)))


def set_head(origin: Path, commit: str) -> None:
    must(git(["update-ref", "refs/heads/main", commit], git_dir=origin))
    must(git(["symbolic-ref", "HEAD", "refs/heads/main"], git_dir=origin))


def raw_entries(git_dir: Path, left: str, right: str) -> list[tuple[str, str]]:
    """`(mode, oid)` for both sides of every change, zero object IDs removed."""
    raw = must(
        git(
            [*STORE_READ_CONFIG, "diff", "--raw", "-z", "--no-abbrev", "--no-renames", left, right],
            git_dir=git_dir,
            env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        )
    ).stdout
    sides: list[tuple[str, str]] = []
    for token in raw.split(b"\0"):
        if token.startswith(b":"):
            old_mode, new_mode, old_oid, new_oid, _status = token[1:].decode().split(" ")
            sides += [(old_mode, old_oid), (new_mode, new_oid)]
    return [(mode, oid) for mode, oid in sides if set(oid) != {"0"}]


def suite_gitlinks(scratch: Path, args: argparse.Namespace) -> None:
    """Gitlinks in a change set, want-list rejection, and the bisecting request flow."""
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "gitlinks"
    recorder = Recorder("gitlinks", scratch, {})
    rng = random.Random("gitlinks")
    origin = tiny_origin(work / "origin.git")
    files: dict[str, tuple[str, str]] = {
        f"src/file{index}.txt": ("100644", write_blob(origin, rng.randbytes(2048)))
        for index in range(8)
    }
    files["tools/run.sh"] = ("100755", write_blob(origin, b"#!/bin/sh\necho one\n"))
    files["vendor/lib"] = ("160000", f"{rng.getrandbits(160):040x}")
    first = write_commit(origin, write_tree(origin, files), [], "one")
    for index in range(4):
        files[f"src/file{index}.txt"] = ("100644", write_blob(origin, rng.randbytes(2048)))
    files["tools/run.sh"] = ("100755", write_blob(origin, b"#!/bin/sh\necho two\n"))
    files["docs/link"] = ("120000", write_blob(origin, b"../src/file0.txt"))
    files["vendor/lib"] = ("160000", f"{rng.getrandbits(160):040x}")
    second = write_commit(origin, write_tree(origin, files), [first], "two")
    set_head(origin, second)

    def fresh_store(name: str) -> Path:
        store = work / name
        remove(store)
        must(
            git(
                clone_args(
                    layout="bare", strategy="blobless", url=file_url(origin), destination=store
                )
            )
        )
        return store

    store = fresh_store("store.git")
    sides = raw_entries(store, first, second)
    modes: dict[str, int] = {}
    for mode, _oid in sides:
        modes[mode] = modes.get(mode, 0) + 1
    naive = sorted({oid for _mode, oid in sides})
    blobs = sorted({oid for mode, oid in sides if mode in BLOB_MODES})
    gitlinks = sorted({oid for mode, oid in sides if mode == "160000"})
    check = git(
        ["cat-file", "--batch-check"],
        git_dir=store,
        env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        stdin=("\n".join(naive) + "\n").encode(),
    )
    reported_missing = {
        line.split()[0] for line in check.stdout.decode().splitlines() if line.endswith(" missing")
    }
    recorder.add(
        case="change_set",
        modes=modes,
        naive_oids=len(naive),
        blob_oids=len(blobs),
        gitlink_oids=len(gitlinks),
        gitlinks_reported_missing=len(reported_missing & set(gitlinks)),
    )

    # Want-list permission and rejection, protocol v0 and v2.
    for allow_any in (False, True):
        must(
            git(
                ["config", "uploadpack.allowAnySHA1InWant", "true" if allow_any else "false"],
                git_dir=origin,
            )
        )
        for protocol in ("0", "2"):
            for label, wants in (("blobs_only", blobs), ("with_gitlink", naive)):
                target = fresh_store("try.git")
                before = cast(int, count_objects(target)["in_pack"])
                outcome = prefetch_oids(
                    target, wants, traces, timeout, extra=["-c", f"protocol.version={protocol}"]
                )
                recorder.add(
                    case="want_list",
                    allow_any_sha1_in_want=allow_any,
                    protocol=protocol,
                    wants=label,
                    oids=len(wants),
                    returncode=outcome.returncode,
                    error_class=outcome.error_class(),
                    stderr=stderr_lines(outcome.stderr),
                    objects_fetched=cast(int, count_objects(target)["in_pack"]) - before,
                )
                remove(target)

    # Routes after fetching only the blob-mode change set, lazy fetch disabled.
    target = fresh_store("routes.git")
    must(prefetch_oids(target, blobs, traces, timeout))
    no_lazy = git_env({"GIT_NO_LAZY_FETCH": "1"})
    flags = ["-M50", "-C", "--diff-merges=first-parent"]
    routes = {
        "commit_detail": [
            "show",
            "-z",
            "--raw",
            "--numstat",
            "-M",
            "-C",
            "--diff-merges=first-parent",
            f"--format={SHOW_FORMAT}",
            second,
        ],
        "manifest_raw": ["diff", "--raw", "-z", "--no-abbrev", *flags, first, second],
        "manifest_numstat": ["diff", "--numstat", "-z", *flags, first, second],
        "patches": ["diff", *flags, first, second],
    }
    for route, argv in routes.items():
        outcome = git([*STORE_READ_CONFIG, *argv], git_dir=target, env=no_lazy)
        recorder.add(
            case="routes_after_blob_prefetch",
            route=route,
            returncode=outcome.returncode,
            stderr=stderr_lines(outcome.stderr),
            mentions_submodule=b"Subproject commit" in outcome.stdout
            or b"160000" in outcome.stdout,
        )
    remove(target)

    # Bisect a rejected want list down to single object IDs.
    target = fresh_store("bisect.git")
    absent = f"{rng.getrandbits(160):040x}"
    wants = [*blobs[:3], gitlinks[0], *blobs[3:], absent]
    requests: list[int] = []
    accepted: list[str] = []
    rejected: list[str] = []

    def attempt(oids: list[str]) -> None:
        outcome = prefetch_oids(target, oids, traces, timeout)
        requests.append(len(oids))
        if outcome.returncode == 0:
            accepted.extend(oids)
        elif len(oids) == 1:
            rejected.extend(oids)
        else:
            middle = (len(oids) + 1) // 2
            attempt(oids[:middle])
            attempt(oids[middle:])

    started = time.perf_counter()
    attempt(wants)
    wall = time.perf_counter() - started
    present = git(
        ["cat-file", "--batch-check"],
        git_dir=target,
        env=no_lazy,
        stdin=("\n".join(accepted) + "\n").encode(),
    ).stdout.decode()
    recorder.add(
        case="bisected_request",
        wants=len(wants),
        request_sizes=requests,
        requests=len(requests),
        accepted=len(accepted),
        rejected_are_gitlink_and_absent=sorted(rejected) == sorted([gitlinks[0], absent]),
        accepted_present=present.count(" blob "),
        wall_s=round(wall, 3),
    )
    if not args.keep:
        remove(work)
    print(recorder.write())


def suite_mailmap(scratch: Path, args: argparse.Namespace) -> None:
    """Which store reads load a mailmap, and which configuration stops them."""
    traces = scratch / "traces"
    work = scratch / "mailmap"
    recorder = Recorder("mailmap", scratch, {})
    origin = tiny_origin(work / "origin.git")
    must(git(["config", "uploadpack.allowAnySHA1InWant", "true"], git_dir=origin))
    mailmap = b"Canonical Name <canonical@example.invalid> <alias@example.invalid>\n"
    files = {
        ".mailmap": ("100644", write_blob(origin, mailmap)),
        "a.txt": ("100644", write_blob(origin, b"one\n")),
    }
    first = write_commit(
        origin, write_tree(origin, files), [], "one", author=("Alias Name", "alias@example.invalid")
    )
    files["a.txt"] = ("100644", write_blob(origin, b"two\n"))
    second = write_commit(
        origin,
        write_tree(origin, files),
        [first],
        "two",
        author=("Alias Name", "alias@example.invalid"),
    )
    set_head(origin, second)
    user_file = work / "user.mailmap"
    user_file.write_bytes(b"User File Name <user@example.invalid> <alias@example.invalid>\n")
    full = work / "full.git"
    blobless = work / "blobless.git"
    for destination, strategy in ((full, "full"), (blobless, "blobless")):
        remove(destination)
        must(
            git(
                clone_args(
                    layout="bare", strategy=strategy, url=file_url(origin), destination=destination
                )
            )
        )
    commands: dict[str, tuple[list[str], bytes | None]] = {
        "history_page": (
            [
                "log",
                "-z",
                f"--format={LOG_FORMAT}",
                "--decorate=full",
                "--date-order",
                "--max-count=250",
                "--stdin",
            ],
            f"{second}\n".encode(),
        ),
        "commit_detail": (
            [
                "show",
                "-z",
                "--raw",
                "--numstat",
                "-M",
                "-C",
                "--diff-merges=first-parent",
                f"--format={SHOW_FORMAT}",
                second,
            ],
            None,
        ),
        "commit_detail_raw_only": (
            ["show", "-z", "--raw", "--no-abbrev", f"--format={SHOW_FORMAT}", second],
            None,
        ),
        "history_count": (["rev-list", "--count", second], None),
        "manifest_raw": (
            ["diff", "--raw", "-z", "--no-abbrev", "--no-renames", first, second],
            None,
        ),
        "refs": (["for-each-ref", "--format=%(refname)", "refs"], None),
        "mailmap_placeholder": (["log", "-1", "--format=%aN <%aE>", second], None),
    }
    variants: dict[str, list[str]] = {
        "git_defaults": [],
        "log_mailmap_false": ["-c", "log.mailmap=false"],
        "mailmap_blob_empty": ["-c", "mailmap.blob="],
        "log_false_and_blob_empty": ["-c", "log.mailmap=false", "-c", "mailmap.blob="],
        "blob_and_file_empty": ["-c", "mailmap.blob=", "-c", "mailmap.file="],
        "all_three": ["-c", "log.mailmap=false", "-c", "mailmap.blob=", "-c", "mailmap.file="],
    }
    for user_mailmap in (False, True):
        inherited = ["-c", f"mailmap.file={user_file}"] if user_mailmap else []
        for variant, config in variants.items():
            for name, (argv, stdin) in commands.items():
                no_lazy = git(
                    [*inherited, *config, *argv],
                    git_dir=blobless,
                    env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
                    stdin=stdin,
                )
                target = copy_store(blobless, work / "lazy.git")
                lazy = git(
                    [*inherited, *config, *argv], git_dir=target, stdin=stdin, trace_dir=traces
                )
                remove(target)
                complete = git([*inherited, *config, *argv], git_dir=full, stdin=stdin)
                recorder.add(
                    user_mailmap_file=user_mailmap,
                    variant=variant,
                    command=name,
                    no_lazy_returncode=no_lazy.returncode,
                    no_lazy_stderr=stderr_lines(no_lazy.stderr),
                    lazy_fetches=lazy.trace.lazy_fetches if lazy.trace else None,
                    full_store_identity=(
                        "canonical"
                        if b"Canonical Name" in complete.stdout
                        else "user_file"
                        if b"User File Name" in complete.stdout
                        else "raw"
                        if b"Alias Name" in complete.stdout
                        else "none"
                    ),
                )
    if not args.keep:
        remove(work)
    print(recorder.write())


def mode_census(path: Path) -> dict[str, Json]:
    directories: dict[str, int] = {}
    files: dict[str, int] = {}
    group_or_other = 0
    for root, dir_names, file_names in os.walk(path):
        for name in dir_names:
            mode = os.lstat(os.path.join(root, name)).st_mode & 0o777
            directories[f"{mode:04o}"] = directories.get(f"{mode:04o}", 0) + 1
            group_or_other += 1 if mode & 0o077 else 0
        for name in file_names:
            mode = os.lstat(os.path.join(root, name)).st_mode & 0o777
            files[f"{mode:04o}"] = files.get(f"{mode:04o}", 0) + 1
            group_or_other += 1 if mode & 0o077 else 0
    return {
        "directories": directories,
        "files": files,
        "entries_with_group_or_other_bits": group_or_other,
    }


def suite_umask(scratch: Path, args: argparse.Namespace) -> None:
    """File modes Git writes into a store under different umasks and sharedRepository."""
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "umask"
    recorder = Recorder("umask", scratch, {})
    rng = random.Random("umask")
    origin = tiny_origin(work / "origin.git")
    must(git(["config", "uploadpack.allowAnySHA1InWant", "true"], git_dir=origin))
    files = {
        f"f{index}.txt": ("100644", write_blob(origin, rng.randbytes(1024))) for index in range(40)
    }
    set_head(origin, write_commit(origin, write_tree(origin, files), [], "one"))
    for label, umask, extra in (
        ("umask_022", 0o022, []),
        ("umask_022_shared_repository_0600", 0o022, ["core.sharedRepository=0600"]),
        ("umask_077", 0o077, []),
    ):
        store = work / f"{label}.git"
        remove(store)
        argv = clone_args(
            layout="bare", strategy="blobless", url=file_url(origin), destination=store
        )
        for item in extra:
            argv[argv.index("--template=") + 1 : argv.index("--template=") + 1] = ["--config", item]
        must(git(argv, umask=umask))
        head = text(git(["rev-parse", "HEAD"], git_dir=store))
        must(prefetch_oids(store, tree_oids(store, head), traces, timeout, umask=umask))
        must(git(["gc", "--prune=now"], git_dir=store, umask=umask))
        recorder.add(case="store_modes", variant=label, **mode_census(store))
    if not args.keep:
        remove(work)
    print(recorder.write())


# ----------------------------------------------------------------------------
# Suite: maintenance


def wait_for_gc(store: Path, limit_s: float = 60.0) -> None:
    """Let a detached automatic gc finish before the store is inspected or removed."""
    deadline = time.monotonic() + limit_s
    time.sleep(0.5)
    while (store / "gc.pid").exists() and time.monotonic() < deadline:
        time.sleep(0.1)


def suite_maintenance(scratch: Path, args: argparse.Namespace) -> None:
    reps = cast(int, args.reps)
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "maintenance"
    recorder = Recorder("maintenance", scratch, {"reps": reps, "timeout_s": timeout})
    name, url = SMALL
    origin = local_origin(scratch, name, url)

    def plain_clone(strategy: str, destination: Path) -> Path:
        remove(destination)
        argv = [*PROTOCOL_ARGS, "clone", "--bare", "--template="]
        if strategy == "blobless":
            argv.append("--filter=blob:none")
        must(git([*argv, "--", file_url(origin), str(destination)]))
        return destination

    # 1. Fetch spawns automatic maintenance unless the store disables it.
    for configured in (False, True):
        store = plain_clone("full", work / "auto.git")
        if configured:
            for item in STORE_CONFIG:
                key, _, value = item.partition("=")
                must(git(["config", key, value], git_dir=store))
        add_origin_commits(origin, f"auto{int(configured)}", count=1, blob_bytes=1024)
        outcome = git(
            [*PROTOCOL_ARGS, "fetch", "--no-tags", "origin", "+refs/heads/*:refs/remotes/origin/*"],
            git_dir=store,
            trace_dir=traces,
        )
        recorder.add(
            case="auto_maintenance_after_fetch",
            store_config=configured,
            returncode=outcome.returncode,
            maintenance_spawns=outcome.trace.maintenance_spawns if outcome.trace else None,
        )
        remove(store)

    # 2. Lazy fetches each spawn maintenance; auto-gc then races the next reader.
    blobless = plain_clone("blobless", work / "blobless.git")
    head = text(git(["rev-parse", "HEAD"], git_dir=blobless))
    for configured in (False, True):
        for rep in range(reps):
            store = copy_store(blobless, work / "race.git")
            if configured:
                for item in STORE_CONFIG:
                    key, _, value = item.partition("=")
                    must(git(["config", key, value], git_dir=store))
            outcome = git(
                ["ls-tree", "-r", "-z", "-l", "--full-tree", head],
                git_dir=store,
                trace_dir=traces,
                timeout=timeout,
            )
            wait_for_gc(store)
            recorder.add(
                case="lazy_fetch_auto_gc_race",
                store_config=configured,
                rep=rep,
                returncode=outcome.returncode,
                error_class=outcome.error_class(),
                wall_s=round(outcome.wall_s, 3),
                entries_listed=outcome.stdout.count(b"\0"),
                lazy_fetches=outcome.trace.lazy_fetches if outcome.trace else None,
                maintenance_spawns=outcome.trace.maintenance_spawns if outcome.trace else None,
                packs_after=len(list((store / "objects" / "pack").glob("*.pack"))),
            )
            remove(store)

    # 3. gc and repack of a blobless store: no fetch, promisor objects kept.
    store = copy_store(blobless, work / "gc-blobless.git")
    before = count_objects(store)
    outcome = git(["gc"], git_dir=store, trace_dir=traces)
    recorder.add(
        case="gc_blobless_store",
        wall_s=round(outcome.wall_s, 3),
        returncode=outcome.returncode,
        lazy_fetches=outcome.trace.lazy_fetches if outcome.trace else None,
        objects_before=before,
        objects_after=count_objects(store),
    )
    remove(store)

    # 4. Retention: which roots keep a fetched object alive through gc.
    base = plain_clone("full", work / "retention-base.git")
    for item in STORE_CONFIG:
        key, _, value = item.partition("=")
        must(git(["config", key, value], git_dir=base))
    retention_refs = add_origin_commits(origin, "retention", count=1, blob_bytes=4096)
    retained_oid = text(git(["rev-parse", retention_refs[0]], git_dir=origin))
    scenarios = (
        ("private_ref_kept", True, False),
        ("private_ref_deleted", True, True),
        ("fetch_head_only", False, False),
    )
    for scenario, with_ref, delete_ref in scenarios:
        for prune in ("default", "now"):
            store = copy_store(base, work / "retention.git")
            if with_ref:
                must(
                    git(
                        [
                            *PROTOCOL_ARGS,
                            "fetch",
                            "--no-tags",
                            "origin",
                            f"+{retention_refs[0]}:refs/metabrowser/subjects/measure",
                        ],
                        git_dir=store,
                    )
                )
                if delete_ref:
                    must(
                        git(
                            ["update-ref", "-d", "refs/metabrowser/subjects/measure"], git_dir=store
                        )
                    )
            else:
                must(
                    git(
                        [*PROTOCOL_ARGS, "fetch", "--no-tags", "origin", retention_refs[0]],
                        git_dir=store,
                    )
                )
            present_before = git(["cat-file", "-e", retained_oid], git_dir=store).returncode == 0
            gc_args = ["gc"] if prune == "default" else ["gc", "--prune=now"]
            gc = git(gc_args, git_dir=store)
            present_after = git(["cat-file", "-e", retained_oid], git_dir=store).returncode == 0
            recorder.add(
                case="object_retention",
                scenario=scenario,
                gc=" ".join(gc_args),
                gc_returncode=gc.returncode,
                present_before=present_before,
                present_after=present_after,
                reflog_written=(store / "logs").exists(),
                log_all_ref_updates=fetch_value(store, "core.logAllRefUpdates"),
            )
            remove(store)
    if not args.keep:
        remove(blobless)
        remove(base)
    print(recorder.write())


# ----------------------------------------------------------------------------
# Suite: platform


def child_hold_lock(path: Path, mode: str, ready: Path) -> subprocess.Popen[bytes]:
    code = (
        "import fcntl, os, sys, time\n"
        f"fd = os.open({str(path)!r}, os.O_RDWR | os.O_CREAT, 0o600)\n"
        f"fcntl.flock(fd, fcntl.LOCK_{mode})\n"
        f"open({str(ready)!r}, 'w').close()\n"
        "time.sleep(60)\n"
    )
    return subprocess.Popen([sys.executable, "-c", code])


def wait_for(path: Path, limit_s: float = 10.0) -> None:
    deadline = time.monotonic() + limit_s
    while not path.exists():
        if time.monotonic() > deadline:
            raise RuntimeError(f"timed out waiting for {path}")
        time.sleep(0.005)


def try_flock(path: Path, operation: int) -> bool:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, operation | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    finally:
        os.close(fd)
    return True


def rename_outcome(action: Callable[[], None]) -> str:
    try:
        action()
    except OSError as exc:
        return errno.errorcode.get(exc.errno or 0, str(exc.errno))
    return "replaced_or_moved"


def suite_platform(scratch: Path, args: argparse.Namespace) -> None:
    work = scratch / "platform"
    remove(work)
    work.mkdir(parents=True)
    recorder = Recorder("platform", scratch, {})

    # 1. Directory and file rename semantics used by publication.
    def fresh(name: str, content: bool) -> Path:
        path = work / name
        path.mkdir()
        if content:
            (path / "marker").write_text(name)
        return path

    staged = fresh("staged-a", True)
    empty_target = fresh("published-empty", False)
    recorder.add(
        primitive="os.rename(dir, existing_empty_dir)",
        outcome=rename_outcome(lambda: os.rename(staged, empty_target)),
        target_marker=(empty_target / "marker").read_text()
        if (empty_target / "marker").exists()
        else None,
    )
    staged = fresh("staged-b", True)
    full_target = fresh("published-full", True)
    recorder.add(
        primitive="os.rename(dir, existing_nonempty_dir)",
        outcome=rename_outcome(lambda: os.rename(staged, full_target)),
    )
    (work / "record.yml").write_text("old")
    (work / "record.tmp").write_text("new")
    recorder.add(
        primitive="os.replace(file, existing_file)",
        outcome=rename_outcome(lambda: os.replace(work / "record.tmp", work / "record.yml")),
        target=(work / "record.yml").read_text(),
    )
    (work / "claim.tmp").write_text("x")
    recorder.add(
        primitive="os.link(file, existing_file)",
        outcome=rename_outcome(lambda: os.link(work / "claim.tmp", work / "record.yml")),
    )
    recorder.add(
        primitive="os.mkdir(existing_dir)",
        outcome=rename_outcome(lambda: os.mkdir(work / "published-full")),
    )
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        rename_excl = 0x00000004  # RENAME_EXCL from <stdio.h>
        staged = fresh("staged-c", True)
        empty_target = fresh("published-empty-2", False)
        result = cast(
            int,
            libc.renamex_np(
                os.fsencode(staged), os.fsencode(empty_target), ctypes.c_uint(rename_excl)
            ),
        )
        recorder.add(
            primitive="renamex_np(dir, existing_empty_dir, RENAME_EXCL)",
            outcome="replaced_or_moved"
            if result == 0
            else errno.errorcode.get(ctypes.get_errno(), "unknown"),
        )
        missing_target = work / "published-new"
        result = cast(
            int,
            libc.renamex_np(
                os.fsencode(staged), os.fsencode(missing_target), ctypes.c_uint(rename_excl)
            ),
        )
        recorder.add(
            primitive="renamex_np(dir, absent_path, RENAME_EXCL)",
            outcome="replaced_or_moved"
            if result == 0
            else errno.errorcode.get(ctypes.get_errno(), "unknown"),
        )

    # 2. flock: exclusive, shared, and release when the holder is killed.
    lock_path = work / "store.lock"
    ready = work / "ready-ex"
    holder = child_hold_lock(lock_path, "EX", ready)
    wait_for(ready)
    blocked = not try_flock(lock_path, fcntl.LOCK_EX)
    killed = time.perf_counter()
    holder.kill()
    holder.wait()
    released_after: float | None = None
    for _attempt in range(2000):
        if try_flock(lock_path, fcntl.LOCK_EX):
            released_after = time.perf_counter() - killed
            break
        time.sleep(0.001)
    recorder.add(
        primitive="flock exclusive, holder SIGKILL",
        blocked_while_held=blocked,
        released_after_ms=round(released_after * 1000, 3) if released_after is not None else None,
    )
    shared_holders: list[subprocess.Popen[bytes]] = []
    for index in range(2):
        marker = work / f"ready-sh-{index}"
        shared_holders.append(child_hold_lock(lock_path, "SH", marker))
        wait_for(marker)
    recorder.add(
        primitive="flock two shared holders",
        third_shared_granted=try_flock(lock_path, fcntl.LOCK_SH),
        exclusive_granted=try_flock(lock_path, fcntl.LOCK_EX),
    )
    for process in shared_holders:
        process.kill()
        process.wait()

    # 3. POSIX record locks vanish when any descriptor for the file closes.
    record_path = work / "record.lock"
    fd = os.open(record_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.lockf(fd, fcntl.LOCK_EX)
    other = os.open(record_path, os.O_RDONLY)
    probe = (
        "import fcntl, os, sys\n"
        f"fd = os.open({str(record_path)!r}, os.O_RDWR)\n"
        "try:\n"
        "    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "except OSError:\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    before_close = subprocess.run([sys.executable, "-c", probe], check=False).returncode == 0
    os.close(other)
    after_close = subprocess.run([sys.executable, "-c", probe], check=False).returncode == 0
    os.close(fd)
    recorder.add(
        primitive="lockf held, unrelated descriptor closed",
        other_process_acquired_before_close=before_close,
        other_process_acquired_after_close=after_close,
    )

    # 4. Name limits and case and Unicode folding of the cache filesystem.
    upper = work / "Slug-Case"
    upper.mkdir()
    case_collides = (work / "slug-case").exists()
    nfc = work / unicodedata.normalize("NFC", "café")
    nfc.mkdir()
    normalization_collides = (work / unicodedata.normalize("NFD", "café")).exists()
    long_name_ok = True
    try:
        (work / ("a" * 255)).mkdir()
    except OSError:
        long_name_ok = False
    too_long_ok = True
    try:
        (work / ("b" * 256)).mkdir()
    except OSError:
        too_long_ok = False
    recorder.add(
        primitive="cache filesystem names",
        name_max=os.pathconf(work, "PC_NAME_MAX"),
        path_max=os.pathconf(work, "PC_PATH_MAX"),
        case_insensitive=case_collides,
        unicode_normalization_insensitive=normalization_collides,
        component_255_bytes_ok=long_name_ok,
        component_256_bytes_ok=too_long_ok,
    )
    if not args.keep:
        remove(work)
    print(recorder.write())


# ----------------------------------------------------------------------------


class RequestRecorder:
    """Records the first request line of each HTTP connection and answers 404."""

    def __init__(self) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(16)
        self.port = cast(int, self.server.getsockname()[1])
        self.lines: list[str] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        with contextlib.suppress(OSError):
            while True:
                connection, _address = self.server.accept()
                data = connection.recv(8192).decode(errors="replace")
                self.lines.append(data.splitlines()[0] if data else "")
                connection.sendall(
                    b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                )
                connection.close()


def suite_url(scratch: Path, _args: argparse.Namespace) -> None:
    """Which URL spellings Git's smart-HTTP transport turns into the same request."""
    recorder = Recorder("url", scratch, {})
    server = RequestRecorder()
    base = f"http://127.0.0.1:{server.port}"
    for path in ("/o/r.git", "/o/r.git/", "/o/r", "/o/r/", "/o/%72.git", "/O/R.git", "/o//r.git"):
        server.lines.clear()
        git(["-c", "protocol.http.allow=always", "ls-remote", base + path], timeout=20)
        recorder.add(url_path=path, first_request=server.lines[0] if server.lines else None)
    server.server.close()
    print(recorder.write())


def missing_reachable(git_dir: Path, revisions: Sequence[str]) -> int:
    """Objects reachable from *revisions* that the store does not have."""
    outcome = must(
        git(
            ["rev-list", "--objects", "--missing=print", *revisions],
            git_dir=git_dir,
            env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        )
    )
    return sum(1 for line in outcome.stdout.splitlines() if line.startswith(b"?"))


def missing_oids(git_dir: Path, revisions: Sequence[str]) -> list[str]:
    outcome = must(
        git(
            ["rev-list", "--objects", "--missing=print", *revisions],
            git_dir=git_dir,
            env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        )
    )
    return [
        line[1:].decode().split()[0]
        for line in outcome.stdout.splitlines()
        if line.startswith(b"?")
    ]


def prefetch_oids(
    git_dir: Path,
    oids: Sequence[str],
    traces: Path,
    timeout: float,
    extra: Sequence[str] = (),
    umask: int = -1,
) -> Outcome:
    """One explicit promisor fetch for a known OID list, as the object-job port would issue."""
    return git(
        [
            *PROTOCOL_ARGS,
            *extra,
            "-c",
            "fetch.negotiationAlgorithm=noop",
            "-c",
            "http.lowSpeedLimit=1000",
            "-c",
            "http.lowSpeedTime=30",
            "fetch",
            "origin",
            "--no-tags",
            "--no-write-fetch-head",
            "--recurse-submodules=no",
            "--filter=blob:none",
            "--stdin",
        ],
        git_dir=git_dir,
        stdin=("\n".join(oids) + "\n").encode(),
        trace_dir=traces,
        timeout=timeout,
        umask=umask,
    )


def suite_prefetch(scratch: Path, args: argparse.Namespace) -> None:
    """Blobless convergence over HTTPS: subject prefetch, backfill coverage, full comparison."""
    reps = cast(int, args.reps)
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "prefetch"
    repositories = [SMALL, MEDIUM]
    if cast(str, args.only):
        repositories = [repo for repo in repositories if repo[0] in cast(str, args.only).split(",")]
    recorder = Recorder("prefetch", scratch, {"reps": reps, "timeout_s": timeout})
    for name, url in repositories:
        for rep in range(reps):
            full = work / f"{name}-full.git"
            blobless = work / f"{name}-blobless.git"
            order = ["full", "blobless"] if rep % 2 == 0 else ["blobless", "full"]
            walls: dict[str, float] = {}
            for strategy in order:
                destination = full if strategy == "full" else blobless
                remove(destination)
                outcome = must(
                    git(
                        clone_args(
                            layout="bare", strategy=strategy, url=url, destination=destination
                        )
                    )
                )
                walls[strategy] = outcome.wall_s
            head = text(git(["rev-parse", "HEAD"], git_dir=full))
            all_refs = ["--all"]
            full_objects = count_objects(full)
            remove(full)
            base_missing_head = missing_reachable(blobless, [head])
            base_missing_all = missing_reachable(blobless, all_refs)
            row: dict[str, Json] = {
                "repository": name,
                "rep": rep,
                "full_clone_s": round(walls["full"], 3),
                "blobless_clone_s": round(walls["blobless"], 3),
                "full_in_pack": full_objects["in_pack"],
                "blobless_missing_reachable_from_head": base_missing_head,
                "blobless_missing_reachable_from_all_refs": base_missing_all,
            }

            # Subject prefetch: exactly the blobs of the pinned HEAD tree.
            target = copy_store(blobless, work / "subject.git")
            listed = time.perf_counter()
            check = git(
                ["cat-file", "--batch-check"],
                git_dir=target,
                env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
                stdin=("\n".join(tree_oids(target, head)) + "\n").encode(),
            )
            wanted = sorted(
                {
                    line.split()[0]
                    for line in check.stdout.decode().splitlines()
                    if line.endswith(" missing")
                }
            )
            list_s = time.perf_counter() - listed
            fetched = prefetch_oids(target, wanted, traces, timeout)
            after = git(
                ["cat-file", "--batch-check"],
                git_dir=target,
                env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
                stdin=("\n".join(tree_oids(target, head)) + "\n").encode(),
            )
            row["subject_prefetch"] = {
                "wanted": len(wanted),
                "list_s": round(list_s, 3),
                "fetch_s": round(fetched.wall_s, 3),
                "returncode": fetched.returncode,
                "error_class": fetched.error_class(),
                "requests": fetched.trace.remote_helpers if fetched.trace else None,
                "added_bytes": disk_usage(target / "objects" / "pack")["apparent_bytes"],
                "tree_missing_after": after.stdout.decode().count(" missing\n"),
            }
            remove(target)

            # Backfill: what it covers, and how long.
            target = copy_store(blobless, work / "backfill.git")
            backfill = git(["backfill"], git_dir=target, trace_dir=traces, timeout=timeout)
            remainder = missing_oids(target, all_refs)
            row["backfill"] = {
                "s": round(backfill.wall_s, 3),
                "returncode": backfill.returncode,
                "missing_from_head_after": missing_reachable(target, [head]),
                "missing_from_all_refs_after": len(remainder),
                "disk_bytes": disk_usage(target)["allocated_bytes"],
            }
            if remainder:
                rest = prefetch_oids(target, remainder, traces, timeout)
                row["backfill"]["remainder_fetch_s"] = round(rest.wall_s, 3)
                row["backfill"]["remainder_returncode"] = rest.returncode
                row["backfill"]["missing_after_remainder"] = missing_reachable(target, all_refs)
            remove(target)

            # One explicit fetch of every missing object reachable from any ref.
            target = copy_store(blobless, work / "converge.git")
            listed = time.perf_counter()
            everything = missing_oids(target, all_refs)
            list_s = time.perf_counter() - listed
            converge = prefetch_oids(target, everything, traces, timeout)
            row["single_request_convergence"] = {
                "wanted": len(everything),
                "list_s": round(list_s, 3),
                "fetch_s": round(converge.wall_s, 3),
                "returncode": converge.returncode,
                "error_class": converge.error_class(),
                "missing_after": missing_reachable(target, all_refs),
                "disk_bytes": disk_usage(target)["allocated_bytes"],
            }
            remove(target)
            remove(blobless)
            recorder.add(**row)
    print(recorder.write())


def suite_catalog(scratch: Path, args: argparse.Namespace) -> None:
    """Cost of scanning a flat directory of source records, the unsharded layout."""
    reps = cast(int, args.reps)
    work = scratch / "catalog"
    recorder = Recorder("catalog", scratch, {"reps": reps})
    record = (
        b"softschema:\n  contract: example/v1\n  envelope: source\n  status: enforced\nsource:\n  id: sha256:"
        + b"0" * 64
        + b"\n"
    )
    for entries in (100, 1_000, 10_000):
        remove(work)
        root = work / "sources"
        root.mkdir(parents=True)
        for index in range(entries):
            entry = root / f"example-com--owner--repository-{index:05d}--{index:012x}"
            entry.mkdir()
            (entry / "source.yml").write_bytes(record)
        scans: list[float] = []
        total = 0
        for _rep in range(reps):
            started = time.perf_counter()
            total = 0
            with os.scandir(root) as iterator:
                for item in iterator:
                    with open(os.path.join(item.path, "source.yml"), "rb") as handle:
                        total += len(handle.read())
            scans.append(time.perf_counter() - started)
        recorder.add(entries=entries, scan_and_read=stats(scans), bytes_read=total)
    if not args.keep:
        remove(work)
    print(recorder.write())


def suite_autogc(scratch: Path, args: argparse.Namespace) -> None:
    """Per-object lazy fetches over HTTPS with and without automatic maintenance."""
    reps = cast(int, args.reps)
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "autogc"
    recorder = Recorder("autogc", scratch, {"reps": reps, "timeout_s": timeout})
    _name, url = SMALL
    blobless = work / "flask-https-blobless.git"
    remove(blobless)
    must(
        git(
            [
                *PROTOCOL_ARGS,
                "clone",
                "--bare",
                "--template=",
                "--filter=blob:none",
                "--",
                url,
                str(blobless),
            ]
        )
    )
    head = text(git(["rev-parse", "HEAD"], git_dir=blobless))
    variants: list[tuple[str, list[str]]] = [
        ("git_defaults", []),
        ("maintenance_disabled", ["maintenance.auto=false", "gc.auto=0"]),
        ("commit_graph_disabled", ["core.commitGraph=false"]),
    ]
    for rep in range(reps):
        for variant, settings in variants if rep % 2 == 0 else list(reversed(variants)):
            store = copy_store(blobless, work / "race.git")
            for item in settings:
                key, _, value = item.partition("=")
                must(git(["config", key, value], git_dir=store))
            outcome = git(
                ["ls-tree", "-r", "-z", "-l", "--full-tree", head],
                git_dir=store,
                trace_dir=traces,
                timeout=timeout,
            )
            wait_for_gc(store)
            recorder.add(
                case="https_lazy_fetch_auto_maintenance",
                variant=variant,
                rep=rep,
                returncode=outcome.returncode,
                error_class=outcome.error_class(),
                wall_s=round(outcome.wall_s, 3),
                entries_listed=outcome.stdout.count(b"\0"),
                lazy_fetches=outcome.trace.lazy_fetches if outcome.trace else None,
                maintenance_spawns=outcome.trace.maintenance_spawns if outcome.trace else None,
                packs_after=len(list((store / "objects" / "pack").glob("*.pack"))),
            )
            remove(store)
    if not args.keep:
        remove(blobless)
    print(recorder.write())


def raw_change_oids(git_dir: Path, left: str, right: str) -> tuple[list[str], float]:
    """Blob IDs on both sides of a tree-only diff.

    Porcelain `git diff` enables rename detection by default (diff.renames),
    and inexact rename detection reads blobs, so the listing names
    `--no-renames` explicitly.
    """
    started = time.perf_counter()
    raw = must(
        git(
            ["diff", "--raw", "-z", "--no-abbrev", "--no-renames", left, right],
            git_dir=git_dir,
            env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
        )
    ).stdout
    oids: set[str] = set()
    for token in raw.split(b"\0"):
        if token.startswith(b":"):
            fields = token.decode().split(" ")
            oids.update(oid for oid in (fields[2], fields[3]) if set(oid) != {"0"})
    return sorted(oids), time.perf_counter() - started


def suite_precheck(scratch: Path, args: argparse.Namespace) -> None:
    """Does the tree-only change set name every blob the v0.10 diff routes read?"""
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "precheck"
    recorder = Recorder("precheck", scratch, {"timeout_s": timeout})
    no_lazy = git_env({"GIT_NO_LAZY_FETCH": "1"})
    for name, url in (SMALL, MEDIUM):
        origin = local_origin(scratch, name, url)
        full = work / f"{name}-full.git"
        remove(full)
        must(
            git(clone_args(layout="bare", strategy="full", url=file_url(origin), destination=full))
        )
        subjects = select_subjects(full)
        remove(full)
        pairs = [(f"{commit}^", commit) for commit in subjects.first_parent[:-1]]
        pairs.append((subjects.wide_base, subjects.head))
        store = work / f"{name}-blobless.git"
        remove(store)
        must(
            git(
                clone_args(
                    layout="bare", strategy="blobless", url=file_url(origin), destination=store
                )
            )
        )
        for left, right in pairs:
            oids, list_s = raw_change_oids(store, left, right)
            started = time.perf_counter()
            check = git(
                ["cat-file", "--batch-check"],
                git_dir=store,
                env=no_lazy,
                stdin=("\n".join(oids) + "\n").encode(),
            )
            missing = [
                line.split()[0]
                for line in check.stdout.decode().splitlines()
                if line.endswith(" missing")
            ]
            check_s = time.perf_counter() - started
            fetch_s: float | None = None
            if missing:
                fetched = must(prefetch_oids(store, missing, traces, timeout))
                fetch_s = fetched.wall_s
            flags = ["-M50", "-C", "--diff-merges=first-parent"]
            routes = {
                "commit_detail": [
                    "show",
                    "-z",
                    "--raw",
                    "--numstat",
                    "-M",
                    "-C",
                    "--diff-merges=first-parent",
                    f"--format={SHOW_FORMAT}",
                    right,
                ],
                "manifest_raw": ["diff", "--raw", "-z", "--no-abbrev", *flags, left, right],
                "manifest_numstat": ["diff", "--numstat", "-z", *flags, left, right],
                "patches": ["diff", *flags, left, right],
            }
            if left == subjects.wide_base:
                del routes["commit_detail"]
            results = {key: git(argv, git_dir=store, env=no_lazy) for key, argv in routes.items()}
            recorder.add(
                repository=name,
                left=left,
                right=right,
                changed_blobs=len(oids),
                missing_before=len(missing),
                raw_list_ms=round(list_s * 1000, 2),
                batch_check_ms=round(check_s * 1000, 2),
                fetch_s=round(fetch_s, 3) if fetch_s is not None else None,
                routes_failed=sorted(
                    key for key, outcome in results.items() if outcome.returncode != 0
                ),
            )
        if not args.keep:
            remove(store)
    print(recorder.write())


def config_digest(git_dir: Path) -> tuple[str, list[str]]:
    """The configuration snapshot: SHA-256 of `git config --file <config> --list -z` output."""
    raw = must(git(["config", "--file", str(git_dir / "config"), "--list", "-z"])).stdout
    keys = [entry.split(b"\n", 1)[0].decode() for entry in raw.split(b"\0") if entry]
    return "sha256:" + hashlib.sha256(raw).hexdigest(), keys


def init_store(path: Path, url: str) -> Path:
    """The frozen layout: init --bare, Metabrowser-written config, one origin remote."""
    remove(path)
    must(git(["init", "--bare", "--template=", "-q", str(path)]))
    for item in STORE_CONFIG:
        key, _, value = item.partition("=")
        must(git(["config", key, value], git_dir=path))
    must(git(["config", "remote.origin.url", url], git_dir=path))
    return path


def suite_storeconfig(scratch: Path, args: argparse.Namespace) -> None:
    """Configuration snapshots, fork sources, hook paths, and blobless retention."""
    timeout = cast(float, args.timeout)
    traces = scratch / "traces"
    work = scratch / "storeconfig"
    remove(work)
    recorder = Recorder("storeconfig", scratch, {})
    rng = random.Random("storeconfig")
    base = tiny_origin(work / "base.git")
    files = {
        f"f{index}.txt": ("100644", write_blob(base, rng.randbytes(1024))) for index in range(6)
    }
    root = write_commit(base, write_tree(base, files), [], "base")
    set_head(base, root)

    # 1. Which operations change the store's configuration after its first fetch.
    store = init_store(work / "store.git", file_url(base))
    _, init_keys = config_digest(store)
    must(
        git(
            [
                *PROTOCOL_ARGS,
                "fetch",
                "--no-write-fetch-head",
                "--filter=blob:none",
                "origin",
                "+refs/heads/*:refs/remotes/origin/*",
            ],
            git_dir=store,
        )
    )
    must(git(["symbolic-ref", "HEAD", "refs/remotes/origin/main"], git_dir=store))
    snapshot, fetch_keys = config_digest(store)
    recorder.add(
        case="config_keys",
        written_by_init_and_metabrowser=init_keys,
        added_by_first_filtered_fetch=[key for key in fetch_keys if key not in init_keys],
    )
    files["f0.txt"] = ("100644", write_blob(base, rng.randbytes(1024)))
    second = write_commit(base, write_tree(base, files), [root], "second")
    must(git(["update-ref", "refs/heads/next", second], git_dir=base))
    operations: list[tuple[str, Callable[[], Outcome]]] = [
        (
            "job_fetch_into_private_refs",
            lambda: git(
                [
                    *PROTOCOL_ARGS,
                    "fetch",
                    "--no-tags",
                    "--no-write-fetch-head",
                    "origin",
                    "+refs/heads/*:refs/metabrowser/jobs/j1/*",
                ],
                git_dir=store,
            ),
        ),
        (
            "object_id_prefetch",
            lambda: prefetch_oids(store, tree_oids(store, second), traces, timeout),
        ),
        (
            "update_ref_transaction",
            lambda: git(
                ["update-ref", "--stdin"],
                git_dir=store,
                stdin=f"start\nupdate refs/remotes/origin/next {second} {ZERO_OID}\ndelete refs/metabrowser/jobs/j1/next {second}\ndelete refs/metabrowser/jobs/j1/main {root}\nprepare\ncommit\n".encode(),
            ),
        ),
        ("gc_prune_now", lambda: git(["gc", "--prune=now"], git_dir=store)),
        ("repack_all", lambda: git(["repack", "-a", "-d"], git_dir=store)),
        (
            "store_read_log",
            lambda: git(
                [*STORE_READ_CONFIG, "log", "-1", "--format=%H", second],
                git_dir=store,
                env=git_env({"GIT_NO_LAZY_FETCH": "1"}),
            ),
        ),
    ]
    for name, operation in operations:
        outcome = operation()
        digest, keys = config_digest(store)
        recorder.add(
            case="config_after_operation",
            operation=name,
            returncode=outcome.returncode,
            digest_unchanged=digest == snapshot,
            keys_changed=sorted(set(keys) ^ set(fetch_keys)),
        )

    # 2. A fork's objects fetched by URL into a blobless store.
    fork = work / "fork.git"
    remove(fork)
    must(git(["clone", "--bare", "--template=", "--no-local", "-q", str(base), str(fork)]))
    must(git(["config", "uploadpack.allowFilter", "true"], git_dir=fork))
    fork_files = dict(files)
    fork_files["fork.txt"] = ("100644", write_blob(fork, rng.randbytes(1024)))
    fork_commit = write_commit(fork, write_tree(fork, fork_files), [second], "fork")
    must(git(["update-ref", "refs/heads/feature", fork_commit], git_dir=fork))
    for variant, extra in (("by_url_filtered", ["--filter=blob:none"]), ("by_url_unfiltered", [])):
        target = copy_store(store, work / "fork-target.git")
        before, before_keys = config_digest(target)
        outcome = git(
            [
                *PROTOCOL_ARGS,
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                *extra,
                file_url(fork),
                "+refs/heads/feature:refs/metabrowser/jobs/fork/feature",
            ],
            git_dir=target,
        )
        after, after_keys = config_digest(target)
        packs = pack_counts(target)
        gc = git(["gc", "--prune=now"], git_dir=target)
        recorder.add(
            case="fork_fetch",
            variant=variant,
            returncode=outcome.returncode,
            digest_unchanged=after == before,
            keys_added=[key for key in after_keys if key not in before_keys],
            non_promisor_packs=packs["non_promisor_packs"],
            gc_returncode=gc.returncode,
            gc_stderr=stderr_lines(gc.stderr),
        )
        remove(target)
    # The provider path: the base repository publishes the change-request head.
    must(
        git(
            [
                *PROTOCOL_ARGS,
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                file_url(fork),
                "+refs/heads/feature:refs/pull/1/head",
            ],
            git_dir=base,
        )
    )
    target = copy_store(store, work / "fork-target.git")
    before, _ = config_digest(target)
    outcome = git(
        [
            *PROTOCOL_ARGS,
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            "origin",
            "+refs/pull/1/head:refs/metabrowser/jobs/change1/head",
        ],
        git_dir=target,
    )
    after, _ = config_digest(target)
    packs = pack_counts(target)
    gc = git(["gc", "--prune=now"], git_dir=target)
    repack = git(["repack", "-a", "-d"], git_dir=target)
    recorder.add(
        case="fork_fetch",
        variant="base_repository_pull_ref_through_origin",
        returncode=outcome.returncode,
        digest_unchanged=after == before,
        non_promisor_packs=packs["non_promisor_packs"],
        gc_returncode=gc.returncode,
        repack_returncode=repack.returncode,
    )
    remove(target)

    # 3. Hook paths: an empty core.hooksPath resolves against the working directory.
    cwd = work / "cwd-with-hooks"
    cwd.mkdir(parents=True, exist_ok=True)
    marker = work / "hook-ran"
    hook_body = f"#!/bin/sh\ntouch '{marker}'\nexit 0\n"
    for directory in (cwd, cwd / "hooks"):
        directory.mkdir(parents=True, exist_ok=True)
        hook = directory / "reference-transaction"
        hook.write_text(hook_body)
        hook.chmod(0o700)
    for variant, value in (
        ("hooks_path_empty", ""),
        ("hooks_path_dev_null", os.devnull),
        ("hooks_path_unset", None),
    ):
        target = copy_store(store, work / "hooks.git")
        must(git(["config", "--unset-all", "core.hooksPath"], git_dir=target))
        if value is not None:
            must(git(["config", "core.hooksPath", value], git_dir=target))
        for place in ("cwd", "store_hooks_dir"):
            remove(marker)
            if place == "store_hooks_dir":
                (target / "hooks").mkdir(exist_ok=True)
                (target / "hooks" / "reference-transaction").write_text(hook_body)
                (target / "hooks" / "reference-transaction").chmod(0o700)
            outcome = git(
                ["update-ref", f"refs/metabrowser/hooks/{place}", root], git_dir=target, cwd=cwd
            )
            recorder.add(
                case="hooks",
                variant=variant,
                planted_in=place,
                returncode=outcome.returncode,
                hook_ran=marker.exists(),
            )
        remove(target)

    # 4. Retention in a blobless store after a job's refs are discarded.
    for strategy in ("blobless", "full"):
        target = init_store(work / f"retention-{strategy}.git", file_url(base))
        filtered = ["--filter=blob:none"] if strategy == "blobless" else []
        must(
            git(
                [
                    *PROTOCOL_ARGS,
                    "fetch",
                    "--no-write-fetch-head",
                    *filtered,
                    "origin",
                    "+refs/heads/main:refs/remotes/origin/main",
                ],
                git_dir=target,
            )
        )
        discarded = dict(files)
        discarded["discarded.txt"] = ("100644", write_blob(base, rng.randbytes(2048)))
        discarded_commit = write_commit(base, write_tree(base, discarded), [root], "discarded")
        must(git(["update-ref", "refs/heads/discarded", discarded_commit], git_dir=base))
        must(
            git(
                [
                    *PROTOCOL_ARGS,
                    "fetch",
                    "--no-tags",
                    "--no-write-fetch-head",
                    *filtered,
                    "origin",
                    "+refs/heads/discarded:refs/metabrowser/jobs/j2/discarded",
                ],
                git_dir=target,
            )
        )
        blob = discarded["discarded.txt"][1]
        if strategy == "blobless":
            must(prefetch_oids(target, [blob], traces, timeout))
        must(git(["update-ref", "-d", "refs/metabrowser/jobs/j2/discarded"], git_dir=target))
        no_lazy = git_env({"GIT_NO_LAZY_FETCH": "1"})
        before = {
            name: git(["cat-file", "-e", oid], git_dir=target, env=no_lazy).returncode == 0
            for name, oid in (("commit", discarded_commit), ("blob", blob))
        }
        for command in (["gc", "--prune=now"], ["repack", "-a", "-d"], ["prune", "--expire=now"]):
            outcome = git(command, git_dir=target)
            after = {
                name: git(["cat-file", "-e", oid], git_dir=target, env=no_lazy).returncode == 0
                for name, oid in (("commit", discarded_commit), ("blob", blob))
            }
            recorder.add(
                case="discarded_job_retention",
                strategy=strategy,
                command=" ".join(command),
                returncode=outcome.returncode,
                present_before=before,
                present_after=after,
            )
        remove(target)
    if not args.keep:
        remove(work)
    print(recorder.write())


def suite_lockdescriptors(scratch: Path, args: argparse.Namespace) -> None:
    """flock on a separate open() versus a dup() of a descriptor holding a shared lease."""
    work = scratch / "lockdescriptors"
    remove(work)
    work.mkdir(parents=True)
    recorder = Recorder("lockdescriptors", scratch, {})
    path = work / "store.maintenance.lock"
    path.write_bytes(b"")
    lease = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    fcntl.flock(lease, fcntl.LOCK_SH)

    def exclusive(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    probe = (
        "import fcntl, os, sys\n"
        "fd = os.open(sys.argv[1], os.O_RDWR)\n"
        "try:\n"
        "    fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)\n"
        "except BlockingIOError:\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    separate = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    separate_granted = exclusive(separate)
    duplicate = os.dup(lease)
    duplicate_granted = exclusive(duplicate)
    other_shared = (
        subprocess.run([sys.executable, "-c", probe, str(path)], check=False).returncode == 0
    )
    recorder.add(
        primitive="flock exclusive attempts while one descriptor holds a shared lease",
        separate_open_exclusive_granted=separate_granted,
        dup_of_lease_exclusive_granted=duplicate_granted,
        other_process_shared_granted_afterwards=other_shared,
    )
    for fd in (duplicate, separate, lease):
        os.close(fd)
    if not args.keep:
        remove(work)
    print(recorder.write())


SUITES: dict[str, Callable[[Path, argparse.Namespace], None]] = {
    "storeconfig": suite_storeconfig,
    "lockdescriptors": suite_lockdescriptors,
    "gitlinks": suite_gitlinks,
    "mailmap": suite_mailmap,
    "umask": suite_umask,
    "precheck": suite_precheck,
    "fetches": suite_fetches,
    "autogc": suite_autogc,
    "prefetch": suite_prefetch,
    "catalog": suite_catalog,
    "url": suite_url,
    "environment": suite_environment,
    "acquire": suite_acquire,
    "read": suite_read,
    "lazy": suite_lazy,
    "concurrency": suite_concurrency,
    "maintenance": suite_maintenance,
    "platform": suite_platform,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 repository-cache measurements.")
    parser.add_argument("suite", choices=sorted(SUITES))
    parser.add_argument("--scratch", type=Path, required=True, help="directory for every clone")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--only", default="", help="comma-separated repository or origin names")
    parser.add_argument("--keep", action="store_true", help="keep created stores for inspection")
    args = parser.parse_args()
    scratch = cast(Path, args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    SUITES[cast(str, args.suite)](scratch.resolve(), args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
