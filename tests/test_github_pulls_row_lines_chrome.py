"""Each Pulls row's run and last line laid out by headless Chrome.

What a row's toggle shows, and when, and what a press and each key do, is browserless
(``tests/dom/github-pulls-row-lines-session.js``); what only a browser can tell is held here
(``tests/dom/github-pulls-row-lines-chrome.mjs``): that a row is its run, the state icon, the
title, the number, and the lines with the chevron after them, every line of it in the text
column past the icon and never cut short, and its last line, the author with the age at its end
(mb-pw8t); that a closed row is ``ROW_ESTIMATE_PX`` tall with a run of three lines; that nothing
but the chevron moves when the lines arrive, at every pane width from 420 px to the 180 px
minimum in both themes, the lines whole and in the row wherever the last line has their room
beside the readiness's column (mb-3n21), and given way only where it has not; that their inks
and weights are the component's; that a row is one item (mb-1z7j), which carries the open row's
highlight, hovers as one wherever the pointer is on it, and takes the focus ring round it, while
the toggle, the lines and the chevron, adds its chevron's own hover and is no stop; and that a
real press on the title, the number, or the author opens the pull request and expands nothing
while one on the chevron or the lines opens and closes the files under it.
``METABROWSER_ROW_LINES_MEASURED``
names a file for what it measured, and ``METABROWSER_ROW_LINES_SHOTS`` a directory for a
screenshot of each width and theme, waiting and shown.

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

SESSION = Path(__file__).resolve().parent / "dom" / "github-pulls-row-lines-chrome.mjs"
# Sixteen mounts, eight widths in two themes, each a mount, a wait past the quiet period, and an
# arrival, and at 299 px in each theme a mount again and its pointer and key input. On a Mac at
# a load average of 10 to 31 the session took 5.3 to 7.5 s after Chrome's start; this is a cold
# start's bound and that six times over.
SESSION_TIMEOUT_S = LAUNCH_TIMEOUT_S + 45
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_rows_lines_arrive_in_its_run_in_place_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    measured = os.environ.get("METABROWSER_ROW_LINES_MEASURED")
    shots = os.environ.get("METABROWSER_ROW_LINES_SHOTS")
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
    passed = re.fullmatch(r"row lines in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
