"""Preview pane loading, empty, and connection states.

The browserless session drives the production pane lifecycle in ``navigation.js`` and
runs the ``app.js`` functions that compose it (selection, re-selection, tab switches,
the inventory stream's reconnect, and the startup settle) with the real navigation
controller. Its complete output is pinned by ``cli-ui-file-lifecycle.tryscript.md``.
The checks below assert the invariants in that output, plus the few seams the session
cannot execute: the shell markup ``server.py`` ships and the startup and Quick File
wiring inside larger functions.
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


@pytest.fixture(scope="module")
def session() -> dict[str, Any]:
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


def test_loading_never_reads_as_select_a_file(session: dict[str, Any]) -> None:
    payload = session

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

    # Every placeholder a loading claim can produce is a loading indicator.
    loading_directives = [
        landing["shipped"],
        landing["whileLoading"],
        payload["loadingToContent"]["whileLoading"],
        empty["whileLoading"],
    ]
    assert all(directive["paint"] == "loading" for directive in loading_directives)
    assert SELECT_A_FILE not in json.dumps(loading_directives)

    # The real activateNavPanel neither claims nor repaints: the folder loading
    # underneath a Files -> Git -> Files switch keeps its claim and lands.
    switch = payload["shell"]["tabSwitchDuringLoad"]
    loading = switch["loading"]
    assert loading["phase"] == "loading"
    assert loading["path"] == "big"
    assert switch["onGitTab"]["pane"] == loading
    assert switch["onGitTab"]["tabs"] == ["files:none", "git:"]
    assert switch["backOnFilesTab"]["pane"] == loading
    assert switch["landed"]["claim"] == loading["claim"]
    assert switch["landed"]["phase"] == "content"

    unselected = payload["landingWithoutSelection"]
    assert unselected["idle"] == {"message": SELECT_A_FILE, "paint": "idle"}
    assert unselected["abandonedLoadSettled"] is False
    assert unselected["commitRouteWithoutOwner"]["unclaimed"]["paint"] == "idle"
    assert unselected["commitRouteWithOwner"]["unclaimed"] == {"paint": "none"}

    startup = payload["shell"]["startupSettle"]
    assert startup["commitRouteWithoutOwner"]["phase"] == "idle"
    assert startup["commitRouteWithoutOwner"]["shows"] == f"preview-empty: {SELECT_A_FILE}"
    assert startup["commitRouteWithGitOwner"]["owner"] == "git"
    assert SELECT_A_FILE not in startup["commitRouteWithGitOwner"]["shows"]
    # A /view/ route's startup settle leaves the shipped loading state alone.
    assert startup["viewRoute"]["beforeSelection"]["phase"] == "starting"
    assert startup["viewRoute"]["afterSelection"]["phase"] == "content"
    assert startup["locationWithoutSelection"]["phase"] == "idle"


def test_unreachable_server_is_a_connection_state_not_a_file_error(
    session: dict[str, Any],
) -> None:
    failures = session["failures"]

    unreachable = failures["serverUnreachable"]
    assert unreachable["outcome"]["status"] == "unreachable"
    assert len(unreachable["shown"]) == 1
    shown = unreachable["shown"][0]
    assert shown["kind"] == "unreachable"
    assert shown["summary"] == "Metabrowser is not reachable."
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

    # A body read that fails after the headers is the same lost connection; a body
    # that is not JSON is still a response problem.
    assert failures["bodyRead"] == {
        "abortPassesThrough": True,
        "interruptedName": "ServerUnreachableError",
        "interruptedPreservesCause": "terminated",
        "malformedJsonPassesThrough": True,
        "markedOnce": True,
    }
    body = session["shell"]["bodyReadFailure"]
    for key in ("interruptedJsonBody", "interruptedErrorBody"):
        assert body[key]["outcome"]["status"] == "unreachable", key
        assert body[key]["pane"]["phase"] == "unreachable", key
        assert body[key]["reconnectRetry"] is not None, key
    assert body["malformedJson"]["outcome"]["status"] == "error"
    assert body["malformedJson"]["reconnectRetry"] is None


def test_reopening_a_failed_path_loads_it_again(session: dict[str, Any]) -> None:
    reselect = session["shell"]["reselectAfterFailure"]

    assert reselect["unreachable"]["pane"]["phase"] == "unreachable"
    retried = reselect["retriedUnreachable"]
    assert retried["fetches"] == 2
    assert retried["outcome"]["status"] == "opened"
    assert retried["pane"]["phase"] == "content"

    # A path the pane already shows only takes its fragment: no second request.
    reopened = reselect["reopenedContent"]
    assert reopened["fetches"] == retried["fetches"]
    assert reopened["pane"]["claim"] == retried["pane"]["claim"]
    assert reopened["fragments"] == retried["fragments"] + 1

    assert reselect["fileError"]["pane"]["phase"] == "error"
    assert reselect["retriedFileError"]["fetches"] == 2
    assert reselect["retriedFileError"]["pane"]["phase"] == "content"

    # After a Git commit replaced it, opening the same file selects it again.
    assert reselect["afterGitClaim"]["pane"]["owner"] == "file"
    assert reselect["afterGitClaim"]["pane"]["phase"] == "content"


def test_reconnect_retries_only_the_unreachable_selection(session: dict[str, Any]) -> None:
    recovery = session["shell"]["reconnectRetry"]

    assert recovery["streamUrl"] == "/api/events?scope=root-depth-2"
    assert recovery["failed"]["phase"] == "unreachable"
    # The real onopen retries through selectFile, which claims before its first
    # await, so a duplicate open finds the pane loading and does not retry twice.
    assert recovery["claimedByOpen"]["phase"] == "loading"
    assert recovery["claimedByOpen"]["claim"] == recovery["failed"]["claim"] + 1
    assert recovery["whileRetrying"]["claim"] == recovery["claimedByOpen"]["claim"]
    assert recovery["whileRetrying"]["shows"] == "loading mb-delayed-loading: Loading folder…"
    assert recovery["fetchesForFailedFolder"] == 2
    assert recovery["recovered"]["phase"] == "content"
    assert recovery["catalogFeedStarts"] == 2
    assert recovery["paletteReconnects"] == 2
    # A Git commit claimed the pane after the failure: nothing is retried.
    assert recovery["afterGitClaim"]["fetches"] == 1
    assert recovery["afterGitClaim"]["pane"]["owner"] == "git"


def test_shell_ships_the_placeholder_the_pane_starts_in(session: dict[str, Any]) -> None:
    html = _render_index_html()
    pane = html[html.index('id="preview-pane"') :]
    pane = pane[pane.index(">") + 1 : pane.index("</main>")]
    # The pane closes, and then the frame that wraps it.
    pane = pane[: pane.rindex("</div>")]
    pane = pane[: pane.rindex("</div>")]
    shipped = re.sub(r"\s+", " ", pane).strip()

    assert SELECT_A_FILE not in shipped
    # server.py and app.js's previewPlaceholderHtml must agree on the starting
    # placeholder, or the first selection replaces one spinner with another.
    assert shipped == session["shell"]["shippedPlaceholderHtml"]


def test_shell_seams_the_session_cannot_execute() -> None:
    app = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "var previewClaimGeneration" not in app
    # The prompt text lives in the module; the shell only paints directives.
    assert SELECT_A_FILE not in app

    # The session pins the ordering behaviorally (a duplicate stream open does not
    # retry twice); this names the reason it holds.
    selection = _function_source(app, "selectFile")
    assert selection.index('claimPreview("file"') < selection.index("await ")

    # Startup settles a /commit/ route once the shell tools, and with them the Git
    # panel, have settled. The DOMContentLoaded handler is too large to run here.
    assert ".finally(settleCommitRoutePreview);" in app

    quick_file = _function_source(app, "initQuickFileFinder")
    assert "describeOpenFailure: window.MetabrowserNavigationRoute.openFailureOutcome" in quick_file


def test_quick_file_reports_connection_failures_with_the_shared_wording() -> None:
    palette = (STATIC / "search-palette.js").read_text(encoding="utf-8")

    assert "Could not open this file. Try again." not in palette
    assert "options.describeOpenFailure(error)" in palette
    assert 'outcome.status === "unreachable"' in palette
    # A settled failure carries its own message; it is never classified again.
    assert "describeOpenFailure(outcome)" not in palette
