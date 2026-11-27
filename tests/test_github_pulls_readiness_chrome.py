"""The Pulls tab's readiness column laid out by headless Chrome (mb-3n21).

Which rows draw a readiness, which verdict, and what each says is browserless
(``tests/dom/github-pulls-readiness-session.js``); what only a browser can tell is held here
(``tests/dom/github-pulls-readiness-chrome.mjs``): that every pull request's row has the
readiness's column between its toggle and its age, one width at one edge on every row, a
stack's member a level in too, holding a glyph or not, so the glyphs read as a column and the
ages stay in theirs; that nothing in a row moves when its readiness arrives; that the glyph
takes its tone's ink and the label the text's, in both themes; that the label follows the glyph exactly
from the container query's bound, whole, every label the server gives a verdict in its room;
and that the bound is the width at which a stack's member has the room its lines need beside
the column with its widest label and the age. ``METABROWSER_READINESS_MEASURED`` names a file
for what it measured, and ``METABROWSER_READINESS_SHOTS`` a directory for a screenshot of the
list at the default pane and a wide one in each theme.

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

SESSION = Path(__file__).resolve().parent / "dom" / "github-pulls-readiness-chrome.mjs"
# Twenty mounts, ten widths in two themes, each a mount and an arrival, then 301 widths of one
# mount a pixel apart. On a 4-core Linux container the session took 6 to 8 s after Chrome's
# start (2026-11-26); this is a cold start's bound and that five times over.
SESSION_TIMEOUT_S = LAUNCH_TIMEOUT_S + 40
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_readiness_column_lines_up_and_its_label_shows_where_it_has_room_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    measured = os.environ.get("METABROWSER_READINESS_MEASURED")
    shots = os.environ.get("METABROWSER_READINESS_SHOTS")
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
    passed = re.fullmatch(r"readiness in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
