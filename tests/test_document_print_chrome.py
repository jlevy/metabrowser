"""A rendered document's print button sits in its card's corner and moves nothing, in Chrome.

The header's print button is gone; the Markdown file view and the README on a folder's
Overview put one in the upper right corner of the document's card instead
(``builtin_plugins/markdown/print-indicator.js``), and printing stays the browser's, as
Command-P is. Which mounts carry it, what it says, and that a click prints are
browserless (``tests/dom/markdown-print-indicator-session.js``); where it lands, that
nothing moves when it arrives, the narrow table of contents toggle and the wide rail beside
it, its tooltip, and what prints are layout and paint, which
``tests/dom/document-print-chrome.mjs`` measures in headless Chrome, trusted and
``--untrusted``, in KPress's phone, narrow, and wide bands (docs/design-system.md, "Print").
Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
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

SESSION = Path(__file__).resolve().parent / "dom" / "document-print-chrome.mjs"
# Two server starts and two Chrome launches, each opening three pages at four widths:
# measured below on a 10-core Mac at a load average near 14, so the bound is several times
# that, with room for a cold first Chrome launch in CI (28.2 s in
# tests/test_page_header_chrome.py).
SESSION_TIMEOUT_S = 120
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and both servers are in it), and the profile's teardown (tests/process_group.py);
# tests/test_process_group.py holds the sum under the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# Long enough for KPress's table of contents: more headings and words than its thresholds
# (``toc_min_headings`` and ``toc_min_words`` in KPress's models.py). The title runs the
# card's width, so a button over the text would cover it.
_SECTION = (
    "This paragraph stands in for the prose a real README holds, long enough that the "
    "sections fill several screens and the table of contents has somewhere to lead. "
) * 6
README = (
    "# A Sample Project Whose Title Runs the Whole Width of the Card Before It Wraps\n\n"
    + "".join(f"## Section {n}\n\n{_SECTION}\n\n{_SECTION}\n\n" for n in range(1, 10))
)
# A document that opens with a paragraph, and is too short for a table of contents.
NOTE = (
    "A note that opens with a paragraph rather than a heading, long enough to run the "
    "whole width of the card's first line. " + _SECTION + "\n\n" + _SECTION + "\n"
)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_the_document_print_button_sits_in_the_card_corner_in_chrome(
    tmp_path: Path, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    root = tmp_path / "served"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "note.md").write_text(NOTE, encoding="utf-8")
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
    passed = re.fullmatch(r"document print in Chrome: (\d+) checks passed\n", result.stdout)
    assert passed is not None and int(passed.group(1)) > 0, result.stdout
