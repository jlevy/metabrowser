"""Atomic probes for the browser smoke playbook.

Each subcommand performs one atomic check against a running
metabrowser server and prints the result as JSON. Pass /
fail judgment lives in ``docs/browser-smoke.playbook.md`` — these
probes are observation tools, not assertions, so a non-zero exit
means *the probe itself failed* (server unreachable, malformed
response), not that the system under test failed.

Each probe assumes a server is already running. Start one with::

    metabrowser --no-open

Usage::

    python -m metabrowser.smoke_probes capabilities
    python -m metabrowser.smoke_probes index-meta
    python -m metabrowser.smoke_probes tree [--path SUBDIR]
    python -m metabrowser.smoke_probes sse-probe [--timeout 10]

Common flags::

    --port N      server port (default 8411)
    --host HOST   server host (default 127.0.0.1)

Output is one JSON object on stdout per invocation.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket as _socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _http_get_json(host: str, port: int, path: str, timeout: float = 30.0) -> dict[str, Any]:
    url = f"http://{host}:{port}{path}"
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "status": resp.status,
            "elapsed_ms": elapsed_ms,
            "bytes": len(body),
            "body": json.loads(body),
        }


def cmd_capabilities(args: argparse.Namespace) -> int:
    out = _http_get_json(args.host, args.port, "/api/capabilities")
    body = out["body"]
    print(
        json.dumps(
            {
                "probe": "capabilities",
                "elapsed_ms": out["elapsed_ms"],
                "backends": body.get("backends"),
                "index": body.get("index"),
                "events": body.get("events"),
            },
            indent=2,
        )
    )
    return 0


def cmd_index_meta(args: argparse.Namespace) -> int:
    out = _http_get_json(args.host, args.port, "/api/index/meta")
    body = out["body"]
    print(
        json.dumps(
            {
                "probe": "index-meta",
                "elapsed_ms": out["elapsed_ms"],
                "status": body.get("status"),
                "indexed_files": body.get("indexed_files"),
                "indexed_dirs": body.get("indexed_dirs"),
                "max_files": body.get("max_files"),
                "complete": body.get("complete"),
                "truncated": body.get("truncated"),
                "suffix_count": len(body.get("suffixes", [])),
            },
            indent=2,
        )
    )
    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    qs = ""
    if args.path:
        qs = "?path=" + urllib.parse.quote(args.path)
    out = _http_get_json(args.host, args.port, f"/api/tree{qs}")
    body = out["body"]
    tree = body.get("tree", []) if isinstance(body, dict) else []
    print(
        json.dumps(
            {
                "probe": "tree",
                "path": args.path or "",
                "elapsed_ms": out["elapsed_ms"],
                "bytes": out["bytes"],
                "entries": len(tree),
                "tally_cache_status": (
                    body.get("tally_cache_status") if isinstance(body, dict) else None
                ),
            },
            indent=2,
        )
    )
    return 0


def _read_sse_events(
    host: str,
    port: int,
    path: str,
    last_event_id: str,
    duration_s: float,
):
    """Yield raw SSE event blocks from /api/events for *duration_s*.

    Uses a raw socket + handwritten HTTP/1.1 GET so we can:
      * set a short per-read timeout (so the loop wakes between
        chunks to check our deadline)
      * parse chunked transfer-encoding ourselves (http.client's
        decoder blocks on the socket between chunks)

    SSE is text-based and the server is local, so this is simpler
    than wedging http.client into non-blocking mode."""

    sock = _socket.create_connection((host, port), timeout=5)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Accept: text/event-stream\r\n"
        f"Last-Event-ID: {last_event_id}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    sock.sendall(request.encode("ascii"))

    deadline = time.monotonic() + duration_s
    sock.settimeout(0.25)
    raw_buf = b""

    # Read response headers up to the blank line.
    while b"\r\n\r\n" not in raw_buf:
        try:
            chunk = sock.recv(4096)
        except TimeoutError:
            if time.monotonic() > deadline:
                sock.close()
                return
            continue
        if not chunk:
            sock.close()
            raise RuntimeError("SSE: connection closed during headers")
        raw_buf += chunk
    header_blob, _, raw_buf = raw_buf.partition(b"\r\n\r\n")
    status_line = header_blob.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    if " 200 " not in status_line:
        sock.close()
        raise RuntimeError(f"SSE: bad status: {status_line!r}")
    chunked = b"transfer-encoding: chunked" in header_blob.lower()

    buf = ""
    try:
        while time.monotonic() < deadline:
            decoded, raw_buf, eof = _strip_chunked(raw_buf) if chunked else (raw_buf, b"", False)
            if not chunked:
                raw_buf = b""
            if decoded:
                buf += decoded.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                record, _, buf = buf.partition("\n\n")
                yield record
            if eof:
                break
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            raw_buf += chunk
    finally:
        sock.close()


def _strip_chunked(raw: bytes) -> tuple[bytes, bytes, bool]:
    """Pull as many complete chunks out of *raw* as possible.
    Returns ``(decoded_payload, leftover, eof_seen)``."""
    out = bytearray()
    pos = 0
    while True:
        eol = raw.find(b"\r\n", pos)
        if eol == -1:
            break
        size_line = raw[pos:eol]
        try:
            size = int(size_line.split(b";", 1)[0].strip(), 16)
        except ValueError:
            return bytes(out), raw[pos:], False
        body_start = eol + 2
        if size == 0:
            return bytes(out), b"", True
        body_end = body_start + size
        if body_end + 2 > len(raw):
            break  # need more bytes
        out.extend(raw[body_start:body_end])
        pos = body_end + 2  # skip trailing \r\n
    return bytes(out), raw[pos:], False


def _parse_sse_record(record: str) -> dict[str, str]:
    out = {"event": "message", "id": "", "data": ""}
    for line in record.split("\n"):
        if line.startswith("event: "):
            out["event"] = line[len("event: ") :]
        elif line.startswith("id: "):
            out["id"] = line[len("id: ") :]
        elif line.startswith("data: "):
            out["data"] += line[len("data: ") :]
    return out


def cmd_sse_probe(args: argparse.Namespace) -> int:
    """Touch a temp file under the served root, watch /api/events
    for the resulting upsert. Pass Last-Event-ID huge to skip the
    snapshot replay (otherwise the per-conn queue can overflow on
    large repos before our touch lands)."""

    # The probe file lives under cwd, which the user is expected to
    # have set to the served root before invoking. Using a dedicated
    # name + timestamp avoids any chance of false positives from
    # other writers.
    served_root = Path.cwd().resolve()
    suffix = f"_smoke_probe_{int(time.time() * 1000)}.tmp"
    probe_file = served_root / suffix

    record: dict[str, Any] = {
        "probe": "sse-probe",
        "served_root": str(served_root),
        "probe_file": probe_file.name,
        "timeout_s": args.timeout,
        "events_seen": 0,
        "matched": False,
        "match_event_id": None,
        "match_latency_ms": None,
        "first_event_kind": None,
    }

    started_wait = time.perf_counter()
    matched_at: float | None = None

    # Start SSE before the touch so we don't race the watcher.
    events_iter = _read_sse_events(
        args.host,
        args.port,
        "/api/events?scope=root-depth-2",
        last_event_id="9999999999",
        duration_s=args.timeout + 2.0,
    )

    def _toucher() -> None:
        time.sleep(0.5)
        with contextlib.suppress(OSError):
            probe_file.write_text("smoke probe", encoding="utf-8")

    t = threading.Thread(target=_toucher, daemon=True)
    t.start()

    try:
        for raw in events_iter:
            parsed = _parse_sse_record(raw)
            if not parsed["event"]:
                continue
            record["events_seen"] += 1
            if record["first_event_kind"] is None:
                record["first_event_kind"] = parsed["event"]
            if probe_file.name in parsed["data"]:
                record["matched"] = True
                record["match_event_id"] = parsed["id"]
                matched_at = time.perf_counter()
                break
            if (time.perf_counter() - started_wait) > args.timeout:
                break
    finally:
        t.join(timeout=2.0)
        with contextlib.suppress(OSError):
            probe_file.unlink(missing_ok=True)

    if matched_at is not None:
        record["match_latency_ms"] = int((matched_at - started_wait) * 1000)

    print(json.dumps(record, indent=2))
    return 0 if record["matched"] else 2


def cmd_health(args: argparse.Namespace) -> int:
    """Composite probe: capabilities + index-meta + tree timing.
    Useful first-look snapshot before drilling into individual
    probes."""

    def safe(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return fn()
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    caps = safe(lambda: _http_get_json(args.host, args.port, "/api/capabilities"))
    meta = safe(lambda: _http_get_json(args.host, args.port, "/api/index/meta"))
    tree = safe(lambda: _http_get_json(args.host, args.port, "/api/tree"))

    def _body_dict(resp: dict[str, Any]) -> dict[str, Any] | None:
        body = resp.get("body")
        return body if isinstance(body, dict) else None

    meta_body = _body_dict(meta)
    tree_body = _body_dict(tree)

    print(
        json.dumps(
            {
                "probe": "health",
                "capabilities": caps.get("body") if "body" in caps else caps,
                "index_meta_elapsed_ms": meta.get("elapsed_ms"),
                "index_meta_status": meta_body.get("status") if meta_body is not None else None,
                "tree_elapsed_ms": tree.get("elapsed_ms"),
                "tree_entries": len(tree_body.get("tree", [])) if tree_body is not None else None,
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m metabrowser.smoke_probes",
        description="Atomic probes for the browser smoke playbook.",
    )
    parser.add_argument("--host", default=os.environ.get("METABROWSER_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("METABROWSER_PORT", "8411")),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "capabilities", help="Fetch /api/capabilities; reports watcher mode + index status."
    )
    sub.add_parser("index-meta", help="Fetch /api/index/meta; reports walker status + counts.")
    p_tree = sub.add_parser("tree", help="Fetch /api/tree; reports timing + entry count.")
    p_tree.add_argument("--path", default=None, help="Optional subtree path.")
    p_sse = sub.add_parser("sse-probe", help="End-to-end watcher round-trip via SSE.")
    p_sse.add_argument(
        "--timeout", type=float, default=10.0, help="Seconds to wait for the touch event."
    )
    sub.add_parser("health", help="Composite snapshot: capabilities + index-meta + tree timing.")

    args = parser.parse_args(argv)
    handlers = {
        "capabilities": cmd_capabilities,
        "index-meta": cmd_index_meta,
        "tree": cmd_tree,
        "sse-probe": cmd_sse_probe,
        "health": cmd_health,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
