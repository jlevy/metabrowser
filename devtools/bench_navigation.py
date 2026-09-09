"""Compare settled HTTP navigation on one existing tree, without a browser.

Runs fresh baseline/candidate/candidate/baseline processes. Measures file reads,
validators, and concurrent inventory requests with and without Recent. Output includes
raw samples, response checks, runtimes, dependency versions and host/process load.
The root is read-only; put output and logs outside it. See docs/engine-performance-model.md.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, cast

from strif import atomic_write_text

from devtools.bench_serving import MetabBuild, Server, resolve_metab_build
from metabrowser.inventory_engine.contract import canonical_inventory_path

# Workload cadence spans activity-tracker ticks while keeping a diagnostic run short.
DEFAULT_ROUNDS = 20
SERIAL_PAUSE_S = 0.12
BURST_PAUSE_S = 0.15
SETTLE_POLL_S = 0.2
# Fail stalled experiments rather than including incomplete requests in latency claims.
REQUEST_TIMEOUT_S = 30
SETTLE_TIMEOUT_S = 120

# Import the server before checking the GIL: an extension can enable it on a
# free-threaded build. Probe the installed console script's interpreter, not ours.
_RUNTIME_PROBE = dedent(r"""
    import hashlib, importlib.metadata, json, platform, sys, sysconfig
    from pathlib import Path
    import metabrowser.server
    package = Path(metabrowser.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(package.rglob('*.py')):
        digest.update(path.relative_to(package).as_posix().encode() + b'\0')
        digest.update(path.read_bytes() + b'\0')
    print(json.dumps({
        'python': sys.version,
        'implementation': platform.python_implementation(),
        'machine': platform.machine(),
        'free_threaded': bool(sysconfig.get_config_var('Py_GIL_DISABLED')),
        'gil_enabled': getattr(sys, '_is_gil_enabled', lambda: True)(),
        'python_source_sha256': digest.hexdigest(),
        'dependencies': dict(sorted((d.metadata['Name'], d.version)
            for d in importlib.metadata.distributions() if d.metadata['Name'] != 'metabrowser')),
    }))
""")


def runtime_identity(build: MetabBuild) -> dict[str, Any]:
    """Require a uv-installed POSIX console script with an explicit interpreter."""

    with build.executable.open() as script:
        shebang = script.readline().strip()
    interpreter = Path(shebang.removeprefix("#!"))
    if not shebang.startswith("#!") or not interpreter.is_absolute() or not interpreter.is_file():
        raise ValueError("benchmark requires a uv-installed metab console script")
    probe = subprocess.run(
        [str(interpreter), "-c", _RUNTIME_PROBE],
        check=True,
        capture_output=True,
        text=True,
        timeout=REQUEST_TIMEOUT_S,
    )
    return cast("dict[str, Any]", json.loads(probe.stdout))


def require_matching_runtimes(identities: dict[str, dict[str, Any]]) -> None:
    baseline, candidate = identities["baseline"], identities["candidate"]
    mismatches = [
        key
        for key in baseline
        if key not in {"dependencies", "python_source_sha256"}
        and baseline[key] != candidate.get(key)
    ]
    if mismatches:
        raise ValueError(
            f"runtime mismatch: {', '.join(mismatches)}; use uv sync --python with the same "
            "interpreter for both builds before claiming a code regression"
        )


@dataclass(frozen=True)
class Route:
    label: str
    url: str
    native_paths: bool = False


@dataclass(frozen=True)
class Response:
    sample: dict[str, Any]
    payload: dict[str, Any]
    etag: str | None


def request(
    base: str, route: Route, *, etag: str | None = None, barrier: threading.Barrier | None = None
) -> Response:
    headers = {"Accept-Encoding": "gzip"}
    if etag is not None:
        headers["If-None-Match"] = etag
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if barrier is not None:
        barrier.wait(timeout=REQUEST_TIMEOUT_S)
    start = time.perf_counter()
    try:
        response = opener.open(
            urllib.request.Request(base + route.url, headers=headers), timeout=REQUEST_TIMEOUT_S
        )
    except urllib.error.HTTPError as error:
        response = error
    with response:
        first_ms = (time.perf_counter() - start) * 1000
        wire = response.read()
        total_ms = (time.perf_counter() - start) * 1000
        server = re.search(r"srv;dur=([\d.]+)", response.headers.get("Server-Timing", ""))
        body = gzip.decompress(wire) if response.headers.get("Content-Encoding") == "gzip" else wire
        payload = cast("dict[str, Any]", json.loads(body)) if body else {}
        sample: dict[str, Any] = {
            "label": route.label,
            "status": response.status,
            "total_ms": total_ms,
            "first_byte_ms": first_ms,
            "server_ms": float(server[1]) if server else None,
            "wire_bytes": len(wire),
        }
        expected = 304 if etag is not None else 200
        if response.status != expected or (expected == 304 and body):
            raise ValueError(f"{route.label}: expected {expected} with valid body, got {sample}")
        # Store selected public fields, never the root-bearing response or raw ETag.
        if route.label.startswith("file:") and expected == 200:
            if not isinstance(payload.get("content"), str):
                raise ValueError("--file must name a text file with a content response")
            sample["content_sha256"] = hashlib.sha256(payload["content"].encode()).hexdigest()
            sample["kind"] = payload["kind"]
            sample["path"] = (
                canonical_inventory_path(payload["path"]) if route.native_paths else payload["path"]
            )
        if route.label == "recent":
            sample["rows"] = len(payload["entries_flat"])
            sample["matching"] = payload["total_matching"]
            sample["paths_sha256"] = hashlib.sha256(
                json.dumps(
                    sorted(
                        canonical_inventory_path(row["path"]) if route.native_paths else row["path"]
                        for row in payload["entries_flat"]
                    )
                ).encode()
            ).hexdigest()
        if route.label == "catalog":
            if payload.get("complete") is not True or payload.get("truncated"):
                raise ValueError("catalog is incomplete")
            sample["files"] = len(payload["files"])
            sample["content_sha256"] = hashlib.sha256(
                json.dumps(
                    sorted(
                        (
                            {
                                "p": canonical_inventory_path(row["p"])
                                if route.native_paths
                                else row["p"],
                                "e": row["e"],
                            }
                            for row in payload["files"]
                        ),
                        key=lambda row: row["p"],
                    ),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        return Response(sample, payload, response.headers.get("ETag"))


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in sorted({str(sample["label"]) for sample in samples}):
        group = [sample for sample in samples if sample["label"] == label]
        item: dict[str, Any] = {"n": len(group)}
        for metric in ("total_ms", "server_ms"):
            values = sorted(float(sample[metric]) for sample in group if sample[metric] is not None)
            if values:
                item[metric] = {
                    "p50": round(statistics.median(values), 2),
                    "p95": round(values[math.ceil(len(values) * 0.95) - 1], 2),
                    "max": round(max(values), 2),
                }
        result[label] = item
    return result


def run_build(
    root: Path,
    build: MetabBuild,
    log: Path,
    file_routes: list[Route],
    *,
    rounds: int,
    render_file: str | None,
    native_paths: bool = False,
) -> dict[str, Any]:
    inventory = [
        Route("navigation", "/api/tree?depth=0"),
        Route("tree", "/api/tree?depth=2"),
        Route("rollup", "/api/rollup?path=&depth=3"),
        Route("catalog", "/api/catalog"),
    ]
    cheap = Route("routes", "/api/routes")
    recent = Route("recent", "/api/recent?window=24h&limit=5000")
    inventory = [replace(route, native_paths=native_paths) for route in inventory]
    recent = replace(recent, native_paths=native_paths)
    file_routes = [replace(route, native_paths=native_paths) for route in file_routes]
    routes = [*file_routes, cheap, *inventory, recent]
    if render_file is not None:
        render_path = render_file if native_paths else canonical_inventory_path(render_file)
        routes.append(
            Route("render", "/api/kpress/render?path=" + urllib.parse.quote(render_path, safe=""))
        )
    result: dict[str, Any] = {"load_before": os.getloadavg()}
    phases: dict[str, list[dict[str, Any]]] = {}
    with Server(root, log, build, provider="python") as server:
        # Polling is intentionally outside measured phases. Main before the provider
        # refactor lacks provider-tagged walker logs; both builds expose index_status.
        deadline = time.monotonic() + SETTLE_TIMEOUT_S
        while True:
            settled = request(server.base_url, inventory[2]).payload
            if settled.get("index_status") == "done":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"inventory did not complete within {SETTLE_TIMEOUT_S} seconds")
            time.sleep(SETTLE_POLL_S)
        result["files_indexed"] = settled["indexed_files"]
        result["process_before"] = server.diagnostics()["process"]
        first = [request(server.base_url, route) for route in routes]
        phases["first"] = [response.sample for response in first]
        etags = {route.label: response.etag for route, response in zip(routes, first, strict=True)}
        for phase in ("warm", "revalidate"):
            samples: list[dict[str, Any]] = []
            for _ in range(rounds):
                for route in [*file_routes, cheap, *[r for r in routes if r.label == "render"]]:
                    etag = (
                        etags[route.label]
                        if phase == "revalidate" and route in file_routes
                        else None
                    )
                    if phase == "revalidate" and route in file_routes and etag is None:
                        raise ValueError(f"{route.label}: missing file ETag")
                    samples.append(request(server.base_url, route, etag=etag).sample)
                time.sleep(SERIAL_PAUSE_S)
            phases[phase] = samples
        for phase, extra in (("without_recent", []), ("with_recent", [recent])):
            burst = [*file_routes, cheap, *inventory, *extra]
            samples = []
            before = server.diagnostics()["process"]
            with ThreadPoolExecutor(max_workers=len(burst)) as pool:
                for _ in range(rounds):
                    barrier = threading.Barrier(len(burst))
                    futures = [
                        pool.submit(request, server.base_url, route, barrier=barrier)
                        for route in burst
                    ]
                    samples.extend(future.result().sample for future in futures)
                    time.sleep(BURST_PAUSE_S)
            phases[phase] = samples
            result[f"{phase}_process"] = {
                "before": before,
                "after": server.diagnostics()["process"],
            }
        result["process_after"] = server.diagnostics()["process"]
    result["load_after"] = os.getloadavg()
    result["phases"] = phases
    result["summary"] = {phase: summarize(samples) for phase, samples in phases.items()}
    return result


def validate_equivalence(runs: list[dict[str, Any]]) -> None:
    """Refuse timing claims when files, catalog or Recent selection changed."""

    expected: dict[str, tuple[Any, ...]] = {}
    if len({run["files_indexed"] for run in runs}) != 1:
        raise ValueError("response mismatch: indexed file populations differ")
    for run in runs:
        for samples in run["phases"].values():
            for sample in samples:
                if sample["status"] != 200:
                    continue
                label = sample["label"]
                if not (label.startswith("file:") or label in {"catalog", "recent"}):
                    continue
                signature = tuple(
                    sample.get(key)
                    for key in (
                        "content_sha256",
                        "kind",
                        "path",
                        "files",
                        "rows",
                        "matching",
                        "paths_sha256",
                    )
                )
                if label in expected and expected[label] != signature:
                    raise ValueError(
                        f"response mismatch for {label}; inspect samples before comparing timings"
                    )
                expected[label] = signature


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-metab", required=True)
    parser.add_argument("--candidate-metab", default="metab")
    parser.add_argument(
        "--baseline-paths",
        choices=("canonical", "native"),
        default="canonical",
        help="use native for main before the inventory path-contract refactor",
    )
    parser.add_argument("--file", action="append", required=True, dest="files")
    parser.add_argument("--render-file")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--json", type=Path, required=True, dest="output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    if not root.is_dir() or output.is_relative_to(root) or args.rounds < 1:
        parser.error(
            "use an existing root, positive rounds, and JSON output outside the served root"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    log_dir = output.with_suffix(".logs")
    log_dir.mkdir(exist_ok=True)
    os.environ["PYTHONHASHSEED"] = "0"
    builds = {
        "baseline": resolve_metab_build(str(args.baseline_metab)),
        "candidate": resolve_metab_build(str(args.candidate_metab)),
    }
    identities = {label: runtime_identity(build) for label, build in builds.items()}
    require_matching_runtimes(identities)
    files = cast("list[str]", args.files)
    result: dict[str, Any] = {
        "schema": 1,
        "method": "fresh ABBA; settled read-only root; gzip; 24h Recent; Python hash seed 0",
        "started_at": datetime.now(UTC).isoformat(),
        "host": {"platform": platform.platform(), "cpu_count": os.cpu_count()},
        "rounds": args.rounds,
        "baseline_paths": args.baseline_paths,
        "response_checks_passed": False,
        "builds": {
            label: {"version": build.version, "runtime": identities[label]}
            for label, build in builds.items()
        },
        "dependencies_match": identities["baseline"]["dependencies"]
        == identities["candidate"]["dependencies"],
        "runs": [],
    }
    if not result["dependencies_match"]:
        print(
            "WARNING: dependency versions differ; inspect builds.runtime.dependencies in the result",
            flush=True,
        )
    for index, label in enumerate(("baseline", "candidate", "candidate", "baseline")):
        print(f"Running {label} {index + 1}/4; load={os.getloadavg()}", flush=True)
        native_paths = label == "baseline" and args.baseline_paths == "native"
        file_routes = [
            Route(
                "file:" + path,
                "/api/file?path="
                + urllib.parse.quote(
                    path if native_paths else canonical_inventory_path(path), safe=""
                ),
            )
            for path in files
        ]
        run = run_build(
            root,
            builds[label],
            log_dir / f"{index}-{label}.log",
            file_routes,
            rounds=int(args.rounds),
            render_file=args.render_file,
            native_paths=native_paths,
        )
        result["runs"].append({"build": label, **run})
        atomic_write_text(output, json.dumps(result, indent=2) + "\n")
        validate_equivalence(result["runs"])
    result["response_checks_passed"] = True
    result["summary"] = {
        label: {
            phase: summarize(
                [
                    sample
                    for run in result["runs"]
                    if run["build"] == label
                    for sample in run["phases"][phase]
                ]
            )
            for phase in result["runs"][0]["phases"]
        }
        for label in builds
    }
    atomic_write_text(output, json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    print(f"Response checks passed. Results: {output}")


if __name__ == "__main__":
    main()
