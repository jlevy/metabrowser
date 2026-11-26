"""A diff's file bars, laid out by headless Chrome at widths from 1,063 px down to 171 px.

Where a bar's parts go as it narrows is layout: which part gives way, which moves to the
next line, and whether anything ends past the bar's edge. No browserless DOM computes it,
and the stylesheet's text passed while View on branch, moved beside the name, took the
name's room on a bar with a Rendered | Source chooser and ran 16 px past a 159 px bar
(review A of #759, A1). ``tests/dom/diff-file-bar-chrome.mjs`` draws the bars
``renderFileBar`` builds, under the shell's and the diff plugin's stylesheets and KPress's
faces, and holds at every width that no part is cut off or covers another, that a bar with
a chooser cuts its name only on a line of its own, that one without cuts a long name on
one line down to ``--diff-file-lead-basis`` and then moves View file to the next line, and
that at rest the stats read with the name rather than with View file (A4).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``BAR_SHOTS`` in the environment names a directory for a screenshot at each width.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_text_chrome import _kpress_static  # pyright: ignore[reportPrivateUsage]

SESSION = Path(__file__).resolve().parent / "dom" / "diff-file-bar-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the six widths took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_diff_file_bar_cuts_off_nothing_from_1063_to_171_px_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    _kpress_static(tmp_path / "kpress")
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
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"diff file bar in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
