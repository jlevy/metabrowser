"""Run the complete browser keyboard contract suite under Node."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

DOM_DIR = Path(__file__).resolve().parent / "dom"
SUITES = (
    "keyboard_shortcuts_behavior.js",
    "overlay_layer_behavior.js",
    "keyboard_help_behavior.js",
    "tree_keyboard_navigation_behavior.js",
)


def test_browser_keyboard_contract_suites_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")

    failures = []
    for suite in SUITES:
        result = subprocess.run(
            ["node", str(DOM_DIR / suite)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.startswith("OK"):
            failures.append(
                f"{suite}: returncode={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )

    assert not failures, "\n".join(failures)
