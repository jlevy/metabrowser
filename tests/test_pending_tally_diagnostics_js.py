"""Behavioral checks for the pending-tally diagnostic watchdog."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

WATCHDOG_TEST_JS = Path(__file__).resolve().parent / "dom" / "pending_tally_diagnostics_behavior.js"


def test_pending_tally_diagnostics_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(WATCHDOG_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "pending tally diagnostics assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
