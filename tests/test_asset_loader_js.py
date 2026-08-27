"""Behavioral contracts for the on-demand asset tier.

The tier's claim is that a document which never opens a consuming view pays
nothing for its library, and that a document which opens two of them pays
once. Both are invisible from a request count, so they are pinned here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "asset-loader-behavior.js"


def _run_shim() -> dict[str, object]:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping asset loader behavioral shim")
    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"asset loader shim failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    return json.loads(result.stdout)


def test_on_demand_assets_load_once_when_asked_and_never_before() -> None:
    payload = _run_shim()

    # Declaring a bundle must load nothing: this is the whole tier.
    assert payload["appendedBeforeAnyRequest"] == 0

    # A bundle loads in order, and a gated entry sees the global its
    # predecessor installed.
    assert payload["orderedLoad"] == ["chart.js", "plugin.js", "adapter.js"]
    assert payload["notifiedPerScript"] == ["chart.js", "plugin.js", "adapter.js"]
    assert payload["loadedFlag"] is True

    # A view opened a second time refetches nothing.
    assert payload["appendsOnSecondRequest"] == 0

    # A gated entry whose dependency never appeared is skipped, not failed.
    assert payload["skippedUngatedDependency"] == ["chart.js"]

    # Simultaneous callers share one load instead of appending duplicates.
    assert payload["appendsWhileThreeCallersWait"] == 1
    assert payload["appendsAfterSharedLoadSettled"] == 1

    # A consumer can tell a missing bundle from a broken one.
    assert payload["unknownBundle"] == "Unknown asset bundle: absent"
    assert payload["failedScript"] == "Failed to load asset: chart.js"

    # A failure must not latch: the next attempt retries rather than
    # reporting a library that is not there.
    assert payload["loadedFlagAfterFailure"] is False
    assert payload["appendsAfterFailedRetry"] == 2
