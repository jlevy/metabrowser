"""DOM checks for the browser's accessible quick-file palette."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

SEARCH_PALETTE_TEST_JS = Path(__file__).resolve().parent / "dom" / "search-palette-behavior.js"


def test_search_palette_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(SEARCH_PALETTE_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"search-palette assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
