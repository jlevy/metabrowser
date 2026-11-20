"""A README's badge row is drawn in Chrome as on github.com, under each trust profile.

That the allowlist keeps an image from the web over https and no referrer, and turns every
other into a chip inside the link it was in, is browserless (``tests/test_inert_html.py``,
``tests/dom/inert-html-session.js``). How the row lays out and what the browser fetches is
paint and the network, so ``tests/dom/markdown-badges-chrome.mjs`` measures it in headless
Chrome against a live ``metab`` serving ``tests/fixtures/badges``, trusted and
``--untrusted``, and then after the reader ticks "Block remote images". Chrome's network
layer answers every badge, so nothing leaves the machine. Without Chrome this skips
(``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION = REPO_ROOT / "tests" / "dom" / "markdown-badges-chrome.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "badges"
# Two server starts and one Chrome launch opening several pages: the bound of
# tests/test_markdown_github_layout_chrome.py, which has the same shape.
SESSION_TIMEOUT_S = 120
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_badges_lie_on_one_line_and_go_where_their_author_sent_them_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    shutil.copytree(FIXTURE, root)
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [require_node(), str(SESSION), str(_METAB), str(root), str(_free_port()), str(state)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    if result.timed_out:
        pytest.fail(f"ran past {SESSION_TIMEOUT_S} s; its steps:\n{result.stderr}")
    # Each step's time, shown with the output when it fails.
    print(result.stderr)
    assert result.returncode == 0, result.stdout or result.stderr
    passed = re.fullmatch(r"markdown badges in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
