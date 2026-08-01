"""Behavioral checks for the headless browser search runtime."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SEARCH_CONTROLLER_TEST_JS = (
    Path(__file__).resolve().parent / "dom" / "search_controller_behavior.js"
)


def test_search_controller_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SEARCH_CONTROLLER_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "search-controller assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
