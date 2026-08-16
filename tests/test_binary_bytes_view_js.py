"""Mount, append, restart, and disposal contracts for the Bytes view."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "binary_bytes_view_behavior.js"


def test_binary_bytes_view_lifecycle() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--experimental-vm-modules", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Binary bytes view lifecycle failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "binary bytes view OK" in result.stdout
