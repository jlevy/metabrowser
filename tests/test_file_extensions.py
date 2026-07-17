"""Tests for Metabrowser's centralized file-extension settings."""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Any

from starlette.responses import FileResponse

from metabrowser import server as proc_browser
from metabrowser.file_extensions import (
    BROWSER_IMAGE_EXTS,
    BROWSER_TEXT_EXTS,
    BROWSER_TRACKABLE_EXTS,
)


def test_browser_text_and_image_sets_are_disjoint() -> None:
    """A given extension routes to exactly one branch in api_file."""
    overlap = BROWSER_TEXT_EXTS & BROWSER_IMAGE_EXTS
    assert overlap == set(), f"Ambiguous classification for: {overlap}"


def test_browser_text_includes_arbitrary_text_formats() -> None:
    """Browser support extends to common text formats.

    `foo.html.gz` should open as HTML in the source view."""
    for ext in (".html", ".xml", ".sql", ".log", ".tsv", ".rst"):
        assert ext in BROWSER_TEXT_EXTS, f"{ext} should be browser-readable"


def test_browser_trackable_excludes_gz() -> None:
    """`.gz` files are write-once-sealed; tracking them would create
    spurious live-update events."""
    assert ".gz" not in BROWSER_TRACKABLE_EXTS


# ── End-to-end: arbitrary .gz extension works in the browser ──────


def test_html_gz_renders_as_text_through_api_file(tmp_path: Path) -> None:
    """A manually-gzipped HTML file should open as text in /api/file
    while preserving its logical extension."""
    html = "<html><body>" + ("<p>line</p>\n" * 50) + "</body></html>"
    gz = tmp_path / "report.html.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(html.encode("utf-8"))
    proc_browser._set_root_dir(tmp_path)

    class _Params:
        def get(self, key: str, default: str = "") -> str:
            return {"path": "report.html.gz"}.get(key, default)

    class _Headers:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeRequest:
        query_params = _Params()
        headers = _Headers()

    response = asyncio.run(proc_browser.api_file(_FakeRequest()))  # pyright: ignore[reportArgumentType]
    body: dict[str, Any] = json.loads(bytes(response.body).decode())
    assert body["type"] == "text"
    assert body["content"] == html
    assert body["logical_ext"] == ".html"
    assert body["compressed"] is True


def test_html_gz_raw_passthrough_uses_html_mime(tmp_path: Path) -> None:
    """The /raw mime type for foo.html.gz comes from the inner ext, so
    the browser actually renders it as HTML when fetched directly."""
    gz = tmp_path / "report.html.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(b"<html><body>hi</body></html>")
    proc_browser._set_root_dir(tmp_path)

    class _Params:
        def get(self, key: str, default: str = "") -> str:
            return {"path": "report.html.gz"}.get(key, default)

    class _Headers:
        def get(self, key: str, default: str = "") -> str:
            return {"accept-encoding": "gzip"}.get(key.lower(), default)

    class _FakeRequest:
        query_params = _Params()
        headers = _Headers()

    response = asyncio.run(proc_browser.raw_file(_FakeRequest()))  # pyright: ignore[reportArgumentType]
    assert isinstance(response, FileResponse)
    assert response.headers["content-encoding"] == "gzip"
    assert response.media_type == "text/html"
