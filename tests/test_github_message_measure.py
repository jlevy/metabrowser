"""The PR-only font measurement follows settings and disposes with its view."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node


def test_message_measure_follows_the_font_setting() -> None:
    require_node()
    script = Path(__file__).parent / "dom" / "github-message-measure-behavior.js"
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
