"""The freshness session runs production browser code on what a served mirror answers.

``tests/dom/source-freshness-session.js`` drives ``static/source-freshness.js`` -- the
polling, the stale label, the newer-revision offer, and pin switching -- and the history
panel's ``classifyPageFailure`` through a scripted conversation, and
``tests/golden/cli-ui-source-freshness.tryscript.md`` pins its transcript. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses
come from ``tests/fixtures/source-freshness-responses.json``: what the in-process
application answered while a mirror went stale, refreshed, gained a newer commit,
switched its pin, lost its origin, and invalidated an open all-branch history cursor.
The first test here replays that story against a real store and fails when the
recording no longer matches.

Fetch times are wall-clock values, so every one is replaced by one fixed stand-in; the
backdated fetch the fixture writes stays literal. Commit IDs are
real: the origin is ``tests/source_mirror_fixture.py``'s, written by ``git fast-import``.

Regenerate the recording after an intended change, then the transcript:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_source_freshness_session.py
    npx --no-install tryscript run --update tests/golden/cli-ui-source-freshness.tryscript.md
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.locks import repository_store_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
)
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import LineSelection, RepositorySelection
from metabrowser.cli.selection import pending_selection_opener
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = REPO_ROOT / "tests" / "dom" / "source-freshness-session.js"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "source-freshness-responses.json"

_JSON = {"content-type": "application/json"}
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_STAND_IN_TIME = "2026-09-23T12:00:00Z"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


def _git(origin: Path, *args: str, stream: bytes | None = None) -> str:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.run(
        ["git", "--git-dir", str(origin), *args],
        check=True,
        capture_output=True,
        input=stream,
        env=env,
    ).stdout.decode()


def _commit_on_topic(origin: Path) -> str:
    """Add ``third`` on ``topic`` with a fixed identity and date."""

    parent = _git(origin, "rev-parse", "--verify", "refs/heads/topic").strip()
    _git(
        origin,
        "fast-import",
        "--quiet",
        "--done",
        stream=(
            b"commit refs/heads/topic\n"
            b"committer Mirror <mirror@example.invalid> 1767236400 +0000\n"
            b"data 6\nthird\n"
            b"from " + parent.encode() + b"\n"
            b"M 100644 inline THIRD.md\ndata 6\nthird\n\n"
            b"done\n"
        ),
    )
    return _git(origin, "rev-parse", "--verify", "refs/heads/topic").strip()


def _settle(client: TestClient) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while True:
        status = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.02)


def _stand_in_times(value: Any) -> Any:
    """Replace every wall-clock time by one fixed stand-in; keep the fixture's own.

    One stand-in rather than one per distinct time: two refreshes a second apart on one
    run and within the same second on another must record the same.
    """

    def replace(match: re.Match[str]) -> str:
        found = match.group(0)
        return found if found == FETCHED_AT else _STAND_IN_TIME

    return json.loads(_TIMESTAMP.sub(replace, json.dumps(value)))


def _write_state(published: PublishedSource, *, operation: StoreOperation) -> None:
    """Record the store's last fetch at the fixture's fixed time, with the production writer."""

    with repository_store_lock(published.home, published.store_key):
        write_record_atomic(
            published.home,
            store_record(published.store_key, "state.yml"),
            RepositoryStoreState(
                default_remote_ref=published.default_remote_ref,
                default_revision=published.default_revision,
                last_fetch_at=FETCHED_AT,
                last_operation=operation,
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    _commit_on_topic(origin)

    async def opener() -> GitRevisionSubject:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=published.default_revision,
            store_identity=published.store_id,
            ref=published.default_remote_ref,
        )

    serve_subject_opener(opener)
    # Serve mode would refresh this stale mirror on its own; the recording starts where
    # the page opens it, so the page's own request is the one that starts the refresh.
    serve_mirror(StoreMirror.from_published(published))
    recorded: dict[str, Any] = {}
    try:
        with TestClient(server.app) as client:
            recorded["stale"] = client.get("/api/source/status").json()
            started = client.post("/api/source/refresh", json={}, headers=_JSON)
            assert started.status_code == 202
            recorded["refresh_started"] = started.json()
            recorded["refreshed"] = _settle(client)
            history = client.get("/api/git/log", params={"limit": "1", "scope": "all"}).json()
            _git(origin, "branch", "side", recorded["refreshed"]["pin"])
            assert client.post("/api/source/refresh", json={}, headers=_JSON).status_code == 202
            _settle(client)
            stale_cursor = client.get(
                "/api/git/log", params={"limit": "1", "scope": "all", "cursor": history["cursor"]}
            )
            assert stale_cursor.status_code == 409
            recorded["history_stale"] = {"status": 409, "body": stale_cursor.json()}
            switched = client.post(
                "/api/source/pin", json={"ref": recorded["refreshed"]["ref"]}, headers=_JSON
            )
            assert switched.status_code == 200
            recorded["switched"] = switched.json()
            recorded["after_switch"] = client.get("/api/source/status").json()
            # A data request from a page still showing the pin before the switch.
            refused_read = client.get(
                "/api/tree",
                params={"depth": "1"},
                headers={"x-metabrowser-pin": recorded["refreshed"]["pin"]},
            )
            assert refused_read.status_code == 409
            recorded["pin_changed"] = {
                "status": refused_read.status_code,
                "headers": {
                    "x-metabrowser-pin-changed": refused_read.headers["x-metabrowser-pin-changed"]
                },
                "body": refused_read.json(),
            }
            refused = client.post("/api/source/pin", json={"ref": "gone"}, headers=_JSON)
            recorded["pin_refused"] = {"status": refused.status_code, "body": refused.json()}
            away = tmp_path / "origin-away.git"
            shutil.move(origin, away)
            assert client.post("/api/source/refresh", json={}, headers=_JSON).status_code == 202
            recorded["failed"] = _settle(client)
        # A later start on a mirror last fetched long ago whose origin is gone: every
        # refresh the page asks for fails, so the page stays stale.
        _write_state(
            published,
            operation=StoreOperation(kind="refresh", outcome="origin_unavailable", at=FETCHED_AT),
        )
        with TestClient(server.app) as client:
            recorded["unreachable"] = client.get("/api/source/status").json()
            started = client.post("/api/source/refresh", json={}, headers=_JSON)
            assert started.status_code == 202
            recorded["unreachable_started"] = started.json()
            recorded["unreachable_after"] = _settle(client)
        # A URL selection the mirror lacked when the page opened: a branch the origin
        # gained since, served once the refresh the page asks for brings it.
        shutil.move(away, origin)
        _git(origin, "branch", "later", recorded["refreshed"]["latest"])
        selection = RepositorySelection(
            kind="blob", ref_and_path=(b"later", b"README.md"), lines=LineSelection(1, 1)
        )
        serve_mirror(
            StoreMirror.from_published(published),
            pending_selection=pending_selection_opener(published, selection),
        )
        with TestClient(server.app) as client:
            recorded["selection_pending"] = client.get("/api/source/status").json()
            started = client.post("/api/source/refresh", json={}, headers=_JSON)
            assert started.status_code == 202
            recorded["selection_refresh_started"] = started.json()
            recorded["selection_found"] = _settle(client)
    finally:
        serve_mirror(None)
        reset_source_session()
    return _stand_in_times(recorded)


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    assert recorded["stale"]["stale"] is True and recorded["stale"]["refreshing"] is False
    assert recorded["refresh_started"]["status"]["refreshing"] is True
    refreshed = recorded["refreshed"]
    assert refreshed["latest"] != refreshed["pin"], "the refresh must bring a newer commit"
    assert recorded["after_switch"]["generation"] == refreshed["generation"] + 1
    assert recorded["history_stale"]["body"]["code"] == "history_stale"
    assert recorded["failed"]["last_outcome"]["outcome"] == "origin_unavailable"
    assert recorded["unreachable"]["stale"] is True
    assert recorded["unreachable_after"]["stale"] is True
    assert recorded["unreachable_after"]["last_outcome"]["outcome"] == "origin_unavailable"
    assert recorded["selection_pending"]["selection_state"] == "pending"
    found = recorded["selection_found"]
    assert (found["selection_state"], found["ref_name"]) == ("found", "later")
    assert found["selection_href"].endswith("#L1")
    rendered = json.dumps(recorded, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        FIXTURE.write_text(rendered, encoding="utf-8")
        return
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "a served mirror answers differently now; regenerate with GOLDEN_UPDATE=1 "
        "and update tests/golden/cli-ui-source-freshness.tryscript.md"
    )


def transcript_pin_after_switch() -> str:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["after_switch"]["pin"]


def test_the_session_runs_on_the_recording() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    steps = json.loads(result.stdout)["steps"]
    by_name = {step["step"]: step for step in steps}
    assert by_name["open a stale page"]["requests"] == [
        "GET /api/source/status",
        "POST /api/source/refresh {}",
    ]
    offer = by_name["the refresh brought a newer commit"]["paint"]["offer"]
    assert offer.endswith("[Switch] → refs/remotes/origin/topic")
    assert by_name["accept the offer"]["reloads"] == 1
    assert by_name["a refused switch says why and does not reload"]["reloads"] == 0
    polls = by_name["a stale page whose refresh fails asks once"]["requests"]
    assert len(polls) == 2 and all(request.startswith("GET ") for request in polls)
    transcript = json.loads(result.stdout)
    history = {row["failure"]: row["means"] for row in transcript["history"]}
    assert history["a refresh moved the refs"] == "stale"
    assert by_name["an unchanged status is a 304"]["repaints"] == 0
    assert by_name["switched before the first poll"]["paint"]["offer"].endswith("[Reload]")
    guard = transcript["guard"]
    assert [row["pin"] for row in guard["sent"]] == [guard["page"], None, None, guard["page"]]
    assert guard["answered"][-1] == 409
    assert guard["reported"] == [transcript_pin_after_switch()]
    # A page opened while its URL selection waited goes to the selection once, anchor kept.
    recording = json.loads(FIXTURE.read_text(encoding="utf-8"))
    arrived = by_name["the fetch brought the selection; the page goes to it"]
    assert arrived["navigated"] == [recording["selection_found"]["selection_href"]]
    assert arrived["navigated"][0].endswith("#L1")
    assert "navigated" not in by_name["a URL selection waits for its fetch"]
    assert "navigated" not in by_name["a page goes to a selection once"]
