"""Untimed probe: server time of a commit's detail and comparison routes, first ask and repeat.

Sequential requests on one keep-alive connection to a running `metab` on a Git checkout.
The commits are the checkout's own recent first-parent history. Prints only.

    python commit_probe.py HOST PORT SHA [SHA ...]

The architecture review of 2026-11-14 ran it once on a loaded host; its readings are
orders of magnitude, not results.
"""

from __future__ import annotations

import http.client
import json
import statistics
import sys
import time
import urllib.parse
from typing import NamedTuple, cast


def field(value: object, key: str) -> object:
    """One member of a decoded JSON object, or `None` for anything else."""

    return cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None


class Answer(NamedTuple):
    ms: float
    status: int
    size: int
    server_timing: str
    body: bytes


def call(conn: http.client.HTTPConnection, url: str, enc: str = "identity") -> Answer:
    start = time.perf_counter()
    conn.request("GET", url, headers={"Accept-Encoding": enc})
    response = conn.getresponse()
    data = response.read()
    return Answer(
        (time.perf_counter() - start) * 1000,
        response.status,
        len(data),
        response.getheader("server-timing") or "",
        data,
    )


def file_count(body: bytes) -> str:
    """The comparison's file count, from either answer shape, or `?`."""

    try:
        doc: object = json.loads(body)
    except ValueError:
        return "?"
    files = field(doc, "files")
    if files is None:
        files = field(field(doc, "document"), "files")
    return str(len(cast("list[object]", files))) if isinstance(files, list) else "?"


def main() -> None:
    host, port = sys.argv[1], int(sys.argv[2])
    shas = sys.argv[3:]
    conn = http.client.HTTPConnection(host, port, timeout=60)
    for sha in shas:
        detail = call(conn, f"/api/git/commit/{sha}")
        query = urllib.parse.urlencode({"left": f"{sha}~1", "right": sha, "base_policy": "direct"})
        url = f"/api/plugin/diff/comparison?{query}"
        first = call(conn, url)
        again = [call(conn, url) for _ in range(5)]
        gzipped = [call(conn, url, "gzip") for _ in range(5)]
        print(
            f"{sha[:8]} detail {detail.ms:6.1f} ms status={detail.status} [{detail.server_timing}]"
        )
        print(
            f"         comparison first {first.ms:7.1f} ms status={first.status}"
            f" body={first.size / 1024:7.1f} KB files={file_count(first.body)}"
            f" [{first.server_timing}]"
        )
        print(
            "         comparison repeat identity median"
            f" {statistics.median(x.ms for x in again):6.1f} ms [{again[-1].server_timing}]"
        )
        print(
            "         comparison repeat gzip     median"
            f" {statistics.median(x.ms for x in gzipped):6.1f} ms"
            f" wire={gzipped[0].size / 1024:.1f} KB [{gzipped[-1].server_timing}]"
        )


if __name__ == "__main__":
    main()
