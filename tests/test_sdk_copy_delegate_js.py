"""Behavioral checks for the SDK-owned copy delegate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

COPY_DELEGATE_TEST_JS = Path(__file__).resolve().parent / "dom" / "sdk_copy_delegate_behavior.js"


def test_sdk_copy_delegate_behavior() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(COPY_DELEGATE_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"copy delegate behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "sdk copy delegate OK" in result.stdout
