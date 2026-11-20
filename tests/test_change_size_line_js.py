"""The change size line's words and markup, and a Pulls row's size, in Node.

``tests/dom/change-size-line-behavior.js`` runs the SDK's view helpers
(``static/plugin-sdk-views.js``) and ``row-lines.js`` (docs/design-system.md, "Change Size
Line").
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_JS = Path(__file__).resolve().parent / "dom" / "change-size-line-behavior.js"


def test_change_size_line_contract() -> None:
    require_node()
    result = subprocess.run(
        ["node", str(TEST_JS), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"change size line failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "change size line OK" in result.stdout
