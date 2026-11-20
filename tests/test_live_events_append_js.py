"""A live tail's rows are drawn with agent-log's exports, inside their measure."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

SHIM = Path(__file__).resolve().parent / "dom" / "live-events-append-behavior.js"


def test_appended_live_events_are_measured_through_their_render() -> None:
    node = require_node()
    result = subprocess.run(
        [node, str(SHIM)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
