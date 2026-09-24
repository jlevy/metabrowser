"""A served mirror over HTTP: freshness, background refresh, pin switching, and route safety.

Serve mode runs in-process with only uvicorn and the port search patched, as in
``tests/test_serve_pin.py``; a ``TestClient`` then drives the same application lifespan
uvicorn would, so the refresh jobs run in the serving loop and are cancelled at its
shutdown. Origins are local bare repositories reached over ``file://``; nothing uses the
network. The acquisition floor is patched as every acquiring test patches it, and left
alone in the admitted-Git CI job.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser import server
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.locks import repository_store_lock, store_fetch_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
)
from metabrowser.cache.update import RefreshOutcome, StoreUpdate
from metabrowser.cli.main import _app
from metabrowser.git.tree_source import GitPath, GitRevisionSubject, store_batch_reader_count
from metabrowser.mirror_refresh import (
    LastOutcome,
    MirrorSession,
    RecordedFreshness,
    RefreshCoordinator,
    RefreshResult,
    followed_outcome,
)
from metabrowser.repository_context import RepositoryContext
from metabrowser.source import (
    SubjectNotOpenError,
    attach_owned_subject,
    close_owned_subject,
    get_source_session,
    replace_owned_subject,
    reset_source_session,
    serve_subject_opener,
)
from tests.test_cache_acquire import _git
from tests.test_serve_pin import (
    _home,
    _Origin,
    _origin,
    _published,
    _rev,
    _serve,
    posix_only,
)

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

runner = CliRunner()

_JSON = {"content-type": "application/json"}
_STALE_AT = "2020-01-01T00:00:00Z"
# Later than any real record, so a faked refresh is the newest outcome the status knows.
_FUTURE = "2099-01-01T00:00:00Z"


def _wire(display: str) -> str:
    return GitPath.from_display(display).to_wire()


@pytest.fixture(autouse=True)
def _isolated_session(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    yield
    reset_source_session()


def _work(origin: _Origin) -> Path:
    return origin.path.parent / "work"


def _push_commit(origin: _Origin, name: str, body: str, message: str) -> str:
    work = _work(origin)
    (work / name).write_text(body, encoding="utf-8")
    _git(work, "add", name)
    _git(work, "commit", "-qm", message)
    _git(work, "push", "-q", str(origin.path), "topic")
    return _rev(work)


def _backdate_last_fetch(tmp_path: Path, origin: _Origin) -> None:
    """Acquire the origin, then record its last fetch long ago with the production writer."""

    published = _published(tmp_path, origin)
    relative = store_record(published.store_key, "state.yml")
    with repository_store_lock(published.home, published.store_key):
        write_record_atomic(
            published.home,
            relative,
            RepositoryStoreState(
                default_remote_ref=published.default_remote_ref,
                default_revision=published.default_revision,
                last_fetch_at=_STALE_AT,
                last_operation=StoreOperation(kind="acquire", outcome="succeeded", at=_STALE_AT),
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )


def _settle(client: TestClient, *, timeout_s: float = 30.0) -> dict[str, Any]:
    """Poll status the way the browser does until no refresh is running."""

    deadline = time.monotonic() + timeout_s
    while True:
        status = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        if time.monotonic() > deadline:
            raise AssertionError("the refresh did not finish")
        time.sleep(0.02)


def _post(client: TestClient, route: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(route, json={} if body is None else body, headers=_JSON)


@pytest.fixture
def origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Origin:
    _home(tmp_path, monkeypatch)
    return _origin(tmp_path)


@pytest.fixture
def served(origin: _Origin) -> Iterator[TestClient]:
    result = _serve(origin.url)
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        yield client


# ── Status ───────────────────────────────────────────────────────────


def test_status_reports_freshness_from_memory_and_revalidates(
    served: TestClient, origin: _Origin
) -> None:
    response = served.get("/api/source/status")
    assert response.status_code == 200
    status = response.json()
    assert status["pin"] == origin.second
    assert status["refreshable"] is True
    assert status["latest"] == origin.second
    assert status["refreshing"] is False
    # Just acquired, so fresh: serving did not start a refresh.
    assert status["stale"] is False
    assert status["last_outcome"]["operation"] == "acquire"
    assert status["last_outcome"]["outcome"] == "succeeded"
    assert status["last_fetch_at"] == status["last_outcome"]["at"]
    # A validator the client must revalidate, never a body a cache may reuse.
    assert response.headers["cache-control"] == "no-cache"
    etag = response.headers["etag"]

    unchanged = served.get("/api/source/status", headers={"if-none-match": etag})
    assert unchanged.status_code == 304
    assert unchanged.headers["etag"] == etag
    assert unchanged.content == b""
    other = served.get("/api/source/status", headers={"if-none-match": '"other"'})
    assert other.status_code == 200
    # Any change to the envelope is a new validator: here, a refresh starting.
    assert _post(served, "/api/source/refresh").status_code == 202
    moved = served.get("/api/source/status", headers={"if-none-match": etag})
    assert moved.status_code == 200
    _settle(served)


def test_a_folder_reports_no_freshness_and_refuses_both_routes(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
        refresh = _post(client, "/api/source/refresh")
        pin = _post(client, "/api/source/pin", {"ref": "topic"})
    assert status["subject"] == "attached_filesystem"
    assert status["refreshable"] is False
    assert status["latest"] is None and status["last_outcome"] is None
    assert refresh.status_code == 409
    assert refresh.json()["capability"] == "refresh"
    assert pin.status_code == 409
    assert pin.json()["capability"] == "pin"


# ── Refresh ──────────────────────────────────────────────────────────


def test_a_refresh_shows_the_newer_revision_and_switching_serves_it(
    served: TestClient, origin: _Origin
) -> None:
    newer = _push_commit(origin, "NEW.md", "# New\n", "third")
    before = served.get("/api/source/status").json()

    started = _post(served, "/api/source/refresh")
    assert started.status_code == 202
    assert started.json()["refresh"] == "started"
    assert started.json()["status"]["refreshing"] is True

    status = _settle(served)
    assert status["last_outcome"]["operation"] == "refresh"
    assert status["last_outcome"]["outcome"] == "succeeded"
    assert status["last_fetch_at"] >= before["last_fetch_at"]
    # The page keeps its pin; the ref moved in the mirror, which is the offer.
    assert status["pin"] == origin.second
    assert status["latest"] == newer
    assert status["generation"] == before["generation"]
    readme = served.get("/api/file", params={"path": _wire("README.md")})
    assert readme.status_code == 200
    assert served.get("/api/file", params={"path": _wire("NEW.md")}).status_code == 404

    switched = _post(served, "/api/source/pin", {"ref": status["ref"]})
    assert switched.status_code == 200
    payload = switched.json()
    assert payload["changed"] is True
    assert payload["status"]["pin"] == newer
    assert payload["status"]["latest"] == newer
    assert payload["status"]["ref"] == "refs/remotes/origin/topic"
    assert payload["status"]["generation"] == before["generation"] + 1
    new_file = served.get("/api/file", params={"path": _wire("NEW.md")})
    assert new_file.status_code == 200
    assert new_file.json()["content"] == "# New\n"

    # The page it replaced stays readable: its commit is still in the mirror.
    assert served.get(f"/api/git/commit/{origin.second}").status_code == 200
    back = _post(served, "/api/source/pin", {"oid": origin.second})
    assert back.json()["status"]["pin"] == origin.second
    assert back.json()["status"]["ref"] is None
    assert back.json()["status"]["latest"] is None
    again = _post(served, "/api/source/pin", {"oid": origin.second})
    assert again.json()["changed"] is False
    assert again.json()["status"]["generation"] == back.json()["status"]["generation"]
    # A file that differs between pins answers from the pin served now, not a cache.
    first = _post(served, "/api/source/pin", {"oid": origin.first})
    assert first.json()["status"]["pin"] == origin.first
    readme = served.get("/api/file", params={"path": _wire("README.md")}).json()
    assert "Second revision." not in readme["content"]
    assert served.get("/api/file", params={"path": _wire("data.json")}).status_code == 404
    history = served.get("/api/git/log", params={"limit": "10"}).json()
    assert [commit["id"] for commit in history["commits"]] == [origin.first]


def test_concurrent_refresh_requests_join_one_fetch(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    release = threading.Event()

    async def held_update(home: Path, store_key: str, *, remote_url: str) -> StoreUpdate:
        calls.append(store_key)
        await asyncio.to_thread(release.wait, 30)
        return StoreUpdate(RefreshOutcome.succeeded, _FUTURE)

    monkeypatch.setattr("metabrowser.cache.served_mirror.update_store", held_update)
    answers = [_post(served, "/api/source/refresh").json()["refresh"] for _ in range(3)]
    assert answers == ["started", "joined", "joined"]
    assert served.get("/api/source/status").json()["refreshing"] is True
    release.set()
    status = _settle(served)
    assert len(calls) == 1
    assert status["last_outcome"] == {"operation": "refresh", "outcome": "succeeded", "at": _FUTURE}
    assert _post(served, "/api/source/refresh").json()["refresh"] == "started"
    _settle(served)
    assert len(calls) == 2


def test_a_failed_refresh_is_a_typed_outcome_and_the_pin_is_still_served(
    served: TestClient, origin: _Origin
) -> None:
    before = served.get("/api/source/status").json()
    shutil.rmtree(origin.path)

    assert _post(served, "/api/source/refresh").status_code == 202
    status = _settle(served)

    assert status["last_outcome"]["outcome"] == "origin_unavailable"
    assert status["last_fetch_at"] == before["last_fetch_at"]
    assert status["pin"] == origin.second
    assert served.get("/view/").status_code == 200
    readme = served.get("/api/file", params={"path": _wire("README.md")})
    assert readme.status_code == 200
    assert "Second revision." in readme.json()["content"]


def test_the_shutdown_cancels_a_running_refresh(
    origin: _Origin, monkeypatch: pytest.MonkeyPatch
) -> None:
    ended: list[str] = []
    fetching = threading.Event()

    async def endless_update(home: Path, store_key: str, *, remote_url: str) -> StoreUpdate:
        fetching.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            ended.append("cancelled")
            raise
        return StoreUpdate(RefreshOutcome.succeeded, _FUTURE)

    monkeypatch.setattr("metabrowser.cache.served_mirror.update_store", endless_update)
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        assert _post(client, "/api/source/refresh").json()["refresh"] == "started"
        assert client.get("/api/source/status").json()["refreshing"] is True
        # The job reads the store record before it fetches; shut down only once the
        # fetch itself is running, so the cancellation lands inside it.
        assert fetching.wait(10)
    assert ended == ["cancelled"]


def test_a_stale_mirror_is_refreshed_once_when_the_server_starts(
    tmp_path: Path, origin: _Origin
) -> None:
    _backdate_last_fetch(tmp_path, origin)
    newer = _push_commit(origin, "NEW.md", "# New\n", "third")
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        status = _settle(client)
    assert status["last_outcome"]["operation"] == "refresh"
    assert status["last_outcome"]["outcome"] == "succeeded"
    assert status["stale"] is False
    # The server opened the pin it announced; the refresh only moved the mirror.
    assert status["pin"] == origin.second
    assert status["latest"] == newer


def test_a_fresh_mirror_is_not_refreshed_when_the_server_starts(
    served: TestClient,
) -> None:
    status = served.get("/api/source/status").json()
    assert status["refreshing"] is False
    assert status["last_outcome"]["operation"] == "acquire"


def test_one_shot_api_never_refreshes_on_its_own(tmp_path: Path, origin: _Origin) -> None:
    _backdate_last_fetch(tmp_path, origin)
    result = runner.invoke(_app, [origin.url, "--api", "/api/source/status"])
    assert result.exit_code == 0, result.output
    assert '"stale": true' in result.stdout
    assert '"refreshing": false' in result.stdout
    again = runner.invoke(_app, [origin.url, "--api", "/api/source/status"])
    assert '"operation": "acquire"' in again.stdout
    assert f'"last_fetch_at": "{_STALE_AT}"' in again.stdout


def test_one_shot_api_finishes_the_refresh_it_was_asked_for(
    tmp_path: Path, origin: _Origin
) -> None:
    newer = _push_commit(origin, "NEW.md", "# New\n", "third")
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")
    started = runner.invoke(_app, [origin.url, "--api", "/api/source/refresh", "--data", str(body)])
    assert started.exit_code == 0, started.output
    assert '"refresh": "started"' in started.stdout
    after = runner.invoke(_app, [origin.url, "--api", "/api/source/status"])
    assert after.exit_code == 0, after.output
    assert '"operation": "refresh"' in after.stdout
    # A new process pins the default branch as the mirror records it now.
    assert f'"pin": "{newer}"' in after.stdout


def test_one_shot_api_fails_when_the_refresh_outlasts_its_wait(
    tmp_path: Path, origin: _Origin, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow_update(home: Path, store_key: str, *, remote_url: str) -> StoreUpdate:
        await asyncio.sleep(60)
        return StoreUpdate(RefreshOutcome.succeeded, _FUTURE)

    monkeypatch.setattr("metabrowser.cache.served_mirror.update_store", slow_update)
    monkeypatch.setattr("metabrowser.cli.api_cli._REFRESH_DRAIN_S", 0.2)
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")
    started = time.monotonic()
    result = runner.invoke(_app, [origin.url, "--api", "/api/source/refresh", "--data", str(body)])
    # Leaving stopped the refresh instead of waiting for it.
    assert time.monotonic() - started < 30
    assert result.exit_code != 0
    assert '"refreshing": true' in result.stdout
    assert str(result.exception) == "the refresh did not finish within 0.2s and was stopped"


# ── Pin switching ────────────────────────────────────────────────────


def test_pin_selections_resolve_in_the_mirror_and_refusals_are_typed(
    served: TestClient, origin: _Origin
) -> None:
    by_prefix = _post(served, "/api/source/pin", {"oid": origin.first[:8]})
    assert by_prefix.status_code == 200
    assert by_prefix.json()["status"]["pin"] == origin.first

    # A server fetches once for a selection its mirror lacks, then answers not found.
    for missing in ({"ref": "nope"}, {"oid": "0" * 40}):
        pending = served.post("/api/source/pin", json=missing, headers=_JSON)
        assert pending.status_code == 202, missing
        assert pending.json()["code"] == "selection_pending"
        assert pending.json()["refresh"] in {"started", "joined"}
        _settle(served)
        gone = served.post("/api/source/pin", json=missing, headers=_JSON)
        assert gone.status_code == 404, missing
        assert gone.json()["code"] == "selection_not_found"

    cases: list[tuple[Any, int, str]] = [
        ({"ref": ":/first"}, 400, "invalid_selection"),
        ({"ref": "topic@{1}"}, 400, "invalid_selection"),
        # A trailing newline is not part of a commit ID, whatever ``$`` would accept.
        ({"oid": origin.first[:7] + "\n"}, 400, "invalid_selection"),
        ({"ref": origin.first[:7] + "\n"}, 400, "invalid_selection"),
        ({"ref": "refs/heads/topic"}, 400, "invalid_selection"),
        ({"ref": "topic", "oid": origin.first}, 400, "invalid_selection"),
        ({}, 400, "invalid_selection"),
        ({"ref": 7}, 400, "invalid_selection"),
        ({"ref": "topic", "extra": 1}, 400, "invalid_selection"),
        (["topic"], 400, "invalid_selection"),
    ]
    for body, status_code, code in cases:
        response = served.post("/api/source/pin", json=body, headers=_JSON)
        assert response.status_code == status_code, body
        assert response.json()["code"] == code, body
    not_json = served.post("/api/source/pin", content=b"{", headers=_JSON)
    assert not_json.status_code == 400
    oversized = served.post(
        "/api/source/pin", content=b'{"ref": "' + b"x" * 5000 + b'"}', headers=_JSON
    )
    assert oversized.status_code == 413
    # None of those changed what is served.
    assert served.get("/api/source/status").json()["pin"] == origin.first


def test_a_branch_pushed_after_serving_began_is_fetched_once_and_served(
    served: TestClient, origin: _Origin
) -> None:
    work = _work(origin)
    _git(work, "checkout", "-q", "-b", "later")
    (work / "later.txt").write_text("later\n", encoding="utf-8")
    _git(work, "add", "later.txt")
    _git(work, "commit", "-qm", "later")
    _git(work, "push", "-q", str(origin.path), "later")
    later = _rev(work)

    pending = _post(served, "/api/source/pin", {"ref": "later"})
    assert pending.status_code == 202
    assert pending.json()["code"] == "selection_pending"
    _settle(served)
    switched = _post(served, "/api/source/pin", {"ref": "later"})
    assert switched.status_code == 200, switched.json()
    status = switched.json()["status"]
    assert (status["pin"], status["ref_name"]) == (later, "later")


def test_a_switched_pin_is_the_one_closed_at_shutdown(origin: _Origin) -> None:
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        first = get_source_session().subject
        assert _post(client, "/api/source/pin", {"oid": origin.first}).json()["changed"]
        second = get_source_session().subject
        assert second is not first
        assert isinstance(second, GitRevisionSubject)
        assert client.get("/api/file", params={"path": _wire("README.md")}).status_code == 200
        # One store, one reader pool: the replaced pin's share is gone, the new one reads.
        assert store_batch_reader_count(second.command_target) >= 1
    assert store_batch_reader_count(second.command_target) == 0


def test_a_refresh_that_moves_a_ref_makes_an_open_all_branch_cursor_stale(
    served: TestClient, origin: _Origin
) -> None:
    """History over all branches is fingerprinted by the refs; the next page is typed stale."""

    first_page = served.get("/api/git/log", params={"limit": "1", "scope": "all"}).json()
    cursor = first_page["cursor"]
    assert cursor
    _git(_work(origin), "branch", "side", origin.first)
    _git(_work(origin), "push", "-q", str(origin.path), "side")
    assert _post(served, "/api/source/refresh").status_code == 202
    _settle(served)

    stale = served.get("/api/git/log", params={"limit": "1", "scope": "all", "cursor": cursor})
    assert stale.status_code == 409
    assert stale.json()["code"] == "history_stale"
    # The default walk is the pin alone, so a moved ref does not disturb it.
    default = served.get("/api/git/log", params={"limit": "1"}).json()
    assert (
        served.get("/api/git/log", params={"limit": "1", "cursor": default["cursor"]}).status_code
        == 200
    )


# ── Route safety ─────────────────────────────────────────────────────


@pytest.mark.parametrize("route", ["/api/source/refresh", "/api/source/pin"])
def test_a_get_cannot_start_work_or_switch_the_pin(served: TestClient, route: str) -> None:
    before = served.get("/api/source/status").json()
    assert served.get(route).status_code == 405
    after = served.get("/api/source/status").json()
    assert after["refreshing"] is False
    assert after["generation"] == before["generation"]


@pytest.mark.parametrize("route", ["/api/source/refresh", "/api/source/pin"])
@pytest.mark.parametrize(
    ("headers", "status_code"),
    [
        ({"origin": "https://attacker.example", "sec-fetch-site": "cross-site"}, 403),
        ({"origin": "null"}, 403),
        ({"sec-fetch-site": "same-site", "origin": "http://sub.localhost"}, 403),
        ({"content-type": "text/plain"}, 415),
        ({"content-type": "application/x-www-form-urlencoded"}, 415),
    ],
)
def test_a_cross_origin_or_form_post_is_refused(
    served: TestClient, route: str, headers: dict[str, str], status_code: int
) -> None:
    before = served.get("/api/source/status").json()
    request_headers = {"content-type": "application/json", **headers}
    response = served.post(route, content=b'{"ref": "topic"}', headers=request_headers)
    assert response.status_code == status_code
    after = served.get("/api/source/status").json()
    assert after["refreshing"] is False
    assert after["generation"] == before["generation"]


def test_a_same_origin_page_may_post(served: TestClient) -> None:
    response = served.post(
        "/api/source/refresh",
        content=b"{}",
        headers={"content-type": "application/json", "sec-fetch-site": "same-origin"},
    )
    assert response.status_code == 202
    _settle(served)


# ── The coordinator ──────────────────────────────────────────────────


def test_the_coordinator_bounds_concurrent_jobs_across_keys() -> None:
    async def scenario() -> tuple[int, list[str]]:
        coordinator = RefreshCoordinator(limit=2)
        running = 0
        peak = 0
        release = asyncio.Event()
        answers: list[str] = []

        async def job() -> None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await release.wait()
            running -= 1

        async def failing() -> None:
            raise RuntimeError("never reaches a request")

        for key in ("a", "b", "c", "a"):
            answers.append(coordinator.start(key, job))
        answers.append(coordinator.start("d", failing))
        await asyncio.sleep(0.05)
        release.set()
        await coordinator.drain(timeout_s=5)
        await coordinator.aclose()
        return peak, answers

    peak, answers = asyncio.run(scenario())
    assert peak == 2
    assert answers == ["started", "started", "started", "joined", "started"]


class _BusyMirror:
    """A mirror whose store another process refreshed and recorded in the same second."""

    key = "store"

    def __init__(self, at: str) -> None:
        self.at = at

    async def open_selection(self, *, ref: str | None, oid: str | None) -> GitRevisionSubject:
        raise AssertionError("not reached")

    async def refresh(self) -> RefreshResult:
        return RefreshResult("refreshing_elsewhere", self.at)

    async def recorded_freshness(self) -> RecordedFreshness:
        return RecordedFreshness(self.at, "refresh", "succeeded", self.at)

    async def ref_tip(self, ref: str) -> str | None:
        return None

    async def refresh_running_elsewhere(self) -> bool:
        return False

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        return None


@pytest.mark.parametrize(
    ("written", "shown"),
    [("after the busy result", "succeeded"), ("before the busy result", "refreshing_elsewhere")],
)
def test_a_same_second_record_outranks_a_busy_result_only_when_newer(
    written: str, shown: str
) -> None:
    """Timestamps have one-second resolution, so a tie goes to a record that changed."""

    async def scenario() -> LastOutcome | None:
        coordinator = RefreshCoordinator()
        session = MirrorSession(_BusyMirror(_FUTURE), coordinator)
        if written == "before the busy result":
            await session.observe()
        session.request_refresh()
        await coordinator.drain(timeout_s=5)
        await coordinator.aclose()
        return session._last_outcome()

    outcome = asyncio.run(scenario())
    assert outcome is not None
    assert (outcome["outcome"], outcome["at"]) == (shown, _FUTURE)


# ── The shell ────────────────────────────────────────────────────────


def test_a_pin_shell_has_a_freshness_row_loaded_on_demand(
    served: TestClient, tmp_path: Path
) -> None:
    shell = served.get("/view/").text
    assert '<div class="source-freshness" id="source-freshness" hidden></div>' in shell
    bundles = shell[shell.index("window.METABROWSER_ASSET_BUNDLES=") :]
    bundles = bundles[: bundles.index("</script>")]
    assert '"source-freshness": [{"src": "/static/source-freshness.js' in bundles
    # On demand, never eager: no blocking script tag names it.
    assert '<script src="/static/source-freshness.js' not in shell


def test_a_folder_shell_has_no_freshness_row(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        shell = client.get("/view/").text
    assert 'id="source-freshness"' not in shell


def test_a_restart_reopens_the_announced_pin_not_a_switched_one(origin: _Origin) -> None:
    """The opener stays the one serve mode configured, so the banner stays true."""

    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        switched = _post(client, "/api/source/pin", {"oid": origin.first}).json()
        assert switched["status"]["pin"] == origin.first
    with TestClient(server.app) as client:
        status = client.get("/api/source/status").json()
    assert status["pin"] == origin.second
    assert status["ref"] == "refs/remotes/origin/topic"


def test_a_switch_attaches_the_new_pin_before_it_closes_the_old() -> None:
    """No request can meet a moment with no subject attached while an opener is set."""

    observed: list[str] = []

    class _Subject:
        kind = "git_revision"
        identity = ""
        capabilities = None
        content = None
        filesystem_root = None

        def __init__(self, name: str) -> None:
            self.name = name

        async def aclose(self) -> None:
            try:
                served = get_source_session().subject.name  # type: ignore[attr-defined]
            except SubjectNotOpenError:
                served = "nothing"
            observed.append(f"close {self.name} while serving {served}")

    async def never_called() -> Any:
        raise AssertionError("the opener only runs in a lifespan")

    serve_subject_opener(never_called)
    try:
        first, second = _Subject("first"), _Subject("second")
        attach_owned_subject(first)  # type: ignore[arg-type]
        before = get_source_session().generation
        session = asyncio.run(replace_owned_subject(second))  # type: ignore[arg-type]
        assert session.subject is second
        assert session.generation == before + 1
        assert observed == ["close first while serving second"]
        # Shutdown is the one moment nothing is served, and a request then is refused.
        asyncio.run(close_owned_subject())
        assert observed[-1] == "close second while serving nothing"
    finally:
        reset_source_session()


# ── Review fixes ─────────────────────────────────────────────────────


def test_a_page_for_another_pin_is_refused_as_pin_changed(
    served: TestClient, origin: _Origin
) -> None:
    """A tab still showing the old pin never reads the new pin's files into its page."""

    shell = served.get("/view/").text
    page = {"pin": origin.second, "ref": "refs/remotes/origin/topic"}
    assert f"window.METABROWSER_SOURCE_PIN={json.dumps(page)};" in shell
    assert "window.MetabrowserSourcePinGuard = Object.freeze(" in shell
    tree = {"depth": "1"}
    assert served.get("/api/tree", params=tree, headers=_pin(origin.second)).status_code == 200

    assert _post(served, "/api/source/pin", {"oid": origin.first}).json()["changed"]
    refused = served.get("/api/tree", params=tree, headers=_pin(origin.second))
    assert refused.status_code == 409
    assert refused.json()["code"] == "pin_changed"
    assert refused.json()["pin"] == origin.first
    assert refused.headers["x-metabrowser-pin-changed"] == origin.first
    # The source routes are how a page finds what is served, so they answer.
    exempt = served.get("/api/source/status", headers=_pin(origin.second))
    assert exempt.status_code == 200
    # A request that names no pin, as curl and metab --api send, is served.
    assert served.get("/api/tree", params=tree).status_code == 200
    assert served.get("/api/tree", params=tree, headers=_pin(origin.first)).status_code == 200
    # Switching back to the pin a page shows makes its requests good again.
    assert _post(served, "/api/source/pin", {"ref": "topic"}).json()["changed"]
    assert served.get("/api/tree", params=tree, headers=_pin(origin.second)).status_code == 200


def test_a_page_left_open_across_a_restart_onto_another_pin_is_refused(
    tmp_path: Path, origin: _Origin
) -> None:
    """Every server process counts generations from 1, so the commit is the token."""

    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        before = client.get("/api/source/status").json()
    newer = _push_commit(origin, "NEW.md", "# New\n", "third")
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")
    assert (
        runner.invoke(
            _app, [origin.url, "--api", "/api/source/refresh", "--data", str(body)]
        ).exit_code
        == 0
    )
    reset_source_session()
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        after = client.get("/api/source/status").json()
        stale = client.get("/api/tree", params={"depth": "1"}, headers=_pin(before["pin"]))
    assert after["generation"] == before["generation"]
    assert after["pin"] == newer != before["pin"]
    assert stale.status_code == 409
    assert stale.headers["x-metabrowser-pin-changed"] == newer


def _pin(value: str) -> dict[str, str]:
    return {"x-metabrowser-pin": value}


def test_a_folder_page_names_no_pin_and_refuses_a_pin_pages_requests(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        shell = client.get("/view/").text
        from_a_pin_page = client.get("/api/tree", headers=_pin("0" * 40))
    assert "METABROWSER_SOURCE_PIN" not in shell
    assert "MetabrowserSourcePinGuard" not in shell
    # A tab left from a pin, now talking to a server that serves a folder.
    assert from_a_pin_page.status_code == 409
    assert from_a_pin_page.headers["x-metabrowser-pin-changed"] == ""


def test_latest_tells_a_deleted_ref_from_an_unobserved_one(
    tmp_path: Path, origin: _Origin, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        assert client.get("/api/source/status").json()["ref_on_origin"] is True
        _git(_work(origin), "branch", "gone", origin.first)
        _git(_work(origin), "push", "-q", str(origin.path), "gone")
        assert _post(client, "/api/source/refresh").status_code == 202
        _settle(client)
        assert _post(client, "/api/source/pin", {"ref": "gone"}).status_code == 200
        _git(_work(origin), "push", "-q", str(origin.path), "--delete", "gone")
        assert _post(client, "/api/source/refresh").status_code == 202
        gone = _settle(client)
        by_id = _post(client, "/api/source/pin", {"oid": origin.first}).json()["status"]
    assert gone["ref_name"] == "gone"
    assert gone["latest"] is None and gone["ref_on_origin"] is False
    assert by_id["ref"] is None and by_id["ref_on_origin"] is None

    # A mirror whose freshness cannot be read at startup knows nothing about the ref.
    async def unreadable(_self: object) -> object:
        raise OSError("state.yml could not be read")

    monkeypatch.setattr(
        "metabrowser.cache.served_mirror.StoreMirror.recorded_freshness", unreadable
    )
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        unknown = client.get("/api/source/status").json()
    assert unknown["latest"] is None and unknown["ref_on_origin"] is None
    assert unknown["refreshable"] is True


def test_a_server_follows_a_refresh_another_process_is_running(
    served: TestClient, origin: _Origin, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Busy elsewhere: this server reports it, then observes the store once that ends."""

    monkeypatch.setattr("metabrowser.mirror_refresh.ELSEWHERE_POLL_S", 0.05)
    published = _published(tmp_path, origin)
    newer = _push_commit(origin, "NEW.md", "# New\n", "third")
    with store_fetch_lock(published.home, published.store_key):
        assert _post(served, "/api/source/refresh").status_code == 202
        deadline = time.monotonic() + 10
        while True:
            status = served.get("/api/source/status").json()
            if status["last_outcome"]["outcome"] == "refreshing_elsewhere":
                break
            assert time.monotonic() < deadline
            time.sleep(0.02)
        # Still following the other refresh, so the page keeps polling quickly.
        assert status["refreshing"] is True
        assert status["latest"] == origin.second
        # The other process's fetch, run here while its lock is held.
        subprocess.run(
            [
                "git",
                "--git-dir",
                str(published.git_dir),
                "fetch",
                "-q",
                "--no-write-fetch-head",
                "origin",
                "+refs/heads/*:refs/remotes/origin/*",
            ],
            check=True,
            env={name: value for name, value in os.environ.items() if not name.startswith("GIT_")},
        )
    followed = _settle(served)
    assert followed["latest"] == newer
    assert followed["refreshing"] is False
    # The other refresh has ended and wrote no record, so the busy result is gone and
    # the record reports what was there before.
    assert followed["last_outcome"]["outcome"] == "succeeded"
    assert followed["last_outcome"]["operation"] == "acquire"


def test_a_detached_origin_head_is_a_quiet_outcome(served: TestClient, origin: _Origin) -> None:
    _git(origin.path, "update-ref", "--no-deref", "HEAD", origin.first)
    assert _post(served, "/api/source/refresh").status_code == 202
    status = _settle(served)
    assert status["last_outcome"]["outcome"] == "default_branch_unknown"
    assert status["ref"] == "refs/remotes/origin/topic"
    assert status["latest"] == origin.second
    assert status["stale"] is False


def test_a_followed_refresh_counts_only_if_it_wrote_its_record() -> None:
    """A refresh another process ran that was killed writes no record; the old one is not it.

    The record file's stamp tells a rewrite apart even within one second; without
    stamps only a record from a later second counts.
    """

    busy_at = "2026-09-24T10:00:05Z"
    before = RecordedFreshness(busy_at, "refresh", "succeeded", busy_at, (7, 1_000))
    rewritten = RecordedFreshness(busy_at, "refresh", "not_found_or_private", busy_at, (8, 1_500))

    def follow(recorded: RecordedFreshness, *, ended: bool = True) -> str:
        return followed_outcome(recorded, baseline=before, since=busy_at, ended=ended)

    # The same second, told apart by the stamp: a rewrite counts, the earlier record not.
    assert follow(rewritten) == "not_found_or_private"
    assert follow(before) == "failed"
    assert follow(rewritten, ended=False) == "failed"
    # Without stamps, a same-second record is not trusted; a later one is.
    unstamped = RecordedFreshness(busy_at, "refresh", "succeeded", busy_at)
    later = RecordedFreshness(busy_at, "refresh", "succeeded", "2026-09-24T10:00:06Z")
    assert followed_outcome(unstamped, baseline=None, since=busy_at, ended=True) == "failed"
    assert followed_outcome(later, baseline=None, since=busy_at, ended=True) == "succeeded"
    empty = RecordedFreshness(None, None, None, None)
    assert followed_outcome(empty, baseline=None, since=busy_at, ended=True) == "failed"
