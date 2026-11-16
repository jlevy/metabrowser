"""Untimed probe: what the server spends serving a landing's static assets, one at a time.

Fetches the shell for a landing from a running `metab`, reads the script and stylesheet
addresses and the on-demand bundles it names, then requests each asset sequentially on one
keep-alive connection, three sweeps accepting gzip and three accepting identity, in turn.
Sequential on purpose: it reads the server's own serial cost per request, with no browser
and no connection contention. Reads only; prints only.

    python static_probe.py HOST PORT LANDING      # LANDING such as /view/README.md

The architecture review of 2026-11-14 ran it once on a loaded host; its readings are orders
of magnitude, not results.
"""

from __future__ import annotations

import http.client
import json
import re
import statistics
import sys
import time
from typing import NamedTuple, cast


def field(value: object, key: str) -> object:
    """One member of a decoded JSON object, or `None` for anything else."""

    return cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None


class Answer(NamedTuple):
    ms: float
    status: int
    size: int
    server_timing: str
    content_encoding: str


def get(conn: http.client.HTTPConnection, host: str, port: int, url: str, enc: str) -> Answer:
    start = time.perf_counter()
    conn.request("GET", url, headers={"Accept-Encoding": enc, "Host": f"{host}:{port}"})
    response = conn.getresponse()
    body = response.read()
    return Answer(
        (time.perf_counter() - start) * 1000,
        response.status,
        len(body),
        response.getheader("server-timing") or "",
        response.getheader("content-encoding") or "identity",
    )


def bundle_sources(html: str) -> list[str]:
    """The `src` of every item in the startup bundles the shell names."""

    match = re.search(r"window\.METABROWSER_ASSET_BUNDLES=(\{.*?\});</script>", html, re.S)
    if not match:
        return []
    bundles: object = json.loads(match.group(1))
    sources: list[str] = []
    for name in ("shell-tools", "view-composition", "sdk-views"):
        items = field(bundles, name)
        if not isinstance(items, list):
            continue
        for item in cast("list[object]", items):
            src = field(item, "src")
            if isinstance(src, str):
                sources.append(src)
    return sources


def main() -> None:
    host, port, landing = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    conn = http.client.HTTPConnection(host, port, timeout=30)
    shell = get(conn, host, port, landing, "identity")
    reader = http.client.HTTPConnection(host, port, timeout=30)
    reader.request("GET", landing, headers={"Accept-Encoding": "identity"})
    html = reader.getresponse().read().decode()
    reader.close()
    print(
        f"shell {landing}: {shell.ms:.1f} ms status={shell.status} bytes={shell.size}"
        f" server-timing=[{shell.server_timing}]"
    )
    urls = re.findall(r'<script src="([^"]+)"', html) + re.findall(
        r'<link rel="stylesheet" href="([^"]+)"', html
    )
    for src in bundle_sources(html):
        if src not in urls:
            urls.append(src)
    local = [url for url in urls if url.startswith("/")]
    print("static assets named by the shell and its startup bundles:", len(local))

    rows: list[tuple[Answer, float]] = []
    for enc in ("gzip", "identity", "gzip", "identity", "gzip", "identity"):
        rows = []
        for url in local:
            answer = get(conn, host, port, url, enc)
            encode_ms = sum(
                float(x) for x in re.findall(r"encode;dur=([0-9.]+)", answer.server_timing)
            )
            rows.append((answer, encode_ms))
        wall = sum(answer.ms for answer, _ in rows)
        print(
            f"accept={enc:8s} requests={len(rows)} wall_sum={wall:7.1f} ms"
            f"  per_request_median={statistics.median(answer.ms for answer, _ in rows):5.2f} ms"
            f"  bytes={sum(answer.size for answer, _ in rows) / 1024:8.1f} KB"
            f"  encode_sum={sum(encode_ms for _, encode_ms in rows):6.1f} ms"
            f"  statuses={sorted({answer.status for answer, _ in rows})}"
            f" enc={sorted({answer.content_encoding for answer, _ in rows})}"
        )
    if rows:
        print("example server-timing:", rows[0][0].server_timing)
    # A cheap data route, for the floor of one request on this stack.
    for path in ("/api/identity", "/api/file?path=README.md"):
        times = [get(conn, host, port, path, "identity").ms for _ in range(40)]
        print(
            f"{path}: median {statistics.median(times):.2f} ms, min {min(times):.2f},"
            f" p90 {sorted(times)[35]:.2f} (n=40, sequential)"
        )


if __name__ == "__main__":
    main()
