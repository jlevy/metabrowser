"""Failure ownership in the exact PR recorder, with process and CDP fault injection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node


def test_pr_page_recorder_owns_readiness_and_process_cleanup() -> None:
    probe = Path(__file__).parent / "dom" / "pr-page-lifecycle-behavior.js"
    result = subprocess.run(
        [require_node(), "--experimental-vm-modules", str(probe)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "recorder lifecycle: 7 scenarios passed\n"
