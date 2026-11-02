"""Wrappers for the diff plugin's DOM behavior suites.

The model suite runs the same conformance corpus as the Python tests —
the agreement mechanism between the two implementations. The view suite
is deliberately lighter: rendering only projects a model the corpus and
the CLI goldens already pin.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
DOM_DIR = Path(__file__).resolve().parent / "dom"


def _run(script: str, marker: str) -> None:
    require_node()
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
    _run("diff-model-behavior.js", "diff model OK")


def test_diff_view_projects_the_model() -> None:
    _run("diff-view-behavior.js", "diff view OK")


def test_what_the_view_says_split_needs_is_what_the_stylesheet_says() -> None:
    """The width below which a diff falls back to Unified is the stylesheet's, in ems."""

    plugin = REPO_ROOT / "src/metabrowser/builtin_plugins/diff"
    styles = (plugin / "styles.css").read_text(encoding="utf-8")
    source = (plugin / "diff-view.js").read_text(encoding="utf-8")
    stated = re.search(r"\.diff-hunk-split \{\s*min-width: (\d+)em;", styles)
    assert stated is not None
    assert f"export const SPLIT_MIN_WIDTH_EM = {stated.group(1)};" in source
    # A column's own minimum is what makes the hunk's the one that overflows first.
    columns = re.search(r"minmax\((\d+)em, 1fr\) minmax\(\1em, 1fr\)", styles)
    assert columns is not None and 2 * int(columns.group(1)) <= int(stated.group(1))
    # A file body's border is the rest of the width it takes.
    assert re.search(r"\.diff-file \{[^}]*border: 1px solid", styles)
    assert "const FILE_BORDER_PX = 2;" in source


def test_diff_syntax_builds_independent_side_streams() -> None:
    _run("diff-syntax-behavior.js", "diff syntax OK")


def test_diff_intraline_refines_changed_runs() -> None:
    _run("diff-intraline-behavior.js", "diff intraline OK")


def test_diff_render_model_caches_progressive_refinement() -> None:
    _run("diff-render-model-behavior.js", "diff render model OK")


def test_diff_view_file_decides_sides_addresses_and_switches() -> None:
    _run("diff-view-file-behavior.js", "diff view file OK")
