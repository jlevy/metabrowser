"""Pure-function tests for structured/preview.js.

Runs the JS-side assertions in tests/dom/test-preview.js via Node's
vm sandbox (same approach as test_plugin_e2e_render.py). Keeps the
ported preview logic honest without inventing a TS toolchain.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

PREVIEW_TEST_JS = Path(__file__).resolve().parent / "dom" / "test-preview.js"


def test_preview_js_assertions_pass() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(PREVIEW_TEST_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"preview.js assertions failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert result.stdout.startswith("OK"), f"unexpected stdout: {result.stdout!r}"
