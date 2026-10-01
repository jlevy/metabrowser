"""Display-contract checks for the binary plugin's byte formatter."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "binary-byte-format-behavior.js"


def test_binary_byte_format_contract() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Binary byte format contract failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "binary byte format OK" in result.stdout
