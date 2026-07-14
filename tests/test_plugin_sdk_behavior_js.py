"""Behavioral contracts for ``plugin_sdk.js`` exercised via Node ``vm``.

The companion shim ``tests/dom/kpress_plugin_sdk_behavior.js`` runs
``plugin_sdk.js`` in a small DOM/fetch sandbox and asserts three
contracts that source-string tests can't validate:

1. ``_loadStylesheet`` resolves only after the link's ``onload`` fires
   (not synchronously on ``appendChild``).
2. Two concurrent ``fetchKpressRender`` calls with the same dedup key
   share one in-flight request; the first call's ``AbortSignal`` becomes
   aborted via ``AbortController``.
3. A non-ok fetch response rejects with an ``err.status`` and an
   ``err.payload`` carrying the server diagnostic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "kpress_plugin_sdk_behavior.js"


def test_plugin_sdk_behavior_contracts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping plugin_sdk.js behavioral shim")

    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"plugin_sdk behavioral shim failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["stylesheet"]["ok"] is True, payload["stylesheet"]
    assert payload["dedup"]["ok"] is True, payload["dedup"]
    assert payload["errorProp"]["ok"] is True, payload["errorProp"]
