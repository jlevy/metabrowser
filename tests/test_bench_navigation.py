"""Reproducibility and correctness gates for the browser-free comparison."""

from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override

import pytest

from devtools.bench_navigation import (
    Route,
    request,
    require_matching_runtimes,
    run_build,
    runtime_identity,
    validate_equivalence,
)
from devtools.bench_serving import build_corpus, resolve_metab_build


def test_runtime_mismatch_rejects_free_threading_and_patch_version() -> None:
    baseline: dict[str, Any] = {"python": "3.14.6", "free_threaded": False, "gil_enabled": True}
    for changes in ({"free_threaded": True}, {"gil_enabled": False}, {"python": "3.14.7"}):
        with pytest.raises(ValueError, match="runtime mismatch"):
            require_matching_runtimes({"baseline": baseline, "candidate": {**baseline, **changes}})


def test_actual_build_runtime_includes_loaded_dependency_versions() -> None:
    identity = runtime_identity(resolve_metab_build("metab"))
    assert identity["python"]
    assert len(identity["python_source_sha256"]) == 64
    assert isinstance(identity["gil_enabled"], bool)
    assert isinstance(identity["free_threaded"], bool)
    assert "starlette" in identity["dependencies"]


def test_response_validation_rejects_changed_content_and_selection() -> None:
    for label, field in (
        ("file:a.txt", "content_sha256"),
        ("catalog", "files"),
        ("recent", "paths_sha256"),
    ):
        first = {"status": 200, "label": label, field: "before"}
        changed = {**first, field: "after"}
        runs = [
            {"files_indexed": 10, "phases": {"warm": [first]}},
            {"files_indexed": 10, "phases": {"warm": [changed]}},
        ]
        with pytest.raises(ValueError, match="response mismatch"):
            validate_equivalence(runs)


def test_gzip_and_conditional_request_validation() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.headers.get("If-None-Match") == '"v1"':
                self.send_response(304)
                self.end_headers()
                return
            body = gzip.compress(
                json.dumps({"content": "hello", "kind": "text", "path": "a.txt"}).encode()
            )
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("ETag", '"v1"')
            self.send_header("Server-Timing", "srv;dur=2.5")
            self.end_headers()
            self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            first = request(base, Route("file:a.txt", "/api/file?path=a.txt"))
            assert first.sample["server_ms"] == 2.5
            assert first.sample["content_sha256"]
            assert "etag" not in first.sample
            conditional = request(
                base, Route("file:a.txt", "/api/file?path=a.txt"), etag=first.etag
            )
            assert conditional.sample["status"] == 304
            with pytest.raises(ValueError, match="expected 304"):
                request(base, Route("file:a.txt", "/api/file?path=a.txt"), etag='"stale"')
        finally:
            server.shutdown()
            thread.join()


def test_equivalence_requires_equal_inventory_populations() -> None:
    with pytest.raises(ValueError, match="populations differ"):
        validate_equivalence([{"files_indexed": 2}, {"files_indexed": 3}])


def test_tiny_real_server_workload_is_read_only_and_complete(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    build_corpus(root, 1)
    (root / "a.txt").write_text("hello")
    before = {path.relative_to(root): path.stat().st_mtime_ns for path in root.rglob("*")}
    result = run_build(
        root,
        resolve_metab_build("metab"),
        tmp_path / "server.log",
        [Route("file:a.txt", "/api/file?path=a.txt")],
        rounds=1,
        render_file=None,
    )
    validate_equivalence([result])
    assert result["phases"]["revalidate"][0]["status"] == 304
    assert any(row["label"] == "recent" for row in result["phases"]["with_recent"])
    assert all(row["label"] != "recent" for row in result["phases"]["without_recent"])
    assert before == {path.relative_to(root): path.stat().st_mtime_ns for path in root.rglob("*")}
