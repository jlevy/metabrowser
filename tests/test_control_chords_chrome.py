"""Control-N and Control-P through a real engine's key events and navigator (mb-lnqj).

The registry's one chord is Control with N or P (docs/design-system.md, "Control
Chords"). The browserless sessions build each key event by hand and stub the navigator,
so ``tests/dom/control-chords-chrome.mjs`` loads the production registry and the Pulls
tab's keys into headless Chrome, presses keys through the DevTools input domain, and reads
how the chord is written there: Control-N and Control-P walk the stack and are cancelled,
Shift changes nothing, the letters alone and Control-Alt (as AltGr reports it) and
Control-Command walk nothing and are left alone, a text field keeps both chords, and the
platform's own Chrome writes the chord ``⌃N`` on a Mac and ``Ctrl+N`` elsewhere.

What the browser itself does with a chord is out of this check's reach: protocol input
reaches the page without the browser's accelerators, so Chrome keeping Ctrl+N for a new
window on Windows and Linux, and macOS moving a field's caret with Control-N, are stated
in the design system and the manual checks of ``docs/e2e-testing.md``, not measured here.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "control-chords-chrome.mjs"
# A cold Chrome start in CI has taken 28.2 s (tests/test_github_pull_header_chrome.py,
# whose launch bound this shares); the nine presses took under 2 s on a Mac.
SESSION_TIMEOUT_S = 48
# The bound, the session's process group stopped after it, and the profile's teardown
# (tests/process_group.py); tests/test_process_group.py holds the sum under the module's
# timeout.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)


def test_control_n_and_control_p_walk_the_stack_in_chrome(chrome_profile: Path) -> None:
    chrome = require_chrome()
    # The session leads a process group of its own, which Chrome joins, and the whole group
    # is stopped however it ends; its profile is the fixture's to remove.
    result = run_in_own_group(
        [require_node(), str(SESSION)],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    if result.timed_out:
        pytest.fail(f"the session ran past {SESSION_TIMEOUT_S} s:\n{result.stderr}")
    assert result.returncode == 0, result.stderr or result.stdout
    record = json.loads(result.stdout.strip().splitlines()[-1])
    presses = record["presses"]
    moved = {name: press["moved"] for name, press in presses.items()}
    assert moved == {
        "Control-N": [1],
        "Control-P": [-1],
        "Control-Shift-N": [1],
        "N alone": [],
        "P alone": [],
        "Control-Alt-N, as AltGr": [],
        "Control-Command-P": [],
        "Control-N in a field": [],
        "Control-P in a text area": [],
    }
    # Each press reached the page as the chord it is, and only a walk was cancelled.
    for name, press in presses.items():
        heard = press["heard"]
        # The letter is the last of the name's first word: "Control-N", "P alone".
        assert heard["key"].lower() == name.split()[0].rstrip(",")[-1].lower(), name
        assert heard["ctrlKey"] is name.startswith("Control"), name
        assert heard["prevented"] is bool(press["moved"]), name
    # The platform's own Chrome names the chord as its platform writes it.
    written = record["written"]
    expected = "⌃N" if sys.platform == "darwin" else "Ctrl+N"
    assert written["visible"] == [expected], written
    assert (written["spoken"], written["aria"]) == ("Control N", "Control+N")
