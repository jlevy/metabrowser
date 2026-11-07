"""Catalog storage, paging, ownership and cancellation beyond the route transcripts."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sqlite3
import subprocess
import threading
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import (
    gh,
    gh_lists,
    pull_catalog,
    pull_list,
    pull_list_refresh,
    pull_list_route,
)
from metabrowser.builtin_plugins.github.gh import GhCursorError, GhError
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, read_list, utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import (
    CATALOG_PROJECTION,
    CatalogState,
    catalog_row,
    catalog_search,
    catalog_window,
    publish_page,
    read_catalog,
)
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    PullRefreshStamp,
    read_list_refresh,
    refresh_is_due,
    write_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_list_refresh import (  # pyright: ignore[reportPrivateUsage]
    _row,
    refresh_pull_list,
)
from metabrowser.builtin_plugins.github.pull_list_route import (
    ListRequestError,
    ListView,
    ListWindow,
    RefreshRequest,
    list_window,
    pull_list_envelope,
    refresh_request,
    refresh_wanted,
    search_query,
)
from metabrowser.cache.locks import run_lock_section, source_alias_lock
from metabrowser.cache.paths import PullListName
from metabrowser.home import ensure_private_directory, write_private_file_atomic
from metabrowser.mirror_refresh import RefreshCoordinator
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    READER,
    account,
    catalog_entries,
    generated_item,
    install_fake_gh,
    next_link,
    ok,
    seed_catalog,
)

SOURCE = FixtureSource("https", CANONICAL)
STAMP = utc_stamp(FETCHED_AT)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _path(repository: ListedRepository) -> Path:
    return repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"


def _seed(repository: ListedRepository, items: list[dict[str, Any]], **kwargs: Any) -> CatalogState:
    return seed_catalog(repository, items, fetched_at=STAMP, **kwargs)


def _provider(
    monkeypatch: pytest.MonkeyPatch,
    items: list[dict[str, Any]],
    *,
    reader: str = READER,
    repository_id: str = "R_demo",
) -> list[str]:
    entries = catalog_entries(items, reader=reader, repository_id=repository_id)
    calls: list[str] = []

    async def active() -> str:
        return reader

    async def graphql(query: str, variables: Any, **kwargs: Any) -> dict[str, Any]:
        tail = query.split("page:pullRequests", 1)[1]
        name = (
            "updated"
            if "field:UPDATED_AT" in tail
            else "closed"
            if "states:[CLOSED,MERGED]" in tail
            else "open"
            if "states:OPEN" in tail
            else "all"
        )
        key = f"graphql:{name}:{variables.get('cursor') or 'start'}"
        calls.append(key)
        return entries[key]["body"]["data"]

    monkeypatch.setattr(pull_list_refresh, "active_account", active)
    monkeypatch.setattr(pull_list_refresh, "gh_graphql", graphql)
    return calls


def test_backfill_all_beyond_old_cap_with_small_indexed_windows(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(number) for number in range(1, 1206)]
    calls = _provider(monkeypatch, items)
    state = asyncio.run(refresh_pull_list(repository, "open"))
    assert state.cached == state.totals == {"all": 1205, "open": 1205, "closed": 0}
    assert state.done["all"]
    assert calls[:5] == [
        f"graphql:open:{'start' if not n else f'open-{n}'}" for n in range(0, 500, 100)
    ]
    assert len(calls) == 18
    _, first, after = catalog_window(repository.home, repository.slug, "open", limit=100)
    _, second, _ = catalog_window(repository.home, repository.slug, "open", limit=100, after=after)
    assert (first[0]["number"], second[0]["number"]) == (1205, 1105)
    assert not any(
        (_path(repository).parent / f"list-{name}.json").exists()
        for name in ("all", "open", "closed")
    )
    assert not list((repository.home / "repository-stores").iterdir())
    calls.clear()
    assert not refresh_wanted(ListView(repository, None, False), RefreshRequest("open", 2000))
    assert asyncio.run(refresh_pull_list(repository, "open", target=2000)).cached == state.cached
    assert calls == []


def test_pull_search_respects_title_budget_and_indexes_exact_numbers(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(number) for number in range(1, 16)]
    items[0].update(title="Straße: 100% _ready", draft=True)
    _seed(repository, items, complete=False)
    before = _fingerprint(repository.home)

    assert catalog_search(repository, "STRASSE _READY 100%") == {
        "rows": [{"number": 1, "title": "Straße: 100% _ready", "state": "draft"}],
        "complete": False,
        "limited": False,
        "truncated": False,
    }
    assert not catalog_search(repository, "100_")["rows"]
    common = catalog_search(repository, "item")
    assert [row["number"] for row in common["rows"]] == list(range(15, 3, -1))
    assert common["truncated"] and not common["limited"]

    monkeypatch.setattr(pull_catalog, "_SEARCH_TITLE_ROWS", 3)
    assert catalog_search(repository, "Straße") == {
        "rows": [],
        "complete": False,
        "limited": True,
        "truncated": False,
    }
    exact = catalog_search(repository, "#1")
    assert exact["rows"][0]["number"] == 1 and not exact["limited"] and not exact["truncated"]
    assert not catalog_search(repository, "#0")["rows"]
    assert not catalog_search(repository, "#999999999999")["rows"]
    assert catalog_search(replace(repository, repo="other"), "#1") == {
        "rows": [],
        "complete": False,
        "limited": False,
        "truncated": False,
    }
    assert _fingerprint(repository.home) == before


def test_actual_gh_transport_keeps_only_lightweight_metadata(
    repository: ListedRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = generated_item(7)
    item["body"] = "private body must not be retained"
    item["user"]["avatar_url"] = "https://avatars.githubusercontent.com/u/123?v=4"
    answers = {"auth": account(), "api": catalog_entries([item]), "api_failure": None}
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)
    no_git = tmp_path / "no-git"
    no_git.mkdir()
    git_log = tmp_path / "git-calls"
    executable = no_git / "git"
    executable.write_text(f"#!/bin/sh\nprintf x >> {shlex.quote(str(git_log))}\nexit 77\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{no_git}{os.pathsep}{os.environ['PATH']}")
    state = asyncio.run(refresh_pull_list(repository, "all"))
    assert not git_log.exists()
    assert state.cached["all"] == 1
    row = catalog_row(repository.home, repository.slug, 7)
    assert (
        row is not None
        and row.author_avatar_url == "https://avatars.githubusercontent.com/u/123?s=40"
    )
    assert b"private body" not in _path(repository).read_bytes()
    log = [
        json.loads(line)["args"]
        for line in (tmp_path / "fake-gh-log.jsonl").read_text().splitlines()
    ]
    assert [args[:2] for args in log if args[0] == "api"] == [["api", "graphql"]]
    assert any("avatar_url:avatarUrl(size:40)" in arg for args in log for arg in args)
    assert not list((repository.home / "repository-stores").iterdir())


def test_append_generation_counts_and_stale_backfill_guard(repository: ListedRepository) -> None:
    before = _seed(repository, [generated_item(10), generated_item(9)], complete=False)
    proposed = before.model_copy(update={"count_at": STAMP})
    assert publish_page(repository, before, proposed, (_row(generated_item(8))[0],))
    appended = read_catalog(repository.home, repository.slug)
    assert appended is not None
    assert appended.generation("open") == before.generation("open")
    fresh = generated_item(10) | {
        "title": "new title",
        "state": "closed",
        "updated_at": "2026-10-02T12:00:00Z",
    }
    assert publish_page(repository, appended, appended, (_row(fresh)[0],))
    moved = read_catalog(repository.home, repository.slug)
    assert moved is not None and moved.cached == {"all": 3, "open": 2, "closed": 1}
    assert moved.generation("open") != before.generation("open")
    assert publish_page(repository, moved, moved, (_row(generated_item(10))[0],))
    assert catalog_row(repository.home, repository.slug, 10).title == "new title"  # type: ignore[union-attr]
    assert not publish_page(repository, before, before, ())


@pytest.mark.parametrize("name", ["all", "open", "closed"])
def test_first_row_in_empty_filter_invalidates_its_held_prefix(
    repository: ListedRepository, name: PullListName
) -> None:
    before = _seed(repository, [])
    window = ListWindow(name)
    held = pull_list_envelope(ListView(repository, None, False), window)
    assert held["rows"] == [] and held["next_after"] is None
    item = generated_item(7)
    if name == "closed":
        item["state"] = "closed"
    totals = {"all": 1, "open": int(name != "closed"), "closed": int(name == "closed")}
    assert publish_page(
        repository, before, before.model_copy(update={"totals": totals}), (_row(item)[0],)
    )
    changed = pull_list_envelope(ListView(repository, None, False), window)
    assert changed["generation"] != held["generation"]
    assert [row["number"] for row in changed["rows"]] == [7]
    assert changed["fetched"] == 1


@pytest.mark.parametrize("projection_version", [0, CATALOG_PROJECTION])
def test_reader_change_replaces_rows_atomically(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, projection_version: int
) -> None:
    old = _seed(repository, [generated_item(9)])
    assert publish_page(
        repository, old, old.model_copy(update={"projection_version": projection_version}), ()
    )
    _provider(monkeypatch, [generated_item(2)], reader="other-reader")
    state = asyncio.run(refresh_pull_list(repository, "all"))
    assert state.reader == "gh:other-reader" and state.epoch != old.epoch
    assert catalog_row(repository.home, repository.slug, 9) is None
    assert catalog_row(repository.home, repository.slug, 2) is not None


def test_incremental_refresh_visits_updated_prefix_only_and_manual_retry_runs(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(n) for n in range(1, 301)]
    old = _seed(repository, items)
    items[0] |= {"title": "changed oldest", "updated_at": "2026-10-02T12:00:00Z"}
    calls = _provider(monkeypatch, items)
    updated = asyncio.run(refresh_pull_list(repository, "open", retry=True))
    assert calls == ["graphql:updated:start"]
    assert updated.done["all"] and updated.watermark != old.watermark
    row = catalog_row(repository.home, repository.slug, 1)
    assert row is not None and row.title == "changed oldest"
    assert updated.generation("open") != old.generation("open")


def test_cancelled_backfill_keeps_checkpoint_and_resumes(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(n) for n in range(1, 251)]
    calls = _provider(monkeypatch, items)
    real = pull_list_refresh._read_page  # pyright: ignore[reportPrivateUsage]

    async def exercise() -> None:
        waiting = asyncio.Event()

        async def held(*args: Any, **kwargs: Any) -> Any:
            if args[2] == "all-100":
                waiting.set()
                await asyncio.Event().wait()
            return await real(*args, **kwargs)

        monkeypatch.setattr(pull_list_refresh, "_read_page", held)
        task = asyncio.create_task(refresh_pull_list(repository, "all"))
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    state = read_catalog(repository.home, repository.slug)
    assert state is not None and state.cached["all"] == 100 and state.cursors["all"] == "all-100"
    monkeypatch.setattr(pull_list_refresh, "_read_page", real)
    calls.clear()
    final = asyncio.run(refresh_pull_list(repository, "all"))
    assert calls == ["graphql:all:all-100", "graphql:all:all-200"]
    assert final.cached["all"] == 250 and final.done["all"]


@pytest.mark.parametrize(
    "replacement", [False, True], ids=["expired-cursor", "repository-replaced"]
)
def test_saved_cursor_can_restart_without_losing_or_looping(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, replacement: bool
) -> None:
    state = _seed(repository, [generated_item(9)], complete=False)
    state2 = state.model_copy(update={"cursors": {"all": "expired", "open": None, "closed": None}})
    assert publish_page(repository, state, state2, ())
    calls = _provider(
        monkeypatch, [generated_item(2)], repository_id="R_new" if replacement else "R_demo"
    )
    real = pull_list_refresh._read_page  # pyright: ignore[reportPrivateUsage]

    async def changed(*args: Any, **kwargs: Any) -> Any:
        if args[2] == "expired":
            if not replacement:
                raise GhCursorError("the cursor is invalid")
            return await real(args[0], args[1], None, **kwargs)
        return await real(*args, **kwargs)

    monkeypatch.setattr(pull_list_refresh, "_read_page", changed)
    final = asyncio.run(refresh_pull_list(repository, "all"))
    assert final.done["all"] and len(calls) <= 2
    assert (catalog_row(repository.home, repository.slug, 9) is None) == replacement


def _fingerprint(directory: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        str(path.relative_to(directory)): (
            path.read_bytes(),
            path.stat().st_mode,
            path.stat().st_mtime_ns,
        )
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_cache_only_get_is_nonmutating_and_counts_are_not_cached_counts(
    repository: ListedRepository,
) -> None:
    state = _seed(repository, [generated_item(4)], complete=False)
    proposed = state.model_copy(update={"totals": {"all": 1375, "open": 800, "closed": 575}})
    assert publish_page(repository, state, proposed, ())
    before = _fingerprint(repository.home)
    envelope = pull_list_envelope(ListView(repository, None, False), ListWindow("open"))
    assert (
        envelope["total"],
        envelope["repository_total"],
        envelope["fetched"],
        envelope["catalog_fetched"],
    ) == (800, 1375, 1, 1)
    assert not envelope["complete"] and envelope["next_after"] is None
    assert _fingerprint(repository.home) == before


@pytest.mark.parametrize(
    "damage", ["wal", "oversized-row", "bad-checkpoint", "future-schema", "symlink", "shared"]
)
def test_untrusted_catalog_reads_are_bounded_and_never_modify(
    repository: ListedRepository, tmp_path: Path, damage: str
) -> None:
    _seed(repository, [generated_item(1)])
    path = _path(repository)
    if damage in {"wal", "oversized-row", "bad-checkpoint", "future-schema"}:
        with sqlite3.connect(path) as db:
            if damage == "wal":
                assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            elif damage == "oversized-row":
                db.execute("UPDATE pulls SET body=?", (" " * 100_000,))
            elif damage == "bad-checkpoint":
                db.execute("UPDATE checkpoint SET value=?", ('{"schema_version": 1}',))
            else:
                db.execute("PRAGMA user_version=999")
    elif damage == "symlink":
        saved = tmp_path / "saved.sqlite3"
        path.rename(saved)
        path.symlink_to(saved)
    else:
        path.chmod(0o644)
    before = _fingerprint(repository.home)
    assert catalog_window(repository.home, repository.slug, "all", limit=100) == (None, [], None)
    assert catalog_search(repository, "#1") == {
        "rows": [],
        "complete": False,
        "limited": False,
        "truncated": False,
    }
    assert _fingerprint(repository.home) == before


def test_empty_initialization_recovers_but_future_schema_refuses_explicitly(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = f"sources/{repository.slug}/pulls/catalog.sqlite3"
    ensure_private_directory(repository.home, f"sources/{repository.slug}/pulls")
    write_private_file_atomic(repository.home, relative, b"")
    _provider(monkeypatch, [generated_item(1)])
    assert asyncio.run(refresh_pull_list(repository, "all")).cached["all"] == 1
    with sqlite3.connect(_path(repository)) as db:
        db.execute("PRAGMA user_version=999")
    before = _path(repository).read_bytes()
    with pytest.raises(PullDataError, match="clear the affected") as caught:
        asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert caught.value.state == "cache_unwritable"
    assert _path(repository).read_bytes() == before


def test_lock_waiter_cancellation_cannot_publish_later(repository: ListedRepository) -> None:
    state = _seed(repository, [generated_item(1)])
    entered, release = threading.Event(), threading.Event()

    def hold() -> None:
        with source_alias_lock(repository.home, repository.slug):
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=hold)
    thread.start()
    assert entered.wait(5)

    async def exercise() -> None:
        task = asyncio.create_task(
            run_lock_section(
                partial(publish_page, repository, state, state, (_row(generated_item(2))[0],))
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        thread.join(5)
    assert catalog_row(repository.home, repository.slug, 2) is None
    assert read_catalog(repository.home, repository.slug) == state


def test_rate_hold_and_failed_attempts_preserve_rows(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _seed(repository, [generated_item(1)])
    stamp = PullRefreshStamp(
        outcome="rate_limited",
        at=STAMP,
        reader=f"gh:{READER}",
        reset_at=utc_stamp(FETCHED_AT + timedelta(minutes=2)),
    )
    write_list_refresh(repository.home, repository.slug, "all", stamp)
    assert not refresh_wanted(ListView(repository, None, False), RefreshRequest("all", retry=True))
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(minutes=3))
    _provider(monkeypatch, [])

    async def refused(*args: Any, **kwargs: Any) -> Any:
        raise GhError("safe refusal", state="not_logged_in")

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", refused)
    with pytest.raises(PullDataError):
        asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert read_catalog(repository.home, repository.slug) == state
    assert read_list_refresh(repository.home, repository.slug, "all").outcome == "not_logged_in"  # type: ignore[union-attr]


def test_late_demand_joins_and_cancel_cleans_coordinator_state(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        coordinator = RefreshCoordinator(limit=1)
        entered, release = asyncio.Event(), asyncio.Event()
        observed: list[Any] = []

        async def held(*args: Any, **kwargs: Any) -> None:
            entered.set()
            await release.wait()
            observed.extend([kwargs["demand"](), kwargs["take_retry"](), kwargs["take_retry"]()])

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
        view = ListView(repository, coordinator, False)
        assert pull_list_route.start_refresh(view, RefreshRequest("open"), wanted=True) == "started"
        await entered.wait()
        assert (
            pull_list_route.start_refresh(view, RefreshRequest("closed", 1500, True), wanted=True)
            == "joined"
        )
        assert (
            pull_list_route.start_refresh(view, refresh_request({"background": True}), wanted=True)
            == "joined"
        )
        reconnect = refresh_request({"reconnect": True, "target": 900})
        assert pull_list_route.start_refresh(view, reconnect, wanted="reconnect") == "joined"
        release.set()
        await coordinator.drain(timeout_s=2)
        assert observed == [("closed", 1500), True, False]
        await coordinator.aclose()
        assert not pull_list_route._DEMANDS  # pyright: ignore[reportPrivateUsage]

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "params",
    [{"limit": "1001"}, {"limit": "-1"}, {"after": "0"}, {"after": "01"}, {"state": "merged"}],
)
def test_invalid_window_is_refused(params: dict[str, str]) -> None:
    with pytest.raises(ListRequestError):
        list_window(params)


@pytest.mark.parametrize(
    "body",
    [
        {"more": True},
        {"target": True},
        {"target": 0},
        {"retry": 1},
        {"background": 1},
        {"reconnect": 1},
        {"reconnect": True, "retry": True},
        {"state": "merged"},
    ],
)
def test_invalid_refresh_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(ListRequestError):
        refresh_request(body)


@pytest.mark.parametrize("query", ["", "  ", "a" * 257])
def test_invalid_search_query_is_refused(query: str) -> None:
    with pytest.raises(ListRequestError):
        search_query(query)


def test_default_open_and_unbounded_display_target() -> None:
    assert list_window({}) == ListWindow("open")
    assert refresh_request({"target": 5000}) == RefreshRequest("open", 5000)


def _answers(pages: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"auth": account(), "api": pages, "api_failure": None, **changes}


def _answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answers: dict[str, Any]) -> None:
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)


def _asked(tmp_path: Path) -> list[list[str]]:
    log = tmp_path / "fake-gh-log.jsonl"
    if not log.exists():
        return []
    calls = [json.loads(line)["args"] for line in log.read_text(encoding="utf-8").splitlines()]
    log.unlink()
    return calls


def _api_paths(calls: list[list[str]]) -> list[str]:
    return [call[-1] for call in calls if call[0] == "api"]


def _read_second_page(cap_bytes: int, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.GH_API_MAX_BYTES", cap_bytes)
    return asyncio.run(
        read_list(
            "repos/octo/demo/pulls",
            key=None,
            cap=100,
            etag='W/"page-two"',
            now=lambda: FETCHED_AT,
            query="state=all&sort=created&direction=desc",
            first_page=2,
        )
    )


def _sized_path(size: int, number: int) -> str:
    query = f"state=all&sort=created&direction=desc&per_page={size}&page={number}"
    return f"repos/octo/demo/pulls?{query}"


def test_an_oversized_page_steps_down_inside_its_own_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A step-down that ran past the page would join the next page's rows to it twice."""

    big = {"body": "x" * 5000}
    small = {"number": 1}
    entries = {_sized_path(100, 2): ok(_sized_path(100, 2), [big] * 100)}
    # Page 2 at 50 a page is pages 3 and 4, which together end where page 2 ends.
    for number in (3, 4):
        path = _sized_path(50, number)
        entries[path] = ok(path, [small] * 50, next_link("repos/octo/demo/pulls", number))
    _answer(tmp_path, monkeypatch, _answers(entries))
    read = _read_second_page(4000, monkeypatch)
    assert len(read.items) == 100
    assert (read.more, read.left_out, read.etag) == (True, False, None)
    assert _api_paths(_asked(tmp_path)) == [
        _sized_path(100, 2),
        _sized_path(50, 3),
        _sized_path(50, 4),
    ]


def test_an_item_too_large_alone_ends_its_page_saying_more_may_follow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The last place on the page is the one with nothing to say what comes after it."""

    monkeypatch.setattr(gh_lists, "EXTRA_PAGE_REQUESTS", 30)
    big = {"body": "x" * 5000}
    small = {"number": 1}
    entries: dict[str, Any] = {}
    too_large = {(100, 2), (50, 4), (25, 8), (5, 40)}
    pieces = [(100, 2), (50, 3), (50, 4), (25, 7), (25, 8), *((5, n) for n in range(36, 41))]
    for size, number in pieces:
        path = _sized_path(size, number)
        items = [big] if (size, number) in too_large else [small] * size
        entries[path] = ok(path, items, next_link("repos/octo/demo/pulls", number))
    for number in range(196, 201):
        path = _sized_path(1, number)
        items = [big] if number == 200 else [small]
        entries[path] = ok(path, items, next_link("repos/octo/demo/pulls", number))
    _answer(tmp_path, monkeypatch, _answers(entries))
    read = _read_second_page(4000, monkeypatch)
    assert len(read.items) == 99
    assert (read.left_out, read.more, read.etag) == (True, True, None)


@pytest.mark.parametrize(
    ("stamp", "seconds", "due"),
    [
        (None, 0, True),
        ({"outcome": "succeeded"}, 60, False),
        ({"outcome": "succeeded"}, 61, True),
        ({"outcome": "network_error"}, 60, False),
        ({"outcome": "network_error"}, 61, True),
        # No reset time to wait for: a window, like any failure.
        ({"outcome": "rate_limited"}, 61, True),
        # A reset time holds it past the window, and no longer.
        ({"outcome": "rate_limited", "reset_at": "2026-09-17T13:00:00Z"}, 61, False),
        ({"outcome": "rate_limited", "reset_at": "2026-09-17T13:00:00Z"}, 3600, True),
        # A local-only success does not lift the independent network hold.
        ({"outcome": "succeeded", "reset_at": "2026-09-17T13:00:00Z"}, 61, False),
        ({"outcome": "succeeded", "reset_at": "2026-09-17T13:00:00Z"}, 3600, True),
        # A reset time inside the window does not shorten the window.
        ({"outcome": "rate_limited", "reset_at": "2026-09-17T12:00:10Z"}, 30, False),
    ],
)
def test_an_automatic_refresh_waits_a_window_and_for_a_reset(
    stamp: dict[str, Any] | None, seconds: int, due: bool
) -> None:
    kept = None if stamp is None else PullRefreshStamp(at="2026-09-17T12:00:00Z", **stamp)
    assert refresh_is_due(kept, now=FETCHED_AT + timedelta(seconds=seconds)) is due


def test_catalog_reconnect_retries_an_early_network_failure_only_once(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_list_refresh(
        repository.home, repository.slug, "all", PullRefreshStamp(outcome="network_error", at=STAMP)
    )
    now = 100.0
    attempts: list[bool] = []
    monkeypatch.setattr(pull_list_route, "monotonic", lambda: now)

    async def refresh(*args: Any, **kwargs: Any) -> None:
        attempts.append(kwargs["take_retry"]())

    monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", refresh)

    async def exercise() -> None:
        nonlocal now
        coordinator = RefreshCoordinator()
        view = ListView(repository, coordinator, False)
        ask = refresh_request({"reconnect": True})
        assert not refresh_wanted(view, RefreshRequest("open"))
        wanted = refresh_wanted(view, ask)
        assert wanted == "reconnect"
        assert pull_list_route.start_refresh(view, ask, wanted=wanted) == "started"
        await coordinator.drain(timeout_s=2)
        assert pull_list_route.start_refresh(view, ask, wanted=wanted) == "not_due"
        now += 60
        assert pull_list_route.start_refresh(view, ask, wanted=wanted) == "started"
        await coordinator.drain(timeout_s=2)
        await coordinator.aclose()

    asyncio.run(exercise())
    assert attempts == [True, True]


@pytest.mark.parametrize(
    "outcome", ["gh_missing", "not_logged_in", "not_found_or_private", "rate_limited"]
)
def test_catalog_reconnect_cannot_bypass_a_non_network_failure(
    repository: ListedRepository, outcome: str
) -> None:
    write_list_refresh(
        repository.home, repository.slug, "all", PullRefreshStamp(outcome=outcome, at=STAMP)
    )
    view = ListView(repository, None, False)
    assert refresh_wanted(view, refresh_request({"reconnect": True})) is False
    if outcome == "rate_limited":
        assert refresh_wanted(view, refresh_request({"retry": True})) is False


@pytest.mark.parametrize("status", [502, 503])
def test_catalog_server_outage_keeps_cached_rows_without_an_early_reconnect(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    items = [generated_item(1)]
    seeded = _seed(repository, items)
    _provider(monkeypatch, items)
    monkeypatch.setattr(pull_list_refresh, "gh_graphql", gh.gh_graphql)

    async def run(args: Any, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(
            args,
            1,
            f"HTTP/2.0 {status}\r\n\r\n".encode() + b'{"message":"private upstream detail"}',
            b"",
        )

    monkeypatch.setattr(gh, "_run", run)
    with pytest.raises(PullDataError) as failure:
        asyncio.run(refresh_pull_list(repository, "open", retry=True))
    assert failure.value.state == "github_unavailable"
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    assert stamp is not None and stamp.outcome == "github_unavailable"
    assert stamp.message == f"GitHub answered HTTP {status}"
    assert read_catalog(repository.home, repository.slug) == seeded
    view = ListView(repository, None, False)
    assert not refresh_wanted(view, refresh_request({"reconnect": True}))


def test_catalog_retries_back_off_when_github_omits_a_rate_reset(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = FETCHED_AT
    items = [generated_item(1)]
    _seed(repository, items)
    _provider(monkeypatch, items)
    monkeypatch.setattr(pull_list, "utc_now", lambda: now)

    async def limited(*args: Any, **kwargs: Any) -> Any:
        raise GhError("GitHub's API rate limit is exhausted", state="rate_limited")

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", limited)
    view = ListView(repository, None, False)
    for seconds in (60, 120):
        with pytest.raises(PullDataError) as failure:
            asyncio.run(refresh_pull_list(repository, "open", retry=True))
        assert failure.value.state == "rate_limited"
        until = now + timedelta(seconds=seconds)
        stamp = read_list_refresh(repository.home, repository.slug, "all")
        assert stamp is not None and stamp.reset_at == utc_stamp(until)
        assert not refresh_wanted(view, refresh_request({"retry": True}))
        assert not refresh_wanted(view, refresh_request({"reconnect": True}))
        now = until

    _provider(monkeypatch, items)
    assert refresh_wanted(view, refresh_request({"retry": True})) is True
    asyncio.run(refresh_pull_list(repository, "open", retry=True))
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    assert stamp is not None and stamp.outcome == "succeeded"


@pytest.mark.parametrize(
    ("errors", "state", "error_type"),
    [
        ([{"type": "RATE_LIMITED", "message": "rate limit exhausted"}], "rate_limited", GhError),
        (
            [{"type": "NOT_FOUND", "message": "secret repository name"}],
            "not_found_or_private",
            GhError,
        ),
        (
            [{"type": "FORBIDDEN", "message": "arbitrary private upstream detail"}],
            "not_found_or_private",
            GhError,
        ),
        ([{"message": "invalid cursor"}], "gh_failed", GhCursorError),
        (
            [
                {
                    "type": "INVALID_CURSOR_ARGUMENTS",
                    "message": "`YWJjZA==` does not appear to be a valid cursor.",
                }
            ],
            "gh_failed",
            GhCursorError,
        ),
        ([{"message": "arbitrary private upstream detail"}], "gh_failed", GhError),
    ],
)
def test_graphql_200_errors_never_publish_partial_data(
    monkeypatch: pytest.MonkeyPatch,
    errors: list[dict[str, str]],
    state: str,
    error_type: type[GhError],
) -> None:
    async def run(args: Any, **kwargs: Any) -> Any:
        payload = json.dumps({"data": {"must_not_escape": True}, "errors": errors}).encode()
        return subprocess.CompletedProcess(
            args, 0, b"HTTP/2.0 200 OK\r\nx-ratelimit-reset: 1789646400\r\n\r\n" + payload, b""
        )

    monkeypatch.setattr(gh, "_run", run)
    with pytest.raises(GhError) as caught:
        asyncio.run(gh.gh_graphql("query Fixed { viewer { login } }", {}, now=FETCHED_AT))
    assert type(caught.value) is error_type
    assert caught.value.state == state
    assert "secret" not in str(caught.value) and "private upstream" not in str(caught.value)


def test_graphql_variables_are_separate_literal_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    async def run(args: list[str], **kwargs: Any) -> Any:
        calls.append(args)
        return subprocess.CompletedProcess(
            args, 0, b'HTTP/2.0 200 OK\r\n\r\n{"data":{"ok":true}}', b""
        )

    monkeypatch.setattr(gh, "_run", run)
    assert asyncio.run(
        gh.gh_graphql(
            "query Fixed { viewer { login } }",
            {"owner": "--help", "cursor": "@private-file", "count": 100, "omit": None},
        )
    ) == {"ok": True}
    assert calls[0][-6:] == ["-f", "owner=--help", "-f", "cursor=@private-file", "-F", "count=100"]
    with pytest.raises(ValueError):
        asyncio.run(gh.gh_graphql("mutation Unsafe {}", {}))


def test_provider_account_change_and_malformed_rows_leave_checkpoint(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _seed(repository, [generated_item(7)])
    _provider(monkeypatch, [generated_item(2)])
    real = pull_list_refresh.gh_graphql

    async def wrong_account(*args: Any, **kwargs: Any) -> Any:
        answer = await real(*args, **kwargs)
        answer["viewer"]["login"] = "other"
        return answer

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", wrong_account)
    with pytest.raises(PullDataError) as caught:
        asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert caught.value.state == "account_changed"
    assert read_catalog(repository.home, repository.slug) == state

    async def wrong_row(*args: Any, **kwargs: Any) -> Any:
        answer = await real(*args, **kwargs)
        answer["repository"]["page"]["nodes"][0]["number"] = "not-a-number"
        return answer

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", wrong_row)
    with pytest.raises(PullDataError):
        asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert read_catalog(repository.home, repository.slug) == state


def test_catalog_response_keeps_its_reader_after_settings_change(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _provider(monkeypatch, [generated_item(7)])
    real = pull_list_refresh.gh_graphql
    configured_reader = READER
    checks = 0

    async def account_now() -> str:
        nonlocal checks
        checks += 1
        return configured_reader

    async def response_then_switch(*args: Any, **kwargs: Any) -> Any:
        nonlocal configured_reader
        answer = await real(*args, **kwargs)
        configured_reader = "other-reader"
        return answer

    monkeypatch.setattr(pull_list_refresh, "active_account", account_now)
    monkeypatch.setattr(pull_list_refresh, "gh_graphql", response_then_switch)
    result = asyncio.run(refresh_pull_list(repository, "all"))
    assert configured_reader == "other-reader" and checks == 1
    assert result.reader == f"gh:{READER}" and result.cached["all"] == 1
    assert catalog_row(repository.home, repository.slug, 7) is not None
    assert calls == ["graphql:all:start"]


def test_catalog_next_viewer_cannot_mix_rows_or_advance_the_checkpoint(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _provider(monkeypatch, [generated_item(n) for n in range(1, 202)])
    real = pull_list_refresh.gh_graphql

    async def switched_page(*args: Any, **kwargs: Any) -> Any:
        answer = await real(*args, **kwargs)
        if len(calls) == 2:
            answer["viewer"]["login"] = "other-reader"
        return answer

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", switched_page)
    with pytest.raises(PullDataError) as caught:
        asyncio.run(refresh_pull_list(repository, "all"))
    assert caught.value.state == "account_changed"
    kept = read_catalog(repository.home, repository.slug)
    assert kept is not None and kept.reader == f"gh:{READER}"
    assert kept.cached["all"] == 100 and kept.cursors["all"] == "all-100"
    assert catalog_row(repository.home, repository.slug, 201) is not None
    assert catalog_row(repository.home, repository.slug, 101) is None
    assert calls == ["graphql:all:start", "graphql:all:all-100"]


def test_catalog_stale_reader_response_cannot_replace_a_new_reader_checkpoint(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(repository, [generated_item(9)])
    calls = _provider(monkeypatch, [generated_item(7)])
    real = pull_list_refresh.gh_graphql
    replacement: CatalogState | None = None

    async def concurrent_reader(*args: Any, **kwargs: Any) -> Any:
        nonlocal replacement
        answer = await real(*args, **kwargs)
        if len(calls) == 1:
            replacement = await asyncio.to_thread(
                _seed, repository, [generated_item(20)], reader="other-reader"
            )
        else:
            answer["viewer"]["login"] = "other-reader"
        return answer

    monkeypatch.setattr(pull_list_refresh, "gh_graphql", concurrent_reader)
    with pytest.raises(PullDataError) as caught:
        asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert caught.value.state == "account_changed"
    assert replacement is not None
    assert read_catalog(repository.home, repository.slug) == replacement
    assert catalog_row(repository.home, repository.slug, 20) is not None
    assert catalog_row(repository.home, repository.slug, 7) is None
    assert calls == ["graphql:updated:start", "graphql:all:start"]


def test_network_slot_is_released_between_pages(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _provider(monkeypatch, [generated_item(n) for n in range(1, 201)])
    real = pull_list_refresh._read_page  # pyright: ignore[reportPrivateUsage]

    async def exercise() -> None:
        slot = asyncio.Semaphore(1)
        entered, next_read = asyncio.Event(), asyncio.Event()
        order: list[str] = []

        async def held(*args: Any, **kwargs: Any) -> Any:
            order.append(str(args[2]))
            if args[2] is None:
                entered.set()
                await next_read.wait()
            return await real(*args, **kwargs)

        monkeypatch.setattr(pull_list_refresh, "_read_page", held)
        task = asyncio.create_task(refresh_pull_list(repository, "all", slot=slot))
        await entered.wait()

        async def foreground() -> None:
            async with slot:
                order.append("foreground")

        foreground_task = asyncio.create_task(foreground())
        await asyncio.sleep(0)
        next_read.set()
        await asyncio.gather(task, foreground_task)
        assert order == ["None", "foreground", "all-100"]

    asyncio.run(exercise())


def test_page_publication_cas_and_counts_do_not_walk_the_catalog(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _seed(repository, [generated_item(n) for n in range(1, 2001)], complete=False)
    queries: list[str] = []
    original = sqlite3.connect

    def traced(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        db = original(*args, **kwargs)
        db.set_trace_callback(queries.append)
        return db

    monkeypatch.setattr(sqlite3, "connect", traced)
    assert publish_page(repository, state, state, (_row(generated_item(2001))[0],))
    assert not publish_page(repository, state, state, (_row(generated_item(2002))[0],))
    current = read_catalog(repository.home, repository.slug)
    assert current is not None and current.cached["all"] == 2001
    assert publish_page(repository, current, current, (_row(generated_item(2002))[0],))
    assert not any("COUNT(" in query.upper() for query in queries)
    with original(_path(repository)) as db:
        plans = db.execute(
            "EXPLAIN QUERY PLAN SELECT body FROM pulls WHERE state=? AND number<? ORDER BY number DESC LIMIT 100",
            ("open", 1000),
        ).fetchall()
    assert any("SEARCH pulls USING INDEX pulls_state_number" in plan[3] for plan in plans)


def test_hostile_bounded_rows_round_trip_without_dropped_rows(repository: ListedRepository) -> None:
    items = [
        generated_item(n) | {"title": "\x00" * 3000, "labels": [{"name": "\x00" * 100}] * 100}
        for n in range(1, 101)
    ]
    state = _seed(repository, items)
    loaded, rows, _ = catalog_window(repository.home, repository.slug, "all", limit=100)
    assert loaded == state and len(rows) == 100
    assert all(len(json.dumps(row).encode()) < 32 * 1024 for row in rows)


def test_closed_includes_merged_and_duplicate_pages_do_not_inflate_cached(
    repository: ListedRepository,
) -> None:
    item = generated_item(1) | {"state": "closed", "merged_at": STAMP, "closed_at": STAMP}
    state = _seed(repository, [item])
    assert publish_page(repository, state, state, (_row(item)[0], _row(item)[0]))
    loaded, rows, _ = catalog_window(repository.home, repository.slug, "closed", limit=100)
    assert loaded is not None and loaded.cached == {"all": 1, "open": 0, "closed": 1}
    assert rows[0]["merged"] is True


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
@pytest.mark.parametrize("kind", ["shared", "symlink"])
def test_catalog_sidecars_follow_private_path_admission(
    repository: ListedRepository, tmp_path: Path, suffix: str, kind: str
) -> None:
    _seed(repository, [generated_item(1)])
    side = Path(str(_path(repository)) + suffix)
    if kind == "shared":
        side.write_bytes(b"untrusted")
        side.chmod(0o644)
    else:
        other = tmp_path / "other"
        other.write_bytes(b"untrusted")
        other.chmod(0o600)
        side.symlink_to(other)
    before = _fingerprint(repository.home)
    assert catalog_window(repository.home, repository.slug, "all", limit=100) == (None, [], None)
    assert _fingerprint(repository.home) == before


def test_missing_source_is_not_created_by_catalog_publication(repository: ListedRepository) -> None:
    missing = ListedRepository(repository.home, "missing-source", "octo", "demo")
    state = CatalogState(
        source=missing.source,
        repository_id="R_demo",
        reader=f"gh:{READER}",
        fetched_at=STAMP,
        count_at=STAMP,
    )
    with pytest.raises(FileNotFoundError):
        publish_page(missing, None, state, ())
    assert not (repository.home / "sources/missing-source").exists()


def test_cancelled_job_releases_demand_ownership(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        entered = asyncio.Event()
        coordinator = RefreshCoordinator(limit=1)

        async def held(*args: Any, **kwargs: Any) -> None:
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
        pull_list_route.start_refresh(
            ListView(repository, coordinator, False), RefreshRequest("open"), wanted=True
        )
        await entered.wait()
        await coordinator.aclose()
        assert not pull_list_route._DEMANDS  # pyright: ignore[reportPrivateUsage]

    asyncio.run(exercise())


def test_two_coordinators_have_independent_demand_ownership(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        coordinators = [RefreshCoordinator(limit=1), RefreshCoordinator(limit=1)]
        release = asyncio.Event()
        entered = 0
        all_entered = asyncio.Event()
        observed: list[Any] = []

        async def held(*args: Any, **kwargs: Any) -> None:
            nonlocal entered
            entered += 1
            if entered == 2:
                all_entered.set()
            await release.wait()
            observed.append(kwargs["demand"]())

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
        for coord, name in zip(coordinators, ("open", "closed"), strict=True):
            pull_list_route.start_refresh(
                ListView(repository, coord, False), RefreshRequest(name), wanted=True
            )
        await all_entered.wait()
        release.set()
        await asyncio.gather(*(coord.drain(timeout_s=2) for coord in coordinators))
        assert set(observed) == {("open", 500), ("closed", 500)}
        await asyncio.gather(*(coord.aclose() for coord in coordinators))
        assert not pull_list_route._DEMANDS  # pyright: ignore[reportPrivateUsage]

    asyncio.run(exercise())


def test_overlapping_worker_keeps_rate_hold_and_stops_before_next_page(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _provider(monkeypatch, [generated_item(n) for n in range(1, 251)])
    real = pull_list_refresh._read_page  # pyright: ignore[reportPrivateUsage]
    reset = utc_stamp(FETCHED_AT + timedelta(minutes=2))

    async def exercise() -> None:
        entered, release = asyncio.Event(), asyncio.Event()

        async def provider(*args: Any, **kwargs: Any) -> Any:
            task = asyncio.current_task()
            if task is not None and task.get_name() == "limited-worker":
                raise PullDataError("rate_limited", "provider hold", reset_at=reset)
            if args[2] is None:
                entered.set()
                await release.wait()
            return await real(*args, **kwargs)

        monkeypatch.setattr(pull_list_refresh, "_read_page", provider)
        first = asyncio.create_task(refresh_pull_list(repository, "all"))
        await entered.wait()
        other = asyncio.create_task(refresh_pull_list(repository, "all"), name="limited-worker")
        with pytest.raises(PullDataError):
            await other
        release.set()
        with pytest.raises(PullDataError) as caught:
            await first
        assert caught.value.state == "rate_limited"

    asyncio.run(exercise())
    stamp = read_list_refresh(repository.home, repository.slug, "all")
    assert stamp is not None and stamp.reset_at == reset
    state = read_catalog(repository.home, repository.slug)
    assert state is not None and state.cached["all"] == 100
    assert calls == ["graphql:all:start"]


def test_repository_reset_reports_known_provider_total_between_pages(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _seed(repository, [generated_item(n) for n in range(1, 201)], complete=False)
    resumed = old.model_copy(update={"cursors": {"all": "all-100", "open": None, "closed": None}})
    assert publish_page(repository, old, resumed, ())
    _provider(monkeypatch, [generated_item(n) for n in range(1, 18)], repository_id="R_replaced")
    real = pull_list_refresh._read_page  # pyright: ignore[reportPrivateUsage]
    observed: list[Any] = []

    async def provider(*args: Any, **kwargs: Any) -> Any:
        if args[2] == "all-100":
            return await real(args[0], args[1], None, **kwargs)
        envelope = pull_list_envelope(ListView(repository, None, True), ListWindow("all"))
        observed.append(
            (envelope["total"], envelope["repository_total"], envelope["catalog_fetched"])
        )
        return await real(*args, **kwargs)

    monkeypatch.setattr(pull_list_refresh, "_read_page", provider)
    assert asyncio.run(refresh_pull_list(repository, "all")).cached["all"] == 17
    assert observed == [(17, 17, 0)]


@pytest.mark.parametrize("outcome", ["succeeded", "network_error"])
def test_outcome_writer_cannot_erase_another_workers_hold(
    repository: ListedRepository, outcome: Any
) -> None:
    hold = PullRefreshStamp(
        outcome="rate_limited", at=STAMP, reset_at=utc_stamp(FETCHED_AT + timedelta(minutes=2))
    )
    write_list_refresh(repository.home, repository.slug, "all", hold)
    write_list_refresh(
        repository.home, repository.slug, "all", PullRefreshStamp(outcome=outcome, at=STAMP)
    )
    assert read_list_refresh(repository.home, repository.slug, "all") == hold


def test_cancelled_stamp_waiter_cannot_publish_after_lock_release(
    repository: ListedRepository,
) -> None:
    entered, release = threading.Event(), threading.Event()

    def hold() -> None:
        with source_alias_lock(repository.home, repository.slug):
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=hold)
    thread.start()
    assert entered.wait(5)

    async def exercise() -> None:
        stamp = PullRefreshStamp(outcome="succeeded", at=STAMP)
        task = asyncio.create_task(
            run_lock_section(
                partial(write_list_refresh, repository.home, repository.slug, "all", stamp)
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        thread.join(5)
    assert read_list_refresh(repository.home, repository.slug, "all") is None


@pytest.mark.parametrize(
    "alter",
    [
        "CREATE TRIGGER unexpected AFTER INSERT ON pulls BEGIN DELETE FROM pulls WHERE number <> NEW.number; END",
        "DROP INDEX pulls_state_number",
        "CREATE VIEW unexpected AS SELECT number FROM pulls",
        "CREATE TABLE unexpected(value TEXT)",
    ],
)
def test_incompatible_sqlite_schema_is_refused_before_reads_or_writes(
    repository: ListedRepository, alter: str
) -> None:
    state = _seed(repository, [generated_item(1)])
    path = _path(repository)
    with sqlite3.connect(path) as db:
        db.execute(alter)
    before = _fingerprint(repository.home)
    assert catalog_window(repository.home, repository.slug, "all", limit=100) == (None, [], None)
    with pytest.raises(ValueError, match="unsupported catalog schema"):
        publish_page(repository, state, state, (_row(generated_item(2))[0],))
    assert _fingerprint(repository.home) == before


@pytest.mark.parametrize("owner", ["OcTo", "someone"])
def test_fake_graphql_respects_repository_identity(
    repository: ListedRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner: str
) -> None:
    answers = {"auth": account(), "api": catalog_entries([generated_item(1)]), "api_failure": None}
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)
    selected = ListedRepository(repository.home, repository.slug, owner, "DeMo")
    request = pull_list_refresh._read_page(selected, "all", None, login=READER)  # pyright: ignore[reportPrivateUsage]
    if owner == "OcTo":
        assert asyncio.run(request).totals["all"] == 1
    else:
        with pytest.raises(PullDataError) as caught:
            asyncio.run(request)
        assert caught.value.state == "not_found_or_private"


def test_old_projection_enriches_once_and_resumes_without_losing_offline_rows(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(n) for n in range(1, 251)]
    _seed(repository, items)
    # An actual pre-avatar cache has neither the checkpoint field nor the row field.
    with sqlite3.connect(_path(repository)) as db:
        checkpoint = json.loads(db.execute("SELECT value FROM checkpoint").fetchone()[0])
        del checkpoint["projection_version"]
        checkpoint["cursors"]["all"] = "all-250"
        checkpoint["cursors"]["open"] = "open-200"
        checkpoint["covered"]["open"] = 200
        db.execute("UPDATE checkpoint SET value=?", (json.dumps(checkpoint),))
        for number, body in db.execute("SELECT number,body FROM pulls").fetchall():
            value = json.loads(body)
            del value["author_avatar_url"]
            db.execute("UPDATE pulls SET body=? WHERE number=?", (json.dumps(value), number))
    old = read_catalog(repository.home, repository.slug)
    assert old is not None and old.projection_version == 0 and old.done["all"]
    write_list_refresh(
        repository.home,
        repository.slug,
        "all",
        PullRefreshStamp(
            outcome="succeeded",
            at=STAMP,
            reader=old.reader,
        ),
    )
    for item in items:
        item["user"]["avatar_url"] = "https://avatars.githubusercontent.com/u/123?v=4"
    calls = _provider(monkeypatch, items)
    before = _fingerprint(repository.home)
    view = ListView(repository, None, False)
    envelope = pull_list_envelope(view, ListWindow("all"))
    assert envelope["complete"] and envelope["catalog_fetched"] == 250
    assert envelope["rows"][0]["author_avatar_url"] is None
    assert not refresh_wanted(view, RefreshRequest("all", 500))
    assert calls == [] and _fingerprint(repository.home) == before
    real = pull_list_refresh._read_page

    async def interrupt() -> None:
        paused = asyncio.Event()

        async def held(*args: Any, **kwargs: Any) -> Any:
            if args[2] == "all-100":
                paused.set()
                await asyncio.Event().wait()
            return await real(*args, **kwargs)

        monkeypatch.setattr(pull_list_refresh, "_read_page", held)
        task = asyncio.create_task(refresh_pull_list(repository, "all", retry=True))
        await paused.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(interrupt())
    partial = read_catalog(repository.home, repository.slug)
    assert partial is not None and partial.projection_version == CATALOG_PROJECTION
    assert not partial.done["all"] and partial.cursors["all"] == "all-100"
    assert partial.cached == old.cached and partial.totals == old.totals
    assert partial.epoch == old.epoch and partial.watermark == old.watermark
    assert partial.cursors["open"] == old.cursors["open"]
    assert partial.covered["open"] == old.covered["open"]
    assert partial.fetched_at == old.fetched_at
    envelope = pull_list_envelope(view, ListWindow("all"))
    assert not envelope["complete"] and envelope["catalog_fetched"] == 250
    assert (
        envelope["rows"][0]["author_avatar_url"]
        == "https://avatars.githubusercontent.com/u/123?s=40"
    )
    oldest = catalog_row(repository.home, repository.slug, 1)
    assert oldest is not None and oldest.author_avatar_url is None
    monkeypatch.setattr(pull_list_refresh, "_read_page", real)
    calls.clear()
    final = asyncio.run(refresh_pull_list(repository, "all"))
    assert calls == ["graphql:all:all-100", "graphql:all:all-200"]
    assert final.done["all"] and final.cached == old.cached
    oldest = catalog_row(repository.home, repository.slug, 1)
    assert oldest is not None and oldest.author_avatar_url is not None
    calls.clear()
    asyncio.run(refresh_pull_list(repository, "all", retry=True))
    assert calls == ["graphql:updated:start"]


def test_projection_reset_loser_keeps_the_winners_resume_cursor(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [generated_item(n) for n in range(1, 151)]
    old = _seed(repository, items)
    assert publish_page(repository, old, old.model_copy(update={"projection_version": 0}), ())
    calls = _provider(monkeypatch, items)
    real = pull_list_refresh._publish
    attempted = False

    async def competing(
        repo: ListedRepository,
        previous: CatalogState | None,
        proposed: CatalogState,
        rows: tuple[pull_list.PullListRow, ...],
    ) -> bool:
        nonlocal attempted
        if not attempted and previous is not None and previous.projection_version == 0:
            attempted = True
            winner = proposed.model_copy(
                update={
                    "cursors": {**proposed.cursors, "all": "all-100"},
                    "covered": {**proposed.covered, "all": 100},
                }
            )
            assert await real(repo, previous, winner, ())
        return await real(repo, previous, proposed, rows)

    monkeypatch.setattr(pull_list_refresh, "_publish", competing)
    final = asyncio.run(refresh_pull_list(repository, "all"))
    assert attempted and calls == ["graphql:all:all-100"]
    assert final.done["all"] and final.cached == old.cached and final.epoch == old.epoch


def test_projection_reset_preserves_an_active_delta_checkpoint_before_network(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _seed(repository, [generated_item(7)])
    proposed = old.model_copy(
        update={
            "projection_version": 0,
            "delta_started": True,
            "delta_cursor": "updated-100",
            "delta_watermark": STAMP,
        }
    )
    assert publish_page(repository, old, proposed, ())
    old = read_catalog(repository.home, repository.slug)
    assert old is not None
    calls = _provider(monkeypatch, [generated_item(7)])

    async def exercise() -> None:
        entered = asyncio.Event()

        async def held(*args: Any, **kwargs: Any) -> Any:
            assert args[2] == "updated-100" and kwargs["updated"]
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(pull_list_refresh, "_read_page", held)
        task = asyncio.create_task(refresh_pull_list(repository, "all"))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    current = read_catalog(repository.home, repository.slug)
    assert current is not None and current.projection_version == CATALOG_PROJECTION
    for key in (
        "reader",
        "source",
        "repository_id",
        "epoch",
        "fetched_at",
        "count_at",
        "watermark",
        "delta_cursor",
        "delta_watermark",
        "delta_started",
        "cached",
        "totals",
    ):
        assert getattr(current, key) == getattr(old, key), key
    assert not current.done["all"] and calls == []
