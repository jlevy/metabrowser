"""The transition-navigation instrument (explorations/performance-loop/transitions*.mjs).

Its pure logic runs browserless: request classes, cache disposition over recorded DevTools
event sequences, frame accounting, region movement, and every refusal and verdict of
``compare`` over fixture rows. Its recorder runs in a real headless Chrome on synthetic
pages, because what it measures is paint and the frame clock: readiness against the
input, the presentation of the ready frame, content on screen, and 304s a server logged.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.required_tools import require_node

DOM = Path(__file__).parent / "dom"
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _chrome() -> str | None:
    named = os.environ.get("CHROME_BIN")
    if named:
        return named
    if Path(MAC_CHROME).exists():
        return MAC_CHROME
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found is not None:
            return found
    return None


def test_transition_instrument_logic() -> None:
    result = subprocess.run(
        [require_node(), str(DOM / "transitions-instrument-behavior.mjs")],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "transitions instrument: 36 checks passed\n"


@pytest.mark.parametrize(("group", "count"), [("frames", 7), ("content", 7), ("network", 1)])
def test_transition_recorder_in_chrome(group: str, count: int) -> None:
    chrome = _chrome()
    if chrome is None:
        pytest.skip("Chrome is not installed")
    result = subprocess.run(
        [require_node(), str(DOM / "transitions-recorder-chrome.mjs"), group],
        capture_output=True,
        check=False,
        text=True,
        timeout=50,
        env={**os.environ, "CHROME_BIN": chrome},
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == f"transitions recorder {group}: {count} checks passed\n"
