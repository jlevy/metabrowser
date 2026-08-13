"""Geometry checks for the folder plugin's treemap layout module."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUT_TEST_JS = Path(__file__).resolve().parent / "dom" / "treemap_layout_behavior.js"


def test_treemap_layout_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(LAYOUT_TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"treemap layout behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "treemap layout OK" in result.stdout
