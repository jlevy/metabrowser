"""Behavioral checks for the browser performance instrumentation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.required_tools import require_node

PERF_TEST_JS = Path(__file__).resolve().parent / "dom" / "perf-behavior.js"


def test_perf_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(PERF_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        "perf instrumentation assertions failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"


def test_without_long_tasks_frame_gaps_are_recorded_under_their_own_fields() -> None:
    """The app's WebKit has no Long Tasks, Long Animation Frames, or Layout Instability.

    A requestAnimationFrame interval past 50 ms stands in, under `raf_frame_gaps`, so it is
    never read as a Long Task: the Long Task fields stay as they were, with `longtask`
    named unsupported, and CLS stays null. The frame loop runs for a window after load,
    after reset(), and after trusted input, and skips the page's hidden time.
    """
    require_node()
    script = Path(__file__).resolve().parent / "dom" / "perf-frame-gap-behavior.js"
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"

    def gaps(count: int, largest: int, over_200: int, sampled: int) -> dict[str, int]:
        return {"gaps": count, "max_ms": largest, "over_200ms": over_200, "sampled_ms": sampled}

    assert json.loads(result.stdout) == {
        "frameRequestedAtLoad": 1,
        # Measured from load: 16, 16, 100, 16, and 300 ms intervals, two of them gaps.
        "afterLoad": gaps(2, 300, 1, 448),
        "longTasks": {"long_tasks": 0, "long_task_max_ms": 0, "unsupported": ["longtask"]},
        "cls": None,
        # Hidden frames, and the first frame after showing, add nothing but sampled time.
        "afterHidden": gaps(2, 300, 1, 464),
        "framesRequestedAfterWindow": 0,
        "framesAfterUntrustedClick": 0,
        "framesAfterTrustedKey": 1,
        # Measured from the waking key: 84 ms to the next frame is a gap, then 100.
        "afterInput": gaps(4, 300, 1, 648),
        "framesAfterSecondWindow": 0,
        # Review B of #372, B1: the 300 ms a waking click blocks before its frame counts.
        "afterBlockingClick": gaps(5, 300, 2, 980),
        "afterReset": gaps(0, 0, 0, 0),
        "framesAfterReset": 1,
    }
