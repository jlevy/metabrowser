"""Shared folder rollup projection behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR = REPO_ROOT / "tests" / "dom" / "folder-rollup-projection-behavior.js"


def test_folder_rollup_projection_behavior() -> None:
    """Overview consumers share one lifecycle-bound normalized projection."""
    require_node()
    result = subprocess.run(
        ["node", str(BEHAVIOR), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
