"""Behavioral contracts for canonical browser navigation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_SHIM = Path(__file__).resolve().parent / "dom" / "navigation_route_behavior.js"


def test_navigation_target_url_codec() -> None:
    """The strict route module safely round-trips one canonical URL shape."""

    if shutil.which("node") is None:
        pytest.skip("node not available; skipping navigation route behavioral shim")

    result = subprocess.run(
        ["node", str(ROUTE_SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "navigation route behavioral shim failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
