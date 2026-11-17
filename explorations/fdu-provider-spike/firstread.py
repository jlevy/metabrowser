"""Server start to each route's first answer, with a socket-only readiness check.

``bench_serving.Server`` waits for ``/api/rollup`` to return 200 before handing the
server over, so any route timed after it inherits the rollup's readiness. Here the
server counts as listening once its socket accepts a connection; three threads then
poll one route each, independently, from that moment: the folder tree at depth 1 (a
native directory page, no tallies), the root summary at depth 0 (the same page plus
navigation tallies, a fallback), and the folder Overview rollup (a fallback). Each
records its first 200, every status it saw, and whether that answer carried tallies.
The server log's unhandled-exception count is recorded too.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

from bench import OUT, ensure_shim, host_record, summarize

from devtools import bench_serving

ROUTES = {
    "tree_depth1": "/api/tree?path=&depth=1",
    "tree_root_summary_depth0": "/api/tree?depth=0",
    "rollup_overview": f"/api/rollup?{bench_serving.OVERVIEW_QUERY}",
}
_BANNER = re.compile(r"http://(?P<host>[^:/]+):(?P<port>\d+)/view/")
_DEADLINE_S = 300.0


def _poll(base: str, route: str, started: float, out: dict[str, Any]) -> None:
    statuses: Counter[int] = Counter()
    while time.monotonic() - started < _DEADLINE_S:
        status, _etag, body, _elapsed = bench_serving._http(f"{base}{route}", timeout=120)
        statuses[status] += 1
        if status == 200:
            payload = cast("dict[str, Any]", json.loads(body))
            if route.startswith("/api/tree") and not payload.get("tree") and "depth=1" in route:
                continue
            out["first_answer_s"] = round(time.monotonic() - started, 3)
            out["tally_cache_status"] = payload.get("tally_cache_status")
            out["carries_tallies"] = payload.get("summary") is not None
            out["index_status"] = payload.get("index_status")
            break
        time.sleep(0.01)
    out["statuses"] = {str(code): count for code, count in sorted(statuses.items())}


def run_once(corpus: Path, provider: str, log_dir: Path) -> dict[str, Any]:
    shim = ensure_shim()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = log_dir / f"firstread-{provider}-{int(time.time() * 1000)}.log"
    environment = {
        **os.environ,
        "METABROWSER_INVENTORY_PROVIDER": provider,
        "METABROWSER_LOG_LEVEL": "DEBUG",
    }
    started = time.monotonic()
    with log.open("wb") as handle:
        process = subprocess.Popen(
            [str(shim), str(corpus), "--no-open", "--port", str(port)],
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=environment,
        )
    record: dict[str, Any] = {"provider": provider}
    try:
        host, bound = "127.0.0.1", port
        while time.monotonic() - started < 60:
            match = _BANNER.search(log.read_text(errors="replace"))
            if match:
                host, bound = match["host"], int(match["port"])
                break
            time.sleep(0.01)
        while time.monotonic() - started < 60:
            with socket.socket() as connection:
                connection.settimeout(0.2)
                if connection.connect_ex((host, bound)) == 0:
                    break
            time.sleep(0.005)
        record["listening_s"] = round(time.monotonic() - started, 3)
        base = f"http://{host}:{bound}"
        results: dict[str, dict[str, Any]] = {name: {} for name in ROUTES}
        threads = [
            threading.Thread(target=_poll, args=(base, route, started, results[name]))
            for name, route in ROUTES.items()
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        record["routes"] = results
        deadline = time.monotonic() + 60
        walk = None
        while walk is None and time.monotonic() < deadline:
            walk = bench_serving._WALK_DONE_RE.search(log.read_text(errors="replace"))
            time.sleep(0.05)
        record["walk_ms"] = int(walk["ms"]) if walk else None
        record["walk_files"] = int(walk["files"]) if walk else None
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    text = log.read_text(errors="replace")
    record["asgi_exceptions"] = text.count("Exception in ASGI application")
    record["version_unavailable_in_log"] = text.count("VersionUnavailableError")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for trial in range(args.trials):
        for provider in ("python", "fdu") if trial % 2 == 0 else ("fdu", "python"):
            runs.append({"trial": trial, **run_once(args.corpus.resolve(), provider, log_dir)})
    summary: dict[str, Any] = {}
    for provider in ("python", "fdu"):
        mine = [run for run in runs if run["provider"] == provider]
        summary[provider] = {
            "listening_s": summarize([run["listening_s"] for run in mine]),
            "walk_ms": summarize([run["walk_ms"] for run in mine if run["walk_ms"] is not None]),
            "asgi_exceptions": [run["asgi_exceptions"] for run in mine],
            **{
                name: {
                    "first_answer_s": summarize(
                        [
                            run["routes"][name]["first_answer_s"]
                            for run in mine
                            if "first_answer_s" in run["routes"][name]
                        ]
                    ),
                    "carries_tallies": sorted(
                        {str(run["routes"][name].get("carries_tallies")) for run in mine}
                    ),
                    "non_200_statuses": sum(
                        count
                        for run in mine
                        for code, count in run["routes"][name]["statuses"].items()
                        if code != "200"
                    ),
                }
                for name in ROUTES
            },
        }
    out = OUT / f"firstread-{args.label}.json"
    out.write_text(
        json.dumps(
            {"host": host_record(), "corpus": args.label, "runs": runs, "summary": summary},
            indent=1,
        )
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
