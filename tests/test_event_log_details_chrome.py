"""A Diff summary that never arrives, and the Details it offers, in headless Chrome.

The owner asked, 2026-11-19, that a Diff summary still loading after many seconds be
captured, surfaced, and easy to debug (mb-9zp5). ``tests/dom/event-log-details-chrome.mjs``
mounts the production pull request page with the shell's stylesheets and SDK, on a record
whose comparison read never answers, and checks in a real browser what no browserless DOM
can: the late line is painted at the threshold, Tab reaches its Details with a visible
focus, Enter opens and closes the panel, which is painted in the design tokens and reads
the job still running and the page's wait, every request carries the page's ID, and
leaving the page delivers the wait's ``never_completed`` report, which only ``keepalive``
does. The same behavior is pinned without a browser in
``tests/dom/github-pull-page-mount-behavior.js`` and ``tests/dom/event-reports-session.js``.

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

SESSION = Path(__file__).resolve().parent / "dom" / "event-log-details-chrome.mjs"
# One Chrome start, one page, and a wait past the session's 0.6 s threshold took 1.8 to
# 2.2 s on a Mac at a load average near 10 (2026-11-19). A cold Chrome start in CI has
# taken 28.2 s (the Overview alignment test, 2026-11-14), so the bound leaves room for one.
SESSION_TIMEOUT_S = 45
# The longest the test can take: the session's bound, its process group stopped after it,
# and the profile's teardown (tests/process_group.py), with 10 s for the rest of the setup.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_a_summary_that_never_arrives_offers_details_and_reports_it_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
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
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    print(result.stderr)
    assert result.returncode == 0, result.stderr or result.stdout
    passed = re.fullmatch(r"event log details in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
