"""A folder Overview's README keeps the table of contents it has opened as a file.

On the Overview, the README sits below File Overview. KPress's narrow toggle used to read
only how far the pane had scrolled, and the Overview asked KPress for no table of contents
at all. Now the README keeps it, and its toggle follows one rule for every document
(``builtin_plugins/markdown/toc-toggle.js``): past KPress's threshold, and once the reader
has reached the document. ``tests/dom/markdown-toc-scrollspy-session.js`` and
``tests/dom/markdown-inert-toc-session.js`` hold the rule and the fragment links
browserlessly; where the rail and the card land, the toggle's fade, and a real click are
layout and paint, which ``tests/dom/overview-readme-toc-chrome.mjs`` measures in headless
Chrome, trusted and ``--untrusted``, against the same README opened as a file
(docs/design-system.md, "Embedded Document Navigation"). Without Chrome this skips
(``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import os
import re
import socket
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "overview-readme-toc-chrome.mjs"
# Two server starts and four Chrome launches, each opening the README and the Overview:
# 11.4 s on a 10-core Mac at a load average near 6, so the bound is several times that,
# with room for a cold first Chrome launch in CI (28.2 s in tests/test_page_header_chrome.py).
SESSION_TIMEOUT_S = 100
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and both servers are in it), and the profile's teardown (tests/process_group.py);
# tests/test_process_group.py holds the sum under the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Long enough for KPress's table of contents: more headings and words than its thresholds
# (``toc_min_headings`` and ``toc_min_words`` in KPress's models.py).
_SECTION = (
    "This paragraph stands in for the prose a real README holds, long enough that the "
    "sections fill several screens and the table of contents has somewhere to lead. "
) * 6
README = "# Sample Project\n\n" + "".join(
    f"## Section {n}\n\n{_SECTION}\n\n{_SECTION}\n\n" for n in range(1, 10)
)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_the_overview_readme_keeps_its_table_of_contents_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text(README, encoding="utf-8")
    # Files of a few kinds, so File Overview above the README has rows to show.
    for n in range(1, 4):
        (root / "src" / f"module{n}.py").write_text(f"VALUE = {n}\n", encoding="utf-8")
        (root / f"data{n}.json").write_text(f'{{"n": {n}}}\n', encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    # The session leads a process group of its own, which Chrome and both servers join, and
    # the whole group is stopped however it ends; the profile is the fixture's to remove.
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
    passed = re.fullmatch(r"overview README TOC in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
