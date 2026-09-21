"""Behavioral checks for the shell's tree-row name spelling."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TREE_NODE_NAME_TEST_JS = Path(__file__).resolve().parent / "dom" / "tree-node-name-behavior.js"


def test_tree_row_names_follow_the_served_source_kind() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(TREE_NODE_NAME_TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"tree node name behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "tree node name OK" in result.stdout
