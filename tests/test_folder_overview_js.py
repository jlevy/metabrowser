"""Composition and lifecycle checks for the folder Overview registry consumer."""

from __future__ import annotations

import re
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


def _overview_rules() -> str:
    """The Overview stylesheet with comments removed.

    Every check in this module is about what the rules do. The comments name
    the KPress classes they are reasoning about, and matching those mentions
    would fail a stylesheet that explains itself.
    """

    css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def test_folder_overview_preserves_the_responsive_markdown_card() -> None:
    css = _overview_rules()

    assert ".folder-overview-panel-heading" in css
    assert "var(--kpress-measure)" in css
    assert "@container kpress-doc (max-width: 47.99rem)" in css
    assert "@container kpress-doc (min-width: 75rem)" in css
    assert "--folder-overview-narrow-document-gutter: 0.5rem" in css
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

    Two things had to line up. The document body was the one body no width rule
    named, so it ran the full width of the pane. And KPress's article frame
    reserves 2rem per side for a floating table-of-contents control that the
    Overview turns off.

    A third was fixed the wrong way round and is now corrected. The wide column
    was the prose measure plus an inset per side, which left the card sitting
    inside the column the other panels filled; sizing it to the measure alone
    aligned the card and narrowed the text, because KPress goes on padding the
    prose by 2.5rem for a track it is no longer in. The column is that track —
    measure plus insets — and every panel shares its edge, so the card lines up
    *and* the text reads at the measure. See
    ``test_one_document_surface_has_one_set_of_breakpoints``.

    What is deliberately *not* here: any rule touching the padding between the
    card's border and its text. That padding is KPress's, it varies with width,
    and recomputing it here is what once flattened the text against the box.
    """

    css = _overview_rules()
    # Every rule that sizes a surface body must also name the document body, or
    # the README drifts out of the column at that breakpoint alone.
    sized = 0
    for block in css.split("}"):
        if ".folder-overview-panel-surface > .folder-overview-panel-body" in block:
            assert ".folder-overview-panel-document > .folder-overview-panel-body" in block, block
            sized += 1
    # Base, narrow container, and wide container.
    assert sized == 3

    # The wide column is KPress's content track: the card fills it, and the
    # text inside reads at the measure rather than at the measure minus the
    # insets KPress still applies.
    wide = css[css.index("--folder-overview-wide-card-width:") :][:200]
    assert "var(--kpress-measure)" in wide
    assert "--folder-overview-wide-toc-inset" in wide
    assert "--folder-overview-wide-prose-inset" not in css

    # Overview reaches into KPress in exactly two ways, both of them things
    # KPress itself does in this band: it drops the 2rem reservation for a
    # table-of-contents control it does not render, and it lifts the two
    # reading-measure caps so the column can be the content track. Anything
    # touching the prose — its padding above all — is out of bounds, because
    # that is KPress's and it varies with width.
    kpress_rules = sorted(
        line.strip()
        for line in css.splitlines()
        if line.strip().startswith(".") and "kpress" in line.strip()
    )
    assert kpress_rules == sorted(
        [
            ".folder-overview-panel-document > .folder-overview-panel-body > .kpress {",
            ".folder-overview-panel-document > .folder-overview-panel-body > .kpress,",
            ".folder-overview-panel-document .kpress-doc-layout {",
        ]
    ), kpress_rules
    assert ".kpress-prose" not in css
    assert ".kpress-long-text" not in css


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
