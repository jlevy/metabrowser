"""DOM checks for the shared keyboard shortcut registry."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.required_tools import require_node

DOM_TESTS = Path(__file__).resolve().parent / "dom"


@pytest.mark.parametrize(
    "script", ["keyboard-shortcuts-behavior.js", "native-history-shortcuts.js"]
)
def test_keyboard_shortcut_js_assertions_pass(script: str) -> None:
    require_node()
    result = subprocess.run(
        ["node", str(DOM_TESTS / script)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"keyboard-shortcut assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
