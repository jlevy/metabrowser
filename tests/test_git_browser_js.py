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


def test_selected_row_marker_fill_is_ordered_after_the_hover_rule() -> None:
    """The hollow HEAD and merge markers must track the row background.

    ``.git-graph-row.selected`` and ``.git-graph-row:hover`` carry equal
    specificity, so on a row that is both, source order alone decides the
    winner. The marker fill has to resolve the same way the row's own
    background does, or a selected row shows a sidebar-coloured disc
    inside the ring that is supposed to be hollow.
    """
    css = (Path(__file__).resolve().parents[1] / "src/metabrowser/static/styles.css").read_text()
    marker = ".git-graph-svg > circle"
    hover = css.index(f".git-graph-row:hover {marker}")
    selected = css.index(f".git-graph-row.selected {marker}")
    assert hover < selected, "the selected marker rule must come after the hover rule"

    # The fill must be the same token the selected row background uses.
    row_selected = css.index(".git-graph-row.selected {")
    assert "var(--highlight-bg)" in css[row_selected : css.index("}", row_selected)]
    assert "var(--highlight-bg)" in css[selected : css.index("}", selected)]
