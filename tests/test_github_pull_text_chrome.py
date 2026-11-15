"""The space around a heading in a pull request's text, laid out by headless Chrome.

A heading belongs to the section it opens, so it sits nearer what follows it than what
precedes it, and inside a text that space is KPress's, the same as a document's
(docs/design-system.md, "The Pull Request Page", "Text"). Margins and their collapsing are
layout, which no browserless DOM computes, so ``tests/dom/github-pull-text-chrome.mjs``
measures KPress's render of these texts, rebuilt by the production inert path, in the page's
card and in a document's frame.

Before the card's padding was the content inset, a heading that opened a text sat 8 px
under the card head and kept 16 px below it, in Chrome 152 and in WebKit (macOS 26.5)
alike, while the same h2 inside a text had 32 px above it.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from metabrowser import kpress_adapter
from metabrowser.inert_html import harden
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-text-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the render and the copy of KPress's files;
# tests/test_process_group.py holds the sum under the module's timeout.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# Each level after each kind of block a description holds, and an h2 opening it.
DESCRIPTION = "\n\n".join(
    [
        "## Summary",
        "The first paragraph.",
        *(
            part
            for heading in ("##", "#", "###")
            for part in (
                f"{heading} After a paragraph",
                "A paragraph.",
                "- A list item.\n- Another list item.",
                f"{heading} After a list",
                "A paragraph.",
                "```\nmake test\n```",
                f"{heading} After a code block",
                "A paragraph.",
                "> A quoted line.",
                f"{heading} After a blockquote",
                "A paragraph.",
            )
        ),
    ]
)
# A comment and a review opening with the other two levels.
TEXTS = {
    "body": DESCRIPTION,
    "issue_comment/1": "# Opens a comment\n\nA paragraph.",
    "review/2": "### Opens a review\n\nA paragraph.",
}


def _rendered(text: str) -> str:
    """What ``pull_markdown.render_part`` answers for *text*: KPress's render, hardened."""

    rendered = kpress_adapter.render_kpress_view(
        source_text=text,
        source_path="pull-7-text.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash="pull-text-spacing",
        size=len(text.encode()),
        include_toc="off",
    )
    return harden(str(rendered["html"]), "https://github.com/octo/demo/pull/7")


def _kpress_static(into: Path) -> list[str]:
    """KPress's tokens and the faces they name, and the document stylesheets a text loads."""

    sheets = [
        str(asset["path"])
        for asset in kpress_adapter.document_stylesheets()["assets"]
        if asset.get("loading") == "stylesheet"
    ]
    for sheet in {"css/style-tokens.css", *sheets}:
        target = into / sheet
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(kpress_adapter.get_kpress_static_asset(sheet).content)
    tokens = (into / "css" / "style-tokens.css").read_text(encoding="utf-8")
    for relative in sorted(set(re.findall(r'url\("\.\./([^"]+)"\)', tokens))):
        target = into / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(kpress_adapter.get_kpress_static_asset(relative).content)
    return sheets


def test_a_heading_is_nearer_its_section_than_what_precedes_it_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    spacing_input = tmp_path / "input.json"
    spacing_input.write_text(
        json.dumps(
            {
                "sheets": sheets,
                "texts": [{"part": part, "html": _rendered(text)} for part, text in TEXTS.items()],
                "document": _rendered(DESCRIPTION),
            }
        ),
        encoding="utf-8",
    )
    # The session leads a process group of its own, which Chrome joins, and the whole group
    # is stopped however it ends; its profile is the fixture's to remove.
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
            "KPRESS_STATIC": str(tmp_path / "kpress"),
            "SPACING_INPUT": str(spacing_input),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"pull text spacing in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
