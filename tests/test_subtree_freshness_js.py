"""Lazy and collapsed folder rows remain coherent with live filesystem events."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_subtree_freshness_after_live_changes() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    shim = Path(__file__).parent / "dom" / "subtree-freshness-behavior.js"
    result = subprocess.run(
        ["node", str(shim)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "subtree freshness OK" in result.stdout
