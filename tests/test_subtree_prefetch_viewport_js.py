"""The subtree sweep warms what is on screen, and only what is on screen.

Measured on a 300,000-file tree in Chromium at 1280x900, median of three cold
loads each: taking stubs in DOM order issued 32 `/api/tree?path=` requests and
transferred 1,566 KB; bounding them to the nav viewport issues 0 and transfers
517 KB, because every stub the root render mounts sits inside a collapsed
branch. See explorations/experiments/exp-002.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SHIM = Path(__file__).resolve().parent / "dom" / "subtree_prefetch_viewport_behavior.js"


def test_subtree_prefetch_is_bounded_to_the_nav_viewport() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SHIM)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"subtree prefetch viewport bound failed:\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "ok" in result.stdout
