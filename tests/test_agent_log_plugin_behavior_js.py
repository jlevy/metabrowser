"""Browser behavior checks for the built-in agent-log plugin."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "agent_log_plugin_behavior.js"


def test_agent_log_escapes_kinds_and_disposes_charts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping agent-log browser behavior")

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
        "chartDisposeCalls": 1,
        "chartRenderCalls": 0,
        "dynamicEndsUnpressed": True,
        "dynamicEventHidden": True,
        "dynamicLabelIsReadable": True,
        "dynamicStartsPressed": True,
        "hasDelegatedClick": True,
        "hasEscapedImage": True,
        "hasInlineKindHandler": False,
        "hasRawImage": False,
        "usesSharedMultiSelect": True,
        "usesWrappedChipCluster": True,
    }
