"""Paired Python-versus-fdu serving measurements through the real `metab` server path.

Three modes, all interleaved with an A/A arm for each provider:

* ``synthetic`` runs ``devtools/bench_serving.py`` unchanged on its 100k-file corpus. The
  only spike-specific inputs are ``fdu`` added to its provider list in this process and
  ``--metab`` pointing at a launcher shim that both providers run through.
* ``tree`` measures an existing tree with bench_serving's ``Server`` and ``_http``:
  first useful read, settled, per-route latency at fresh versions, mutation to SSE
  latency, and sampled RSS and CPU.
* ``floor`` times each engine alone in a fresh process: fdu's opened root from open to
  settled, and the Python reference store from open to settled.

Raw results go to the gitignored ``.bench/fdu-spike/`` (bench output is machine-local
and recreated by rerunning); ``run.py`` normalizes the summaries into ``evidence/``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / ".bench" / "fdu-spike"
sys.path.insert(0, str(REPO))

from devtools import bench_serving  # noqa: E402

from metabrowser import smoke_probes  # noqa: E402

ARMS: tuple[tuple[str, str], ...] = (("python", "A"), ("fdu", "A"), ("python", "B"), ("fdu", "B"))


def host_record() -> dict[str, Any]:
    load = os.getloadavg()
    meminfo = Path("/proc/meminfo").read_text().splitlines()[0]
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "memory": meminfo,
        "python": platform.python_version(),
        "load_1_5_15": [round(value, 2) for value in load],
        "virtualized": Path("/sys/hypervisor").exists() or "vm" in platform.node(),
    }


def ensure_shim() -> Path:
    """An executable `metab` for bench_serving that runs `launcher.py` in this interpreter."""

    OUT.mkdir(parents=True, exist_ok=True)
    shim = OUT / "metab-spike"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "import launcher\n"
        "raise SystemExit(launcher.main())\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def rotated(trial: int) -> list[tuple[str, str]]:
    start = trial % len(ARMS)
    return list(ARMS[start:] + ARMS[:start])


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return round(ordered[index], 2)


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50": _percentile(values, 0.5),
        "p95": _percentile(values, 0.95),
        "min": round(min(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
    }


# ── Synthetic corpus via bench_serving ─────────────────────────────


def run_synthetic(trials: int, files: int, label: str) -> Path:
    shim = ensure_shim()
    bench_serving.INVENTORY_PROVIDERS = ("python", "fdu")  # type: ignore[misc]
    runs: list[dict[str, Any]] = []
    record_path = OUT / f"{label}.json"
    for trial in range(trials):
        for provider, arm in rotated(trial):
            out = OUT / f"{label}-t{trial}-{provider}-{arm}.json"
            started = time.time()
            code = bench_serving.main(
                [
                    "--files",
                    str(files),
                    "--provider",
                    provider,
                    "--metab",
                    str(shim),
                    "--label",
                    f"{provider}-{arm}-t{trial}",
                    "--json",
                    str(out),
                ]
            )
            runs.append(
                {
                    "trial": trial,
                    "provider": provider,
                    "arm": arm,
                    "exit": code,
                    "wall_s": round(time.time() - started, 1),
                    "result": json.loads(out.read_text()) if out.exists() else None,
                }
            )
            record_path.write_text(
                json.dumps({"host": host_record(), "files": files, "runs": runs}, indent=1)
            )
    return record_path


# ── Real trees ──────────────────────────────────────────────────────


class _Sampler:
    """Sample the server's RSS and CPU every quarter second, for a peak."""

    def __init__(self, server: Any) -> None:
        self._server = server
        self._stop = threading.Event()
        self.samples: list[tuple[float, int | None, float | None]] = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _Sampler:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(2)

    def _run(self) -> None:
        started = time.monotonic()
        while not self._stop.wait(0.25):
            sample = self._server._sample_process_resources()
            self.samples.append(
                (round(time.monotonic() - started, 2), sample["rss_kb"], sample["cpu_seconds"])
            )

    @property
    def peak_rss_kb(self) -> int | None:
        values = [rss for _t, rss, _cpu in self.samples if rss is not None]
        return max(values) if values else None


def _json(url: str) -> tuple[int, Any, float, str | None]:
    status, etag, body, elapsed = bench_serving._http(url)
    payload: Any = None
    if status == 200 and body:
        with contextlib.suppress(ValueError):
            payload = json.loads(body)
    return status, payload, elapsed, etag


def _routes(subpath: str | None) -> dict[str, str]:
    routes = {
        "navigation": "/api/tree?depth=0",
        "tree_root_depth1": "/api/tree?path=&depth=1",
        "tree_root_depth2": "/api/tree?path=&depth=2",
        "tree_filtered_md": "/api/tree?path=&depth=3&types=.md",
        "tree_grouped_type": "/api/tree?path=&depth=2&group_by=type",
        "rollup_overview": f"/api/rollup?{bench_serving.OVERVIEW_QUERY}",
        "rollup_treemap": f"/api/rollup?{bench_serving.TREEMAP_QUERY}",
        "recent": "/api/recent",
        "catalog": "/api/catalog",
    }
    if subpath:
        routes["tree_subpath_depth2"] = f"/api/tree?path={subpath}&depth=2"
    return routes


class _SseWatch:
    """One persistent /api/events connection that timestamps every record."""

    def __init__(self, base: str) -> None:
        host, port = base.removeprefix("http://").split(":")
        self._host, self._port = host, int(port)
        self.records: list[tuple[float, str]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _SseWatch:
        self._thread.start()
        time.sleep(1.0)
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(3)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                for raw in smoke_probes._read_sse_events(
                    self._host, self._port, "/api/events?scope=root-depth-2", "0", 3600.0
                ):
                    with self._lock:
                        self.records.append((time.monotonic(), raw))
                    if self._stop.is_set():
                        return
            except (OSError, RuntimeError):
                time.sleep(0.2)

    def wait_for(self, token: str, since: float, timeout: float = 15.0) -> float | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for stamp, raw in self.records:
                    if stamp >= since and token in raw:
                        return stamp
            time.sleep(0.005)
        return None


def _first_subdir(base: str) -> str | None:
    status, payload, _elapsed, _etag = _json(f"{base}/api/tree?path=&depth=1")
    if status != 200 or not isinstance(payload, dict):
        return None
    nodes = cast("list[dict[str, Any]]", payload.get("nodes") or payload.get("children") or [])
    dirs = [node for node in nodes if node.get("type") == "dir" and not node.get("gitignored")]
    if not dirs:
        dirs = [node for node in nodes if node.get("type") == "dir"]
    if not dirs:
        return None
    best = max(dirs, key=lambda node: node.get("total_files") or 0)
    return cast("str", best.get("path"))


def tree_trial(corpus: Path, provider: str, log_dir: Path, rounds: int) -> dict[str, Any]:
    shim = ensure_shim()
    build = bench_serving.resolve_metab_build(str(shim))
    marker_dir = corpus
    log = log_dir / f"tree-{provider}-{int(time.time() * 1000)}.log"
    started = time.monotonic()
    result: dict[str, Any] = {"provider": provider}
    with bench_serving.Server(corpus, log, build, provider=provider) as server, _Sampler(
        server
    ) as sampler:
        base = server.base_url
        result["listening_s"] = round(time.monotonic() - started, 3)
        first_useful: float | None = None
        first_count: float | None = None
        settled: float | None = None
        polls = 0
        while time.monotonic() - started < bench_serving.SCAN_TIMEOUT_S:
            polls += 1
            status, payload, _elapsed, _etag = _json(f"{base}/api/tree?path=&depth=1")
            if first_useful is None and status == 200 and isinstance(payload, dict):
                if payload.get("nodes") or payload.get("children"):
                    first_useful = time.monotonic() - started
            status, rollup, _elapsed, _etag = _json(f"{base}/api/rollup?{bench_serving.OVERVIEW_QUERY}")
            if status == 200 and isinstance(rollup, dict):
                node = cast("dict[str, Any]", rollup.get("node") or {})
                if first_count is None and node.get("total_files"):
                    first_count = time.monotonic() - started
                if rollup.get("index_status") in ("done", "truncated"):
                    settled = time.monotonic() - started
                    break
            time.sleep(0.02)
        walk = server.await_walk(timeout_s=30)
        result.update(
            {
                "first_useful_read_s": round(first_useful, 3) if first_useful else None,
                "first_count_s": round(first_count, 3) if first_count else None,
                "settled_s": round(settled, 3) if settled else None,
                "startup_polls": polls,
                "walk": walk,
            }
        )
        time.sleep(1.0)
        settled_sample = server._sample_process_resources()
        result["settled_rss_kb"] = settled_sample["rss_kb"]
        result["settled_cpu_s"] = settled_sample["cpu_seconds"]
        subpath = _first_subdir(base)
        result["subpath"] = subpath
        routes = _routes(subpath)
        fresh: dict[str, list[float]] = {name: [] for name in routes}
        retained: dict[str, list[float]] = {name: [] for name in routes}
        statuses: dict[str, list[int]] = {name: [] for name in routes}
        live: list[float] = []
        missed = 0
        with _SseWatch(base) as sse:
            for round_index in range(rounds):
                token = f"fdu-spike-live-{provider}-{round_index}-{int(time.time() * 1000)}"
                marker = marker_dir / f"{token}.tmp"
                written = time.monotonic()
                marker.write_text(token, encoding="utf-8")
                seen = sse.wait_for(token, written)
                if seen is None:
                    missed += 1
                else:
                    live.append((seen - written) * 1000)
                for name, route in routes.items():
                    status, _payload, elapsed, _etag = _json(f"{base}{route}")
                    statuses[name].append(status)
                    if status == 200:
                        fresh[name].append(elapsed)
                    status, _payload, elapsed, _etag = _json(f"{base}{route}")
                    if status == 200:
                        retained[name].append(elapsed)
                marker.unlink(missing_ok=True)
                time.sleep(0.3)
        result["live_change_ms"] = summarize(live)
        result["live_change_missed"] = missed
        result["fresh_route_ms"] = {name: summarize(values) for name, values in fresh.items()}
        result["retained_route_ms"] = {name: summarize(values) for name, values in retained.items()}
        result["route_statuses"] = {
            name: sorted(set(values)) for name, values in statuses.items()
        }
        final = server.diagnostics()
        result["final_rss_kb"] = final["process"]["rss_kb"]
        result["final_cpu_s"] = final["process"]["cpu_seconds"]
        result["peak_rss_kb_sampled"] = sampler.peak_rss_kb
        result["provider_reported"] = final.get("provider")
        result["diagnostics"] = {
            key: final.get(key)
            for key in ("provider", "contract", "files_indexed", "directories_indexed", "watch_state")
        }
    return result


def run_tree(corpus: Path, trials: int, label: str, rounds: int) -> Path:
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    record_path = OUT / f"{label}.json"
    for trial in range(trials):
        for provider, arm in rotated(trial):
            started = time.time()
            try:
                trial_result = tree_trial(corpus, provider, log_dir, rounds)
            except (SystemExit, OSError, RuntimeError) as error:
                trial_result = {"provider": provider, "error": str(error)}
            runs.append(
                {
                    "trial": trial,
                    "provider": provider,
                    "arm": arm,
                    "wall_s": round(time.time() - started, 1),
                    "result": trial_result,
                }
            )
            record_path.write_text(
                json.dumps(
                    {"host": host_record(), "corpus": label, "rounds": rounds, "runs": runs},
                    indent=1,
                )
            )
    return record_path


# ── Engine floor ────────────────────────────────────────────────────

_FLOOR_SCRIPT = r"""
import asyncio, json, resource, sys, time
sys.path.insert(0, sys.argv[3])
from pathlib import Path
root = Path(sys.argv[2]).resolve()
which = sys.argv[1]
from metabrowser.inventory_engine.runtime import default_inventory_config
from dataclasses import replace
config = replace(default_inventory_config(), watch_mode="off")
cpu0 = time.process_time(); wall0 = time.monotonic()
if which == "fdu-opened":
    from fdu import opened as fdu
    from adapter import downlevel_registry
    from probe import AdapterProbe
    options = fdu.OpenedOptions(prune_hidden=True, hidden_allow=config.hidden_allowlist,
        exclude_special=True, max_files=config.budget.max_files, observe=False,
        type_rules=downlevel_registry(config.registry_document, AdapterProbe()))
    index = fdu.OpenedIndex.open(root, options)
    while index.state().state.phase is fdu.LifecyclePhase.DISCOVERING:
        time.sleep(0.002)
    state = index.state().state
    files = state.progress.files_retained
    entries = index.read(fdu.Diagnostics()).results[0].value.entries
    index.close()
elif which == "python-store":
    from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend
    from metabrowser.inventory_engine.contract import ReadRequest, LifecyclePhase
    async def go():
        handle = await PythonInventoryBackend().open(root, config)
        while True:
            r = await handle.read(ReadRequest())
            if r.state.phase is not LifecyclePhase.DISCOVERING:
                break
            await asyncio.sleep(0.002)
        files = handle._files_indexed
        entries = len(handle._entries)
        await handle.close()
        return files, entries
    files, entries = asyncio.run(go())
wall = time.monotonic() - wall0; cpu = time.process_time() - cpu0
print(json.dumps({"engine": which, "wall_s": round(wall, 4), "cpu_s": round(cpu, 4),
    "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "files": files,
    "entries": entries}))
"""


def run_floor(corpus: Path, trials: int, label: str) -> Path:
    runs: list[dict[str, Any]] = []
    record_path = OUT / f"{label}.json"
    OUT.mkdir(parents=True, exist_ok=True)
    engines = ("fdu-opened", "python-store")
    for trial in range(trials):
        order = engines if trial % 2 == 0 else tuple(reversed(engines))
        for engine in order:
            completed = subprocess.run(
                [sys.executable, "-c", _FLOOR_SCRIPT, engine, str(corpus), str(HERE)],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO,
            )
            line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
            try:
                record = json.loads(line)
            except ValueError:
                record = {"engine": engine, "error": completed.stderr[-800:]}
            runs.append({"trial": trial, **record})
            record_path.write_text(
                json.dumps({"host": host_record(), "corpus": label, "runs": runs}, indent=1)
            )
    return record_path


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    synthetic = sub.add_parser("synthetic")
    synthetic.add_argument("--trials", type=int, default=3)
    synthetic.add_argument("--files", type=int, default=100_000)
    synthetic.add_argument("--label", default="synthetic-100000")
    tree = sub.add_parser("tree")
    tree.add_argument("--corpus", type=Path, required=True)
    tree.add_argument("--trials", type=int, default=3)
    tree.add_argument("--rounds", type=int, default=10)
    tree.add_argument("--label", required=True)
    floor = sub.add_parser("floor")
    floor.add_argument("--corpus", type=Path, required=True)
    floor.add_argument("--trials", type=int, default=5)
    floor.add_argument("--label", required=True)
    args = parser.parse_args()
    if args.mode == "synthetic":
        path = run_synthetic(args.trials, args.files, args.label)
    elif args.mode == "tree":
        path = run_tree(args.corpus.resolve(), args.trials, args.label, args.rounds)
    else:
        path = run_floor(args.corpus.resolve(), args.trials, args.label)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
