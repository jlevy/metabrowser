"""Serve mode for GitHub URLs, with a local origin standing in for github.com.

``metabrowser.cache.acquire.remote_url_for`` sends ``https://github.com/octo/demo`` to
the ``file://`` origin in ``tests/github_origin.py`` for acquisition and refresh alike,
so the store, the banner, and ``/api/source/status`` carry the canonical GitHub identity
while nothing leaves the machine. The GitHub provider sees no ``gh``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser import server
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource
from metabrowser.cli.main import _app
from metabrowser.git.tree_source import GitPath
from metabrowser.mirror_refresh import RefreshResult
from metabrowser.source import reset_source_session
from metabrowser.source_routes import GENERATION_HEADER, PIN_CHANGED_HEADER
from tests.git_pin_harness import git_env
from tests.github_origin import FIRST_COMMIT, SECOND_COMMIT, github_origin
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

REPO = "https://github.com/octo/demo"
runner = CliRunner()


@pytest.fixture
def origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    _allow_installed_git(monkeypatch)
    built = github_origin(tmp_path)
    local = f"file://{built.resolve()}"

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == REPO else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
    # No gh anywhere: the provider imports the lookup by name, and every other gh run,
    # a pull request's among them, goes through the gh module's own. Nothing here can
    # reach the gh a developer has signed in.
    monkeypatch.setattr("metabrowser.builtin_plugins.github.provider.gh_executable", lambda: None)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    yield built
    reset_source_session()


def _serve(url: str) -> Any:
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_class,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, [url, "--no-open"])
    if result.exit_code == 0:
        assert server_class.call_args.args[0].app is server.app
    return result


def _served_line(stdout: str) -> str:
    return next(line for line in stdout.splitlines() if line.startswith("Serving "))


def _settle(client: TestClient) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while True:
        status = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.02)


def test_a_blob_url_serves_its_branch_and_opens_at_the_file_and_lines(origin: Path) -> None:
    result = _serve(f"{REPO}/blob/release/v1/docs/v1.md#L1-L2")
    assert result.exit_code == 0, result.output
    wire = GitPath.from_display("docs/v1.md").to_wire()
    assert _served_line(result.stdout).startswith(
        f"Serving {REPO} at http://127.0.0.1:8411/view/{wire}#L1-L2"
    )
    assert f"Revision: {SECOND_COMMIT} (release/v1)\n" in result.stdout
    assert "Selection: blob docs/v1.md#L1-L2\n" in result.stdout
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
        assert (status["pin"], status["ref_name"]) == (SECOND_COMMIT, "release/v1")
        assert status["pull_request"] is None and status["selection_state"] is None
        shell = client.get("/view/").text
        context = re.search(r"window\.METABROWSER_REPOSITORY_CONTEXT=(\{[^<]*\});", shell)
        assert context is not None, "a GitHub mirror has a repository context"
        assert '"owner": "octo"' in context.group(1) and '"name": "demo"' in context.group(1)
        assert f'"revision": "{SECOND_COMMIT}"' in context.group(1)
        assert '"branch": "release/v1"' in context.group(1)


def test_a_pull_request_it_cannot_open_serves_the_default_branch_and_says_why(
    origin: Path,
) -> None:
    result = _serve(f"{REPO}/pull/7/files")
    assert result.exit_code == 0, result.output
    assert f"Revision: {FIRST_COMMIT} (topic)\n" in result.stdout
    note = next(line for line in result.stdout.splitlines() if line.startswith("Pull request:"))
    assert note.startswith(f"Pull request: 7 (not opened: pull request 7 of {REPO}: ")
    assert note.endswith("(gh_missing); the pin is the default branch)")
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
        assert (status["pin"], status["pull_request"]) == (FIRST_COMMIT, 7)


def _push_branch(origin: Path, tmp_path: Path, name: str) -> str:
    env = git_env(tmp_path)
    commit = subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "refs/heads/release/v1"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    subprocess.run(
        ["git", "--git-dir", str(origin), "update-ref", f"refs/heads/{name}", commit],
        check=True,
        env=env,
    )
    return commit


def test_a_selection_the_mirror_lacks_is_fetched_once_then_served(
    origin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first open acquires; a branch pushed later is fetched in the background.

    Serving the selection once the fetch brings it is a pin switch like any other: it
    takes a new session generation, so a page rendered for the default pin while the
    fetch ran is refused as ``pin_changed`` rather than reading the new pin's files.
    """

    assert _serve(REPO).exit_code == 0
    reset_source_session()
    later = _push_branch(origin, tmp_path, "later")
    fetch_may_run = threading.Event()
    real_refresh = StoreMirror.refresh

    async def gated_refresh(mirror: StoreMirror) -> RefreshResult:
        await asyncio.to_thread(fetch_may_run.wait, 30)
        return await real_refresh(mirror)

    monkeypatch.setattr(StoreMirror, "refresh", gated_refresh)

    result = _serve(f"{REPO}/tree/later/docs")
    assert result.exit_code == 0, result.output
    assert f"Revision: {FIRST_COMMIT} (topic)\n" in result.stdout
    assert "Selection: tree not in the mirror yet" in result.stdout
    with TestClient(server.app) as client:
        waiting = client.get("/api/source/status").json()
        assert (waiting["selection_state"], waiting["pin"]) == ("pending", FIRST_COMMIT)
        page = waiting["generation"]
        shell = client.get("/view/").text
        assert f"window.METABROWSER_SOURCE_GENERATION={json.dumps(page)};" in shell
        fetch_may_run.set()
        status = _settle(client)
        assert status["selection_state"] == "found"
        assert (status["pin"], status["ref_name"]) == (later, "later")
        # Whatever form the generation takes, the switch changed it, and the guard
        # refuses the page's with the one now served.
        served = status["generation"]
        assert served != page
        stale_page = {GENERATION_HEADER: str(page)}
        refused = client.get("/api/tree", params={"depth": "1"}, headers=stale_page)
        assert refused.status_code == 409 and refused.json()["code"] == "pin_changed"
        assert refused.json()["generation"] == served
        assert refused.headers[PIN_CHANGED_HEADER] == str(served)


def test_a_selection_no_fetch_brings_is_reported_not_found(origin: Path) -> None:
    assert _serve(REPO).exit_code == 0
    reset_source_session()
    result = _serve(f"{REPO}/tree/never/docs")
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        page = client.get("/api/source/status").json()["generation"]
        status = _settle(client)
        assert status["selection_state"] == "not_found"
        # Nothing was switched, so a page rendered for the default pin stays current.
        assert (status["pin"], status["generation"]) == (FIRST_COMMIT, page)


def test_one_shot_modes_still_refuse_a_missing_selection(origin: Path) -> None:
    result = runner.invoke(_app, [f"{REPO}/tree/never", "--api", "/api/source/status"])
    assert result.exit_code == 1
    assert "(ref_not_found)" in str(result.exception)
