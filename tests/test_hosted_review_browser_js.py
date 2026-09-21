from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve().parent / "dom" / "hosted-review-model-behavior.js"


def test_browser_change_request_model_agrees_with_the_portable_corpus() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")

    result = subprocess.run(
        ["node", str(SCRIPT), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        f"hosted-review model failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "hosted review model OK" in result.stdout
