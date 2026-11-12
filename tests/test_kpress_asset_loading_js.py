"""JS-side integration tests for KPress render asset loading.

Runs ``plugin-sdk.js`` in the same Node ``vm`` simulated DOM style used
by the plugin registration/render tests. The goal is to cover the async
``fetchKpressRender -> loadKpressAssets`` path that a source-string test
cannot validate.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "kpress-asset-loading.js"


def test_kpress_browser_assets_honor_manifest_loading_modes() -> None:
    require_node()

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
    # The manifest is authoritative. toc.js is loaded via dynamic import (so
    # the host drives initKpressToc per render) and dependency-only runtime.js
    # is not emitted. Remaining entry points preserve manifest order.
    assert [script["src"] for script in scripts] == [
        "/kpress-static/v0.3.0/js/theme.js",
        "/kpress-static/v0.3.0/js/code-copy.js",
        "/kpress-static/v0.3.0/katex/katex.min.js",
    ]
    assert [script["type"] for script in scripts] == ["module", "module", "text/javascript"]
    assert all(script["async"] is False for script in scripts)

    # Every fetch starts at once: both stylesheets in manifest (cascade) order, and a
    # preload for each script. The scripts run only after every stylesheet settled, one
    # after another in manifest order, as before.
    fetched_at_start = [
        "stylesheet:/k/a.css",
        "stylesheet:/k/b.css",
        "modulepreload:/k/m1.js",
        "preload:/k/k.js",
        "modulepreload:/k/m2.js",
    ]
    assert payload["held"] == {
        "atStart": fetched_at_start,
        "afterSecondStylesheet": fetched_at_start,
        "afterBothStylesheets": [*fetched_at_start, "script:/k/m1.js"],
        "afterFirstScript": [*fetched_at_start, "script:/k/m1.js", "script:/k/k.js"],
        "atEnd": [*fetched_at_start, "script:/k/m1.js", "script:/k/k.js", "script:/k/m2.js"],
    }
