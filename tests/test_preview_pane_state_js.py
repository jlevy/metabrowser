"""Preview pane loading, empty, and connection states.

The browserless session drives the production pane lifecycle in ``navigation.js``
through every transition the shell composes; its complete output is pinned by
``cli-ui-file-lifecycle.tryscript.md``. The structural checks below protect the thin
``app.js`` and ``server.py`` seams that hand those decisions to the pane.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser import server as proc_browser

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION = Path(__file__).resolve().parent / "dom" / "preview-pane-state-session.js"
STATIC = REPO_ROOT / "src" / "metabrowser" / "static"
SELECT_A_FILE = "Select a file to preview."


def _function_source(js: str, name: str) -> str:
    """One top-level function's source, up to the next column-zero definition."""

    start = js.index(f"function {name}(")
    end = js.find("\nfunction ", start + 1)
    return js[start:] if end == -1 else js[start:end]


def _render_index_html() -> str:
    class _FakeQuery:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeReq:
        def __init__(self) -> None:
            self.query_params = _FakeQuery()
            self.headers: dict[str, str] = {}

    response = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    body = response.body
    return body.decode() if isinstance(body, (bytes, bytearray)) else str(body)


def _run_session() -> dict[str, Any]:
    if shutil.which("node") is None:
        pytest.skip("node not available; skipping preview pane browserless session")
    result = subprocess.run(
        ["node", str(SESSION)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return cast(dict[str, Any], json.loads(result.stdout))


def test_loading_never_reads_as_select_a_file() -> None:
    payload = _run_session()

    landing = payload["rootLanding"]
    assert landing["target"] == {"path": ""}
    assert landing["shipped"]["paint"] == "loading"
    assert landing["shipped"] == {"paint": "loading", "subject": "preview"}
    assert landing["whileLoading"] == {"paint": "loading", "subject": "folder"}
    assert landing["afterSettle"] == {"paint": "none"}

    assert payload["loadingToContent"]["whileLoading"]["subject"] == "file"
    assert payload["loadingToContent"]["snapshot"]["phase"] == "content"

    empty = payload["loadingToEmptyFolder"]
    assert empty["response"] == {"cacheRetained": False, "commit": "folder"}
    assert empty["settled"] is True
    assert empty["snapshot"]["phase"] == "content"

    switch = payload["panelSwitchDuringLoad"]
    assert switch["claimCurrentAfterSwitch"] is True
    assert switch["afterSwitch"] == switch["beforeSwitch"]
    assert switch["afterSwitch"]["paint"] == "loading"
    assert switch["afterSettle"]["phase"] == "content"

    # Every placeholder a loading claim can produce is a loading indicator.
    loading_directives = [
        landing["shipped"],
        landing["whileLoading"],
        payload["loadingToContent"]["whileLoading"],
        empty["whileLoading"],
        switch["beforeSwitch"],
        switch["afterSwitch"],
        payload["recoveryOnReconnect"]["whileRetrying"],
    ]
    assert all(directive["paint"] == "loading" for directive in loading_directives)
    assert SELECT_A_FILE not in json.dumps(loading_directives)

    unselected = payload["landingWithoutSelection"]
    assert unselected["idle"] == {"message": SELECT_A_FILE, "paint": "idle"}
    assert unselected["abandonedLoadSettled"] is False
    assert unselected["commitRouteWithoutOwner"]["unclaimed"]["paint"] == "idle"
    assert unselected["commitRouteWithOwner"]["unclaimed"] == {"paint": "none"}


def test_unreachable_server_is_a_connection_state_not_a_file_error() -> None:
    payload = _run_session()
    failures = payload["failures"]

    unreachable = failures["serverUnreachable"]
    assert unreachable["outcome"]["status"] == "unreachable"
    assert len(unreachable["shown"]) == 1
    shown = unreachable["shown"][0]
    assert shown["kind"] == "unreachable"
    assert "isn’t reachable" in shown["summary"]
    assert "metab <folder>" in shown["detail"]
    assert "Could not open" not in json.dumps(unreachable)
    assert "Failed to fetch" not in json.dumps(unreachable)
    assert unreachable["snapshot"]["phase"] == "unreachable"

    for key in ("httpNotFound", "httpServerError", "rendererTypeError"):
        settled = failures[key]
        assert settled["shown"][0]["kind"] == "error", key
        assert settled["shown"][0]["summary"] == "Could not open this file.", key
        assert settled["snapshot"]["phase"] == "error", key
    assert failures["httpNotFound"]["outcome"]["status"] == "not-found"
    assert failures["httpServerError"]["shown"][0]["detail"] == "The request failed (HTTP 500)."

    assert failures["abortPassesThrough"] is True
    assert failures["aborted"]["outcome"] == {"status": "cancelled"}
    assert failures["aborted"]["shown"] == []
    assert failures["aborted"]["snapshot"]["phase"] == "loading"

    assert failures["quickFile"]["unreachableThrow"]["status"] == "unreachable"
    assert failures["quickFile"]["unreachableThrow"]["message"] == unreachable["outcome"]["message"]
    assert failures["quickFile"]["opaqueThrow"] == {
        "message": "Could not open this file. Try again.",
        "status": "error",
    }


def test_reconnect_retries_only_the_unreachable_selection() -> None:
    recovery = _run_session()["recoveryOnReconnect"]

    assert recovery["beforeFailure"] is None
    assert recovery["retry"] == {"folder": True, "path": "empty", "viewId": "overview"}
    assert recovery["duplicateOpen"] is None
    assert recovery["whileRetrying"] == {"paint": "loading", "subject": "folder"}
    assert recovery["settled"] is True
    assert recovery["afterRecovery"] is None
    assert recovery["movedOnRetry"] is None


def test_shell_ships_a_loading_preview_rather_than_a_prompt() -> None:
    html = _render_index_html()
    pane = html[html.index('id="preview-pane"') :]
    pane = pane[: pane.index("</main>")]

    assert SELECT_A_FILE not in pane
    assert '<div class="loading mb-delayed-loading"><div class="spinner"></div>' in pane
    assert 'class="sr-only">Loading preview…</span>' in pane


def test_shell_composes_pane_states_from_the_navigation_module() -> None:
    app = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "MetabrowserNavigationRoute.createPreviewPaneLifecycle()" in app
    assert "var previewClaimGeneration" not in app
    # The prompt text lives in the module; the shell only paints directives.
    assert SELECT_A_FILE not in app

    activate = _function_source(app, "activateNavPanel")
    # A tab switch changes the visible navigation list, not the selection, so
    # it neither invalidates an in-flight load nor repaints the pane.
    assert "claimPreview(" not in activate
    assert "preview-pane" not in activate
    assert "innerHTML" not in activate

    landing = _function_source(app, "showNavigationLanding")
    assert 'claimPreview("none")' in landing
    assert "previewPlaceholderHtml(previewPane.placeholder(" in landing

    selection = app[
        app.index("async function selectFile(") : app.index("function openedFileOutcome(")
    ]
    assert "previewPane.placeholder(previewClaim)" in selection
    # Only a rejected fetch is a transport failure; HTTP errors and renderer
    # exceptions keep their own wording.
    assert re.search(
        r"fetch\([^;]*\)\.catch\(\(error\) => \{\s*throw window\.MetabrowserNavigationRoute\.requestFailure\(error\);",
        selection,
    )

    failure = _function_source(app, "fileSelectionFailureOutcome")
    assert "pane: previewPane" in failure
    assert "previewErrorHtml(failure.summary, failure.detail)" in failure
    assert "Could not open this file." not in failure

    opened = _function_source(app, "openedFileOutcome")
    assert 'previewPane.settle(previewClaim, "content")' in opened

    onopen = app[app.index("inventoryEventSource.onopen") :]
    onopen = onopen[: onopen.index("inventoryEventSource.onerror")]
    assert "retryUnreachablePreview();" in onopen
    retry = _function_source(app, "retryUnreachablePreview")
    assert "previewPane.reconnected()" in retry
    assert "selectFile(retry.path, retry.viewId)" in retry

    deferred = _function_source(app, "settleUnclaimedPreview")
    assert "previewPane.settleUnclaimed()" in deferred

    quick_file = _function_source(app, "initQuickFileFinder")
    assert "describeOpenFailure: window.MetabrowserNavigationRoute.openFailureOutcome" in quick_file


def test_quick_file_reports_connection_failures_with_the_shared_wording() -> None:
    palette = (STATIC / "search-palette.js").read_text(encoding="utf-8")

    assert "Could not open this file. Try again." not in palette
    assert "options.describeOpenFailure(error)" in palette
    assert 'outcome.status === "unreachable"' in palette
