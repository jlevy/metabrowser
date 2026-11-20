"""A README's GitHub layout attributes are drawn in Chrome as on github.com, both profiles.

github.com keeps ``align``, ``width``, and ``height`` in the HTML of a README and draws
``<p align="center"><img width="192">`` as a small centered logo. That the allowlist of an
untrusted render keeps them, with checked values, is browserless
(``tests/test_inert_html.py``); how the page lays them out under KPress's stylesheets and
the shell's (``static/styles.css``, "GitHub's layout attributes in rendered Markdown") is
paint, so ``tests/dom/markdown-github-layout-chrome.mjs`` measures it in headless Chrome
against a live ``metab`` serving ``tests/fixtures/github-layout``, trusted and
``--untrusted``. Without Chrome this skips (``require_chrome`` in
``tests/required_tools.py``).
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
SESSION = REPO_ROOT / "tests" / "dom" / "markdown-github-layout-chrome.mjs"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "github-layout"
# Two server starts and one Chrome launch opening two pages: lighter than
# tests/test_markdown_diagrams_chrome.py's two launches and six pages, so its bound, which
# leaves room for a cold first Chrome launch in CI, holds here too.
SESSION_TIMEOUT_S = 120
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and both servers are in it), and the profile's teardown (tests/process_group.py).
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_github_layout_attributes_draw_as_on_github_in_chrome(
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
    passed = re.fullmatch(r"markdown github layout in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
