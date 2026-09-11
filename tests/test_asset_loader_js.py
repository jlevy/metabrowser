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

    # A partial retry resumes at the failed entry. The successful Chart core
    # is not evaluated again, which also prevents duplicate lifetime hooks in
    # modules that subscribe to global events at evaluation time.
    assert payload["partialFailureRetryAppends"] == [
        "chart.js",
        "charts-runtime.js",
        "adapter.js",
        "adapter.js",
    ]
    assert payload["partialFailureNotifications"] == [
        "chart.js",
        "charts-runtime.js",
        "adapter.js",
    ]
    assert payload["partialFailureLoaded"] is True

    # A script load event is not success when its declared global is absent.
    # The missing core stops gated dependants and neither script nor bundle is
    # latched, so a later request retries the core and can recover.
    assert payload["missingProvidedGlobal"] == (
        "Asset chart.js did not provide expected global: Chart"
    )
    assert payload["missingProvidedGlobalFirstAppends"] == ["chart.js"]
    assert payload["missingProvidedGlobalFirstNotifications"] == []
    assert payload["missingProvidedGlobalLatched"] is False
    assert payload["missingProvidedGlobalRetryAppends"] == [
        "chart.js",
        "chart.js",
        "plugin.js",
    ]
    assert payload["missingProvidedGlobalRetryNotifications"] == ["chart.js", "plugin.js"]
    assert payload["missingProvidedGlobalRetryLoaded"] is True

    # A concurrent stronger declaration must clear a weaker src-only latch
    # when its postcondition is absent, so the first retry performs the load.
    assert payload["concurrentStrongFailure"] == (
        "Asset shared.js did not provide expected global: Shared"
    )
    assert payload["concurrentStrongRetryAppends"] == ["shared.js", "shared.js"]
    assert payload["concurrentStrongRetryLoaded"] is True
