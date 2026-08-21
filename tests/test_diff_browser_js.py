"""Wrappers for the diff plugin's DOM behavior suites.

The model suite runs the same conformance corpus as the Python tests —
the agreement mechanism between the two implementations. The view suite
is deliberately lighter: rendering only projects a model the corpus and
the CLI goldens already pin.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOM_DIR = Path(__file__).resolve().parent / "dom"


def _run(script: str, marker: str) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(DOM_DIR / script), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert marker in result.stdout


def test_diff_model_agrees_with_the_corpus() -> None:
    _run("diff_model_behavior.js", "diff model OK")


def test_diff_view_projects_the_model() -> None:
    _run("diff_view_behavior.js", "diff view OK")
