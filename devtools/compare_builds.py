"""Compare two installed Metabrowser builds on one tree: same answers, and how fast.

Equivalence first. A performance change earns its place by making the same answer
arrive sooner, so a timing is only worth reading once the two builds are known to
agree. What is allowed to differ is *when* rows appear. Response-list order remains
part of the comparison: the navigation tree is ordered for display, and a generic
sort would hide a user-visible regression.

Every guard below is a mistake that was made validating the 0.6.1 perf work, and
each one produced a confident wrong answer that nothing in the output
contradicted. They are guards rather than advice for that reason.

* **The poll key is asserted against the first response.** ``index_status`` is a
  real field on ``/api/rollup`` and absent from ``/api/tree``; carried across, it
  made ``.get`` return None forever and every run consumed its deadline. A run
  that waits seven minutes and reports nothing reads as a slow build, which is
  the thing being measured.

* **Rows and tallies are separate endpoints.** ``/api/tree`` with no depth is the
  nav tree's own request, which the server resolves to ``DEFAULT_TREE_DEPTH``;
  ``depth=0`` is the tally channel and returns no rows ever. Polling the wrong
  one compares a computed answer against an uncomputed one and reads as a
  regression.

* **The corpus is fingerprinted before and after.** A tree the measurement can
  write to is a variable: running over a working checkout writes ``__pycache__``
  between the two builds, and the diff fills with ``.pyc`` counts belonging to
  neither.

* **Both builds are launched the same way**, as installed console scripts. A
  candidate behind ``uv run`` carries a resolver the baseline does not -- about
  half a second, which is harmless for a large difference and decisive for a
  small one, exactly backwards from where it matters.

* **The two builds must not report the same version.** That is never a
  comparison anyone wants, and it is undetectable from the results afterwards.

* **Each build is resolved to an absolute path and that path is reported.** Run
  under ``uv run``, a bare ``metab`` resolves to the project venv rather than the
  globally installed release, so "baseline" silently becomes the candidate again.
  Resolving and printing is what makes that visible; prefer absolute paths for
  both, and read the ``resolved`` field before believing a result.

Timings are measured from the moment the server accepted a connection, never from
process spawn, so start-up is not charged to the code under test.

Usage::

    uv --config-file uv.toml run --frozen python -m devtools.compare_builds \\
        /path/to/tree --baseline metab --candidate /tmp/cand/bin/metab --runs 5 \\
        --output .bench/release-comparison/backend.json

Build a candidate to compare against a released baseline with ``uv build --wheel``
and ``uv pip install`` into a throwaway venv; that is what makes both sides a
console script. ``devtools/bench_serving.py --corpus project`` builds a corpus of
a known shape to point this at.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, cast

from strif import atomic_output_file

SETTLE_KEY = "tally_cache_status"
SETTLE_VALUE = "done"

# The browser makes TWO different /api/tree requests, and conflating them is
# what made a deliberate change read as a regression.
#
# Rows come from `/api/tree` with no depth parameter, which the server resolves
# to DEFAULT_TREE_DEPTH = 2 (tree.py). So depth=2 is not some unused channel --
# it is exactly what the file tree renders from, and it is the only one of the
# two that can answer "when did the first row exist".
ROW_ENDPOINT = "/api/tree"
# Tallies come from a separate poll behind the render
# (scheduleRootSummaryRefresh, app.js:1032). Since #66 this is the only channel
# that computes them; a row request carries them only from a fresh memo, and
# the client guards every tally field individually.
TALLY_ENDPOINT = "/api/tree?depth=0"
PROGRESS_ENDPOINT = "/api/index/progress"
# The fixed implementation records 61.5-109.9 ms on the 123,657-file project
# corpus; c123ae6 records 317.4 ms because the request loop waits on the worker's
# lock. Two hundred milliseconds matches the browser responsiveness boundary and
# separates those mechanisms while retaining headroom for host scheduling noise.
TALLY_OVERLAP_PROGRESS_BUDGET_MS = 200.0

# Since #66, the row endpoint deliberately omits navigation tallies unless a
# fresh memo already exists. Compare the row contract that the tree consumes,
# then compare the complete tally response on its dedicated endpoint. Keeping
# this projection explicit prevents a generic recursive key filter from also
# erasing nested contract fields such as `file_type_registry.schema_version`.
ROW_COMPARISON_FIELDS = ("root", "tree")
REQUIRED_FIELDS = {
    "rows": ROW_COMPARISON_FIELDS,
    "tallies": ("root", "summary", "tally_cache_status", "tree"),
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get(port: int, path: str, timeout: float = 60.0) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def timed_get(port: int, path: str, timeout: float = 60.0) -> tuple[Any, float]:
    """Return one JSON response and its wall time in milliseconds."""
    started = time.monotonic()
    payload = get(port, path, timeout)
    return payload, (time.monotonic() - started) * 1000.0


def measure_tally_overlap(port: int, timeout: float = 60.0) -> dict[str, Any]:
    """Measure server-loop availability while a full tally is in flight.

    A tally computes in a worker, but another tally request still consults its memo on
    the request loop. Repeating the depth-0 channel makes that overlap deterministic
    without adding the settled depth-2 tree builder as a second O(index) cost. The
    lightweight progress endpoint reports whether unrelated request work can keep
    running while the overlap happens.
    """
    stop_competing_tallies = threading.Event()
    competing_tally_latencies: list[float] = []
    competing_tally_errors: list[str] = []
    progress_latencies: list[float] = []
    tally_elapsed_ms: float | None = None

    def competing_tally_pressure() -> None:
        while not stop_competing_tallies.is_set():
            try:
                _, elapsed_ms = timed_get(port, TALLY_ENDPOINT, timeout)
                competing_tally_latencies.append(elapsed_ms)
            except Exception as exc:  # pragma: no cover - reported by the real comparator
                competing_tally_errors.append(f"{type(exc).__name__}: {exc}")
                return

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tally_future = pool.submit(timed_get, port, TALLY_ENDPOINT, timeout)
        # Let the tally request snapshot the index and enter its worker before the
        # competing channel starts. The loop repeats, so an overlap is not dependent
        # on one precisely timed request.
        time.sleep(0.01)
        competing_tally_future = pool.submit(competing_tally_pressure)
        error: str | None = None
        try:
            while not tally_future.done():
                _, elapsed_ms = timed_get(port, PROGRESS_ENDPOINT, timeout)
                progress_latencies.append(elapsed_ms)
            _, tally_elapsed_ms = tally_future.result()
        except Exception as exc:  # pragma: no cover - reported by the real comparator
            error = f"{type(exc).__name__}: {exc}"
        finally:
            stop_competing_tallies.set()
            try:
                competing_tally_future.result(timeout=timeout)
            except Exception as exc:  # pragma: no cover - reported by the real comparator
                competing_tally_errors.append(f"{type(exc).__name__}: {exc}")

    result: dict[str, Any] = {
        "tally_overlap_tally_ms": (
            round(tally_elapsed_ms, 1) if tally_elapsed_ms is not None else None
        ),
        "tally_overlap_progress_max_ms": (
            round(max(progress_latencies), 1) if progress_latencies else None
        ),
        "tally_overlap_progress_samples": len(progress_latencies),
        "tally_overlap_competing_tally_max_ms": (
            round(max(competing_tally_latencies), 1) if competing_tally_latencies else None
        ),
        "tally_overlap_competing_tally_samples": len(competing_tally_latencies),
    }
    if error is not None:
        result["tally_overlap_error"] = error
    if competing_tally_errors:
        result["tally_overlap_competing_tally_errors"] = competing_tally_errors
    return result


def fingerprint(tree: Path) -> dict[str, Any]:
    """Enough of the tree's state to prove a run did not change it."""
    files = dirs = 0
    newest = 0.0
    for root, dirnames, filenames in os.walk(tree):
        dirs += len(dirnames)
        files += len(filenames)
        for name in filenames:
            # A file that vanished between listing and stat says the tree is
            # moving, which the before/after comparison is what reports.
            with contextlib.suppress(OSError):
                newest = max(newest, os.lstat(os.path.join(root, name)).st_mtime)
    return {"files": files, "dirs": dirs, "newest_mtime": round(newest, 3)}


def peak_rss_mb(pid: int, current: float) -> float:
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False
        )
        return max(current, int(out.stdout.strip() or 0) / 1024)
    except (ValueError, OSError):
        return current


def run_once(command: list[str], tree: str, poll: float, deadline_s: float) -> dict[str, Any]:
    """One server lifetime. Times are relative to the first accepted connection."""
    port = free_port()
    process = subprocess.Popen(
        [*command, tree, "--port", str(port), "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd="/tmp",
    )
    spawned = time.monotonic()
    out: dict[str, Any] = {
        "spawn_to_serving": None,
        "first_row": None,
        "index_done": None,
        "peak_rss_mb": 0.0,
    }
    try:
        # Serving: the first moment a request is answered at all.
        serving = None
        while time.monotonic() - spawned < 180:
            try:
                get(port, "/api/tree?depth=0", timeout=5)
                serving = time.monotonic()
                break
            except Exception:
                if process.poll() is not None:
                    err = process.stderr.read() if process.stderr is not None else b""
                    stderr_tail = err.decode("utf8", "replace")[-400:]
                    out["error"] = f"server exited rc={process.returncode} stderr={stderr_tail!r}"
                    return out
        if serving is None:
            out["error"] = "server never accepted a connection"
            return out
        out["spawn_to_serving"] = round(serving - spawned, 3)

        first = get(port, ROW_ENDPOINT)
        # A poll key that is not in the payload cannot fail -- it waits. Fail now.
        if not isinstance(first, dict) or SETTLE_KEY not in first:
            keys: object = (
                sorted(cast("dict[str, Any]", first))
                if isinstance(first, dict)
                else type(first).__name__
            )
            out["error"] = f"{SETTLE_KEY!r} not in response; keys={keys}"
            return out

        while time.monotonic() - serving < deadline_s:
            out["peak_rss_mb"] = peak_rss_mb(process.pid, out["peak_rss_mb"])
            try:
                payload = get(port, ROW_ENDPOINT)
            except Exception:
                time.sleep(poll)
                continue
            rows = payload.get("tree")
            if out["first_row"] is None and isinstance(rows, list) and rows:
                out["first_row"] = round(time.monotonic() - serving, 3)
            if payload.get(SETTLE_KEY) == SETTLE_VALUE:
                out["index_done"] = round(time.monotonic() - serving, 3)
                break
            time.sleep(poll)
        else:
            out["error"] = f"never settled within {deadline_s}s"

        out["peak_rss_mb"] = round(peak_rss_mb(process.pid, out["peak_rss_mb"]), 1)
        out.update(measure_tally_overlap(port))
        out["final"] = {"rows": get(port, ROW_ENDPOINT), "tallies": get(port, TALLY_ENDPOINT)}
        err = b""
        if process.stderr is not None and process.poll() is not None:
            err = process.stderr.read() or b""
        if err:
            out["stderr_tail"] = err.decode("utf8", "replace")[-400:]
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
    return out


def comparison_payload(channel: str, payload: Any) -> Any:
    """Select the documented answer carried by one comparison channel."""
    if channel != "rows" or not isinstance(payload, dict):
        return payload
    mapping = cast("dict[str, Any]", payload)
    return {key: mapping[key] for key in ROW_COMPARISON_FIELDS if key in mapping}


def missing_required_fields(channel: str, payload: Any) -> list[str]:
    """Report a malformed final response instead of comparing two empty shapes."""
    if not isinstance(payload, dict):
        return ["<object>"]
    mapping = cast("dict[str, Any]", payload)
    return [field for field in REQUIRED_FIELDS[channel] if field not in mapping]


def normalise(payload: Any) -> Any:
    """Canonicalise object-key presentation without changing response meaning."""
    if isinstance(payload, dict):
        mapping = cast("dict[str, Any]", payload)
        return {key: normalise(value) for key, value in sorted(mapping.items())}
    if isinstance(payload, list):
        items = cast("list[Any]", payload)
        return [normalise(value) for value in items]
    return payload


def resolve_tree(requested: str) -> Path:
    """Resolve the corpus before benchmark servers change their working directory."""
    tree = Path(requested).expanduser().resolve()
    if not tree.is_dir():
        raise SystemExit(f"benchmark tree is not a directory: {requested}")
    return tree


def resolve_executable(requested: str) -> str | None:
    """Resolve an executable before benchmark servers change their working directory."""
    found = shutil.which(requested)
    return str(Path(found).resolve()) if found is not None else None


def differences(left: Any, right: Any, path: str, out: list[str], limit: int = 25) -> None:
    if len(out) >= limit:
        return
    if type(left) is not type(right):
        out.append(f"{path}: {type(left).__name__} vs {type(right).__name__}")
        return
    if isinstance(left, dict):
        left_map = cast("dict[str, Any]", left)
        right_map = cast("dict[str, Any]", right)
        for key in sorted(set(left_map) | set(right_map)):
            if key not in left_map:
                out.append(f"{path}.{key}: candidate only")
            elif key not in right_map:
                out.append(f"{path}.{key}: baseline only")
            else:
                differences(left_map[key], right_map[key], f"{path}.{key}", out, limit)
        return
    if isinstance(left, list):
        left_list = cast("list[Any]", left)
        right_list = cast("list[Any]", right)
        if len(left_list) != len(right_list):
            out.append(f"{path}: length {len(left_list)} vs {len(right_list)}")
        # Lengths already reported above; pair what there is.
        for i, (a, b) in enumerate(zip(left_list, right_list, strict=False)):
            differences(a, b, f"{path}[{i}]", out, limit)
        return
    if left != right:
        out.append(f"{path}: {left!r:.60} vs {right!r:.60}")


def stats(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "median": ordered[len(ordered) // 2],
        "min": ordered[0],
        "max": ordered[-1],
        "n": len(ordered),
    }


def comparison_failures(report: dict[str, Any]) -> list[str]:
    """Return every condition that makes the printed timings inadmissible."""
    failures = [f"run failed: {error}" for error in report.get("errors", [])]
    runs_raw = report.get("runs")
    runs = cast("dict[str, Any]", runs_raw) if isinstance(runs_raw, dict) else {}
    candidate_runs_raw = runs.get("candidate")
    if not isinstance(candidate_runs_raw, list) or not candidate_runs_raw:
        failures.append("candidate tally-overlap progress measurements are missing")
    else:
        for run_raw in cast("list[Any]", candidate_runs_raw):
            if not isinstance(run_raw, dict):
                failures.append("candidate tally-overlap progress measurement is malformed")
                continue
            run = cast("dict[str, Any]", run_raw)
            overlap_error = run.get("tally_overlap_error")
            if isinstance(overlap_error, str):
                failures.append(f"candidate tally-overlap measurement failed: {overlap_error}")
            competing_errors = run.get("tally_overlap_competing_tally_errors")
            if isinstance(competing_errors, list) and competing_errors:
                failures.append("candidate competing tally request failed")
            samples = run.get("tally_overlap_progress_samples")
            maximum = run.get("tally_overlap_progress_max_ms")
            if not isinstance(samples, int) or isinstance(samples, bool) or samples < 1:
                failures.append("candidate tally-overlap progress measurement has no samples")
            elif not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
                failures.append("candidate tally-overlap progress latency is missing")
            elif maximum >= TALLY_OVERLAP_PROGRESS_BUDGET_MS:
                failures.append(
                    "candidate tally-overlap progress latency "
                    f"{float(maximum):.1f} ms exceeds "
                    f"{TALLY_OVERLAP_PROGRESS_BUDGET_MS:g} ms"
                )
    if report.get("corpus_unchanged") is not True:
        failures.append("corpus changed during comparison")
    equivalence_raw = report.get("equivalence")
    if not isinstance(equivalence_raw, dict):
        return [*failures, "equivalence results are missing"]
    equivalence = cast("dict[str, Any]", equivalence_raw)
    for channel in REQUIRED_FIELDS:
        result_raw = equivalence.get(channel)
        if not isinstance(result_raw, dict):
            failures.append(f"{channel} equivalence result is missing")
            continue
        result = cast("dict[str, Any]", result_raw)
        missing = result.get("missing_fields")
        if missing:
            failures.append(f"{channel} response is missing required fields: {missing}")
        if result.get("difference_count") != 0:
            failures.append(
                f"{channel} responses differ ({result.get('difference_count', 'unknown')} found)"
            )
    return failures


def write_report(report: dict[str, Any], output: Path) -> None:
    """Atomically persist the complete comparison report."""
    with atomic_output_file(output, make_parents=True) as temporary:
        temporary.write_text(f"{json.dumps(report, indent=2, default=str)}\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tree")
    p.add_argument("--baseline", default="metab")
    p.add_argument("--candidate", default="/tmp/mb-cand/bin/metab")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--poll", type=float, default=0.25)
    p.add_argument("--deadline", type=float, default=300.0)
    p.add_argument("--corpus-name", default="")
    p.add_argument(
        "--output",
        type=Path,
        help="write the complete validated report as JSON",
    )
    args = p.parse_args(argv)
    tree = resolve_tree(args.tree)

    # Resolve to absolute paths before anything else. Under `uv run` a bare name
    # finds the project venv first, which quietly makes "baseline" the candidate.
    resolved: dict[str, str] = {}
    requested: tuple[tuple[str, str], ...] = (
        ("baseline", str(args.baseline)),
        ("candidate", str(args.candidate)),
    )
    for name, given in requested:
        found = resolve_executable(given)
        if not found:
            print(json.dumps({"error": f"{name} {given!r} is not on PATH"}, indent=1))
            return 2
        resolved[name] = found

    builds = {name: [path] for name, path in resolved.items()}
    versions = {}
    for name, command in builds.items():
        r = subprocess.run([*command, "--version"], capture_output=True, text=True, check=False)
        versions[name] = (
            (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "?"
        )
    if resolved["baseline"] == resolved["candidate"]:
        print(
            json.dumps(
                {"error": "both builds resolve to the same binary", "resolved": resolved}, indent=1
            )
        )
        return 2
    if versions["baseline"] == versions["candidate"]:
        print(
            json.dumps(
                {
                    "error": "both builds report the same version -- not a comparison",
                    "versions": versions,
                    "resolved": resolved,
                },
                indent=1,
            )
        )
        return 2

    before = fingerprint(tree)
    print(
        json.dumps(
            {
                "tree": str(tree),
                "corpus": args.corpus_name,
                "versions": versions,
                "resolved": resolved,
                "row_endpoint": ROW_ENDPOINT,
                "tally_endpoint": TALLY_ENDPOINT,
                "corpus_before": before,
            },
            indent=1,
        ),
        flush=True,
    )

    results: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
    finals: dict[str, Any] = {}
    for index in range(args.runs):
        for name, command in builds.items():
            run = run_once(command, str(tree), args.poll, args.deadline)
            final = run.pop("final", None)
            if index == 0 and final is not None:
                finals[name] = final
            results[name].append(run)
            print(
                f"  run {index + 1} {name:9s} "
                f"start={run.get('spawn_to_serving')}s first_row={run.get('first_row')}s "
                f"index_done={run.get('index_done')}s rss={run.get('peak_rss_mb')}MB "
                f"tally_overlap_progress_max="
                f"{run.get('tally_overlap_progress_max_ms')}ms"
                f"{' ERROR=' + run['error'] if 'error' in run else ''}",
                flush=True,
            )

    after = fingerprint(tree)
    report: dict[str, Any] = {
        "corpus": args.corpus_name,
        "tree": str(tree),
        "versions": versions,
        "resolved": resolved,
        "row_endpoint": ROW_ENDPOINT,
        "tally_endpoint": TALLY_ENDPOINT,
        "runs": results,
        "corpus_before": before,
        "corpus_after": after,
        "corpus_unchanged": before == after,
        "timings": {},
        "errors": [r.get("error") for rs in results.values() for r in rs if r.get("error")],
    }
    for metric in (
        "spawn_to_serving",
        "first_row",
        "index_done",
        "peak_rss_mb",
        "tally_overlap_tally_ms",
        "tally_overlap_progress_max_ms",
        "tally_overlap_competing_tally_max_ms",
    ):
        for name, runs in results.items():
            values = [r[metric] for r in runs if isinstance(r.get(metric), (int, float))]
            if values:
                report["timings"].setdefault(metric, {})[name] = stats(values)

    equivalence: dict[str, Any] = {}
    if "baseline" in finals and "candidate" in finals:
        for channel in ("rows", "tallies"):
            diffs: list[str] = []
            missing = {
                name: fields
                for name, fields in (
                    (
                        "baseline",
                        missing_required_fields(channel, finals["baseline"][channel]),
                    ),
                    (
                        "candidate",
                        missing_required_fields(channel, finals["candidate"][channel]),
                    ),
                )
                if fields
            }
            differences(
                normalise(comparison_payload(channel, finals["baseline"][channel])),
                normalise(comparison_payload(channel, finals["candidate"][channel])),
                channel,
                diffs,
            )
            equivalence[channel] = {
                "difference_count": len(diffs),
                "differences": diffs,
                "missing_fields": missing,
            }
    report["equivalence"] = equivalence
    report["validation_errors"] = comparison_failures(report)
    report["valid"] = not report["validation_errors"]
    if args.output is not None:
        write_report(report, args.output)
    print(json.dumps(report, indent=1, default=str))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
