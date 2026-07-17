"""Browser behavior checks for numeric Markdown table cells."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "markdown_table_numeric_behavior.js"


def test_markdown_tables_align_strict_localized_numbers() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping Markdown table browser behavior")

    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "invalid": [],
        "valid": [
            "0",
            "-45.1%",
            "−45.1%",
            "+12%",
            "1,234.56",
            "-1.234,56%",
            "1234,5",
            ".75",
            ",75%",
        ],
    }
