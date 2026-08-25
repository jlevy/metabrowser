"""Behavioral contracts for ``plugin-sdk.js`` exercised via Node ``vm``.

The companion shim ``tests/dom/kpress-plugin-sdk-behavior.js`` runs
``plugin-sdk.js`` in a small DOM/fetch sandbox and asserts three
contracts that source-string tests can't validate:

1. ``_loadStylesheet`` resolves only after the link's ``onload`` fires
   (not synchronously on ``appendChild``).
2. Two concurrent ``fetchKpressRender`` calls with the same dedup key
   share one in-flight request; the first call's ``AbortSignal`` becomes
   aborted via ``AbortController``.
3. A non-ok fetch response rejects with an ``err.status`` and an
   ``err.payload`` carrying the server diagnostic.
4. Failed stylesheet, script, and TOC module loads can be retried.
    5. Cached stylesheets settle when the browser exposes ``link.sheet`` without
       dispatching a load event.
    6. Auxiliary asset failures preserve an already-rendered document payload.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "kpress-plugin-sdk-behavior.js"
SYNTAX_SHIM = Path(__file__).resolve().parent / "dom" / "syntax-token-sdk-behavior.js"


def test_plugin_sdk_behavior_contracts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping plugin-sdk.js behavioral shim")

    result = subprocess.run(
        ["node", "--experimental-vm-modules", str(SHIM), str(REPO_ROOT)],
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
    assert payload["assetRetry"]["ok"] is True, payload["assetRetry"]
    assert payload["cachedStylesheet"]["ok"] is True, payload["cachedStylesheet"]
    assert payload["assetFailureFallback"]["ok"] is True, payload["assetFailureFallback"]
    assert payload["transformedSource"]["ok"] is True, payload["transformedSource"]
    assert payload["fileCatalog"]["ok"] is True, payload["fileCatalog"]
    assert payload["completeText"]["ok"] is True, payload["completeText"]
    assert payload["pathText"]["ok"] is True, payload["pathText"]
    assert payload["sameKindOrder"]["ok"] is True, payload["sameKindOrder"]


def test_plugin_sdk_syntax_token_contracts() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping plugin-sdk.js syntax shim")

    result = subprocess.run(
        ["node", str(SYNTAX_SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"syntax token SDK shim failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "syntax token SDK OK" in result.stdout
