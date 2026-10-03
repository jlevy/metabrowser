"""Behavioral checks for the pending-tally diagnostic watchdog."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

WATCHDOG_TEST_JS = Path(__file__).resolve().parent / "dom" / "pending-tally-diagnostics-behavior.js"


def test_pending_tally_diagnostics_js_assertions_pass() -> None:
    require_node()
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
