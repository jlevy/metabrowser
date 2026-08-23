"""Behavioral checks for the browser performance instrumentation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PERF_TEST_JS = Path(__file__).resolve().parent / "dom" / "perf_behavior.js"


def test_perf_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(PERF_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "perf instrumentation assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
