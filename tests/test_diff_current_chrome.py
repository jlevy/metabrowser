"""A diff's toolbar choosers, its file bars' end groups, and the place a choice keeps, in Chrome.

The diff's toolbar ends with its choosers, one group on one line and right-aligned: **Diff**
| **Current**, then **Split** | **Unified**, or **Diff** | **Current** alone where the host
fixes the layout, as a pull request's Docs tab does (docs/design-system.md, "Diff
Toolbar"). Where they do not fit beside the File type control, they take the next line
together, and nothing runs past the toolbar. A file bar's end group holds a rendered file's
**Rendered** | **Source** alone, at the bar's end ("Diff File Bar"). What the toolbar and a
bar hold, and in what order, is pinned browserlessly (``tests/dom/diff-view-behavior.js``,
``tests/golden/cli-ui-diff-current.tryscript.md``); where they land is layout, which only a
browser computes, so ``tests/dom/diff-current-chrome.mjs`` mounts a Markdown file and a
code file through the production ``mountDiffView``, with the shell's chip family, as
Changes mounts it, with the production File type control painted in each state the filter
paints, as a diff with no File type control does, and as Docs does, and measures the toolbars
and bars from 1,063 to 320 px, in Diff and in Current, and with the Markdown file in Rendered
and in Source.

Which row a Diff | Current choice keeps is the browserless session's
(``tests/dom/diff-current-session.js``); where it lands beside the browser's own scroll
anchoring is the browser's, so the same script mounts a long code file and a long rendered
document in a 600 px pane and reads the row at the pane's top before and after each choice.

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
