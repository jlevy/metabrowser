"""Behavioral coverage for the public live directory-totals store."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "directory_totals_store_behavior.js"


def test_directory_totals_store_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping directory totals store behavior")
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
