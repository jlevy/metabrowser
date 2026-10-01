"""Run the headless behavioural checks for the filter modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

DOM_DIR = Path(__file__).resolve().parent / "dom"


def _run_node_suite(script: Path, expected_prefix: str) -> None:
    require_node()
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
    _run_node_suite(DOM_DIR / "filter-state-behavior.js", "OK filter state")


def test_filter_controls_js_assertions_pass() -> None:
    _run_node_suite(DOM_DIR / "filter-controls-behavior.js", "OK filter controls")


def test_tree_filter_model_js_assertions_pass() -> None:
    _run_node_suite(DOM_DIR / "tree-filter-model-behavior.js", "OK tree filter model")


def test_recent_filter_session_runs_against_production_modules() -> None:
    _run_node_suite(DOM_DIR / "recent-filter-session.js", '{\n  "request":')
