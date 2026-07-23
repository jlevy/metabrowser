"""Behavioral checks for the shared FilterState module (nav + views)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FILTER_TEST_JS = Path(__file__).resolve().parent / "dom" / "filter_state_behavior.js"


def test_filter_state_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(FILTER_TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"filter state behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "filter state OK" in result.stdout
