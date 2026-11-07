"""Optional native stack snapshots: bounded reads, independent work, and ownership."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from collections.abc import Sequence
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import paths_safe
from metabrowser.builtin_plugins.github import gh, pull_list, pull_stacks
from metabrowser.builtin_plugins.github.gh import GhError, GhResponse
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, write_list_refresh
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.builtin_plugins.github.pull_stacks import read_stacks, refresh_stacks
from metabrowser.builtin_plugins.github.pull_stacks_route import StackView, stack_envelope
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.server import app
from tests.cache_home_fixture import FixtureSource, _stage_and_publish_source, build_empty_home
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    READER,
    account,
    generated_item,
    install_fake_gh,
    logged_gh_calls,
    seed_catalog,
)


def test_stack_get_on_plain_folder_is_cache_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths_safe._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]

    async def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a cache-only stack GET consulted gh")

    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh._run", forbidden)
    with TestClient(app) as client:
        response = client.get("/api/plugin/github/stacks")
        assert response.status_code == 200
        assert response.json()["reason"] == "not_github"
        assert response.json()["stacks"] == []
        again = client.get(
            "/api/plugin/github/stacks", headers={"if-none-match": response.headers["etag"]}
        )
        assert again.status_code == 304
        assert client.post("/api/plugin/github/stacks-refresh", json={}).status_code == 409


SOURCE = FixtureSource("https", CANONICAL)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    pull_stacks._UNWRITTEN.clear()  # pyright: ignore[reportPrivateUsage]
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def native(number: int, *pulls: int) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
        "base": {"ref": "main"},
        "open": True,
        "pull_requests": [{"number": n} for n in pulls or (number,)],
    }


def response(items: list[dict[str, Any]], *, more: bool = False, etag: str = '"v1"') -> GhResponse:
    headers = {"etag": etag}
    if more:
        headers["link"] = '<https://api.github.com/repos/octo/demo/stacks?page=2>; rel="next"'
    return GhResponse(200, headers, json.dumps(items).encode())


def provider(
    monkeypatch: pytest.MonkeyPatch,
    answers: Sequence[GhResponse | BaseException],
    *,
    readers: tuple[str, ...] = (READER,),
    available: bool = True,
) -> list[str]:
    calls: list[str] = []
    pending = list(answers)
    accounts = iter(readers)
    last = readers[-1]

    async def capability() -> bool:
        calls.append("version")
        return available

    async def active() -> str:
        calls.append("auth")
        return next(accounts, last)

    async def api(path: str, *, etag: str | None = None) -> GhResponse:
        calls.append(path + (f" etag={etag}" if etag else ""))
        answer = pending.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(pull_stacks, "gh_stack_available", capability)
    monkeypatch.setattr(pull_stacks, "active_account", active)
    monkeypatch.setattr(pull_stacks, "gh_api", api)
    return calls


def envelope(repository: ListedRepository) -> dict[str, Any]:
    return dict(stack_envelope(StackView(repository, None, False)))


def test_titles_follow_the_matching_catalog_without_refetching_native_membership(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_stacks_route import envelope_etag

    calls = provider(monkeypatch, [response([native(30, 7, 9)])])
    asyncio.run(refresh_stacks(repository))
    before = stack_envelope(StackView(repository, None, False))
    assert before["stacks"][0]["titles"] == [None, None]
    stored = read_stacks(repository)
    seed_catalog(repository, [generated_item(7) | {"title": "A useful title"}])
    first = stack_envelope(StackView(repository, None, False))
    assert first["stacks"][0]["titles"] == ["A useful title", None]
    assert envelope_etag(first) != envelope_etag(before)
    seed_catalog(
        repository,
        [generated_item(7) | {"title": "Updated title", "updated_at": "2026-10-02T12:00:00Z"}],
    )
    assert envelope(repository)["stacks"][0]["titles"] == ["Updated title", None]
    assert read_stacks(repository) == stored
    assert len(calls) == 4, "projecting cached titles never invokes the provider"
    data = (repository.home / f"sources/{repository.slug}/pulls/stacks.json").read_text()
    assert '"titles"' not in data, "native membership does not duplicate catalog metadata"


@pytest.mark.parametrize("changed", ["reader", "source"])
def test_stack_titles_never_cross_catalog_identity(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    provider(monkeypatch, [response([native(30, 7)])])
    asyncio.run(refresh_stacks(repository))
    state = seed_catalog(repository, [generated_item(7)])
    value = "gh:someone-else" if changed == "reader" else "https://github.com/other/repo"
    altered = state.model_copy(update={changed: value})
    path = repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE checkpoint SET value=? WHERE id=1", (altered.model_dump_json(),))
    assert envelope(repository)["stacks"][0]["titles"] == [None]


def test_stack_titles_span_indexed_catalog_batches(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = provider(monkeypatch, [response([native(30, *range(1, 1001)), native(31, 1001)])])
    asyncio.run(refresh_stacks(repository))
    seed_catalog(repository, [generated_item(number) for number in range(1, 1002)])
    stacks = envelope(repository)["stacks"]
    assert stacks[0]["titles"] == [f"Work item {number}" for number in range(1, 1001)]
    assert stacks[1]["titles"] == ["Work item 1001"]
    assert len(calls) == 4


def test_pages_preserve_order_and_conditional_continuation_without_link(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = provider(
        monkeypatch, [response([native(30, 7, 9)], more=True), response([native(50, 2)])]
    )
    asyncio.run(refresh_stacks(repository))
    first = envelope(repository)
    assert first["complete"] and first["stacks"][0]["pulls"] == [7, 9]
    assert [row["number"] for row in first["stacks"]] == [30, 50]
    assert first["stacks"][0]["titles"] == [None, None]
    assert first["reader"] == "gh:" + READER
    assert len(calls) == 5
    calls = provider(monkeypatch, [GhResponse(304, {}, b""), GhResponse(304, {}, b"")])
    asyncio.run(refresh_stacks(repository, retry=True))
    assert envelope(repository) == first
    assert len(calls) == 5 and all("etag=" in call for call in calls[2:4])
    # A new terminal first page never keeps the preceding tail.
    provider(monkeypatch, [response([native(30, 7, 9)], etag='"v2"')])
    asyncio.run(refresh_stacks(repository, retry=True))
    assert [row["number"] for row in envelope(repository)["stacks"]] == [30]


def test_missing_optional_tool_backs_off_and_explicit_retry_reprobes(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = provider(monkeypatch, [], available=False)
    asyncio.run(refresh_stacks(repository))
    assert envelope(repository)["reason"] == "gh_stack_missing"
    assert envelope(repository)["fresh_for_s"] == 300
    asyncio.run(refresh_stacks(repository))
    assert calls == ["version"]
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=10))
    assert envelope(repository)["fresh_for_s"] == 290
    calls = provider(monkeypatch, [response([])])
    asyncio.run(refresh_stacks(repository, retry=True))
    assert calls[0] == "version" and len(calls) == 4
    result = envelope(repository)
    assert result["state"] == "current" and result["complete"] and result["stacks"] == []


@pytest.mark.parametrize(
    "failure",
    [
        GhError("Unavailable", state="not_found_or_private"),
        GhError("Unavailable", state="gh_failed"),
    ],
)
def test_optional_failure_retains_known_snapshot_and_core_stamps(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    failure: GhError,
) -> None:
    provider(monkeypatch, [response([native(12, 7)])])
    asyncio.run(refresh_stacks(repository))
    core = PullRefreshStamp(outcome="succeeded", at=utc_stamp(FETCHED_AT), reader="gh:" + READER)
    write_list_refresh(repository.home, repository.slug, "all", core)
    before = pull_list.read_list_refresh(repository.home, repository.slug, "all")
    provider(monkeypatch, [failure])
    asyncio.run(refresh_stacks(repository, retry=True))
    result = envelope(repository)
    assert result["state"] == "stale" and result["stacks"][0]["number"] == 12
    assert result["last_refresh"]["outcome"] == failure.state
    assert pull_list.read_list_refresh(repository.home, repository.slug, "all") == before


def test_final_account_check_and_new_reader_conditional_isolation(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [response([native(12, 7)])])
    asyncio.run(refresh_stacks(repository))
    provider(monkeypatch, [response([native(13, 8)])], readers=(READER, "new-reader"))
    asyncio.run(refresh_stacks(repository, retry=True))
    result = envelope(repository)
    assert result["reader"] == "gh:" + READER and result["stacks"][0]["number"] == 12
    assert result["last_refresh"]["outcome"] == "account_changed"
    calls = provider(monkeypatch, [response([native(13, 8)])], readers=("new-reader",))
    asyncio.run(refresh_stacks(repository, retry=True))
    assert "etag=" not in calls[2]
    assert envelope(repository)["reader"] == "gh:new-reader"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [None],
        [native(True)],
        [{**native(1), "url": "https://api.github.com/repos/other/repo/stacks/1"}],
        [{**native(1), "url": None}],
        [native(1, 7), native(1, 8)],
    ],
)
def test_malformed_or_foreign_metadata_is_typed_and_not_adopted(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    provider(monkeypatch, [GhResponse(200, {}, json.dumps(payload).encode())])
    asyncio.run(refresh_stacks(repository))
    result = envelope(repository)
    assert result["state"] == "absent" and result["reason"] == "unreadable"
    assert result["stacks"] == []


def test_bounded_pages_show_positive_membership_without_asserting_completeness(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        response([native(i) for i in range(page * 100 + 1, page * 100 + 101)], more=True)
        for page in range(10)
    ]
    calls = provider(monkeypatch, pages)
    asyncio.run(refresh_stacks(repository))
    result = envelope(repository)
    assert len(result["stacks"]) == 1000 and not result["complete"]
    assert len(calls) == 13  # capability, initial/final account, ten pages


def test_cancellation_does_not_publish_partial_pages(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [])

    async def run() -> None:
        entered = asyncio.Event()
        parked = asyncio.Event()

        async def api(path: str, *, etag: str | None = None) -> GhResponse:
            if path.endswith("&page=1"):
                return response([native(1)], more=True)
            entered.set()
            await parked.wait()
            raise AssertionError("cancelled page resumed")

        monkeypatch.setattr(pull_stacks, "gh_api", api)
        task = asyncio.create_task(refresh_stacks(repository))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert read_stacks(repository) is None


def test_rate_hold_written_while_waiting_for_network_slot_is_honored(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = provider(monkeypatch, [])

    async def run() -> None:
        slot = asyncio.Semaphore(0)
        entered = asyncio.Event()

        async def capability() -> bool:
            calls.append("version")
            entered.set()
            return True

        monkeypatch.setattr(pull_stacks, "gh_stack_available", capability)
        task = asyncio.create_task(refresh_stacks(repository, slot=slot))
        await entered.wait()
        held = PullRefreshStamp(
            outcome="rate_limited",
            at=utc_stamp(FETCHED_AT),
            reset_at=utc_stamp(FETCHED_AT + timedelta(seconds=60)),
        )
        await asyncio.to_thread(write_list_refresh, repository.home, repository.slug, "all", held)
        slot.release()
        await task

    asyncio.run(run())
    assert calls == ["version"]
    assert envelope(repository)["last_refresh"]["outcome"] == "rate_limited"
    assert not pull_stacks.refresh_wanted(repository, retry=True)


def test_stale_writer_cannot_replace_newer_account_snapshot(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [response([native(1)])])
    asyncio.run(refresh_stacks(repository))
    old = read_stacks(repository)
    assert old is not None and old.snapshot is not None
    provider(monkeypatch, [response([native(2)])], readers=("new-reader",))
    asyncio.run(refresh_stacks(repository, retry=True))
    assert not pull_stacks.publish_stacks(repository, old, old.snapshot, old.last_refresh)
    assert envelope(repository)["reader"] == "gh:new-reader"


def test_real_capability_probe_uses_isolated_cwd_and_bounded_optional_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in install_fake_gh(
        tmp_path, {"stack_version": "0.1.0", "auth": account(READER), "api": {}}
    ).items():
        monkeypatch.setenv(key, value)
    assert asyncio.run(gh.gh_stack_available())
    assert logged_gh_calls(tmp_path) == ["gh stack --version"]
    for key, value in install_fake_gh(tmp_path, {"auth": account(READER), "api": {}}).items():
        monkeypatch.setenv(key, value)
    assert not asyncio.run(gh.gh_stack_available())


def test_membership_in_distinct_stacks_is_preserved(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [response([native(10, 7, 8), native(20, 7, 9)])])
    asyncio.run(refresh_stacks(repository))
    assert [row["pulls"] for row in envelope(repository)["stacks"]] == [[7, 8], [7, 9]]


def test_cached_route_etag_ignores_countdown_but_changes_at_expiry(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider(monkeypatch, [response([native(10, 7, 8)])])
    asyncio.run(refresh_stacks(repository))
    from metabrowser.builtin_plugins.github import pull_stacks_route

    monkeypatch.setattr(
        pull_stacks_route, "stack_view", lambda app: StackView(repository, None, False)
    )
    paths_safe._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]

    async def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("cache-only GET started a process")

    monkeypatch.setattr(gh, "_run", forbidden)
    before = (repository.home / f"sources/{repository.slug}/pulls/stacks.json").read_bytes()
    with TestClient(app) as client:
        first = client.get("/api/plugin/github/stacks")
        assert first.status_code == 200 and first.json()["fresh_for_s"] == 300
        monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=30))
        assert envelope(repository)["fresh_for_s"] == 270
        assert (
            client.get(
                "/api/plugin/github/stacks", headers={"if-none-match": first.headers["etag"]}
            ).status_code
            == 304
        )
        monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(seconds=301))
        expired = client.get(
            "/api/plugin/github/stacks", headers={"if-none-match": first.headers["etag"]}
        )
        assert expired.status_code == 200 and expired.json()["state"] == "stale"
        assert expired.json()["fresh_for_s"] == 0
        assert client.get("/api/plugin/github/stacks?number=7").status_code == 400
        for body in ({"number": 7}, {"retry": 1}, {"retry": None}):
            assert client.post("/api/plugin/github/stacks-refresh", json=body).status_code == 400
    assert (repository.home / f"sources/{repository.slug}/pulls/stacks.json").read_bytes() == before


def test_cache_byte_bound_keeps_only_completed_pages_and_marks_partial(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = pull_stacks._page(repository, response([native(1)]), None)  # pyright: ignore[reportPrivateUsage]
    limit = pull_stacks._ENVELOPE_BYTES + len(one.model_dump_json().encode()) + 100  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(pull_stacks, "MAX_STACK_BYTES", limit)
    provider(
        monkeypatch, [response([native(1)], more=True), response([native(2, *range(100, 500))])]
    )
    asyncio.run(refresh_stacks(repository))
    result = envelope(repository)
    assert result["state"] == "current" and not result["complete"]
    assert [row["number"] for row in result["stacks"]] == [1]


def test_cache_read_refuses_symlink_and_atomic_write_leaves_target_untouched(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider(monkeypatch, [response([native(1)])])
    asyncio.run(refresh_stacks(repository))
    path = repository.home / f"sources/{repository.slug}/pulls/stacks.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    assert read_stacks(repository) is None
    before = outside.read_bytes()
    provider(monkeypatch, [response([native(2)])])
    asyncio.run(refresh_stacks(repository, retry=True))
    assert outside.read_bytes() == before and not path.is_symlink()
    assert envelope(repository)["stacks"][0]["number"] == 2


def test_membership_budget_never_truncates_one_stack(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        response([native(n, *range(n * 100, n * 100 + 100)) for n in range(1, 101)], more=True),
        response([native(101)]),
    ]
    calls = provider(monkeypatch, pages)
    asyncio.run(refresh_stacks(repository))
    result = envelope(repository)
    assert not result["complete"] and len(result["stacks"]) == 100
    assert sum(len(row["pulls"]) for row in result["stacks"]) == 10000
    assert len(calls) == 5
    provider(monkeypatch, [response([native(102, *range(1, 1002))])])
    asyncio.run(refresh_stacks(repository, retry=True))
    refused = envelope(repository)
    assert refused["last_refresh"]["outcome"] == "unreadable"
    assert refused["stacks"] == result["stacks"]


def test_cancelled_publication_lock_waiter_never_writes_later(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [response([native(1)])])
    asyncio.run(refresh_stacks(repository))
    old = read_stacks(repository)
    assert old is not None
    entered, release = threading.Event(), threading.Event()

    def hold() -> None:
        with source_alias_lock(repository.home, repository.slug):
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=hold)
    thread.start()
    assert entered.wait(5)

    async def run() -> None:
        failed = PullRefreshStamp(outcome="gh_failed", at=utc_stamp(FETCHED_AT))
        task = asyncio.create_task(
            run_lock_section(partial(pull_stacks.publish_stacks, repository, old, None, failed))
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(run())
    finally:
        release.set()
        thread.join(5)
    assert read_stacks(repository) == old


def test_unwritable_cache_keeps_snapshot_and_process_backoff(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider(monkeypatch, [response([native(1)])])
    asyncio.run(refresh_stacks(repository))
    directory = repository.home / f"sources/{repository.slug}/pulls"
    directory.chmod(0o500)
    try:
        provider(monkeypatch, [response([native(2)])])
        asyncio.run(refresh_stacks(repository, retry=True))
        result = envelope(repository)
        assert result["stacks"][0]["number"] == 1
        assert result["last_refresh"]["outcome"] == "cache_unwritable"
        assert not pull_stacks.refresh_wanted(repository)
    finally:
        directory.chmod(0o700)
    provider(monkeypatch, [response([native(2)])])
    asyncio.run(refresh_stacks(repository, retry=True))
    assert envelope(repository)["stacks"][0]["number"] == 2
