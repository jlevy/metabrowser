"""Behavioral checks for the folder built-in plugin (views + treemap)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_TEST_JS = Path(__file__).resolve().parent / "dom" / "folder_plugin_behavior.js"


def test_folder_plugin_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(PLUGIN_TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"folder plugin behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "folder plugin OK" in result.stdout
