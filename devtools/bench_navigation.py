"""Compare settled HTTP navigation on one existing tree, without a browser.

Runs fresh baseline/candidate/candidate/baseline processes. Measures file reads,
validators, and concurrent inventory requests with and without Recent. Output includes
raw samples, response checks, runtimes, dependency versions and host/process load.
The root is read-only; put output and logs outside it. See docs/development.md,
"Comparing File Navigation Without a Browser".

Install both checkouts with their committed locks and the same explicit Python
interpreter, patch release and free-threading mode included::

    uv --config-file "$BASELINE/uv.toml" sync --project "$BASELINE" \
      --python "$PWD/.venv/bin/python" --all-extras --all-groups --locked
    uv --config-file uv.toml run --frozen python -m devtools.bench_navigation \
      --root . --baseline-metab "$BASELINE/.venv/bin/metab" \
      --file docs/engine-performance-model.md \
      --file tests/test_active_tracker_event_loop_stall.py \
      --render-file docs/engine-performance-model.md \
      --rounds 20 --json "$RESULTS/navigation-comparison.json"

``$BASELINE`` is an independently checked-out baseline, ``$RESULTS`` a directory
outside the served tree for the JSON and its ``.logs``, and file arguments name paths
relative to the served root; ``--baseline-paths native`` is for a baseline from before
canonical path identities. The tool refuses mismatched Python builds or GIL modes, and
records dependency versions, source hashes, host load, process CPU and RSS, and raw and
summarized latencies; weigh a dependency difference it reports before attributing a
result to code. Leave the tree unchanged and pause tests, installs, and other benchmarks
during the run. It reports success only when status, indexed population, text content,
kind and path, catalog membership and extensions, and Recent membership and counts
agree: a file ageing out of the Recent window, or a Recent population above the
provider's display cap, fails the comparison. Finish in a browser for rendering and
interaction costs HTTP cannot see.
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
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, cast

from strif import atomic_write_text

from devtools.bench_serving import (
    MetabBuild,
    Server,
    resolve_metab_build,
    split_console_launcher,
)
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
    """Require a uv-installed POSIX console script, and probe the interpreter it runs under."""

    parts = split_console_launcher(build.executable.read_bytes())
    if parts is None:
        raise ValueError("benchmark requires a uv-installed metab console script")
    interpreter, _body = parts
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
    compare_fields: tuple[str, ...] = ()
    expect: dict[str, Any] = field(default_factory=dict)
    revalidate: bool = False


def load_api_cases(path: Path) -> list[Route]:
    """Load named GET cases with explicit JSON fields and expected values."""

    cases: object = json.loads(path.read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError("API cases must be a nonempty JSON array")
    routes: list[Route] = []
    labels: set[str] = set()
    for case in cast("list[object]", cases):
        if not isinstance(case, dict):
            raise ValueError("each API case must be an object")
        data = cast("dict[str, Any]", case)
        label = data.get("name")
        url = data.get("path")
        fields = data.get("compare")
        expect = data.get("expect", {})
        revalidate = data.get("revalidate", False)
        if not isinstance(label, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", label):
            raise ValueError("API case names use letters, digits, underscores and hyphens")
        if label in labels:
            raise ValueError(f"duplicate API case name: {label}")
        if (
            not isinstance(url, str)
            or not url.startswith("/api/")
            or "#" in url
            or "\\" in url
            or any(ord(char) <= 32 or ord(char) == 127 for char in url)
        ):
            raise ValueError(f"{label}: expected a local /api/ request path")
        if (
            not isinstance(fields, list)
            or not fields
            or not all(isinstance(name, str) and name for name in cast("list[object]", fields))
        ):
            raise ValueError(f"{label}: compare must name one or more JSON fields")
        if not isinstance(expect, dict) or not isinstance(revalidate, bool):
            raise ValueError(f"{label}: invalid expect or revalidate")
        labels.add(label)
        routes.append(
            Route(
                "api:" + label,
                url,
                compare_fields=tuple(cast("list[str]", fields)),
                expect=cast("dict[str, Any]", expect),
                revalidate=revalidate,
            )
        )
    return routes


def _api_fields(payload: object, names: tuple[str, ...], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in names:
        value = payload
        for key in name.split("."):
            if not isinstance(value, dict) or key not in cast("dict[str, object]", value):
                raise ValueError(f"{label}: missing response field {name}")
            value = cast("dict[str, object]", value)[key]
        result[name] = value
    return result


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
        timing = response.headers.get("Server-Timing", "")
        server = re.search(r"srv;dur=([\d.]+)", timing)
        body = gzip.decompress(wire) if response.headers.get("Content-Encoding") == "gzip" else wire
        payload = cast("dict[str, Any]", json.loads(body)) if body else {}
        sample: dict[str, Any] = {
            "label": route.label,
            "status": response.status,
            "total_ms": total_ms,
            "first_byte_ms": first_ms,
            "server_ms": float(server[1]) if server else None,
            "wire_bytes": len(wire),
            "server_timing": timing or None,
        }
        expected = 304 if etag is not None else 200
        if response.status != expected or (expected == 304 and body):
            raise ValueError(f"{route.label}: expected {expected} with valid body, got {sample}")
        if route.compare_fields and expected == 200:
            checked = _api_fields(payload, tuple(route.expect), route.label)
            if checked != route.expect:
                raise ValueError(f"{route.label}: response did not match expect")
            compared = _api_fields(payload, route.compare_fields, route.label)
            sample["content_sha256"] = hashlib.sha256(
                json.dumps(compared, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
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
        for metric in ("total_ms", "first_byte_ms", "server_ms", "wire_bytes"):
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
    api_routes: tuple[Route, ...] = (),
    prepare_api: frozenset[str] = frozenset(),
    cache_seed: Path | None = None,
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
    routes = [*file_routes, cheap, *inventory, recent, *api_routes]
    if render_file is not None:
        render_path = render_file if native_paths else canonical_inventory_path(render_file)
        routes.append(
            Route("render", "/api/kpress/render?path=" + urllib.parse.quote(render_path, safe=""))
        )
    result: dict[str, Any] = {"load_before": os.getloadavg()}
    phases: dict[str, list[dict[str, Any]]] = {}
    state_root = Path(tempfile.mkdtemp(prefix=f"{log.stem}-state-", dir=log.parent))
    result["event_log"] = str(state_root / "state" / "events")
    if cache_seed is not None:
        shutil.copytree(cache_seed, state_root / "cache")
    start = time.perf_counter()
    with Server(root, log, build, provider="python", state_root=state_root) as server:
        result["http_ready_ms"] = (time.perf_counter() - start) * 1000
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
        result["inventory_ready_ms"] = (time.perf_counter() - start) * 1000
        result["files_indexed"] = settled["indexed_files"]
        result["process_before"] = server.diagnostics()["process"]
        if prepare_api:
            prepare_start = time.perf_counter()
            phases["startup_preparation"] = [
                request(server.base_url, route).sample
                for route in api_routes
                if route.label in prepare_api
            ]
            result["startup_preparation_ms"] = (time.perf_counter() - prepare_start) * 1000
        first = [request(server.base_url, route) for route in routes]
        phases["first"] = [response.sample for response in first]
        etags = {route.label: response.etag for route, response in zip(routes, first, strict=True)}
        for phase in ("warm", "revalidate"):
            samples: list[dict[str, Any]] = []
            for _ in range(rounds):
                for route in [
                    *file_routes,
                    cheap,
                    *[r for r in routes if r.label == "render"],
                    *api_routes,
                ]:
                    conditional = phase == "revalidate" and (
                        route in file_routes or route.revalidate
                    )
                    etag = etags[route.label] if conditional else None
                    if conditional and etag is None:
                        raise ValueError(f"{route.label}: missing ETag")
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
                if not (label.startswith(("file:", "api:")) or label in {"catalog", "recent"}):
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
    parser.add_argument("--baseline-metab", help="omit for a single-build survey")
    parser.add_argument("--candidate-metab", default="metab")
    parser.add_argument(
        "--baseline-paths",
        choices=("canonical", "native"),
        default="canonical",
        help="use native for main before the inventory path-contract refactor",
    )
    parser.add_argument("--file", action="append", default=[], dest="files")
    parser.add_argument("--api-cases", type=Path, help="JSON cases for golden-backed GET routes")
    parser.add_argument(
        "--prepare-api",
        action="append",
        default=[],
        metavar="NAME",
        help="issue this API case during a separate startup preparation phase",
    )
    parser.add_argument("--cache-seed", type=Path, help="copy one prepared cache into each server")
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
    if not (args.files or args.api_cases):
        parser.error("supply --file or --api-cases")
    try:
        api_routes = tuple(load_api_cases(args.api_cases)) if args.api_cases else ()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    prepare_api = frozenset("api:" + name for name in cast("list[str]", args.prepare_api))
    if prepare_api - {route.label for route in api_routes}:
        parser.error("--prepare-api names a case absent from --api-cases")
    cache_seed = args.cache_seed.resolve() if args.cache_seed else None
    if cache_seed is not None and (not cache_seed.is_dir() or log_dir.is_relative_to(cache_seed)):
        parser.error(
            "--cache-seed must be an existing cache outside the output log directory’s ancestry"
        )
    builds = {"candidate": resolve_metab_build(str(args.candidate_metab))}
    order = ("candidate",)
    if args.baseline_metab:
        builds["baseline"] = resolve_metab_build(str(args.baseline_metab))
        order = ("baseline", "candidate", "candidate", "baseline")
    identities = {label: runtime_identity(build) for label, build in builds.items()}
    if args.baseline_metab:
        require_matching_runtimes(identities)
    files = cast("list[str]", args.files)
    result: dict[str, Any] = {
        "schema": 1,
        "method": "settled read-only root; gzip; 24h Recent; Python hash seed 0",
        "order": order,
        "seeded_cache": cache_seed is not None,
        "started_at": datetime.now(UTC).isoformat(),
        "host": {"platform": platform.platform(), "cpu_count": os.cpu_count()},
        "rounds": args.rounds,
        "baseline_paths": args.baseline_paths,
        "response_checks_passed": False,
        "builds": {
            label: {"version": build.version, "runtime": identities[label]}
            for label, build in builds.items()
        },
        "dependencies_match": (
            identities["baseline"]["dependencies"] == identities["candidate"]["dependencies"]
            if args.baseline_metab
            else None
        ),
        "runs": [],
    }
    if result["dependencies_match"] is False:
        print(
            "WARNING: dependency versions differ; inspect builds.runtime.dependencies in the result",
            flush=True,
        )
    for index, label in enumerate(order):
        print(f"Running {label} {index + 1}/{len(order)}; load={os.getloadavg()}", flush=True)
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
            api_routes=api_routes,
            prepare_api=prepare_api,
            cache_seed=cache_seed,
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
