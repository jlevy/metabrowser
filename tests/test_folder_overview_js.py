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


def test_folder_overview_preserves_the_responsive_markdown_card() -> None:
    css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )

    assert ".folder-overview-panel-heading" in css
    assert "var(--kpress-measure)" in css
    assert "@container (max-width: 47.99rem)" in css
    assert "@container (min-width: 75rem)" in css
    assert "--folder-overview-narrow-document-gutter: 1.25rem" in css
    assert "--folder-overview-regular-card-width" in css
    assert "calc(100% - 4rem)" in css
    assert "calc(var(--kpress-measure) - 2rem)" in css
    assert "width: var(--folder-overview-regular-card-width);" in css
    assert "--folder-overview-wide-card-width" in css
    assert ".kpress-long-text" not in css
    assert "border: none" not in css
    assert "box-shadow: none" not in css


def test_folder_overview_uses_the_shared_section_disclosure() -> None:
    overview_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    core_css = (REPO_ROOT / "src/metabrowser/static/styles.css").read_text(encoding="utf-8")

    assert ".folder-overview-panel-toggle" in overview_css
    assert ".section-disclosure-trigger::after" in core_css
    assert '.section-disclosure-trigger[aria-expanded="true"]::after' in core_css
    assert "var(--section-disclosure-chevron-color)" in core_css
    assert "var(--section-disclosure-chevron-size)" in core_css


def test_folder_headers_share_the_tight_divider_spacing_token() -> None:
    overview_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    core_css = (REPO_ROOT / "src/metabrowser/static/styles.css").read_text(encoding="utf-8")

    assert "--section-heading-divider-gap: 5px" in core_css
    assert "padding: 0 0 var(--section-heading-divider-gap)" in overview_css
