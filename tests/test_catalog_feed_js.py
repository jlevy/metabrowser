"""Behavioral checks for the browser's Quick File catalog feed module."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

CATALOG_FEED_TEST_JS = Path(__file__).resolve().parent / "dom" / "catalog-feed-behavior.js"


def test_catalog_feed_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(CATALOG_FEED_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"catalog feed assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
