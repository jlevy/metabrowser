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
import shutil
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
from metabrowser.cache.locks import repository_store_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
)
from metabrowser.cache.update import RefreshOutcome, StoreUpdate
from metabrowser.cli.main import _app
from metabrowser.git.tree_source import GitPath, GitRevisionSubject, store_batch_reader_count
from metabrowser.mirror_refresh import RefreshCoordinator
from metabrowser.source import get_source_session, reset_source_session
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
    assert response.headers["cache-control"] == "no-store"
    etag = response.headers["etag"]

    unchanged = served.get("/api/source/status", headers={"if-none-match": etag})
    assert unchanged.status_code == 304
    assert unchanged.headers["etag"] == etag
    assert unchanged.content == b""
    weak = served.get("/api/source/status", headers={"if-none-match": f"W/{etag}"})
    assert weak.status_code == 304
    other = served.get("/api/source/status", headers={"if-none-match": '"other"'})
    assert other.status_code == 200


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


def test_concurrent_refresh_requests_join_one_fetch(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    release = threading.Event()

    async def held_update(home: Path, store_key: str) -> StoreUpdate:
        calls.append(store_key)
        await asyncio.to_thread(release.wait, 30)
        return StoreUpdate(RefreshOutcome.succeeded, "2026-09-23T12:00:00Z")

    monkeypatch.setattr("metabrowser.cache.served_mirror.update_store", held_update)
    answers = [_post(served, "/api/source/refresh").json()["refresh"] for _ in range(3)]
    assert answers == ["started", "joined", "joined"]
    assert served.get("/api/source/status").json()["refreshing"] is True
    release.set()
    status = _settle(served)
    assert len(calls) == 1
    assert status["last_outcome"] == {
        "operation": "refresh",
        "outcome": "succeeded",
        "at": "2026-09-23T12:00:00Z",
    }
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

    async def endless_update(home: Path, store_key: str) -> StoreUpdate:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            ended.append("cancelled")
            raise
        return StoreUpdate(RefreshOutcome.succeeded, "2026-09-23T12:00:00Z")

    monkeypatch.setattr("metabrowser.cache.served_mirror.update_store", endless_update)
    assert _serve(origin.url).exit_code == 0
    with TestClient(server.app) as client:
        assert _post(client, "/api/source/refresh").json()["refresh"] == "started"
        assert client.get("/api/source/status").json()["refreshing"] is True
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


# ── Pin switching ────────────────────────────────────────────────────


def test_pin_selections_resolve_in_the_mirror_and_refusals_are_typed(
    served: TestClient, origin: _Origin
) -> None:
    by_prefix = _post(served, "/api/source/pin", {"oid": origin.first[:8]})
    assert by_prefix.status_code == 200
    assert by_prefix.json()["status"]["pin"] == origin.first

    cases: list[tuple[Any, int, str]] = [
        ({"ref": "nope"}, 404, "selection_not_found"),
        ({"oid": "0" * 40}, 404, "selection_not_found"),
        ({"ref": ":/first"}, 400, "invalid_selection"),
        ({"ref": "topic@{1}"}, 400, "invalid_selection"),
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
