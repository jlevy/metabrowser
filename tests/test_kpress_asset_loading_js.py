"""JS-side integration tests for KPress render asset loading.

Runs ``plugin_sdk.js`` in the same Node ``vm`` simulated DOM style used
by the plugin registration/render tests. The goal is to cover the async
``fetchKpressRender -> loadKpressAssets`` path that a source-string test
cannot validate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "kpress_asset_loading.js"


def test_kpress_browser_assets_honor_manifest_loading_modes() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping JS-side KPress asset-loading shim")

    result = subprocess.run(
        ["node", str(SHIM), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"KPress asset-loading shim failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    scripts = [
        node
        for node in payload["appended"]
        if node["tagName"] == "SCRIPT" and node["type"] != "importmap"
    ]
    # theme.js is skipped (metabrowser owns the theme); toc.js is loaded via
    # dynamic import (so the host drives initKpressToc per render) and is not
    # appended as a script tag; dependency-only runtime.js is also not emitted.
    # The remaining module and classic entry points preserve manifest order.
    assert [script["src"] for script in scripts] == [
        "/kpress-static/v0.2.1/js/code-copy.js",
        "/kpress-static/v0.2.1/katex/katex.min.js",
    ]
    assert [script["type"] for script in scripts] == ["module", "text/javascript"]
    assert all(script["async"] is False for script in scripts)
