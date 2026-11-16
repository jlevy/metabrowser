"""Untimed probe: the server's cost of one Markdown render request, GET against POST, gzip
against identity.

Sequential requests on one keep-alive connection to a running `metab` on a folder that holds
the three files named below. The POST body carries the file's own text as `source_text`,
which is what the page uploads when its preparation changed the source; the page's prepared
text is not reproduced here. Prints only.

    python render_probe.py HOST PORT FOLDER

The architecture review of 2026-11-14 ran it once on a loaded host; its readings are orders
of magnitude, not results.
"""

from __future__ import annotations

import http.client
import json
import statistics
import sys
import time
from pathlib import Path
from typing import NamedTuple

FILES = ("README.md", "docs/development.md", "docs/design-system.md")


class Answer(NamedTuple):
    ms: float
    status: int
    size: int
    server_timing: str


def call(
    conn: http.client.HTTPConnection, method: str, url: str, enc: str, body: bytes | None = None
) -> Answer:
    headers = {"Accept-Encoding": enc}
    if body is not None:
        headers["Content-Type"] = "application/json"
    start = time.perf_counter()
    conn.request(method, url, body=body, headers=headers)
    response = conn.getresponse()
    data = response.read()
    return Answer(
        (time.perf_counter() - start) * 1000,
        response.status,
        len(data),
        response.getheader("server-timing") or "",
    )


def main() -> None:
    host, port, corpus = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    conn = http.client.HTTPConnection(host, port, timeout=60)
    for rel in FILES:
        source = (corpus / rel).read_text()
        query = f"/api/kpress/render?path={rel}&view=rendered&profile=document"
        cold = call(conn, "GET", query, "identity")
        print(f"\n{rel}: source {len(source.encode()) / 1024:.1f} KB")
        print(
            f"  GET first (cold render): {cold.ms:7.1f} ms status={cold.status}"
            f" body={cold.size / 1024:.1f} KB  [{cold.server_timing}]"
        )
        for enc in ("identity", "gzip"):
            warm = [call(conn, "GET", query, enc) for _ in range(7)]
            print(
                f"  GET warm accept={enc:8s}: median {statistics.median(x.ms for x in warm):6.1f} ms"
                f" (min {min(x.ms for x in warm):.1f}) wire={warm[0].size / 1024:7.1f} KB"
                f"  [{warm[-1].server_timing}]"
            )
        body = json.dumps(
            {"path": rel, "view": "rendered", "profile": "document", "source_text": source}
        ).encode()
        first = call(conn, "POST", "/api/kpress/render", "gzip", body)
        posts = [call(conn, "POST", "/api/kpress/render", "gzip", body) for _ in range(7)]
        print(
            f"  POST upload {len(body) / 1024:.1f} KB: first {first.ms:.1f} ms"
            f" status={first.status};"
            f" warm accept=gzip median {statistics.median(x.ms for x in posts):6.1f} ms"
            f" (min {min(x.ms for x in posts):.1f})"
            f" statuses={[x.status for x in posts]}  [{posts[-1].server_timing}]"
        )
        envelope = [call(conn, "GET", f"/api/file?path={rel}", "gzip") for _ in range(7)]
        print(
            f"  /api/file accept=gzip: median {statistics.median(x.ms for x in envelope):.1f} ms"
            f" wire={envelope[0].size / 1024:.1f} KB"
        )


if __name__ == "__main__":
    main()
