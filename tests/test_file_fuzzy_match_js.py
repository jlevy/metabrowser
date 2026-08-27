"""Golden behavioral checks for the browser's fuzzy file matcher."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FILE_FUZZY_MATCH_TEST_JS = Path(__file__).resolve().parent / "dom" / "file-fuzzy-match-behavior.js"
FILE_FUZZY_MATCH_PROFILE_JS = (
    Path(__file__).resolve().parent / "dom" / "file-fuzzy-match-profile.js"
)


def test_file_fuzzy_match_js_assertions_pass() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(FILE_FUZZY_MATCH_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "fuzzy-file matcher assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"


def test_file_fuzzy_match_public_profile_completes() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(FILE_FUZZY_MATCH_PROFILE_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"fuzzy-file matcher profile failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("PROFILE "), f"unexpected stdout: {result.stdout!r}"
