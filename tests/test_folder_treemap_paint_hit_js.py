"""Invariants of the folder plugin's treemap paint list, mark ops, and hit grid."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
BEHAVIOR_JS = Path(__file__).resolve().parent / "dom" / "treemap-paint-hit-behavior.js"


def test_treemap_paint_and_hit_behavior() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(BEHAVIOR_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"treemap paint and hit behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "treemap paint and hit OK" in result.stdout
