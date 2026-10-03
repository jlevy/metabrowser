"""Behavioral checks for the browser's Quick File catalog feed module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.required_tools import require_node

CATALOG_FEED_TEST_JS = Path(__file__).resolve().parent / "dom" / "catalog-feed-behavior.js"


def test_catalog_feed_js_assertions_pass() -> None:
    require_node()
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
    assert json.loads(result.stdout)["observed"], f"unexpected stdout: {result.stdout!r}"
