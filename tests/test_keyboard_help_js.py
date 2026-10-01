"""DOM checks for Help and contextual shortcut chrome."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

HELP_TEST_JS = Path(__file__).resolve().parent / "dom" / "keyboard-help-behavior.js"


def test_keyboard_help_js_assertions_pass() -> None:
    require_node()
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
