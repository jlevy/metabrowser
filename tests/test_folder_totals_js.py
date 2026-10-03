"""Shared Overview/treemap folder totals model behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "folder-totals-model-behavior.js"


def test_folder_totals_model_behavior() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
