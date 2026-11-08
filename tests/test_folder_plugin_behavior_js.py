"""Behavioral checks for the folder built-in plugin (views + treemap)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = Path(__file__).resolve().parent / "dom"


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        ("folder-plugin-behavior.js", "folder plugin OK"),
        ("treemap-not-indexed-session.js", '"rollupResources": 0'),
    ],
)
def test_folder_plugin_behavior(session: str, expected: str) -> None:
    require_node()
    result = subprocess.run(
        ["node", str(SESSION_DIR / session), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"folder plugin behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert expected in result.stdout
