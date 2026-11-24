"""The space between a rendered Markdown diff's blocks, laid out by headless Chrome.

A rendered diff is the document it compares, so a reader who opens a Markdown file's
Document view and then its pull request's Changes or Docs reads one rhythm: the distance
from one block's text to the next block's is the Document view's, between unchanged
blocks, between changed ones, and with the removed blocks hidden, as Current shows the new
version alone. Each block of the diff is a row of its own, so the space between them is
margin collapsing across rows, which only a browser computes. So
``tests/dom/diff-markdown-spacing-chrome.mjs`` builds the server's projection of a change
to a document holding every heading level, paragraphs, lists, a quote, and a code block
through the production ``appendBlocks`` and ``sanitizeBlock``, sets KPress's render of
each version in a Document view's frame beside it, and measures both.

Before the rows let their blocks' margins collapse (mb-6d1s), each row padded 4 px above
and below its block and kept the block's margins inside it, so two blocks' margins added
up and the rows' padding with them: 52 px from a paragraph to an h2 where the document
has 32, 36 px from an h2 to its paragraph where the document has 16, and 32 px between
two paragraphs where it has 12. The table of before and after is in
``explorations/performance-loop/design-rule-measurements.md``, "Rendered Diff Block
Spacing".

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``SPACING_SHOTS`` in the environment names a directory for screenshots of the Document
view and the diff of the same text.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from metabrowser import kpress_adapter
from metabrowser.diff.markdown_projection import project_markdown_diff
from metabrowser.inert_html import harden
from metabrowser.settings import DOC_MAX_CHARS_DEFAULT
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_text_chrome import _kpress_static  # pyright: ignore[reportPrivateUsage]
from tests.test_markdown_diff_projection import _patch  # pyright: ignore[reportPrivateUsage]

SESSION = Path(__file__).resolve().parent / "dom" / "diff-markdown-spacing-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the renders and the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# Every heading level after a paragraph and before one, paragraphs, a list, a numbered
# list, a quote, and a code block, unchanged; a removed paragraph; an added paragraph,
# h2, and h3 between unchanged blocks; a list's first and last items edited; and an
# edited paragraph after an h6 and after an h1.
_OLD = b"""# Spacing Guide

The opening paragraph sets the scene. It runs long enough to wrap onto a second line in a
reading column of the default width, so its line boxes are a paragraph's.

A second paragraph follows the first, unchanged.

## A Second-Level Heading

A paragraph after the h2, unchanged in both versions.

A paragraph the new version removes.

### A Third-Level Heading

A paragraph after the h3.

- A first list item.
- A second list item.
- A third list item.

A paragraph after the list.

1. A first numbered item.
2. A second numbered item.

A paragraph after the numbered list.

> A quoted paragraph, unchanged.

```
make test
```

A paragraph after the code block.

#### A Fourth-Level Heading

A paragraph after the h4.

##### A Fifth-Level Heading

A paragraph after the h5.

###### A Sixth-Level Heading

A paragraph after the h6.

# A Second Top-Level Heading

A paragraph after the second h1, which the new version edits.

## A Heading Before a Subheading

### A Subheading Straight After It

A paragraph after the subheading.

### A Third-Level Heading After a Paragraph

A paragraph before the last h1.

# A Last Top-Level Heading

The closing paragraph.
"""
_NEW = (
    _OLD.replace(
        b"A paragraph the new version removes.\n",
        b"An added paragraph.\n\n## An Added Second-Level Heading\n\n"
        b"A paragraph after the added h2.\n\n### An Added Third-Level Heading\n\n"
        b"A paragraph after the added h3.\n",
    )
    .replace(b"A first list item.", b"A first list item, edited.")
    .replace(b"A third list item.", b"A third list item, edited.")
    .replace(b"A paragraph after the h6.", b"A paragraph after the h6, edited.")
    .replace(b"which the new version edits", b"which this version has edited")
)


def _rendered(text: bytes, name: str) -> str:
    """KPress's render of *text* as a Document view renders it, hardened."""

    rendered = kpress_adapter.render_kpress_view(
        source_text=text.decode(),
        source_path=f"docs/{name}.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash=f"diff-spacing-{name}",
        size=len(text),
        include_toc="off",
    )
    return harden(str(rendered["html"]), "https://github.com/octo/demo/blob/main/docs/guide.md")


def test_a_rendered_diff_spaces_its_blocks_as_the_document_does_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    projection = project_markdown_diff(
        old=_OLD, new=_NEW, patch=_patch(_OLD, _NEW), namespace="comparison/docs/guide.md"
    )
    assert projection["status"] == "ready"
    kinds = {block["kind"] for block in projection["blocks"]}
    assert kinds == {"context", "added", "removed"}, kinds
    spacing_input = tmp_path / "input.json"
    spacing_input.write_text(
        json.dumps(
            {
                "sheets": sheets,
                "blocks": projection["blocks"],
                "documents": {"old": _rendered(_OLD, "old"), "new": _rendered(_NEW, "new")},
                "docMaxChars": DOC_MAX_CHARS_DEFAULT,
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
    passed = re.fullmatch(r"diff spacing in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
