"""Composition and lifecycle checks for the folder Overview registry consumer."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "folder-overview-behavior.js"


def test_folder_overview_composer() -> None:
    require_node()
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

    assert "var(--doc-measure)" in css
    assert "calc(var(--doc-measure) + 2 * var(--folder-overview-column-inset))" in css
    assert "@container kpress-doc (min-width: 48rem)" in css
    assert "--folder-overview-column-inset: calc(var(--pane-header-padding-x) - 1px)" in css
    assert ".kpress-long-text" not in css
    assert "border: none" not in css
    assert "box-shadow: none" not in css


def test_the_readme_card_fills_the_same_column_as_every_other_panel() -> None:
    """Every panel shares the README card edge and the normal pane text gutter."""

    css = _overview_rules()
    width_rule = next(
        block for block in css.split("}") if "width: var(--folder-overview-card-width)" in block
    )
    for selector in (
        ".folder-overview-panel-surface > .folder-overview-panel-heading",
        ".folder-overview-panel-surface > .folder-overview-panel-body",
        ".folder-overview-panel-document > .folder-overview-panel-heading",
        ".folder-overview-panel-document > .folder-overview-panel-body",
    ):
        assert selector in width_rule
    assert "margin-inline-start: 0" in width_rule
    assert "margin-inline-end: auto" in width_rule
    assert "padding-inline: var(--pane-header-padding-x)" in css
    assert ".kpress-prose" not in css
    assert ".kpress-long-text" not in css
    assert "toc-width" not in css
    rendered = (REPO_ROOT / "src/metabrowser/builtin_plugins/markdown/rendered.js").read_text(
        encoding="utf-8"
    )
    assert (
        'container.classList.add("metabrowser-kpress-host", "metabrowser-markdown-document")'
        in rendered
    )


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
    # The heading's type and rule are the shared primitive; only its space below is local.
    assert "padding: 0 0 var(--section-heading-divider-gap)" in core_css
    assert "--section-heading-divider-gap" not in overview_css
