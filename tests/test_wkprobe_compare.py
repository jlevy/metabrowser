"""The WKWebView probe's compare (explorations/performance-loop/wkprobe*.mjs).

Its decisions run browserless over synthetic rows: request counting, the relaunch
freshness regime, the per-metric minimum, the back-to-back pair rule, expectations,
refusals, and the command's exit code. Nothing here starts WebKit, a server, or a
timed run, so it is not a performance measurement and gates nothing about speed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

DOM = Path(__file__).parent / "dom"


def test_wkprobe_compare_decisions() -> None:
    result = subprocess.run(
        [require_node(), str(DOM / "wkprobe-compare-behavior.mjs")],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "wkprobe compare: 18 checks passed\n"
