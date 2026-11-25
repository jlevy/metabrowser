"""A code diff's hunk gaps, laid out by headless Chrome, and the place opening one keeps.

A hunk's ``@@`` separator in a code file is the diff's fold bar, the one a long run of
changed lines folds behind, with the separator kept beside its label, and it opens to the
unchanged lines between hunks (docs/design-system.md, "Fold Expanders"). What each bar
holds, what it asks the route for, and the rows it draws are the browserless session's
(``tests/dom/diff-hunk-gap-session.js``, ``tests/golden/cli-ui-diff-hunk-gap.tryscript.md``);
how it computes beside the changed run's bar, at rest, under the pointer, and under the
keyboard's ring, whether its separator gives way at a narrow width, and where the reader's
row lands while the browser's scroll anchoring and the group's height transition run
beside the diff's own place-keeping are the browser's. So
``tests/dom/diff-hunk-gap-chrome.mjs`` mounts a comparison with two hunks and a long
changed run through the production ``mountDiffView``, with a gap loader answering in the
page, and measures both.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``GAP_SHOTS`` in the environment names a directory for a screenshot closed, open, and
narrow.
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

SESSION = Path(__file__).resolve().parent / "dom" / "diff-hunk-gap-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the session's five pages took under 15 s on a Mac at a load
# average near 200.
SESSION_TIMEOUT_S = 60
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_hunk_gap_is_the_diffs_fold_bar_and_keeps_the_place_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    gap_input = tmp_path / "input.json"
    gap_input.write_text(json.dumps({"sheets": sheets}), encoding="utf-8")
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
            "GAP_INPUT": str(gap_input),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"diff hunk gap in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
