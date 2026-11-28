"""A changed YAML or JSON file's Rendered tree, laid out and timed by headless Chrome.

``tests/dom/diff-structured-chrome.mjs`` draws merged trees through the production
``mountStructuredDiff`` (``builtin_plugins/diff/diff-structured.js``) and the structured
renderer’s preview and tree scripts, under the shell’s, the shared tree’s and
the diff plugin's stylesheets, in a pull request's diff host. Only a browser computes
what it holds:

- A changed value's row wraps, so a long changed string shows where it changed, while an
  unchanged row and a container's row keep the file view's one clipped line. Before the
  rule in ``builtin_plugins/diff/styles.css``, a removed and an added string that differ
  past the clip drew as two rows reading the same (C8 of mb-8274 review).
- A first draw stays within ``ROW_BUDGET`` rows on the shapes review A5 timed at the
  projection's node budget; a whole value's root past the file view's threshold opens on
  a click, a page at a time; and a click draws again only the rows it changes, so the
  rows it keeps are the elements they were.
- The note above a ``source_only`` tree is the app's muted chrome.

Each shape's mount and click times are printed with the case's output. With
``STRUCTURED_SWEEP=1`` the session times drawing the first N rows of four row shapes,
the measurement ``ROW_BUDGET`` and ``PAGE`` record (run it by hand; see the session).

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from metabrowser.settings import DOC_MAX_CHARS_DEFAULT
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "diff-structured-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the session itself took 3 to 6 s on a 10-core Mac at a load
# average of 20 to 30.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py).
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_structured_diff_wraps_changes_and_bounds_its_draw_in_chrome(
    chrome_profile: Path,
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
            "STRUCTURED_SWEEP": "",
            "DOC_MAX_CHARS": str(DOC_MAX_CHARS_DEFAULT),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"structured diff in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
