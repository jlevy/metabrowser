"""DOM checks for the shared keyboard shortcut registry."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SHORTCUT_TEST_JS = Path(__file__).resolve().parent / "dom" / "keyboard_shortcuts_behavior.js"


def test_keyboard_shortcut_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SHORTCUT_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"keyboard-shortcut assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
