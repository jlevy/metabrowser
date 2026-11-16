"""A pull request's Conversation timeline, laid out and painted by headless Chrome.

A commit row is set in a card head's type and sits in its row as a card head's text sits
in its card, a run of commits stands at least as far from the cards around it as one
commit's glyphs stand from the next's, and one line joins every two adjacent events, with a node on it at each
commit (docs/design-system.md, "The Pull Request Page", "Conversation Timeline"). Sizes
resolved through the cascade, boxes, and what is painted where are layout and paint,
which no browserless DOM computes, so ``tests/dom/github-pull-timeline-chrome.mjs`` mounts
the production page module on a recorded record in a real engine and reads them, in both
places the page puts commits.

Before the timeline line, in Chrome 152 on a Mac: a commit row was set at 12 px against a
card head's 14 px, its glyphs sat 13 px below the event above where a card head's sat 16,
1 px under its row's top and 6 px over its bottom, and nothing joined the events. Before the
avatar's slot, a card head whose author had no avatar started its name 22 px left of the
commits' subjects.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_text_chrome import _kpress_static  # pyright: ignore[reportPrivateUsage]

SESSION = Path(__file__).resolve().parent / "dom" / "github-pull-timeline-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the five layouts took under 3 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's files;
# tests/test_process_group.py holds the sum under the module's timeout.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_commits_and_cards_share_one_type_and_one_line_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
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
            "KPRESS_SHEETS": json.dumps(sheets),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"pull timeline in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
