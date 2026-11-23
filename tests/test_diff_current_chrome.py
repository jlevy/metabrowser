"""A diff file bar's end group, laid out by headless Chrome.

A file bar ends with its choosers, right-aligned: the diff's **Diff** | **Current** on
every bar with a text diff, then a rendered file's **Rendered** | **Source**, which ends
the bar, both on one line (docs/design-system.md, "Diff File Bar"). Where the bar is too
narrow for its two groups, the end group takes the next line, still at the bar's end.
Which chooser a bar has and their order are pinned browserlessly
(``tests/dom/diff-view-behavior.js``, ``tests/test_design_vocabulary.py``); where they
land is layout, which only a browser computes, so ``tests/dom/diff-current-chrome.mjs``
mounts a Markdown file and a code file through the production ``mountDiffView``, with the
shell's chip family, and measures the bars, at a wide and a narrow width, in Diff and in
Current, and with the Markdown file in Rendered and in Source.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
``CURRENT_SHOTS`` in the environment names a directory for a screenshot of each state.
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

SESSION = Path(__file__).resolve().parent / "dom" / "diff-current-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); the measurement itself took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's files.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_bars_choosers_share_its_end_in_chrome(tmp_path: Path, chrome_profile: Path) -> None:
    chrome = require_chrome()
    sheets = _kpress_static(tmp_path / "kpress")
    current_input = tmp_path / "input.json"
    current_input.write_text(json.dumps({"sheets": sheets}), encoding="utf-8")
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
