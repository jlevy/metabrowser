"""Run the headless behavioural checks for the filter modules."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

DOM_DIR = Path(__file__).resolve().parent / "dom"


def _run_node_suite(script: Path, expected_prefix: str) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script.name} assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith(expected_prefix), f"unexpected stdout: {result.stdout!r}"


def test_filter_state_js_assertions_pass() -> None:
    _run_node_suite(DOM_DIR / "filter_state_behavior.js", "OK filter state")


def test_filter_controls_js_assertions_pass() -> None:
    _run_node_suite(DOM_DIR / "filter_controls_behavior.js", "OK filter controls")


def test_tree_filter_model_js_assertions_pass() -> None:
    _run_node_suite(DOM_DIR / "tree_filter_model_behavior.js", "OK tree filter model")
