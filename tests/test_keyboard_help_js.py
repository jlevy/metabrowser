"""DOM checks for Help and contextual shortcut chrome."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HELP_TEST_JS = Path(__file__).resolve().parent / "dom" / "keyboard_help_behavior.js"


def test_keyboard_help_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(HELP_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"keyboard-help assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
