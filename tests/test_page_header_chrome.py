"""A commit's page and a pull request's page have one header, laid out where the design says.

The owner asked that the lines under the two titles share one design (mb-26zj): every line
at the regular body size, the Diff summary's included, which was a step smaller on both
pages (mb-kisi), and the author drawn the same on both, an avatar's box and then the bold
name, with a profile icon for a commit's author (mb-nunw, mb-s3g8). The classes each page
writes are held browserless (``tests/test_design_vocabulary.py``); the computed type is the
cascade's, which only a browser resolves: ``tests/dom/page-header-chrome.mjs`` draws both
headers with their production code in headless Chrome at 980, 560, and 360 px, each with
the Diff summary the diff plugin draws in its place, and holds every line under each title
and every run of its text to the body size, a revision among them and a chip at its own,
the two pages' lines to one size and one line height, the shared lines to one order,
each title as tall as its lines and its first line `--page-title-gap` under it (mb-wcbc),
both authors' boxes to 18 px holding the person glyph, both names to one start and one
type, and an avatar arriving in either box to moving nothing (docs/design-system.md, "Page
Headers" and "Actor Identity").

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

SESSION = Path(__file__).resolve().parent / "dom" / "page-header-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py, whose
# launch bound this shares); both headers were drawn and read at every width in under 1 s on
# a Mac at a load average of 10.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py), with 10 s for the copy of KPress's faces.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_the_commit_and_pull_request_headers_are_one_design_in_chrome(
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
    passed = re.fullmatch(r"page header in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
