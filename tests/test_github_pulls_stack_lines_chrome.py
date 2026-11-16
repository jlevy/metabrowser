"""Each stack heading's brief change line in the Pulls tab, laid out by headless Chrome.

What a heading shows, and when, is browserless (``tests/dom/github-pulls-stack-lines-session.js``);
what only a browser can tell is held here: that nothing moves when the line arrives, that
the heading stays one line at every pane width from 420 px to the 180 px minimum in both
themes, its line whole, its statuses cut short, or out of view, and that the line's inks
and weights are the component's (``tests/dom/github-pulls-stack-lines-chrome.mjs``).
``METABROWSER_STACK_LINES_MEASURED`` names a file for what it measured, and
``METABROWSER_STACK_LINES_SHOTS`` a directory for a screenshot of each width and theme.

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
    LAUNCH_TIMEOUT_S,
    _kpress_faces,  # pyright: ignore[reportPrivateUsage]
)

SESSION = Path(__file__).resolve().parent / "dom" / "github-pulls-stack-lines-chrome.mjs"
# Sixteen mounts, eight widths in two themes, each a mount, a wait past the quiet period,
# and an arrival. On a Mac at a load average of 11 to 16 the session took 6 to 9 s after
# Chrome's start; this is a cold start's bound and that six times over.
SESSION_TIMEOUT_S = LAUNCH_TIMEOUT_S + 40
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_stack_headings_change_line_arrives_in_place_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    measured = os.environ.get("METABROWSER_STACK_LINES_MEASURED")
    shots = os.environ.get("METABROWSER_STACK_LINES_SHOTS")
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={
            **os.environ,
            "CHROME_BIN": chrome,
            "CHROME_PROFILES": str(chrome_profile),
            "KPRESS_STATIC": str(_kpress_faces(tmp_path / "kpress")),
            **({"MEASURE_OUT": measured} if measured else {}),
            **({"SHOTS_DIR": shots} if shots else {}),
        },
    )
    if result.timed_out:
        pytest.fail(f"ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"stack lines in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
