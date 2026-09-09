"""Tests that ``.gz`` files are sealed: SSE rejects them, activity skips them.

Both protect the gzipped-log invariant from the producer side
(``gzip-text --exclude-active`` + the post-compress stability check)
mirrored on the reader side.
"""

from __future__ import annotations

import asyncio
import gzip
from pathlib import Path

from metabrowser import server as proc_browser
from metabrowser.active_tracker import _is_trackable
from metabrowser.inventory_engine.contract import CatalogRecord


class _Params:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _Headers:
    def get(self, key: str, default: str = "") -> str:
        return default


class _FakeRequest:
    def __init__(self, **params: str) -> None:
        self.query_params = _Params(params)
        self.headers = _Headers()


def _setup_logs_dir(tmp_path: Path) -> Path:
    """Create a .logs/ subtree with both a plain and a gzipped JSONL."""
    logs = tmp_path / ".logs"
    logs.mkdir()
    (logs / "live.jsonl").write_text('{"event":"init"}\n')
    body = b'{"event":"init"}\n'
    with gzip.open(logs / "archived.jsonl.gz", "wb") as fh:
        fh.write(body)
    return logs


def test_sse_returns_400_for_gz(tmp_path: Path) -> None:
    """Live-tail a sealed log makes no sense; should 400 not 200."""
    logs = _setup_logs_dir(tmp_path)
    proc_browser._set_root_dir(tmp_path)
    fake = _FakeRequest(path=str((logs / "archived.jsonl.gz").relative_to(tmp_path)))
    response = asyncio.run(proc_browser.api_stream(fake))  # pyright: ignore[reportArgumentType]
    assert response.status_code == 400
    body_attr = getattr(response, "body", b"")
    body = bytes(body_attr) if isinstance(body_attr, (bytes, memoryview)) else b""
    assert b"sealed" in body.lower()


def test_sse_still_serves_plain_jsonl(tmp_path: Path) -> None:
    """Sanity: the .gz gate doesn't break the live-tail happy path."""
    logs = _setup_logs_dir(tmp_path)
    proc_browser._set_root_dir(tmp_path)
    fake = _FakeRequest(path=str((logs / "live.jsonl").relative_to(tmp_path)))
    response = asyncio.run(proc_browser.api_stream(fake))  # pyright: ignore[reportArgumentType]
    assert response.status_code == 200
    assert response.media_type == "text/event-stream"


def test_activity_tracker_skips_gz_files(tmp_path: Path) -> None:
    """``.gz`` files are write-once-sealed by construction; the activity
    poll is for files being actively written, so ``.gz`` must never appear
    in the tracked set even if dropped into a ``.logs/`` directory.
    """
    _setup_logs_dir(tmp_path)
    assert _is_trackable(
        CatalogRecord(
            path=".logs/live.jsonl",
            logical_extension=".jsonl",
            size=10,
            mtime_ns=1,
        )
    )
    assert not _is_trackable(
        CatalogRecord(
            path=".logs/archived.jsonl.gz",
            logical_extension=".jsonl.gz",
            size=10,
            mtime_ns=1,
        )
    )
