"""Lazy and collapsed folder rows remain coherent with live filesystem events."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node


def test_subtree_freshness_after_live_changes() -> None:
    require_node()
    shim = Path(__file__).parent / "dom" / "subtree-freshness-behavior.js"
    result = subprocess.run(
        ["node", str(shim)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "subtree freshness OK" in result.stdout
