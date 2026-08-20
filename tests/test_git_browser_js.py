"""Node-driven checks for the Git graph browser modules.

Both suites run under a ``vm`` sandbox with a fake DOM, matching the
pattern used by ``test_tree_expansion_js.py`` and
``test_file_fuzzy_match_js.py``. The layout suite is the important one:
the swimlane algorithm is a port, and a port that drifts is the failure
mode this whole file exists to catch.

The stylesheet check at the end covers the one graph rule whose
correctness lives in CSS cascade order rather than in either module.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_DOM_DIR = Path(__file__).resolve().parent / "dom"
GIT_GRAPH_TEST_JS = _DOM_DIR / "git_graph_behavior.js"
GIT_PANEL_TEST_JS = _DOM_DIR / "git_panel_behavior.js"


def _run_node_suite(script: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script.name} assertions failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"


def test_git_graph_layout_assertions_pass() -> None:
    _run_node_suite(GIT_GRAPH_TEST_JS)


def test_git_panel_behavior_assertions_pass() -> None:
    _run_node_suite(GIT_PANEL_TEST_JS)


def test_node_markers_do_not_restate_the_row_background() -> None:
    """A node's shape must not depend on the row's state.

    The hollow centre used to be a disc painted with a copy of the row
    background, so every row state had to restate that colour and any
    state that did not left a filled-looking node. The hole is punched
    now (one evenodd path), so the row's own background shows through
    whatever it is — and no stylesheet rule may reintroduce a fill.
    """
    css = (Path(__file__).resolve().parents[1] / "src/metabrowser/static/styles.css").read_text()
    assert ".git-graph-svg > circle" not in css, (
        "a rule filling graph markers reintroduces state-dependent node shapes"
    )
    graph = (
        Path(__file__).resolve().parents[1] / "src/metabrowser/static/git_graph.js"
    ).read_text()
    assert 'setAttribute("fill-rule", "evenodd")' in graph, "the ring must punch a real hole"
