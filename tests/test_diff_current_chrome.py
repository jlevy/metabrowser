"""Diff toolbar layout and scroll anchoring in Chrome.

The production diff mounts a Markdown and a code file in Changes, with and without
the File type control, and in Docs, where the source layout is fixed. At widths from
1,063 to 320 px, the toolbar keeps the presentation and source layout controls
together and the Markdown file bar keeps Rendered | Source at its end. The browserless
session in ``tests/dom/diff-current-session.js`` covers which controls appear.

A long code file and a long rendered document exercise the pane's scroll position
when changing presentation. The script scrolls one screen at a time so the rendered
document draws the chunks ahead of the reader.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``CURRENT_SHOTS`` in the environment names a directory for a screenshot of each state and
``toolbar-widths.json``, each toolbar's height and overflow at each width.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node
from tests.test_github_pull_text_chrome import _kpress_static  # pyright: ignore[reportPrivateUsage]

SESSION = Path(__file__).resolve().parent / "dom" / "diff-current-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the measurements, five File type states at five widths and the
# six place pages, took 19.1 s after a 5.1 s launch on a Mac at a load average near 380 (the
# session writes both to stderr).
SESSION_TIMEOUT_S = 60
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_toolbars_choosers_share_its_end_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    current_input = tmp_path / "input.json"
    current_input.write_text(
        json.dumps({"sheets": sheets, "presets": FILTER_TYPE_PRESETS}), encoding="utf-8"
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
            "CURRENT_INPUT": str(current_input),
        },
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    # What it measured, shown with the case's output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"diff current in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
