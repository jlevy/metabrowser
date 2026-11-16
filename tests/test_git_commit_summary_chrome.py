"""A commit's page has one Diff summary, at its top, laid out where the design says.

A commit's counts of files and lines are its Diff summary's header, which the commit's diff
draws in the commit summary's place, under its identity and above its description; the
block of ``M``, ``A``, and ``D`` counts and line totals is gone from the page and kept only
in the hover summary, which has no diff (docs/design-system.md, "Git Commit Summary" and
"Diff Summary"; mb-pb35). The markup and the hand-off of the place are browserless
(``tests/dom/git-panel-behavior.js`` and ``tests/dom/diff-view-behavior.js``). Where the
summary lands is layout, which only a browser computes:
``tests/dom/git-commit-summary-chrome.mjs`` draws the page with the Git panel's
``renderCommitSummary`` and the diff plugin's ``mountDiffSummary`` in headless Chrome, from
980 to 320 px, and reads the summary's place, its header's row, its tree opened, and an
empty place.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_header_chrome import (
    _kpress_faces,  # pyright: ignore[reportPrivateUsage]
)

SESSION = Path(__file__).resolve().parent / "dom" / "git-commit-summary-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); every width was drawn and read in under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's faces;
# tests/test_process_group.py holds the sum under the module's timeout.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_commits_diff_summary_is_at_the_top_of_its_page_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    # The session leads a process group of its own, which Chrome joins, and the whole group
    # is stopped however it ends; its profile is the fixture's to remove.
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
            "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
        },
    )
    if result.timed_out:
        pytest.fail(f"ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    # Each step's time, shown with the output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"commit summary in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
