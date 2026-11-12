"""Behavioral checks for the staged view's wait on the faces its text is set in."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

STAGED_FONTS_TEST_JS = Path(__file__).resolve().parent / "dom" / "staged-fonts-behavior.js"


def test_staged_fonts_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(STAGED_FONTS_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"staged font assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
