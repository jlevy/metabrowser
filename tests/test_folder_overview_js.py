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


def test_the_readme_card_fills_the_same_column_as_every_other_panel() -> None:
    """The README's visible card is main content, not a card floating in one.

    Three things had to line up. The document body was the one body no width
    rule named, so it ran the full width of the pane. KPress's article frame
    reserves 2rem per side for a floating table-of-contents control that the
    Overview turns off. And the wide column was built as the prose measure plus
    an inset per side, so even once placed, the card sat 2.5rem inside the
    column the other panels filled.

    What is deliberately *not* here: any rule touching the padding between the
    card's border and its text. That padding is KPress's, it varies with width,
    and recomputing it here is what once flattened the text against the box.
    """

    css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )

    # Every rule that sizes a surface body must also name the document body, or
    # the README drifts out of the column at that breakpoint alone.
    sized = 0
    for block in css.split("}"):
        if ".folder-overview-panel-surface > .folder-overview-panel-body" in block:
            assert ".folder-overview-panel-document > .folder-overview-panel-body" in block, block
            sized += 1
    # Base, narrow container, and wide container.
    assert sized == 3

    # The wide column is the measure itself, so the card fills it rather than
    # floating inside it with a gutter the other panels do not have.
    assert "--folder-overview-wide-card-width: var(--kpress-measure);" in css
    assert "--folder-overview-wide-prose-inset" not in css

    # The single KPress override drops the reservation for a control the
    # Overview does not render. Anything touching the prose is out of bounds.
    kpress_rules = [
        line.strip()
        for line in css.splitlines()
        if line.strip().startswith(".") and "kpress" in line.strip()
    ]
    assert kpress_rules == [
        ".folder-overview-panel-document > .folder-overview-panel-body > .kpress {"
    ], kpress_rules
    assert ".kpress-prose" not in css
    assert ".kpress-doc-layout" not in css


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
