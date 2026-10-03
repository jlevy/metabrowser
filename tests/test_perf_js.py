"""Behavioral checks for the browser performance instrumentation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

PERF_TEST_JS = Path(__file__).resolve().parent / "dom" / "perf-behavior.js"


def test_perf_js_assertions_pass() -> None:
    require_node()
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
