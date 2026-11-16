"""A rendered Markdown diff's fold of unchanged blocks, laid out by headless Chrome.

A fold is a place in the document, not a box in it: closed, it is one quiet line between
the blocks around it, with no border, background, or margin; open, the blocks it held
stand in place, in the face, measure, and spacing of the unchanged blocks around them,
and nothing else moves; closed again, the layout is as it was. The fold is a
``<details>`` inside the comparison's ``article.kpress``, so KPress's document disclosure
box reached it, and only a browser computes that cascade and the boxes it draws. So
``tests/dom/diff-markdown-fold-chrome.mjs`` builds the server's projection of a document
with a long unchanged run through the production ``appendBlocks`` and ``sanitizeBlock``
and measures it. A document's own ``<details>`` keeps KPress's box beside it.

Before the fold's rule in ``builtin_plugins/diff/styles.css``, it drew KPress's 1px
border and 12px block margins, and opening it drew a rule under its summary, moving the
blocks after it 1px further than the blocks it inserted.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``FOLD_SHOTS`` in the environment names a directory for a screenshot closed and open.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from metabrowser.diff.markdown_projection import project_markdown_diff
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
# beside each edit and folds the six between them.
_OLD = (
    b"# Guide\n\nThe old opening line.\n\n"
    + b"".join(b"Unchanged paragraph %d.\n\n" % index for index in range(10))
    + b"The old closing line.\n"
)
_NEW = _OLD.replace(b"old opening", b"new opening").replace(b"old closing", b"new closing")


def test_a_fold_expands_in_place_without_a_box_in_chrome(
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
    fold_input = tmp_path / "input.json"
    fold_input.write_text(
        json.dumps({"sheets": sheets, "blocks": projection["blocks"]}), encoding="utf-8"
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
