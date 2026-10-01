"""Run the complete browser keyboard contract suite under Node."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

DOM_DIR = Path(__file__).resolve().parent / "dom"
SUITES = (
    "keyboard-shortcuts-behavior.js",
    "overlay-layer-behavior.js",
    "keyboard-help-behavior.js",
    "tree-keyboard-navigation-behavior.js",
)


def test_browser_keyboard_contract_suites_pass() -> None:
    require_node()

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
