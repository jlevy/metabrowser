"""Behavioral theme contracts for SDK and built-in Chart.js canvases."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "chart_theme_behavior.js"


def test_charts_repaint_from_theme_tokens_until_disposed() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping chart theme behavioral shim")

    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"chart theme shim failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    payload = json.loads(result.stdout)

    assert payload["lazyMountCreatesNoChart"] is True
    assert payload["directInitialColors"] == {
        "series": "light-series",
        "label": "light-label",
    }
    assert payload["directDarkColors"] == {
        "series": "dark-series",
        "label": "dark-label",
        "updateCalls": ["none"],
    }
    assert payload["directUpdatesAfterDestroy"] == 1
    assert payload["staticInputsPreserved"] is True
    assert payload["staticUpdateCalls"] == 0
    assert payload["firstRuntime"] == {
        "initialSeries": "dark-series",
        "oklchAlpha": "oklch(70% 0.1 95 / 0.13)",
        "destroyedOnRepaint": 1,
        "repaintedSeries": "light-series",
        "specTokenPreserved": "var(--chart-series-info)",
    }
    assert payload["replacement"] == {
        "firstRepaintDestroyed": 1,
        "secondDestroyedOnRepaint": 1,
        "repaintedLabel": "Second series",
        "repaintedSeries": "dark-series",
    }
    assert payload["disposal"]["activeDestroyed"] == 1
    assert (
        payload["disposal"]["chartCountAfterTheme"]
        == payload["disposal"]["chartCountBeforeDispose"]
    )
