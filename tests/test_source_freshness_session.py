"""The freshness session runs production browser code on what a served mirror answers.

``tests/dom/source-freshness-session.js`` drives ``static/source-freshness.js`` -- the
polling, the stale label, the newer-revision offer, pin switching, and opening a commit
the mirror lacks -- and the history panel's ``classifyPageFailure`` through a scripted
conversation, and ``tests/golden/cli-ui-source-freshness.tryscript.md`` pins its
transcript. So that the conversation is the real server's and not envelopes a test wrote
by hand, its responses come from ``tests/fixtures/source-freshness-responses.json``:
what the in-process application answered while a mirror went stale, refreshed, gained a
newer commit, switched its pin, lost its origin, invalidated an open all-branch history
cursor, and was asked for commits it did not have.
The first test here replays that story against a real store and fails when the
recording no longer matches.

Fetch times are wall-clock values, so every one is replaced by one fixed stand-in; the
backdated fetch the fixture writes stays literal. Commit IDs are
real: the origin is ``tests/source_mirror_fixture.py``'s, written by ``git fast-import``.
``make golden-update`` rewrites the recording and then the transcript.
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
from datetime import UTC, datetime
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
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import LineSelection, RepositorySelection
from metabrowser.cli.selection import pending_selection_opener
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session
from tests.golden_harness import (
    JSON_BODY,
    answer,
    check_recording,
    read_recording,
    run_session,
    serve_published,
    stand_in_sandbox,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source

RECORDING = "source-freshness-responses.json"
TRANSCRIPT = "cli-ui-source-freshness.tryscript.md"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# A full commit ID no repository in these tests has.
_ABSENT_COMMIT = "0123456789abcdef0123456789abcdef01234567"
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_STAND_IN_TIME = "2026-09-23T12:00:00Z"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    needs_git,
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


def _write_state(
    published: PublishedSource, *, operation: StoreOperation, fetched_at: str = FETCHED_AT
) -> None:
    """Record the store's last fetch, at the fixture's fixed time unless *fetched_at*
    names another, with the production writer."""

    with repository_store_lock(published.home, published.store_key):
        write_record_atomic(
            published.home,
            store_record(published.store_key, "state.yml"),
            RepositoryStoreState(
                default_remote_ref=published.default_remote_ref,
                default_revision=published.default_revision,
                last_fetch_at=fetched_at,
                last_operation=operation,
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )


class _Beside:
    """Data served beside the mirror, as a pull request's record is, for the recording.

    A stand-in: it fetches nothing. It is stale when told to be, and its refresh holds
    the turn it shares with the mirror's fetch until released, so what the server
    answers while only it is refreshing, and while a fetch of the mirror waits behind
    it, is recorded without a race.
    """

    key = "recording:beside"

    def __init__(self) -> None:
        self.stale = False
        self._released = threading.Event()
        self._released.set()

    def hold(self) -> None:
        self._released.clear()

    def release(self) -> None:
        self._released.set()

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        return self.stale

    async def refresh(self) -> None:
        await asyncio.to_thread(self._released.wait)
        self.stale = False


def _commit_fetch(client: TestClient, *, retry: bool = False) -> Any:
    body: dict[str, Any] = {"for": "commit", "retry": True} if retry else {"for": "commit"}
    return client.post("/api/source/refresh", json=body, headers=JSON_BODY)


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    _commit_on_topic(origin)

    # Serve mode would refresh this stale mirror on its own; the recording starts where
    # the page opens it, so the page's own request is the one that starts the refresh.
    serve_published(published)
    recorded: dict[str, Any] = {}
    try:
        with TestClient(server.app) as client:
            recorded["stale"] = client.get("/api/source/status").json()
            started = client.post("/api/source/refresh", json={}, headers=JSON_BODY)
            assert started.status_code == 202
            recorded["refresh_started"] = started.json()
            recorded["refreshed"] = _settle(client)
            history = client.get("/api/git/log", params={"limit": "1", "scope": "all"}).json()
            _git(origin, "branch", "side", recorded["refreshed"]["pin"])
            assert client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code == 202
            _settle(client)
            stale_cursor = client.get(
                "/api/git/log", params={"limit": "1", "scope": "all", "cursor": history["cursor"]}
            )
            assert stale_cursor.status_code == 409
            recorded["history_stale"] = {"status": 409, "body": stale_cursor.json()}
            switched = client.post(
                "/api/source/pin", json={"ref": recorded["refreshed"]["ref"]}, headers=JSON_BODY
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
            refused = client.post("/api/source/pin", json={"ref": "gone"}, headers=JSON_BODY)
            recorded["pin_refused"] = {"status": refused.status_code, "body": refused.json()}
            away = tmp_path / "origin-away.git"
            shutil.move(origin, away)
            assert client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code == 202
            recorded["failed"] = _settle(client)
        # A later start on a mirror last fetched long ago whose origin is gone: every
        # refresh the page asks for fails, so the page stays stale.
        _write_state(
            published,
            operation=StoreOperation(kind="refresh", outcome="origin_unavailable", at=FETCHED_AT),
        )
        with TestClient(server.app) as client:
            recorded["unreachable"] = client.get("/api/source/status").json()
            started = client.post("/api/source/refresh", json={}, headers=JSON_BODY)
            assert started.status_code == 202
            recorded["unreachable_started"] = started.json()
            recorded["unreachable_after"] = _settle(client)
            # A commit this stale mirror lacks: a page's own request fetches for it,
            # because the last fetch is older than the freshness window, and the fetch
            # cannot run.
            asked = _commit_fetch(client)
            recorded["commit_stale_started"] = answer(asked)
            recorded["commit_stale_unfetched"] = _settle(client)
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
            started = client.post("/api/source/refresh", json={}, headers=JSON_BODY)
            assert started.status_code == 202
            recorded["selection_refresh_started"] = started.json()
            recorded["selection_found"] = _settle(client)
        # One the fetch does not bring, then one whose fetch cannot run.
        for name, key in (("never", "selection_not_found"), ("gone", "selection_fetch_failed")):
            if key == "selection_fetch_failed":
                shutil.move(origin, away)
            missing = RepositorySelection(kind="tree", ref_and_path=(name.encode(),))
            serve_mirror(
                StoreMirror.from_published(published),
                pending_selection=pending_selection_opener(published, missing),
            )
            with TestClient(server.app) as client:
                assert (
                    client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code
                    == 202
                )
                recorded[key] = _settle(client)
                if key == "selection_fetch_failed":
                    retried = client.post("/api/source/refresh", json={}, headers=JSON_BODY)
                    assert retried.status_code == 202
                    recorded["selection_retry_started"] = retried.json()
                    _settle(client)
        # A commit the mirror lacks, asked for by its address in a served page. The
        # commit route names the miss and never fetches. The page asks for the fetch such
        # a commit waits for, which the server starts by itself only outside the
        # freshness window; a reader's retry always fetches.
        shutil.move(away, origin)
        # Served as a server serves it: there a refresh fetches only what is stale, and
        # a commit's address is opened nowhere else.
        beside = _Beside()
        serve_mirror(StoreMirror.from_published(published), serving=True, companion=beside)
        with TestClient(server.app) as client:
            # A fetch that just succeeded, so the page opens inside the window; the
            # origin gains the commit only after it.
            assert client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code == 202
            _settle(client)
            unfetched = _commit_on_topic(origin)
            recorded["commit_page"] = client.get("/api/source/status").json()
            for key, oid in (("commit_missing", unfetched), ("commit_absent", _ABSENT_COMMIT)):
                missing = client.get(f"/api/git/commit/{oid}")
                recorded[key] = {"oid": oid, **answer(missing)}
            # A request the route refuses is not an answer about the commit: here, one
            # from a page that shows another pin than the server serves.
            refused = client.get(
                f"/api/git/commit/{unfetched}", headers={"x-metabrowser-pin": _ABSENT_COMMIT}
            )
            recorded["commit_refused"] = {"oid": unfetched, **answer(refused)}
            # Inside the window a page's own request starts nothing.
            recorded["commit_fresh"] = answer(_commit_fetch(client))
            assert client.get("/api/source/status").json() == recorded["commit_page"], (
                "inside the freshness window a missing commit must not start a fetch"
            )
            # Only the data beside the mirror is stale. The page's own refresh starts
            # that data's refresh alone; a request for the commit's fetch then starts
            # no fetch of the mirror either, and the answer says so.
            beside.stale = True
            beside.hold()
            recorded["commit_beside_page"] = client.get("/api/source/status").json()
            recorded["commit_beside_refresh"] = answer(
                client.post("/api/source/refresh", json={}, headers=JSON_BODY)
            )
            recorded["commit_beside_only"] = answer(_commit_fetch(client))
            # A reader's retry fetches the mirror, here waiting its turn behind that
            # refresh, and a page's own request then joins the fetch that is running.
            recorded["commit_retry_started"] = answer(_commit_fetch(client, retry=True))
            recorded["commit_joined"] = answer(_commit_fetch(client))
            beside.release()
            recorded["commit_fetched"] = _settle(client)
            found = client.get(f"/api/git/commit/{unfetched}")
            recorded["commit_found"] = {
                "oid": unfetched,
                "status": found.status_code,
                "commit": found.json()["commit"]["id"],
            }
            still = client.get(f"/api/git/commit/{_ABSENT_COMMIT}")
            recorded["commit_absent_after"] = {"oid": _ABSENT_COMMIT, **answer(still)}
        # A mirror whose last refresh found the repository gone or private, inside the
        # window: the row says so in the words the command line uses.
        _write_state(
            published,
            operation=StoreOperation(kind="refresh", outcome="not_found_or_private", at=_utc_now()),
            fetched_at=_utc_now(),
        )
        serve_mirror(StoreMirror.from_published(published))
        with TestClient(server.app) as client:
            recorded["origin_not_shown"] = client.get("/api/source/status").json()
        # A server restarted on a folder, which serves no commit at all: what a page
        # still open on the mirror, or brought back by Back, is told.
        folder = tmp_path / "folder"
        folder.mkdir()
        serve_mirror(None)
        reset_source_session()
        server._set_root_dir(folder)
        with TestClient(server.app) as client:
            recorded["folder"] = client.get("/api/source/status").json()
    finally:
        serve_mirror(None)
    return stand_in_sandbox(
        _stand_in_times(recorded), tmp_path, published.store_key, home=published.home
    )


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
    assert recorded["selection_not_found"]["selection_state"] == "not_found"
    assert recorded["selection_fetch_failed"]["selection_state"] == "fetch_failed"
    assert recorded["selection_retry_started"]["status"]["selection_state"] == "pending"
    page = recorded["commit_page"]
    assert (page["refreshable"], page["refreshing"], page["stale"]) == (True, False, False)
    assert page["last_outcome"]["outcome"] == "succeeded"
    for key in ("commit_missing", "commit_absent", "commit_absent_after"):
        assert recorded[key]["status"] == 404
        assert recorded[key]["body"] == {"error": "unknown revision", "code": "commit_not_found"}
    assert recorded["commit_refused"]["status"] == 409
    assert recorded["commit_refused"]["body"]["code"] == "pin_changed"
    # Inside the window nothing starts; beside the mirror only, the mirror is not fetched.
    assert recorded["commit_fresh"]["status"] == 200
    assert recorded["commit_fresh"]["body"]["refresh"] == "fresh"
    assert recorded["commit_fresh"]["body"]["status"] == page
    assert recorded["commit_beside_refresh"]["body"]["status"]["refreshing"] is True
    beside = recorded["commit_beside_only"]
    assert (beside["status"], beside["body"]["refresh"]) == (202, "fresh")
    assert beside["body"]["status"]["refreshing"] is True
    assert recorded["commit_retry_started"]["body"]["refresh"] == "started"
    assert recorded["commit_joined"]["body"]["refresh"] == "joined"
    assert recorded["commit_fetched"]["last_outcome"]["outcome"] == "succeeded"
    assert recorded["commit_found"]["status"] == 200
    assert recorded["commit_found"]["commit"] == recorded["commit_missing"]["oid"]
    # Outside the window a page's own request fetches, and here the fetch cannot run.
    stale = recorded["commit_stale_started"]
    assert (stale["status"], stale["body"]["refresh"]) == (202, "started")
    assert stale["body"]["status"]["stale"] is True
    assert recorded["commit_stale_unfetched"]["last_outcome"]["outcome"] == "origin_unavailable"
    shown = recorded["origin_not_shown"]
    assert (shown["stale"], shown["last_outcome"]["outcome"]) == (False, "not_found_or_private")
    assert recorded["folder"]["pin"] is None
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_runs_on_the_recording() -> None:
    transcript = run_session("source-freshness-session.js")
    recording = read_recording(RECORDING)
    by_name = {step["step"]: step for step in transcript["steps"]}
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
    history = {row["failure"]: row["means"] for row in transcript["history"]}
    assert history["a refresh moved the refs"] == "stale"
    assert by_name["an unchanged status is a 304"]["repaints"] == 0
    assert by_name["switched before the first poll"]["paint"]["offer"].endswith("[Reload]")
    guard = transcript["guard"]
    assert [row["pin"] for row in guard["sent"]] == [guard["page"], None, None, guard["page"]]
    assert guard["answered"][-1] == 409
    assert guard["reported"] == [recording["after_switch"]["pin"]]
    # A page opened while its URL selection waited goes to the selection once, anchor kept.
    arrived = by_name["the fetch brought the selection; the page goes to it"]
    assert arrived["navigated"] == [recording["selection_found"]["selection_href"]]
    assert arrived["navigated"][0].endswith("#L1")
    assert "navigated" not in by_name["a URL selection waits for its fetch"]
    assert "navigated" not in by_name["a page goes to a selection once"]
    # The row says what became of the address, and offers a retry when its fetch failed.
    assert by_name["the address is not on the origin"]["paint"]["tone"] == "warning"
    failed = by_name["the address could not be fetched"]["paint"]
    assert failed["tone"] == "warning" and failed["offer"] == "Fetch the address again [Retry]"
    assert by_name["retry the address"]["requests"] == ["POST /api/source/refresh {}"]
    # Inside the freshness window a missing commit starts no fetch; a retry does.
    missing = recording["commit_missing"]["oid"]
    inside = by_name["inside the freshness window a missing commit starts no fetch"]
    assert inside["requests"] == []
    assert inside["commit"]["state"] == "not_found" and inside["commit"]["offer"] == "[Retry]"
    assert "as fetched" in inside["commit"]["detail"]
    retried = by_name["retry fetches for the commit"]
    assert retried["requests"] == ['POST /api/source/refresh {"for":"commit","retry":true}']
    assert retried["commit"]["state"] == "pending" and retried["commit"]["offer"] is None
    assert by_name["the commit waits while the fetch runs"]["commit"]["repaints"] == 0
    brought = by_name["the fetch brought the commit; it opens"]
    assert brought["requests"][-1] == f"GET /api/git/commit/{missing}"
    assert brought["commit"] == {"repaints": 1, "shows": missing}
    # Only a fetch of the mirror that ran lets the view say the origin lacks the commit.
    absent = by_name["the fetch ran and did not bring the commit"]["commit"]
    assert (
        absent["state"] == "not_found" and "no branch or tag there reaches it" in absent["detail"]
    )
    beside = by_name["no fetch of the mirror ran, and the view does not say one did"]["commit"]
    assert beside["state"] == "not_found" and "as fetched" in beside["detail"]
    assert "did not bring it" not in beside["detail"]
    # A re-ask that failed is a load failure, not an answer about the commit.
    refused = by_name["asking again failed; the view does not say not found"]["commit"]
    assert refused["state"] == "failed" and refused["title"] == "Could not load this commit."
    # Outside the window the page asks by itself, with the request the server floors.
    outside = by_name["outside the window the page asks for the fetch itself"]
    assert outside["requests"] == ['POST /api/source/refresh {"for":"commit"}']
    unfetched = by_name["the commit could not be fetched"]["commit"]
    assert unfetched["state"] == "fetch_failed" and unfetched["offer"] == "[Retry]"
    assert "The origin could not be read." in unfetched["detail"]
    left = by_name["the reader left before the fetch ended"]
    assert left["requests"] == ["GET /api/source/status"] and left["commit"]["repaints"] == 0
    joined = by_name["a fetch of the mirror already running is joined"]
    assert joined["requests"] == ['POST /api/source/refresh {"for":"commit"}']
    # A server that stops answering is not polled every second, nor waited for.
    stopped = by_name["the server stopped answering while the fetch ran"]
    assert stopped["timer"] == "slow" and stopped["commit"]["state"] == "fetch_failed"
    assert "The server did not answer." in stopped["commit"]["detail"]
    shown = by_name["the origin no longer shows the repository"]["paint"]["detail"]
    assert shown.startswith("The repository was not found, or it is private and could not be read.")
