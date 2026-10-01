"""Behavioral checks for the browser tree-expansion budget."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

TREE_EXPANSION_TEST_JS = Path(__file__).resolve().parent / "dom" / "tree-expansion-behavior.js"


def test_tree_expansion_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(TREE_EXPANSION_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"tree expansion assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
