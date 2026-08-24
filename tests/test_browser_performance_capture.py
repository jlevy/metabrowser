"""CLI contract for the dependency-free Chrome performance driver."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "explorations" / "performance-loop" / "capture-browser.js"


def test_capture_browser_argument_contract() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
const capture = require({json.dumps(str(CAPTURE))});
const parsed = capture.parseArgs([
  "--url", "http://127.0.0.1:8411/view/",
  "--probe", "probe.js",
  "--output", "profile.json",
  "--headed",
  "--width", "1600",
  "--height", "900"
]);
process.stdout.write(JSON.stringify(parsed));
"""

    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["headed"] is True
    assert parsed["width"] == 1600
    assert parsed["height"] == 900
    assert parsed["url"] == "http://127.0.0.1:8411/view/"


def test_capture_browser_records_controlled_retained_heap() -> None:
    source = CAPTURE.read_text(encoding="utf-8")

    assert 'session.send("HeapProfiler.collectGarbage")' in source
    assert 'session.send("Runtime.getHeapUsage")' in source
    assert "payload.js_heap_after_gc_mb" in source
