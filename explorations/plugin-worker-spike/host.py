"""Spike: the host half of an out-of-process sidekick worker.

Runs with the host Metabrowser's interpreter, spawns ``worker.py`` with a plugin
environment's interpreter, and measures what the plugin-sources plan depends on. See
``README.md`` beside this file for the command and the recorded results.

Usage: host.py ENV_PYTHON ROOT PROCESS_SPEC FIXTURE_DIR OUT_JSON
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import threading
import time
import tomllib
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import metabrowser
from metabrowser.plugin_loader.manifest import load_manifest

WORKER = Path(__file__).with_name("worker.py")
Header = dict[str, Any]
Frame = tuple[Header, bytes]


class Worker:
    """One worker process and the request multiplexing over its pipes."""

    def __init__(self, python: str, root: str, stderr_log: Path) -> None:
        env = {
            "HOME": os.environ["HOME"],
            "PATH": "/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        self.started = time.perf_counter()
        self._stderr = stderr_log.open("wb")
        self.proc = subprocess.Popen(
            [python, "-I", "-B", str(WORKER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            cwd=root,
            env=env,
        )
        self._next = 0
        self._pending: dict[int, Future[Frame]] = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        stdout = self.proc.stdout
        if stdout is None:
            return
        while line := stdout.readline():
            header: Header = json.loads(line)
            size = int(header.get("body_len", 0))
            body = stdout.read(size) if size else b""
            self._pending.pop(int(header["id"])).set_result((header, body))

    def request(self, op: str, body: bytes = b"", **fields: Any) -> Future[Frame]:
        stdin = self.proc.stdin
        if stdin is None:
            raise RuntimeError("worker stdin is closed")
        with self._lock:
            self._next += 1
            future: Future[Frame] = Future()
            self._pending[self._next] = future
            header = {"id": self._next, "op": op, **fields, "body_len": len(body)}
            stdin.write(json.dumps(header).encode() + b"\n" + body)
            stdin.flush()
        return future

    def call(self, op: str, body: bytes = b"", **fields: Any) -> Frame:
        header, out = self.request(op, body, **fields).result(timeout=120)
        if not header.get("ok"):
            raise RuntimeError(str(header.get("error")))
        return header, out

    def rss_mb(self) -> float:
        ps = ["ps", "-o", "rss=", "-p", str(self.proc.pid)]
        out = subprocess.run(ps, capture_output=True, text=True, check=True)
        return int(out.stdout.strip()) / 1024

    def close(self) -> Header:
        stdin = self.proc.stdin
        started = time.perf_counter()
        if stdin is not None:
            stdin.close()
        code = self.proc.wait(timeout=10)
        self._stderr.close()
        return {"code": code, "ms": (time.perf_counter() - started) * 1000}


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def synthetic_pool_log(lines: int) -> list[str]:
    """A log in the motivating plugin's pool format: one start event, then a mix."""
    start = {"event": "pool_start", "pool_id": "p", "backend": "local", "max_concurrency": 8}
    out = [json.dumps({**start, "ts": "2026-11-12T00:00:00Z"})]
    kinds = ("process_start", "process_exit", "pressure_check")
    for i in range(1, lines):
        event = {
            "event": kinds[i % 3],
            "label": f"item-{i}",
            "pid": 1000 + i,
            "exit_code": 0,
            "elapsed_s": 1.5,
            "level": "ok",
            "available_pct": 60,
            "ts": "2026-11-12T00:00:01Z",
        }
        out.append(json.dumps(event))
    return out


def main() -> None:
    env_python, root, spec_path, fixture_dir, out_json = sys.argv[1:6]
    result: Header = {"host_metabrowser": metabrowser.__version__}
    worker = Worker(env_python, root, Path(out_json).with_suffix(".stderr.log"))

    hello, _ = worker.call("hello")
    result["spawn_to_hello_ms"] = (time.perf_counter() - worker.started) * 1000
    result["hello"] = {k: hello[k] for k in ("protocol", "python", "metabrowser_in_env")}

    started = time.perf_counter()
    listing, _ = worker.call("list")
    result["list_ms"] = (time.perf_counter() - started) * 1000
    result["plugins"] = [(p["entry_point"], p["dist_version"]) for p in listing["plugins"]]
    result["adapters"] = listing["adapters"]
    result["list_errors"] = listing["errors"]
    result["rss_after_list_mb"] = worker.rss_mb()

    # The host reads every manifest with its own schema and SDK gate. The spike then
    # reads the hooks from the raw TOML, so the proxy can be measured past that gate.
    hooks: dict[tuple[str, str], str] = {}
    verdicts: Header = {}
    for plugin in listing["plugins"]:
        manifest_path = Path(plugin["dir"]) / "manifest.toml"
        try:
            load_manifest(manifest_path)
            verdicts[plugin["entry_point"]] = "accepted"
        except ValueError as exc:
            verdicts[plugin["entry_point"]] = str(exc).splitlines()[-1].strip()
        raw = tomllib.loads(manifest_path.read_text())
        for declared in raw.get("data_hook", []):
            hooks[(raw["plugin"]["name"], declared["route"])] = declared["sidekick"]
    result["host_manifest_verdicts"] = verdicts
    plugin_name = next(name for name, route in hooks if route == "viz-model")
    worker.call("set_root", root=root)

    def hook(route: str, query: str = "") -> tuple[Header, bytes, float]:
        started = time.perf_counter()
        header, body = worker.call(
            "call",
            sidekick=hooks[(plugin_name, route)],
            path=f"/api/plugin/{plugin_name}/{route}",
            query=query,
            method="GET",
        )
        return header, body, (time.perf_counter() - started) * 1000

    first, _, first_ms = hook("info")
    result["info_first_call_ms"] = first_ms
    result["info_status"] = first["status"]
    rtts: list[float] = []
    overheads: list[float] = []
    for _ in range(300):
        header, _, ms = hook("info")
        rtts.append(ms)
        overheads.append(ms - float(header["handler_ms"]))
    result["info_rtt_ms"] = {
        "p50": statistics.median(rtts),
        "p95": percentile(rtts, 0.95),
        "max": max(rtts),
    }
    result["info_ipc_overhead_ms_p50"] = statistics.median(overheads)

    # One large response, with small calls issued beside it.
    started = time.perf_counter()
    slow = worker.request(
        "call",
        sidekick=hooks[(plugin_name, "viz-model")],
        path=f"/api/plugin/{plugin_name}/viz-model",
        query=f"process={spec_path}",
        method="GET",
    )
    beside: list[float] = []
    while not slow.done():
        beside.append(hook("info")[2])
        time.sleep(0.02)
    viz_header, viz_body = slow.result()
    viz_total = (time.perf_counter() - started) * 1000
    viz: Header = {
        "ok": viz_header.get("ok"),
        "status": viz_header.get("status"),
        "error": viz_header.get("error"),
        "handler_ms": viz_header.get("handler_ms"),
        "total_ms": viz_total,
        "bytes": len(viz_body),
        "info_calls_beside": len(beside),
        "info_beside_p50_ms": statistics.median(beside) if beside else None,
        "info_beside_max_ms": max(beside) if beside else None,
    }
    if viz_header.get("ok"):
        viz["ipc_overhead_ms"] = viz_total - float(viz_header["handler_ms"])
    result["viz_model"] = viz
    result["rss_after_viz_mb"] = worker.rss_mb()

    detections: Header = {}
    for name in ("pool.jsonl", "process.jsonl"):
        lines = Path(fixture_dir, name).read_text().splitlines()[:20]
        started = time.perf_counter()
        detected, _ = worker.call("detect", lines=lines)
        elapsed = (time.perf_counter() - started) * 1000
        detections[name] = {"adapter": detected["adapter"], "ms": elapsed}
    result["detect"] = detections

    events = synthetic_pool_log(100_000)
    adapter = next(a for a in listing["adapters"] if a != "process")
    batch = 2000
    for label, omit_raw in (("parse_100k_lines", False), ("parse_100k_lines_omit_raw", True)):
        parse_ms = 0.0
        n_events = 0
        n_bytes = 0
        started = time.perf_counter()
        for first_line in range(0, len(events), batch):
            chunk = "\n".join(events[first_line : first_line + batch]).encode()
            header, payload = worker.call(
                "parse",
                chunk,
                adapter=adapter,
                stream=label,
                flush=first_line + batch >= len(events),
                omit_raw=omit_raw,
            )
            parse_ms += float(header["parse_ms"])
            n_events += int(header["events"])
            n_bytes += len(payload)
            json.loads(payload)  # the host decodes what it receives
        total = (time.perf_counter() - started) * 1000
        result[label] = {
            "batch": batch,
            "total_ms": total,
            "in_worker_parse_ms": parse_ms,
            "transport_and_codec_ms": total - parse_ms,
            "events": n_events,
            "event_bytes": n_bytes,
        }

    result["eof_exit"] = worker.close()
    Path(out_json).write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
