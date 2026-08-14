"""Behavioral checks for the keyed File types distribution renderer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve().parent / "dom" / "file_type_summary_behavior.js"


def test_file_type_summary_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node is unavailable")
    result = subprocess.run(
        ["node", str(SCRIPT), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "file type summary OK" in result.stdout
