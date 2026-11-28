"""The freshness session runs production browser code on what a served mirror answers.

``tests/dom/source-freshness-session.js`` drives ``static/source-freshness.js`` -- the
polling, the stale label, following a branch, pin switching, and opening a commit
the mirror lacks -- and the history panel's ``classifyPageFailure`` through a scripted
conversation, and ``tests/golden/cli-ui-source-freshness.tryscript.md`` pins its
transcript. So that the conversation is the real server's and not envelopes a test wrote
by hand, its responses come from ``tests/fixtures/source-freshness-responses.json``:
what the in-process application answered while a mirror went stale, refreshed, gained a
newer commit that the server followed, switched its pin, lost its origin, invalidated an open all-branch history
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
from datetime import UTC, datetime, timedelta
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
from metabrowser.cache.update import update_store
from metabrowser.cache.urls import LineSelection, RepositorySelection
from metabrowser.cli.selection import pending_selection_opener
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MAX_PULL_JOBS,
    STORE_PROBE_S,
    mirror_session,
    serve_mirror,
)
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
from tests.loop_gate import held_until
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

    def __init__(
        self, key: str = "recording:beside", *, released: threading.Event | None = None
    ) -> None:
        self.key = key
        self.stale = False
        if released is None:
            released = threading.Event()
            released.set()
        self._released = released

    def hold(self) -> None:
        self._released.clear()

    def release(self) -> None:
        self._released.set()

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        return self.stale

    async def refresh(self, asks: object) -> None:
        await held_until(self._released, 30)
        self.stale = False


class _BesideSet:
    """The pull requests a server serves here, as a provider's set hands them over: 7's
    data is *beside*, and every other number's is a stand-in of its own whose refresh is
    held until :meth:`release`, so a queue of them waits while the server is asked."""

    def __init__(self, beside: _Beside) -> None:
        self.beside = beside
        self.others: dict[int, _Beside] = {}
        self._released = threading.Event()

    def key(self, number: int) -> str:
        return self.beside.key if number == 7 else f"recording:pull/{number}"

    async def companion(self, number: int) -> _Beside:
        if number == 7:
            return self.beside
        return self.others.setdefault(number, _Beside(self.key(number), released=self._released))

    async def attend(self, number: int) -> _Beside:
        return await self.companion(number)

    def release(self) -> None:
        self._released.set()


def _commit_fetch(client: TestClient, *, retry: bool = False) -> Any:
    body: dict[str, Any] = {"for": "commit", "retry": True} if retry else {"for": "commit"}
    return client.post("/api/source/refresh", json=body, headers=JSON_BODY)


def _page_ask(client: TestClient) -> Any:
    return client.post("/api/source/refresh", json={"for": "page"}, headers=JSON_BODY)


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
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
            # The refresh moved the served branch, and the server followed it.
            recorded["refreshed"] = _settle(client)
            # A page still drawn for the commit before asks for the branch at its address,
            # which changes nothing now and says where the page is on the new commit.
            followed = client.post(
                "/api/source/pin",
                json={"ref": recorded["refreshed"]["ref"], "view": "/view/"},
                headers=JSON_BODY,
            )
            assert followed.status_code == 200
            recorded["followed"] = followed.json()
            # One on a file the new commit lacks lands at the root.
            gone = "/view/g1-R09ORS5tZA"  # GONE.md, which no commit here has
            elsewhere = client.post(
                "/api/source/pin",
                json={"ref": recorded["refreshed"]["ref"], "view": gone},
                headers=JSON_BODY,
            )
            assert elsewhere.status_code == 200
            recorded["followed_elsewhere"] = {"view": gone, "answer": elsewhere.json()}
            history = client.get("/api/git/log", params={"limit": "1", "scope": "all"}).json()
            # A branch at the commit before, which the next refresh brings.
            _git(origin, "branch", "side", recorded["stale"]["pin"])
            assert client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code == 202
            _settle(client)
            stale_cursor = client.get(
                "/api/git/log", params={"limit": "1", "scope": "all", "cursor": history["cursor"]}
            )
            assert stale_cursor.status_code == 409
            recorded["history_stale"] = {"status": 409, "body": stale_cursor.json()}
            # Another tab switches to another branch, at another commit: a page still on
            # the first is refused and offered a reload.
            switched = client.post("/api/source/pin", json={"ref": "side"}, headers=JSON_BODY)
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
        pulls = _BesideSet(beside)
        serve_mirror(
            StoreMirror.from_published(published),
            serving=True,
            pull_request=7,
            pull_requests=pulls,
        )
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
            # A full queue: other pull requests a reader asked for wait, held, with the
            # attended 7 one over, and then the reader attends 20, whose record is stale
            # and finds no room. The mirror was fetched just now, so a page's own refresh
            # would refresh only 20's record, and the server refuses it.
            session = mirror_session(server.app)
            assert session is not None and client.portal is not None
            beside.hold()
            for number in (*range(100, 100 + MAX_PULL_JOBS), 7):
                assert (
                    client.portal.call(session.request_pull_refresh, number, "record") == "started"
                )
            client.portal.call(session.attend, 20)
            pulls.others[20].stale = True
            recorded["queue_full_page"] = client.get("/api/source/status").json()
            recorded["queue_full_refresh"] = answer(
                client.post("/api/source/refresh", json={}, headers=JSON_BODY)
            )
            # A reader's retry for a commit fetches the mirror, which waits its turn behind
            # the queue, and says the pull request's refresh, which alone brings a newer
            # head of it, was refused.
            recorded["commit_unqueued_started"] = answer(_commit_fetch(client, retry=True))
            beside.release()
            pulls.release()
            recorded["commit_unqueued_fetched"] = _settle(client)
            deadline = time.monotonic() + 30
            queued = (*range(100, 100 + MAX_PULL_JOBS), 7)
            while any(session.pull_refreshing(number) for number in queued):
                assert time.monotonic() < deadline, "the queue did not drain"
                time.sleep(0.02)
            still = client.get(f"/api/git/commit/{_ABSENT_COMMIT}")
            recorded["commit_unqueued_after"] = {"oid": _ABSENT_COMMIT, **answer(still)}
        # A visible page on a branch makes its own ask every few seconds. The server asks
        # the origin where the branch is: where the mirror has it, so nothing is fetched;
        # then, after a push, somewhere else, so the fetch starts at once and the served
        # branch follows. A page on a commit is told to send no such ask, and one sent
        # all the same asks the origin nothing.
        probe_clock = [1000.0]
        monkeypatch.setattr("metabrowser.mirror_refresh._monotonic", lambda: probe_clock[0])
        serve_mirror(StoreMirror.from_published(published), serving=True)
        with TestClient(server.app) as client:
            assert client.post("/api/source/refresh", json={}, headers=JSON_BODY).status_code == 202
            recorded["probe_page"] = _settle(client)
            recorded["probe_unchanged"] = answer(_page_ask(client))
            _commit_on_topic(origin)
            probe_clock[0] += STORE_PROBE_S
            recorded["probe_moved"] = answer(_page_ask(client))
            recorded["probe_followed"] = _settle(client)
            # Once a window the ask fetches the whole mirror, which nobody pressed for:
            # the status calls that fetch quiet. The clock is ahead only while it is asked.
            later = datetime.now(UTC) + timedelta(seconds=FRESHNESS_WINDOW_S + 5)
            probe_clock[0] += STORE_PROBE_S
            with monkeypatch.context() as aged:
                aged.setattr("metabrowser.mirror_refresh._now_utc", lambda: later)
                recorded["window_fetch"] = answer(_page_ask(client))
            recorded["window_fetched"] = _settle(client)
            pinned = client.post(
                "/api/source/pin", json={"oid": recorded["probe_page"]["pin"]}, headers=JSON_BODY
            )
            assert pinned.status_code == 200
            recorded["commit_pin"] = pinned.json()["status"]
            probe_clock[0] += STORE_PROBE_S
            recorded["commit_pin_ask"] = answer(_page_ask(client))
            # The server's own fetch, which its timer starts while no page asks, held
            # here until the status has been read: quiet too.
            fetching = threading.Event()
            real_update = update_store

            async def held_update(home: Path, store_key: str, *, remote_url: str) -> Any:
                await held_until(fetching, 30)
                return await real_update(home, store_key, remote_url=remote_url)

            session = mirror_session(server.app)
            assert session is not None and client.portal is not None
            with monkeypatch.context() as held:
                held.setattr("metabrowser.cache.served_mirror.update_store", held_update)
                assert client.portal.call(session.request_idle_refresh) == "started"
                recorded["idle_fetch"] = client.get("/api/source/status").json()
                fetching.set()
                _settle(client)
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
    stale = recorded["stale"]
    assert refreshed["pin"] != stale["pin"], "the refresh must bring a newer commit"
    # The server followed the branch: the new tip is served, under the same ref.
    assert (refreshed["ref"], refreshed["follows"]) == (stale["ref"], True)
    assert refreshed["latest"] == refreshed["pin"]
    assert refreshed["generation"] == stale["generation"] + 1
    assert recorded["followed"]["changed"] is False
    assert recorded["followed"]["view_href"] == "/view/"
    assert recorded["followed_elsewhere"]["answer"]["view_href"] == "/view/"
    after_switch = recorded["after_switch"]
    assert (after_switch["ref"], after_switch["pin"]) != (refreshed["ref"], refreshed["pin"])
    assert after_switch["pin"] == stale["pin"]
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
    stale_commit = recorded["commit_stale_started"]
    assert (stale_commit["status"], stale_commit["body"]["refresh"]) == (202, "started")
    assert stale_commit["body"]["status"]["stale"] is True
    assert recorded["commit_stale_unfetched"]["last_outcome"]["outcome"] == "origin_unavailable"
    shown = recorded["origin_not_shown"]
    assert (shown["stale"], shown["last_outcome"]["outcome"]) == (False, "not_found_or_private")
    # A full queue refuses a refresh that would refresh only the attended pull request.
    full = recorded["queue_full_page"]
    assert (full["stale"], full["refreshing"], full["pull_request"]) == (True, False, 20)
    refused = recorded["queue_full_refresh"]
    assert (refused["status"], refused["body"]["code"]) == (429, "too_many")
    assert refused["body"]["status"] == full, "a refused refresh starts nothing"
    # A commit's fetch then fetches the mirror and says the pull request's was refused.
    unqueued = recorded["commit_unqueued_started"]
    assert unqueued["status"] == 202
    assert (unqueued["body"]["refresh"], unqueued["body"]["pull_refresh"]) == (
        "started",
        "too_many",
    )
    assert unqueued["body"]["status"]["refreshing"] is True
    fetched = recorded["commit_unqueued_fetched"]
    assert (fetched["refreshing"], fetched["last_outcome"]["outcome"]) == (False, "succeeded")
    assert recorded["commit_unqueued_after"]["body"]["code"] == "commit_not_found"
    # The other answers of a commit's fetch say how the pull request's refresh was asked.
    assert recorded["commit_retry_started"]["body"]["pull_refresh"] == "joined"
    assert recorded["commit_fresh"]["body"]["pull_refresh"] is None
    assert recorded["folder"]["pin"] is None
    # A page's own ask: a probe that found the branch where the mirror has it fetched
    # nothing, and one that found a push started the fetch the served branch followed.
    probe_page = recorded["probe_page"]
    assert (probe_page["probe_every_s"], probe_page["stale"]) == (STORE_PROBE_S, False)
    unchanged = recorded["probe_unchanged"]
    assert (unchanged["status"], unchanged["body"]["refresh"]) == (200, "probed")
    assert unchanged["body"]["status"] == probe_page
    moved = recorded["probe_moved"]
    assert (moved["status"], moved["body"]["refresh"]) == (202, "started")
    assert moved["body"]["status"]["refreshing"] is True
    followed = recorded["probe_followed"]
    assert followed["pin"] != probe_page["pin"] and followed["latest"] == followed["pin"]
    assert recorded["commit_pin"]["probe_every_s"] is None
    window = recorded["window_fetch"]
    assert (window["status"], window["body"]["refresh"]) == (202, "started")
    quiet = window["body"]["status"]
    assert (quiet["refreshing"], quiet["refresh_quiet"]) == (True, True)
    assert moved["body"]["status"]["refresh_quiet"] is False, "the page asked for that one"
    assert recorded["window_fetched"]["refreshing"] is False
    idle = recorded["idle_fetch"]
    assert (idle["refreshing"], idle["refresh_quiet"], idle["ref"]) == (True, True, None)
    unasked = recorded["commit_pin_ask"]
    assert (unasked["status"], unasked["body"]["refresh"]) == (200, "not_due")
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_a_folders_row_names_its_store_of_the_origin_on_every_page() -> None:
    """The row on a repository folder's pages, its working tree's among them: a store
    grown old is fetched once by the page's own quiet ask, since the page shows nothing
    of it, and only the reader's Refresh says "Refreshing…"; the row says what was
    fetched is Metabrowser's store, and leaves the reload offer to the ref selector."""

    folder = run_session("source-freshness-session.js", "folder")
    by_name = {step["step"]: step for step in folder["steps"]}
    stale = by_name["the working tree's page, its origin's store grown old, asks quietly, once"]
    assert stale["requests"] == [
        "GET /api/source/status",
        'POST /api/source/refresh {"for":"page"}',
    ]
    assert stale["paint"] is None
    pressed = by_name["the reader's own Refresh says so while it runs"]
    assert pressed["requests"] == ["POST /api/source/refresh {}"]
    assert pressed["paint"]["label"] == "Refreshing…"
    fetched = by_name["the store was fetched without showing the footer or reloading"]
    assert fetched["paint"] is None
    failed = by_name["a fetch that failed says the checkout is unchanged"]
    assert failed["paint"]["label"].startswith("Refresh failed · origin fetched ")
    for step in folder["steps"]:
        assert "mirror" not in json.dumps(step["paint"]), step["step"]
        assert step["paint"] is None or step["paint"]["offer"] is None, step["step"]
        assert step.get("reloads", 0) == 0, step["step"]


def test_a_folders_page_follows_its_checkouts_own_branch() -> None:
    """A page on one of the checkout's own branches asks as often as its status says, and
    goes with the branch when the reader's commit moved it, with a store and without."""

    part = run_session("source-freshness-session.js", "checkout-branch")
    by_name = {step["step"]: step for step in part["steps"]}
    ask = 'POST /api/source/refresh {"for":"page"}'
    opened = by_name["a page on the checkout's own branch asks where the branch is"]
    assert opened["requests"] == ["GET /api/source/status", ask]
    assert opened["timer"] == "ask"
    unmoved = by_name["the branch is where it was: nothing repaints, and it asks again"]
    assert (unmoved["requests"], unmoved["repaints"], unmoved["reloads"]) == ([ask], 0, 0)
    followed = by_name["the reader committed on the branch; the page follows it"]
    assert followed["requests"][0] == ask
    assert followed["requests"][1].startswith('POST /api/source/pin {"ref":"refs/heads/trunk"')
    assert (followed["reloads"], followed["paint"]["label"]) == (1, "Updating to trunk…")
    # With no store nothing is refreshable, so there is no row, and the page asks all the same.
    plain = by_name["with no store of an origin there is no row, and the page still asks"]
    assert (plain["requests"], plain["timer"], plain["paint"]) == (
        ["GET /api/source/status", ask],
        "ask",
        None,
    )
    refused = by_name["a follow the server refused says the branch moved, and why"]
    assert (refused["reloads"], refused["paint"]["label"]) == (0, "trunk moved")
    assert refused["paint"]["error"] == "Could not follow trunk to its new commit."
    pressed = by_name["pressed, the page asks again and follows"]
    assert len(pressed["requests"]) == 1 and pressed["requests"][0].startswith(
        'POST /api/source/pin {"ref":"refs/heads/trunk"'
    )
    assert pressed["reloads"] == 1
    hidden = by_name["a hidden page asks nothing"]
    assert (hidden["requests"], hidden["timer"]) == ([], None)
    # A branch the reader deleted keeps its last commit shown, and a quiet row says so,
    # the store's row too when the folder keeps one.
    gone = by_name["the reader deleted the branch: the row says its last commit stays"]
    assert (gone["reloads"], gone["paint"]["tone"]) == (0, "quiet")
    assert gone["paint"]["label"] == "topic no longer exists"
    assert gone["paint"]["detail"].startswith("topic no longer exists in this checkout;")
    stored = by_name["with a store, the store's row says the branch is gone"]["paint"]
    assert stored["label"].startswith("trunk no longer exists · origin fetched ")


def test_the_session_runs_on_the_recording() -> None:
    transcript = run_session("source-freshness-session.js")
    asks = run_session("source-freshness-session.js", "asks")
    recording = read_recording(RECORDING)
    by_name = {step["step"]: step for step in (*transcript["steps"], *asks["steps"])}
    assert by_name["open a stale page"]["requests"] == [
        "GET /api/source/status",
        "POST /api/source/refresh {}",
    ]
    # The refresh moved the branch; the page goes with it, with nothing offered.
    followed = by_name["the refresh moved the branch; the page follows it"]
    assert followed["requests"][-1] == (
        'POST /api/source/pin {"ref":"refs/remotes/origin/topic","view":"/view/"}'
    )
    assert (followed["reloads"], followed["paint"]["offer"]) == (1, None)
    assert followed["paint"]["label"] == "Updating to topic…"
    elsewhere = by_name["a page on a file the new commit lacks goes to the root"]
    assert (elsewhere["navigated"], elsewhere["reloads"]) == (["/view/"], 0)
    refused_follow = by_name["a refused follow says why and offers a reload"]
    assert refused_follow["reloads"] == 0
    assert refused_follow["paint"]["error"].startswith("Could not follow topic")
    assert refused_follow["paint"]["offer"].endswith("[Reload page]")
    again = by_name["a refused follow is not asked again on the next poll"]
    assert not any(request.startswith("POST /api/source/pin") for request in again["requests"])
    assert again["paint"]["error"] == refused_follow["paint"]["error"]
    assert by_name["the reload a refused follow offers"]["reloads"] == 1
    # The page's own ask, every probe_every_s while it is visible, stands in for the poll.
    page_ask = 'POST /api/source/refresh {"for":"page"}'
    opened = by_name["a page on a branch asks with its first status"]
    assert opened["requests"] == ["GET /api/source/status", page_ask]
    assert opened["timer"] == "ask"
    unchanged = by_name["an unchanged branch: the ask is the poll, and nothing repaints"]
    assert (unchanged["requests"], unchanged["repaints"]) == ([page_ask], 0)
    hidden = by_name["a hidden page asks nothing"]
    assert (hidden["requests"], hidden["timer"]) == ([], None)
    assert by_name["shown again, the page asks at once"]["requests"][-1] == page_ask
    pushed = by_name["the origin moved the branch: the fetch starts at once"]
    assert (pushed["requests"], pushed["timer"]) == ([page_ask], "fast")
    assert pushed["paint"]["tone"] == "refreshing"
    arrived_push = by_name["the fetch brought the push; the page follows its branch"]
    assert arrived_push["requests"][-1].startswith("POST /api/source/pin ")
    assert arrived_push["reloads"] == 1
    refused_ask = by_name["a refused ask says nothing, and the page polls instead"]
    assert (refused_ask["timer"], refused_ask["paint"]) == ("slow", None)
    after_refusal = by_name["the poll after a refused ask"]["requests"]
    assert len(after_refusal) == 1 and after_refusal[0].startswith("GET /api/source/status")
    silent = by_name["the server stopped answering the page's asks"]
    assert (silent["timer"], silent["paint"]["error"]) == ("slow", "The server did not answer.")
    # A fetch nobody asked for changes nothing the row says: no repaint, so nothing is
    # announced and no button is disabled, and no quick poll (review A2 of #721).
    for name, timer in (
        ("once a window the mirror is fetched, and the row says nothing", "ask"),
        ("the quiet fetch ended, and the row still says nothing new", "ask"),
        ("the server's own fetch says nothing on a page that is open", "slow"),
    ):
        quiet = by_name[name]
        assert (quiet["repaints"], quiet["timer"]) == (0, timer), name
        assert quiet["paint"] is None
    # The commit view does not wait for the page's first ask (review A4 of #721).
    unheld = by_name["a missing commit does not wait for the page's first ask"]
    assert unheld["answeredBeforeTheAsk"] is True
    assert unheld["requests"] == ["GET /api/source/status", page_ask]
    assert unheld["commit"]["state"] == "not_found"
    assert by_name["the page's first ask is answered afterwards"]["timer"] == "ask"
    on_commit = by_name["a page on a commit sends no ask of its own"]
    assert (on_commit["requests"], on_commit["timer"]) == (["GET /api/source/status"], "slow")
    assert all(
        request.startswith("GET ")
        for request in by_name["a page on a commit polls slowly"]["requests"]
    )
    # The page asks for a refresh by itself once per visible period, and the server
    # holds its own asks while a fetch has just failed, so neither is repeated per poll.
    polls = by_name["a stale page whose refresh fails asks once"]["requests"]
    assert "POST /api/source/refresh {}" not in polls
    history = {row["failure"]: row["means"] for row in transcript["history"]}
    assert history["a refresh moved the refs"] == "stale"
    # A page whose revision another tab switched keeps its rows: the walk would be refused
    # again, and the freshness row offers the reload.
    assert history["another tab switched the revision"] == "failed"
    assert history["the session expired"] == "recover"
    assert by_name["an unchanged status is a 304"]["repaints"] == 0
    assert by_name["switched before the first poll"]["paint"]["offer"].endswith("[Reload page]")
    guard = transcript["guard"]
    page = guard["page"]
    # The status route, another origin, and the event log's routes name no pin; a route
    # whose name only begins like the event log's does.
    assert [row["pin"] for row in guard["sent"]] == [page, None, None, None, None, page, page]
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
    assert "as last fetched" in inside["commit"]["detail"]
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
        absent["state"] == "not_found"
        and absent["detail"] == "No branch or tag on the origin has this commit."
    )
    beside = by_name["no fetch of the mirror ran, and the view does not say one did"]["commit"]
    assert beside["state"] == "not_found" and "as last fetched" in beside["detail"]
    assert "did not bring it" not in beside["detail"]
    # A re-ask that failed is a load failure, not an answer about the commit.
    refused = by_name["asking again failed; the view does not say not found"]["commit"]
    assert refused["state"] == "failed" and refused["title"] == "Could not load this commit."
    # Outside the window the page asks by itself, with the request the server floors.
    outside = by_name["outside the window the page asks for the fetch itself"]
    assert outside["requests"] == ['POST /api/source/refresh {"for":"commit"}']
    unfetched = by_name["the commit could not be fetched"]["commit"]
    assert unfetched["state"] == "fetch_failed" and unfetched["offer"] == "[Retry]"
    assert unfetched["detail"] == "The origin could not be read."
    left = by_name["the reader left before the fetch ended"]
    assert left["requests"] == ["GET /api/source/status"] and left["commit"]["repaints"] == 0
    joined = by_name["a fetch of the mirror already running is joined"]
    assert joined["requests"] == ['POST /api/source/refresh {"for":"commit"}']
    # A server that stops answering is not polled every second, nor waited for.
    stopped = by_name["the server stopped answering while the fetch ran"]
    assert stopped["timer"] == "slow" and stopped["commit"]["state"] == "fetch_failed"
    assert stopped["commit"]["detail"] == "This commit could not be fetched."
    # A fetch that ran while a full queue refused the pull request's refresh does not let
    # the view say the origin lacks the commit.
    unqueued = by_name["the queue had no room for the pull request's refresh"]["commit"]
    assert unqueued["state"] == "fetch_failed" and unqueued["offer"] == "[Retry]"
    assert "while others are being fetched" in unqueued["detail"]
    assert "No branch or tag" not in unqueued["detail"]
    # A refusal of the page's own refresh says nothing; the reader's press says why.
    own = by_name["a page's own refresh with no room in the queue says nothing"]
    assert own["requests"] == ["GET /api/source/status", "POST /api/source/refresh {}"]
    assert own["paint"] is None
    pressed = by_name["a press with no room in the queue says why"]
    assert pressed["requests"] == ["POST /api/source/refresh {}"]
    # The answer's own words are the agent's; its code says waiting would help.
    assert recording["queue_full_refresh"]["body"]["code"] == "too_many"
    assert pressed["paint"]["error"] == "Other refreshes are running. Try again shortly."
    shown = by_name["the origin no longer shows the repository"]["paint"]["detail"]
    assert shown.startswith("The repository was not found, or it is private and could not be read.")
