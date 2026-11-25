"""A rendered Markdown diff's fold of unchanged blocks, laid out by headless Chrome.

Every fold of a diff draws as one bar (docs/design-system.md, "Fold Expanders"): a
rendered Markdown file's run of unchanged blocks folds behind the bar a code file's long
run of changed lines does, the same element and classes (``foldExpander`` in
``builtin_plugins/diff/diff-fold.js``), so it must also compute the same, at rest and
under the pointer, across its file's width. Closed, the bar stands between the blocks
around it; open, the blocks it held stand after it in the face, measure, and spacing of
the unchanged blocks around them, the bar does not move, and everything after it moves by
one amount; closed again, the layout is as it was. The bar is a ``button`` inside the
comparison's ``article.kpress``, so KPress's document stylesheets reach it, and only a
browser computes that cascade and the boxes it draws. So
``tests/dom/diff-markdown-fold-chrome.mjs`` mounts the route's Concise answer for a
document with a long unchanged run through the production ``createMarkdownViews``, beside
a code file's fold bar, and measures both.

Before the group of a Markdown fold clipped with ``overflow: clip``, the code fold's
``overflow: hidden`` started a formatting context there and kept the last block's margin
inside the open group, adding it to the next block's: 24 px from the last block the fold
holds to the paragraph after it, where the document has 12.

The session then draws a comparison of a quote holding inline code and of a code block
beside a document holding the same blocks, and holds, in the light and the dark theme,
that the comparison's quote rule, quoted text, and code edges, corners, padding, and
colors are the document's, in the app's border and muted tokens. The comparison's
article is outside ``.metabrowser-kpress-host``; while the token bridge in
``static/styles.css`` was keyed on that host, KPress 0.3.8 drew the comparison's quote
rule and muted text in its own palette, and on 0.3.6 its quote had no rule at all.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``FOLD_SHOTS`` in the environment names a directory for a screenshot closed and open.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github.pull_rendered_diff import (
    _kept,  # pyright: ignore[reportPrivateUsage]
    _view_answer,  # pyright: ignore[reportPrivateUsage]
)
from metabrowser.diff.markdown_projection import project_markdown_diff
from metabrowser.settings import DOC_MAX_CHARS_DEFAULT
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_text_chrome import _kpress_static  # pyright: ignore[reportPrivateUsage]
from tests.test_markdown_diff_projection import _patch  # pyright: ignore[reportPrivateUsage]

SESSION = Path(__file__).resolve().parent / "dom" / "diff-markdown-fold-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the projection and the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

# An edit at each end of a run of ten unchanged paragraphs, so the run keeps two blocks
# beside each edit and folds the six between them, short enough to come with the answer.
_OLD = (
    b"# Guide\n\nThe old opening line.\n\n"
    + b"".join(b"Unchanged paragraph %d.\n\n" % index for index in range(10))
    + b"The old closing line.\n"
)
_NEW = _OLD.replace(b"old opening", b"new opening").replace(b"old closing", b"new closing")
# A quote holding inline code and a code block, unchanged beside one edit, so they stand
# as context rows outside any fold.
_QUOTED_OLD = b"> Quoted text with `inline code`.\n\n```\nmake test\n```\n\nThe old line.\n"
_QUOTED_NEW = _QUOTED_OLD.replace(b"old line", b"new line")


def test_a_markdown_fold_is_the_diffs_fold_bar_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    projection = dict(
        project_markdown_diff(
            old=_OLD, new=_NEW, patch=_patch(_OLD, _NEW), namespace="comparison/docs/guide.md"
        )
    )
    assert projection["status"] == "ready"
    answer = json.loads(_view_answer(_kept(projection), "concise"))
    assert [(fold["count"], "withheld" in fold) for fold in answer["folds"]] == [(6, False)]
    quoted = dict(
        project_markdown_diff(
            old=_QUOTED_OLD,
            new=_QUOTED_NEW,
            patch=_patch(_QUOTED_OLD, _QUOTED_NEW),
            namespace="comparison/docs/quoted.md",
        )
    )
    assert quoted["status"] == "ready"
    fold_input = tmp_path / "input.json"
    fold_input.write_text(
        json.dumps(
            {
                "sheets": sheets,
                "answer": answer,
                "quoted": quoted["blocks"],
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
            "FOLD_INPUT": str(fold_input),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"diff fold in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
