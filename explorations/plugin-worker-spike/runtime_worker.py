"""Spike: the worker in the plan's shape, shipped by the host and run on a plugin environment.

Run as ``<env-python> -I -B runtime_worker.py RUNTIME_DIR`` with the request pipe on
descriptor 3 and the reply pipe on descriptor 4. It puts ``RUNTIME_DIR`` first on
``sys.path``, so plugin code imports the host's runtime as ``metabrowser``, points
descriptor 0 at ``/dev/null`` and descriptor 1 at stderr, ignores SIGINT, and keeps the
protocol descriptors out of every subprocess plugin code starts.

Frames are one JSON header line and ``body_len`` raw bytes. Host requests carry ``id``;
the worker's own requests to the host carry ``wid``, and their replies come back on the
request pipe.
"""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
import importlib.metadata as md
import inspect
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

Header = dict[str, Any]
Reply = tuple[Header, bytes]

_requests = os.fdopen(3, "rb")
_replies = os.fdopen(4, "wb", buffering=0)
os.set_inheritable(3, False)
os.set_inheritable(4, False)
_devnull = os.open(os.devnull, os.O_RDONLY)
os.dup2(_devnull, 0)
os.dup2(2, 1)
sys.stdout = sys.stderr
signal.signal(signal.SIGINT, signal.SIG_IGN)
sys.path.insert(0, sys.argv[1])
# The host's runtime, from the folder just inserted, whatever the environment holds.
runtime: Any = importlib.import_module("metabrowser")

_write_lock = threading.Lock()
_pending: dict[int, tuple[threading.Event, list[Header]]] = {}
_next_wid = 0
_sidekicks: dict[str, Callable[..., Any]] = {}
_streams: dict[str, Any] = {}


def _send(header: Header, body: bytes = b"") -> None:
    frame = json.dumps({**header, "body_len": len(body)}, separators=(",", ":")).encode()
    with _write_lock:
        _replies.write(frame + b"\n" + body)


def host_call(op: str, args: Header) -> Any:
    """Ask the host something mid-call, from any thread, and wait for its answer."""
    global _next_wid
    with _write_lock:
        _next_wid += 1
        wid = _next_wid
    done = threading.Event()
    box: list[Header] = []
    _pending[wid] = (done, box)
    _send({"wid": wid, "op": f"host.{op}", "args": args})
    if not done.wait(30):
        raise TimeoutError(f"host did not answer {op}")
    answer = box[0]
    if not answer.get("ok"):
        raise RuntimeError(str(answer.get("error")))
    return answer.get("result")


class HookRequest:
    """The SDK's request: what the three downstream plugins read, and no Starlette."""

    def __init__(self, method: str, query: str, headers: list[list[str]], body: bytes) -> None:
        self.method = method
        self.query_params = {k: v[-1] for k, v in parse_qs(query).items()}
        self.headers = {k.lower(): v for k, v in headers}
        self._body = body

    async def body(self) -> bytes:
        return self._body

    async def json(self) -> Any:
        return json.loads(self._body)


def op_hello(header: Header, _body: bytes) -> Reply:
    runtime._bind(Path(header["root"]), host_call)
    env_mb: str | None
    try:
        env_mb = md.version("metabrowser")
    except md.PackageNotFoundError:
        env_mb = None
    reply: Header = {"python": sys.version.split()[0], "pid": os.getpid()}
    return {**reply, "metabrowser_installed_in_env": env_mb}, b""


def op_list(_header: Header, _body: bytes) -> Reply:
    plugins: list[Header] = []
    errors: list[str] = []
    for ep in md.entry_points(group="metabrowser.plugins"):
        try:
            module_name, _, attr = ep.value.partition(":")
            factory = getattr(importlib.import_module(module_name), attr)
            plugins.append({"entry_point": ep.name, "dir": str(Path(factory()).resolve())})
        except Exception as exc:  # report the entry point and keep listing
            errors.append(f"{ep.name}: {type(exc).__name__}: {exc}")
    where = Path(runtime.__file__).parent.as_posix()
    reply: Header = {"plugins": plugins, "errors": errors, "runtime": where}
    return {**reply, "adapters": runtime.adapter_names()}, b""


async def op_call(header: Header, body: bytes) -> Reply:
    spec: str = header["sidekick"]
    fn = _sidekicks.get(spec)
    if fn is None:
        module_name, _, attr = spec.partition(":")
        fn = getattr(importlib.import_module(module_name), attr)
        _sidekicks[spec] = fn
    request = HookRequest(header.get("method", "GET"), header.get("query", ""), [], body)
    started = time.perf_counter()
    if inspect.iscoroutinefunction(fn):
        result = await fn(request)
    else:
        result = await asyncio.to_thread(fn, request)
    handler_ms = (time.perf_counter() - started) * 1000
    if hasattr(result, "status_code") and hasattr(result, "body"):
        raw_headers: list[tuple[bytes, bytes]] = getattr(result, "raw_headers", [])
        headers = [(k.decode(), v.decode()) for k, v in raw_headers]
        reply: Header = {"status": result.status_code, "headers": headers}
        return {**reply, "handler_ms": handler_ms}, bytes(result.body)
    reply = {"status": 200, "headers": [("content-type", "application/json")]}
    return {**reply, "handler_ms": handler_ms}, json.dumps(result).encode()


def op_parse(header: Header, body: bytes) -> Reply:
    stream: str = header["stream"]
    parser = _streams.get(stream)
    if parser is None:
        parser = runtime.create_plugin_parser(header["adapter"])
        _streams[stream] = parser
    events: list[Any] = []
    for line in body.decode().splitlines():
        events.extend(parser.parse_line(line))
    if header.get("flush"):
        events.extend(parser.flush())
        _streams.pop(stream, None)
    rows: list[Header] = [dataclasses.asdict(event) for event in events]
    return {"events": len(rows)}, json.dumps(rows, default=str).encode()


def op_probe_subprocess(_header: Header, _body: bytes) -> Reply:
    """What a plugin's subprocess sees: stdout and stdin, and whether it reaches 3 or 4."""
    shell = "printf 'junk from a plugin subprocess\\n'; cat; printf x >&4 && echo reached-4"
    done = subprocess.run(["/bin/sh", "-c", shell], timeout=5, check=False)
    return {"returncode": done.returncode}, b""


def op_sleep(header: Header, _body: bytes) -> Reply:
    """A synchronous handler that ignores its deadline, as a stuck hook would."""
    time.sleep(float(header["seconds"]))
    return {}, b""


SYNC_OPS: dict[str, Callable[[Header, bytes], Reply]] = {
    "hello": op_hello,
    "list": op_list,
    "parse": op_parse,
    "probe_subprocess": op_probe_subprocess,
    "sleep": op_sleep,
}


async def _handle(header: Header, body: bytes) -> None:
    op = header.get("op")
    reply: Header = {"id": header.get("id")}
    out_body = b""
    try:
        if op == "call":
            out, out_body = await op_call(header, body)
        elif isinstance(op, str) and op in SYNC_OPS:
            out, out_body = await asyncio.to_thread(SYNC_OPS[op], header, body)
        else:
            raise ValueError(f"unknown op {op!r}")
        reply.update(out)
        reply["ok"] = True
    except Exception as exc:  # every failure becomes a reply, never a dead worker
        reply.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        out_body = b""
    _send(reply, out_body)


def main() -> None:
    loop = asyncio.new_event_loop()

    def reader() -> None:
        while True:
            line = _requests.readline()
            if not line:  # the request pipe closed: the server is gone, so is this worker
                loop.call_soon_threadsafe(loop.stop)
                return
            header: Header = json.loads(line)
            size = int(header.get("body_len", 0))
            body = _requests.read(size) if size else b""
            if "wid" in header:  # the host's answer to one of this worker's own requests
                done, box = _pending.pop(int(header["wid"]))
                box.append(header)
                done.set()
                continue
            asyncio.run_coroutine_threadsafe(_handle(header, body), loop)

    threading.Thread(target=reader, daemon=True).start()
    loop.run_forever()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
