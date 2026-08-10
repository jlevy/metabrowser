"""Behavioral checks for the browser's locally known file catalog."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

KNOWN_FILE_CATALOG_TEST_JS = (
    Path(__file__).resolve().parent / "dom" / "known_file_catalog_behavior.js"
)


def test_known_file_catalog_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(KNOWN_FILE_CATALOG_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "known-file catalog assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
