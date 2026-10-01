"""Behavioral checks for the shell's data-path selector escaping."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

PATH_SELECTOR_TEST_JS = Path(__file__).resolve().parent / "dom" / "path-selector-escaping.js"


def test_path_selector_escaping_round_trips() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(PATH_SELECTOR_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"path selector escaping failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "path selector escaping OK" in result.stdout
