"""Segmented folder totals DOM behavior."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR = REPO_ROOT / "tests" / "dom" / "folder-totals-view-behavior.js"


def test_folder_totals_view_behavior() -> None:
    """The Files and Ignored rows render independent full-width compositions."""
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping folder totals view behavior")
    result = subprocess.run(
        ["node", str(BEHAVIOR), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"folder totals view behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
