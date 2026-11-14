"""Spike: a host-shipped runtime and worker serving a real plugin from its own environment.

Runs with the host Metabrowser's interpreter. It assembles the runtime folder from this
host's own files, spawns ``runtime_worker.py`` with the plugin environment's interpreter
through ``posix_spawn``, with the request pipe on descriptor 3 and the reply pipe on 4,
and answers the worker's own requests (built-in adapter detection, agent-log charts).

Usage: host_runtime.py ENV_PYTHON REPO_ROOT PROCESS_SPEC FIXTURE_DIR OUT_DIR
"""

from __future__ import annotations

import json
import os
import shutil
import signal
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
from metabrowser.logutil.parsing import detect_adapter
from metabrowser.projections import extract_agent_charts_cached

HERE = Path(__file__).parent
Header = dict[str, Any]
Frame = tuple[Header, bytes]


def assemble_runtime(out_dir: Path) -> Path:
    """The runtime is this host's code: the shim plus verbatim copies of two host modules."""
    runtime = out_dir / "runtime"
    package = runtime / "metabrowser"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "runtime_metabrowser.py", package / "__init__.py")
    host_package = Path(metabrowser.__file__).parent
    for name in ("gz_io.py", "content_errors.py"):
        shutil.copyfile(host_package / name, package / name)
    return runtime


class Worker:
    def __init__(self, python: str, root: Path, runtime: Path, log: Path) -> None:
        self.root = root.resolve()
        req_r, self._req_w = os.pipe()
        self._rep_r, rep_w = os.pipe()
        log_fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        env = {"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"}
        self.started = time.perf_counter()
        self.pid = os.posix_spawn(
            python,
            [python, "-I", "-B", str(HERE / "runtime_worker.py"), str(runtime)],
            env,
            file_actions=[
                (os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0),
                (os.POSIX_SPAWN_DUP2, log_fd, 1),
                (os.POSIX_SPAWN_DUP2, log_fd, 2),
                (os.POSIX_SPAWN_DUP2, req_r, 3),
                (os.POSIX_SPAWN_DUP2, rep_w, 4),
            ],
        )
        for fd in (req_r, rep_w, log_fd):
            os.close(fd)
        self._out = os.fdopen(self._req_w, "wb", buffering=0)
        self._in = os.fdopen(self._rep_r, "rb")
        self._next = 0
        self._pending: dict[int, Future[Frame]] = {}
        self._lock = threading.Lock()
        self.callbacks: list[str] = []
        threading.Thread(target=self._reader, daemon=True).start()

    def _write(self, header: Header, body: bytes = b"") -> None:
        frame = json.dumps({**header, "body_len": len(body)}).encode()
        with self._lock:
            self._out.write(frame + b"\n" + body)

    def _reader(self) -> None:
        while line := self._in.readline():
            header: Header = json.loads(line)
            size = int(header.get("body_len", 0))
            body = self._in.read(size) if size else b""
            if "wid" in header:
                threading.Thread(target=self._answer, args=(header,), daemon=True).start()
            else:
                self._pending.pop(int(header["id"])).set_result((header, body))

    def _answer(self, header: Header) -> None:
        """The host side of the worker's requests: checked against this worker's root."""
        op: str = header["op"]
        args: Header = header.get("args", {})
        self.callbacks.append(op)
        try:
            if op == "host.detect_builtin":
                result: Any = detect_adapter(list(args["lines"]))
            elif op == "host.agent_charts":
                target = (self.root / str(args["path"])).resolve()
                target.relative_to(self.root)  # refuses a path outside the served root
                result = extract_agent_charts_cached(target)
            else:
                raise ValueError(f"unknown host op {op}")
            self._write({"wid": header["wid"], "ok": True, "result": result})
        except Exception as exc:  # the worker gets the error as its answer
            self._write({"wid": header["wid"], "ok": False, "error": str(exc)})

    def request(self, op: str, body: bytes = b"", **fields: Any) -> Future[Frame]:
        with self._lock:
            self._next += 1
            rid = self._next
        future: Future[Frame] = Future()
        self._pending[rid] = future
        self._write({"id": rid, "op": op, **fields}, body)
        return future

    def call(self, op: str, body: bytes = b"", timeout: float = 120, **fields: Any) -> Frame:
        header, out = self.request(op, body, **fields).result(timeout=timeout)
        if not header.get("ok"):
            raise RuntimeError(str(header.get("error")))
        return header, out

    def rss_mb(self) -> float:
        ps = ["ps", "-o", "rss=", "-p", str(self.pid)]
        return int(subprocess.run(ps, capture_output=True, text=True, check=True).stdout) / 1024

    def close(self) -> Header:
        started = time.perf_counter()
        self._out.close()
        _, status = os.waitpid(self.pid, 0)
        return {
            "status": os.waitstatus_to_exitcode(status),
            "ms": (time.perf_counter() - started) * 1000,
        }

    def kill(self) -> None:
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)


def hooks_of(plugin_dir: str) -> dict[str, str]:
    manifest = tomllib.loads(Path(plugin_dir, "manifest.toml").read_text())
    return {hook["route"]: hook["sidekick"] for hook in manifest.get("data_hook", [])}


def start(python: str, root: Path, runtime: Path, log: Path) -> tuple[Worker, Header]:
    worker = Worker(python, root, runtime, log)
    hello, _ = worker.call("hello", root=str(root))
    listing, _ = worker.call("list")
    ready = (time.perf_counter() - worker.started) * 1000
    return worker, {"hello": hello, "listing": listing, "spawn_to_listed_ms": ready}


def main() -> None:
    env_python, repo_root, spec_path, fixture_dir, out = sys.argv[1:6]
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = assemble_runtime(out_dir)
    log = out_dir / "worker.stderr.log"
    result: Header = {"host_metabrowser": metabrowser.__version__}

    # A: the repository root, the large hook, and the descriptor and signal checks.
    worker, ready = start(env_python, Path(repo_root), runtime, log)
    listing = ready["listing"]
    result["a_ready"] = {
        "spawn_to_listed_ms": ready["spawn_to_listed_ms"],
        "python": ready["hello"]["python"],
        "metabrowser_installed_in_env": ready["hello"]["metabrowser_installed_in_env"],
        "runtime_is_host_copy": listing["runtime"].startswith(runtime.as_posix()),
        "plugins": [p["entry_point"] for p in listing["plugins"]],
        "adapters": listing["adapters"],
        "errors": listing["errors"],
    }
    target = next(p for p in listing["plugins"] if "viz-model" in hooks_of(p["dir"]))
    plugin = target["entry_point"]
    hooks = hooks_of(target["dir"])

    def hook(route: str, query: str = "", on: Worker = worker) -> tuple[Header, bytes, float]:
        started = time.perf_counter()
        header, body = on.call(
            "call", sidekick=hooks[route], path=f"/api/plugin/{plugin}/{route}", query=query
        )
        return header, body, (time.perf_counter() - started) * 1000

    info, info_body, _ = hook("info")
    rtts = [hook("info")[2] for _ in range(200)]
    result["a_info"] = {
        "status": info["status"],
        "routes": json.loads(info_body).get("routes"),
        "rtt_p50_ms": statistics.median(rtts),
    }
    viz, viz_body, viz_ms = hook("viz-model", f"process={spec_path}")
    result["a_viz_model"] = {
        "status": viz["status"],
        "bytes": len(viz_body),
        "handler_ms": viz["handler_ms"],
        "total_ms": viz_ms,
        "headers": [name for name, _ in viz["headers"]],
    }
    result["a_rss_mb"] = worker.rss_mb()
    probe, _ = worker.call("probe_subprocess")
    after_probe = hook("info")[0]["status"]
    os.kill(worker.pid, signal.SIGINT)
    time.sleep(0.2)
    after_sigint = hook("info")[0]["status"]
    result["a_isolation"] = {
        "subprocess_returncode": probe["returncode"],
        "info_after_subprocess": after_probe,
        "info_after_sigint": after_sigint,
    }
    result["a_eof_exit"] = worker.close()

    # B: a fixture root, the charts hook on both log families, parsing, and a deadline.
    worker, ready = start(env_python, Path(fixture_dir), runtime, log)
    charts: Header = {}
    for name in ("pool.jsonl", "agent.jsonl"):
        before = len(worker.callbacks)
        header, body, ms = hook("charts", f"path={name}", worker)
        payload = json.loads(body)
        charts[name] = {
            "status": header["status"],
            "ms": ms,
            "chart_count": len(payload.get("charts") or []),
            "has_summary": payload.get("summary") is not None,
            "host_callbacks": worker.callbacks[before:],
        }
    result["b_charts"] = charts
    adapter = next(a for a in ready["listing"]["adapters"] if a != "process")
    lines = Path(fixture_dir, "pool.jsonl").read_text().encode()
    parsed, events = worker.call("parse", lines, adapter=adapter, stream="s", flush=True)
    result["b_parse"] = {"events": parsed["events"], "bytes": len(events)}

    started = time.perf_counter()
    stuck = worker.request("sleep", seconds=60)
    deadline_s, grace_s = 1.0, 1.0
    try:
        stuck.result(timeout=deadline_s + grace_s)
    except TimeoutError:
        worker.kill()
    killed_ms = (time.perf_counter() - started) * 1000
    worker, again = start(env_python, Path(fixture_dir), runtime, log)
    result["b_deadline"] = {
        "deadline_plus_grace_s": deadline_s + grace_s,
        "killed_after_ms": killed_ms,
        "respawn_to_listed_ms": again["spawn_to_listed_ms"],
        "info_after_respawn": hook("info", on=worker)[0]["status"],
    }
    result["b_eof_exit"] = worker.close()

    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
