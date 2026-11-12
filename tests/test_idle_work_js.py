"""``metabrowser.whenIdle``: the one way the shell and plugins schedule idle work.

The app's WebKit (WKWebView, macOS 26) has no ``requestIdleCallback``; the five call
sites that wanted one fell back to fixed timers, so prefetch started on a clock rather
than when the page was free (research 2026-11-11, 3.9). Without one, the helper waits
for the first view to settle and for input to go quiet, bounded by the caller's timeout.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "metabrowser"
SESSION = Path(__file__).resolve().parent / "dom" / "idle-work-behavior.js"


def test_idle_work_waits_for_the_first_view_and_quiet_input() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(SESSION), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    assert json.loads(result.stdout) == {
        "helper": "function",
        # Review B of #372, B6: installed only where the fallback reads them, and passive.
        "inputListeners": [{"capture": True, "passive": True}] * 3,
        "inputListenersWithIdleCallback": [],
        # Before the first view settles: untimed work waits; a timeout is the bound.
        "beforeTimeout": [],
        "atTimeout": ["timed-2000@2000"],
        "unsettledLongAfter": ["timed-2000@2000"],
        # The settle releases waiting work in a task of its own, not inside the event.
        "synchronouslyOnSettle": ["timed-2000@2000"],
        "afterSettle": ["timed-2000@2000", "untimed@7000"],
        # Input defers it until input has been quiet for 250 ms.
        "deferredWhileInputIsRecent": [],
        "afterQuiet": ["after-key@8350"],
        "quietAfterLastInputMs": 250,
        "keyThenPointerGapMs": 100,
        # A timeout bounds the wait for quiet too.
        "timeoutDuringInput": ["timed-100@8450"],
        "cancelled": [],
        "timersLeft": 0,
        # Where the engine has requestIdleCallback, the helper is that, and passes the
        # callback nothing, as the fallback does.
        "nativeCalls": [{"options": {"timeout": 300}}, {"options": {}}],
        "nativeArgumentCounts": [0, 0],
        "nativeCancelled": [7],
    }


def test_idle_work_has_one_implementation() -> None:
    """Every idle call site goes through the helper, so its WebKit fallback is everyone's."""
    offenders: list[str] = []
    candidates = [SRC / "server.py", *SRC.glob("static/*.js"), *SRC.glob("builtin_plugins/**/*.js")]
    for path in candidates:
        if path.name == "plugin-sdk.js" or "vendor" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith(("#", "//", "*")):
                continue
            if re.search(r"\brequestIdleCallback\b", line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
    assert not offenders, "schedule idle work with metabrowser.whenIdle:\n  " + "\n  ".join(
        offenders
    )
