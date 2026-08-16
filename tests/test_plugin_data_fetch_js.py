"""Contracts for the SDK's ``fetchPluginData`` helper.

A data hook that explains a refusal in its response body is only useful if
the caller can read it, so a non-ok response must reach the plugin with its
status and parsed body attached. A view that is disposed mid-request must be
able to abort it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "plugin_data_fetch_behavior.js"


def test_fetch_plugin_data_contracts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"fetchPluginData contracts failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "plugin data fetch OK" in result.stdout
