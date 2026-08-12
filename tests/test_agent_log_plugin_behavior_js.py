"""Browser behavior checks for the built-in agent-log plugin."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = Path(__file__).resolve().parent / "dom" / "agent_log_plugin_behavior.js"
PLUGIN_JS = REPO_ROOT / "src/metabrowser/builtin_plugins/agent_log/index.js"
APP_JS = REPO_ROOT / "src/metabrowser/static/app.js"


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
        "mixedUnknownKindHasNoChip": True,
        "singleKindFilterHidden": True,
        "singleKnownKindVisible": True,
        "unknownFilterHidden": True,
        "unknownEventHiddenWhenFiltering": True,
        "unknownEventRestoredWithAllKinds": True,
        "unknownKindLabelHidden": True,
        "unknownSummaryLabelHidden": True,
        "unknownSummaryValueVisible": True,
        "usesSharedMultiSelect": True,
        "usesWrappedChipCluster": True,
    }


def test_agent_log_scopes_filter_and_raw_state_to_each_container() -> None:
    source = PLUGIN_JS.read_text()
    assert "const logViewStates = new WeakMap()" in source
    assert "logViewStates.set(container, state)" in source
    assert "logViewStates.delete(container)" in source
    assert "state.rawCache" in source
    assert "logFilterUnbind" not in source
    assert "_logEventRawCache" not in source


def test_shell_disposes_the_specific_plugin_container() -> None:
    source = APP_JS.read_text()
    start = source.index("function mountPluginView(container, pluginView, ctx)")
    block = source[start : start + 500]
    assert "activePluginDisposers.push(() => pluginView.dispose(container))" in block
