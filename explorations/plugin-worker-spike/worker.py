"""Spike: an out-of-process sidekick worker, run with a plugin environment's interpreter.

Stdlib-only on its own side. It imports the plugin code of the environment it runs in,
and nothing from the host's Metabrowser. Run as ``<env-python> -I -B worker.py``.

Framing: one JSON header line, then ``body_len`` raw bytes. Requests carry ``id``;
replies echo it, so several requests can be in flight at once.

SPIKE SHORTCUTS, which the plan replaces with the plugin SDK's binding:

- ``set_root`` calls the environment's own ``metabrowser.paths_safe._set_root_dir``, a
  private name of whatever Metabrowser version that environment holds.
- adapter names and parser factories come from that version's private
  ``_PLUGIN_ADAPTERS``.
- a hook gets a Starlette ``Request``, Starlette being the plugins' own dependency.
"""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
import importlib.metadata as md
import inspect
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROTOCOL = 1
_out = sys.stdout.buffer
_in = sys.stdin.buffer
_write_lock = threading.Lock()
# Plugin code must never write to the protocol stream, so its prints go to stderr.
sys.stdout = sys.stderr

Header = dict[str, Any]
Reply = tuple[Header, bytes]

_sidekicks: dict[str, Any] = {}
_streams: dict[str, Any] = {}


def _send(header: Header, body: bytes = b"") -> None:
    frame = json.dumps({**header, "body_len": len(body)}, separators=(",", ":")).encode()
    with _write_lock:
        _out.write(frame + b"\n" + body)
        _out.flush()


def _read_frame() -> tuple[Header, bytes] | None:
    line = _in.readline()
    if not line:
        return None
    header: Header = json.loads(line)
    size = int(header.get("body_len", 0))
    return header, (_in.read(size) if size else b"")


def _version(dist: str) -> str | None:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def op_hello(_header: Header, _body: bytes) -> Reply:
    return {
        "protocol": PROTOCOL,
        "python": sys.version.split()[0],
        "metabrowser_in_env": _version("metabrowser"),
        "pid": os.getpid(),
    }, b""


def op_list(_header: Header, _body: bytes) -> Reply:
    plugins: list[Header] = []
    errors: list[str] = []
    for ep in md.entry_points(group="metabrowser.plugins"):
        try:
            module_name, _, attr = ep.value.partition(":")
            factory = getattr(importlib.import_module(module_name), attr)
            plugin_dir = Path(factory()).expanduser().resolve()
            dist = ep.dist.name if ep.dist else None
            plugins.append(
                {
                    "entry_point": ep.name,
                    "dist": dist,
                    "dist_version": _version(dist) if dist else None,
                    "dir": str(plugin_dir),
                }
            )
        except Exception as exc:  # report the entry point and keep listing
            errors.append(f"{ep.name}: {type(exc).__name__}: {exc}")
    adapters: list[str] = []
    try:
        from metabrowser.logutil import parsing

        adapters = sorted(parsing._PLUGIN_ADAPTERS)  # pyright: ignore[reportPrivateUsage]
    except Exception as exc:  # an environment without the registry has no adapters
        errors.append(f"adapters: {exc}")
    return {"plugins": plugins, "adapters": adapters, "errors": errors}, b""


def op_set_root(header: Header, _body: bytes) -> Reply:
    from metabrowser.paths_safe import _set_root_dir  # pyright: ignore[reportPrivateUsage]

    _set_root_dir(Path(header["root"]))
    return {"root": header["root"]}, b""


def _resolve(spec: str) -> Callable[..., Any]:
    fn = _sidekicks.get(spec)
    if fn is None:
        module_name, _, attr = spec.partition(":")
        fn = getattr(importlib.import_module(module_name), attr)
        _sidekicks[spec] = fn
    return fn


async def op_call(header: Header, body: bytes) -> Reply:
    from starlette.requests import Request

    fn = _resolve(header["sidekick"])
    path: str = header["path"]
    scope: Header = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": header.get("method", "GET"),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": str(header.get("query", "")).encode(),
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in header.get("headers", [])],
        "client": None,
        "server": None,
        "path_params": {},
    }

    async def receive() -> Header:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive)
    started = time.perf_counter()
    if inspect.iscoroutinefunction(fn):
        result = await fn(request)
    else:
        result = await asyncio.to_thread(fn, request)
        if inspect.isawaitable(result):
            result = await result
    handler_ms = (time.perf_counter() - started) * 1000
    if hasattr(result, "status_code") and hasattr(result, "body"):
        raw_headers: list[tuple[bytes, bytes]] = getattr(result, "raw_headers", [])
        headers = [(k.decode(), v.decode()) for k, v in raw_headers]
        reply: Header = {"status": result.status_code, "headers": headers}
        return {**reply, "handler_ms": handler_ms}, bytes(result.body)
    reply = {"status": 200, "headers": [("content-type", "application/json")]}
    return {**reply, "handler_ms": handler_ms}, json.dumps(result).encode()


def op_detect(header: Header, _body: bytes) -> Reply:
    from metabrowser import detect_adapter

    return {"adapter": detect_adapter(header["lines"])}, b""


def op_parse(header: Header, body: bytes) -> Reply:
    from metabrowser.logutil import parsing

    stream: str = header["stream"]
    parser = _streams.get(stream)
    if parser is None:
        registry = parsing._PLUGIN_ADAPTERS  # pyright: ignore[reportPrivateUsage]
        parser = registry[header["adapter"]][1]()
        _streams[stream] = parser
    started = time.perf_counter()
    events: list[Any] = []
    for line in body.decode().splitlines():
        events.extend(parser.parse_line(line))
    if header.get("flush"):
        events.extend(parser.flush())
        _streams.pop(stream, None)
    parse_ms = (time.perf_counter() - started) * 1000
    rows: list[Header] = [dataclasses.asdict(event) for event in events]
    if header.get("omit_raw"):
        for row in rows:
            row.pop("raw", None)
    payload = json.dumps(rows, default=str).encode()
    return {"events": len(events), "parse_ms": parse_ms}, payload


SYNC_OPS: dict[str, Callable[[Header, bytes], Reply]] = {
    "hello": op_hello,
    "list": op_list,
    "set_root": op_set_root,
    "detect": op_detect,
    "parse": op_parse,
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
            frame = _read_frame()
            if frame is None:  # stdin closed: the host is gone, so is this worker
                loop.call_soon_threadsafe(loop.stop)
                return
            asyncio.run_coroutine_threadsafe(_handle(*frame), loop)

    threading.Thread(target=reader, daemon=True).start()
    loop.run_forever()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
