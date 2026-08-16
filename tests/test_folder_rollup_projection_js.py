"""Shared folder rollup projection behavior."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR = REPO_ROOT / "tests" / "dom" / "folder_rollup_projection_behavior.js"


def test_folder_rollup_projection_behavior() -> None:
    """Overview consumers share one lifecycle-bound normalized projection."""
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping rollup projection behavior")
    result = subprocess.run(
        ["node", str(BEHAVIOR), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
