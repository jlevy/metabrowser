"""The WKWebView probe's decisions (explorations/performance-loop/wkprobe*.mjs).

They run browserless over synthetic rows and synthetic probe output:

- ``compare``: request counting, the relaunch freshness regime, the per-metric minimum,
  the back-to-back pair rule, expectations, refusals, and the command's exit code;
- the run side: step attribution, each scenario row's refusals and derived figures, the
  device pixel ratio, and the probe lock.

Nothing here starts WebKit, a server, or a timed run, so it is not a performance
measurement and gates nothing about speed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.required_tools import require_node

DOM = Path(__file__).parent / "dom"


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("wkprobe-compare-behavior.mjs", "wkprobe compare: 22 checks passed\n"),
        ("wkprobe-run-behavior.mjs", "wkprobe run: 11 checks passed\n"),
    ],
)
def test_wkprobe_decisions(script: str, expected: str) -> None:
    result = subprocess.run(
        [require_node(), str(DOM / script)],
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
