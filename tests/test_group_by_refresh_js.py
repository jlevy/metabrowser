"""A Group by refresh keeps what is on screen, and paints the open folders at once."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node


def test_group_by_refresh_against_the_shell() -> None:
    shim = Path(__file__).parent / "dom" / "group-by-refresh-behavior.js"
    result = subprocess.run(
        [require_node(), str(shim)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "group by refresh OK" in result.stdout
