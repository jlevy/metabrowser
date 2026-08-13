"""Composition and lifecycle checks for the folder Overview registry consumer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "folder_overview_behavior.js"


def test_folder_overview_composer() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"folder Overview behavior failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "folder overview OK" in result.stdout


def test_folder_overview_uses_the_flat_markdown_text_measure() -> None:
    css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )

    assert ".folder-overview-panel-heading" in css
    assert "var(--kpress-measure)" in css
    assert "@container (max-width: 47.99rem)" in css
    assert "@container (min-width: 75rem)" in css
    assert ".kpress-long-text.kpress-prose" in css
    assert "border: none" in css
    assert "box-shadow: none" in css
