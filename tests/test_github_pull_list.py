"""What the transcripts of the list routes cannot show.

``tests/test_cli_github_pulls_golden.py`` and ``tests/golden/cli-github-pulls.tryscript.md``
pin what the routes answer. These add the evidence a transcript has no way to give: that
listing runs no Git and needs no store, what never reaches a written file, that every list
written can be read back, how a page is read past an oversized item, and what happens
while a job is running. Each says why it is here.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import (
    gh_lists,
    pull_list,
    pull_list_refresh,
    pull_list_route,
)
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, read_list
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_LIST_PAGES,
    MAX_LIST_ROWS,
    MAX_PULL_LIST_BYTES,
    PULL_LIST_SCHEMA,
    ListedRepository,
    ListPageMark,
    PullList,
    PullListRow,
    read_list_refresh,
    read_pull_list,
    refresh_is_due,
    serialize_pull_list,
    write_list_refresh,
    write_pull_list,
)
from metabrowser.builtin_plugins.github.pull_list_refresh import refresh_pull_list
from metabrowser.builtin_plugins.github.pull_list_route import (
    ListRequestError,
    list_window,
    listed_repository,
    refresh_request,
)
from metabrowser.builtin_plugins.github.pull_record import MAX_LABELS, PullRefreshStamp
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.paths import source_pull_list
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource
from metabrowser.cli import api_cli
from metabrowser.cli.asgi_client import ApiResponse
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.server import app
from metabrowser.source_routes import PIN_HEADER
from tests.cache_home_fixture import (
    FixtureSource,
    _stage_and_publish_source,  # pyright: ignore[reportPrivateUsage]
    build_empty_home,
)
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    READER,
    Origin,
    account,
    generated_item,
    install_fake_gh,
    list_page,
    next_link,
    ok,
    scenario,
)
from tests.golden_harness import run_metab, serve_published
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

PULLS = "/api/plugin/github/pulls"
REFRESH = "/api/plugin/github/pulls-refresh"
_JSON = {"content-type": "application/json"}
SOURCE = FixtureSource("https", CANONICAL)
_SECRET = "ghp_exampleSecretTokenValue0123456789"


def _answers(pages: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"auth": account(), "api": pages, "api_failure": None, **changes}


def _page(number: int, items: list[dict[str, Any]], *, more: bool = False) -> dict[str, Any]:
    path = list_page("all", number)
    return {path: ok(path, items, next_link("repos/octo/demo/pulls", number) if more else None)}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An application home with one source directory, published with no store."""

    path = tmp_path / "home"
    build_empty_home(path)
    _stage_and_publish_source(path, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    return path


@pytest.fixture
def repository(home: Path) -> ListedRepository:
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


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


# ── No Git, no store ───────────────────────────────────────────


def test_listing_succeeds_for_a_source_directory_with_no_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """The independent evidence that listing touches no Git.

    There is no store to read and no ``git`` to run: one that fails and logs is first on
    ``PATH``, which a transcript over a mirror could not rule out. Listing takes only the
    home, the slug, and the names, so nothing here hands it a ``PublishedSource``.
    """

    bin_directory = tmp_path / "no-git"
    bin_directory.mkdir()
    git_log = tmp_path / "git-calls.log"
    git = bin_directory / "git"
    git.write_text(f'#!/bin/sh\necho "$*" >> {git_log}\nexit 1\n', encoding="utf-8")
    git.chmod(0o755)
    _answer(tmp_path, monkeypatch, _answers(_page(1, [generated_item(2), generated_item(1)])))
    monkeypatch.setenv("PATH", f"{bin_directory}{os.pathsep}{os.environ['PATH']}")

    listed = asyncio.run(refresh_pull_list(repository, "all"))

    assert [row.number for row in listed.rows] == [2, 1]
    assert not git_log.exists()
    assert not list((home / "repository-stores").iterdir())
    assert read_pull_list(home, SOURCE.slug, "all") == listed
    stamp = read_list_refresh(home, SOURCE.slug, "all")
    assert stamp is not None and stamp.outcome == "succeeded"

    # The source directory is still what the cache calls it, with the list beside it.
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    cached = run_metab([str(root), "--api", f"/api/cache/source/{SOURCE.slug}"])
    assert cached.exit_code == 0, cached.stderr
    row = cached.payload()["source"] if "source" in cached.payload() else cached.payload()
    assert row["publication"] == "unattached"


# ── What a written file holds ───────────────────────────────────


def test_no_written_file_carries_a_credential_or_a_dropped_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """Written files are not in any transcript, and neither is what gh printed for itself.

    The token is everywhere a careless job could copy it from: gh's environment, what
    ``gh auth status`` answers, a response header, and gh's standard error on a failure.
    """

    monkeypatch.setenv("GH_TOKEN", _SECRET)
    item = {**generated_item(1), "body": "a description only GitHub keeps"}
    path = list_page("all")
    answers = _answers({path: ok(path, [item], {"X-Oauth-Scopes": _SECRET})})
    answers["auth"] = {
        "stdout": account()["stdout"].replace('"keyring"', json.dumps(_SECRET)),
        "exit": 0,
    }
    _answer(tmp_path, monkeypatch, answers)
    asyncio.run(refresh_pull_list(repository, "all"))
    failing = {**answers, "api_failure": {"stderr": f"Authorization: {_SECRET}\n", "exit": 1}}
    _answer(tmp_path, monkeypatch, failing)
    with pytest.raises(PullDataError):
        asyncio.run(refresh_pull_list(repository, "all"))

    written = [entry for entry in (home / "sources").rglob("*") if entry.is_file()]
    assert {entry.name for entry in written} >= {"list-all.json", "list-all.refresh.json"}
    for entry in written:
        text = entry.read_text(encoding="utf-8")
        assert _SECRET not in text, entry.name
    listed = (home / source_pull_list(SOURCE.slug, "all")).read_text(encoding="utf-8")
    assert "a description only GitHub keeps" not in listed
    assert "api.github.com" not in listed and "2700AF" not in listed and "_links" not in listed


def test_a_failed_refresh_leaves_the_file_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """A transcript shows the same rows; only this compares the bytes and the inode."""

    answers = _answers(_page(1, [generated_item(1)]))
    _answer(tmp_path, monkeypatch, answers)
    asyncio.run(refresh_pull_list(repository, "all"))
    target = home / source_pull_list(SOURCE.slug, "all")
    before, inode = target.read_bytes(), target.stat().st_ino
    failing = {**answers, "api_failure": {"stderr": "dial tcp: i/o timeout\n", "exit": 1}}
    _answer(tmp_path, monkeypatch, failing)
    with pytest.raises(PullDataError) as failed:
        asyncio.run(refresh_pull_list(repository, "all"))
    assert failed.value.state == "network_error"
    assert (target.read_bytes(), target.stat().st_ino) == (before, inode)


# ── Bounds ──────────────────────────────────────────────────────


def _hostile_item(number: int) -> dict[str, Any]:
    """Every field at its longest, in the characters that cost the most to write."""

    control = "\x01" * 10_000
    labels = [{"name": control} for _label in range(MAX_LABELS + 20)]
    side = {"ref": control, "repo": {"full_name": control}}
    return {
        **generated_item(number),
        "title": control,
        "labels": labels,
        "head": side,
        "base": side,
        "user": {"login": "a" * 100},
    }


def test_a_list_of_the_worst_rows_the_bounds_allow_can_be_read_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """The read bound holds at the cap, for rows no real repository has.

    A real page is a few hundred bytes a row, so no transcript comes near it. Escaping
    counts: a control character costs six bytes written.
    """

    rows = pull_list_refresh._rows([_hostile_item(1)])  # pyright: ignore[reportPrivateUsage]
    assert rows[1] is True
    row = rows[0][0]
    worst = PullList(
        schema_version=PULL_LIST_SCHEMA,
        source=repository.source,
        list="all",
        fetched_at="2026-09-17T12:00:00Z",
        reader=f"gh:{READER}",
        pages=MAX_LIST_PAGES,
        complete=False,
        truncated=True,
        etags=tuple(
            ListPageMark(
                etag='W/"' + "e" * 290 + '"',
                numbers=tuple(
                    range(9_999_999_999 - page * 100, 9_999_999_999 - page * 100 - 100, -1)
                ),
                truncated=True,
            )
            for page in range(MAX_LIST_PAGES)
        ),
        rows=tuple(
            row.model_copy(update={"number": 9_999_999_999 - index})
            for index in range(MAX_LIST_ROWS)
        ),
    )
    data = serialize_pull_list(worst)
    assert len(data) <= MAX_PULL_LIST_BYTES
    write_pull_list(home, SOURCE.slug, worst)
    assert read_pull_list(home, SOURCE.slug, "all") == worst


def test_a_row_past_its_bounds_is_cut_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    long_title = {**generated_item(3), "title": "x" * 5000}
    many_labels = {
        **generated_item(2),
        "labels": [{"name": f"label-{index}"} for index in range(MAX_LABELS + 1)],
    }
    fine = generated_item(1)
    _answer(tmp_path, monkeypatch, _answers(_page(1, [long_title, many_labels, fine])))
    listed = asyncio.run(refresh_pull_list(repository, "all"))
    title_row, labels_row, _fine_row = listed.rows
    assert len(title_row.title) == pull_list.MAX_ROW_TITLE_BYTES
    assert len(labels_row.labels) == MAX_LABELS
    assert listed.truncated and listed.complete
    assert listed.etags[0].truncated


@pytest.mark.parametrize(
    "broken",
    [
        {"number": "seven"},
        {"state": "reopened"},
        {"created_at": "yesterday"},
        {"head": None},
        {"base": {"ref": None}},
    ],
)
def test_an_item_that_cannot_be_read_is_left_out_and_said(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    broken: dict[str, Any],
) -> None:
    items = [{**generated_item(2), **broken}, generated_item(1)]
    _answer(tmp_path, monkeypatch, _answers(_page(1, items)))
    listed = asyncio.run(refresh_pull_list(repository, "all"))
    assert [row.number for row in listed.rows] == [1]
    assert listed.truncated


def test_every_list_a_file_can_hold_is_one_listing() -> None:
    """A list that fails these reads as ``unreadable`` and the next refresh replaces it."""

    row = PullListRow.model_validate(
        {
            "number": 2,
            "title": "t",
            "state": "open",
            "draft": False,
            "merged_at": None,
            "author": None,
            "created_at": "2026-09-17T12:00:00Z",
            "updated_at": "2026-09-17T12:00:00Z",
            "closed_at": None,
            "base_ref": "b",
            "head_ref": "h",
            "head_repository": None,
            "labels": [],
        }
    )
    fields: dict[str, Any] = {
        "schema_version": PULL_LIST_SCHEMA,
        "source": CANONICAL,
        "list": "all",
        "fetched_at": "2026-09-17T12:00:00Z",
        "reader": "gh:octo",
        "pages": 1,
        "complete": True,
        "truncated": False,
        "etags": (ListPageMark(etag=None, numbers=(2,), truncated=False),),
        "rows": (row,),
    }
    PullList.model_validate(fields)
    for changes in (
        {"rows": (row, row)},
        {"rows": (row.model_copy(update={"number": 1}), row)},
        {"pages": 2},
        {"etags": (ListPageMark(etag=None, numbers=(9,), truncated=False),)},
        {"list": "merged"},
        {"reader": "someone"},
    ):
        with pytest.raises(ValueError):
            PullList.model_validate({**fields, **changes})


@pytest.mark.parametrize(
    ("content", "absence"),
    [
        (b"{not json", "unreadable"),
        (b'{"schema_version": 999}', "schema_mismatch"),
        (json.dumps({"schema_version": PULL_LIST_SCHEMA}).encode(), "unreadable"),
    ],
)
def test_a_damaged_or_older_file_is_no_list(
    home: Path, content: bytes, absence: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.home import ensure_private_directory, write_private_file_atomic

    ensure_private_directory(home, f"sources/{SOURCE.slug}/pulls")
    write_private_file_atomic(home, source_pull_list(SOURCE.slug, "all"), content)
    assert read_pull_list(home, SOURCE.slug, "all") == absence


def test_a_file_past_the_read_bound_or_for_another_list_is_no_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    _answer(tmp_path, monkeypatch, _answers(_page(1, [generated_item(1)])))
    listed = asyncio.run(refresh_pull_list(repository, "all"))
    target = home / source_pull_list(SOURCE.slug, "open")
    target.write_bytes(serialize_pull_list(listed))
    target.chmod(0o600)
    assert read_pull_list(home, SOURCE.slug, "open") == "unreadable"
    monkeypatch.setattr(pull_list, "MAX_PULL_LIST_BYTES", 16)
    assert read_pull_list(home, SOURCE.slug, "all") == "unreadable"


def test_a_list_stops_growing_at_its_cap_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    """Load more ten times over, past the cap: too many pages for a transcript to print."""

    pages: dict[str, Any] = {}
    number = MAX_LIST_ROWS + 100
    for page_number in range(1, MAX_LIST_PAGES + 1):
        items = [generated_item(number - index) for index in range(100)]
        number -= 100
        pages |= _page(page_number, items, more=True)
    _answer(tmp_path, monkeypatch, _answers(pages))
    listed = asyncio.run(refresh_pull_list(repository, "all", more=True))
    for _extension in range(MAX_LIST_PAGES - 1):
        listed = asyncio.run(refresh_pull_list(repository, "all", more=True))
    assert (listed.pages, len(listed.rows), listed.complete) == (MAX_LIST_PAGES, 1000, False)
    _asked(tmp_path)

    # Asking again rereads what is held, and never page 11.
    again = asyncio.run(refresh_pull_list(repository, "all", more=True))
    paths = _api_paths(_asked(tmp_path))
    assert paths == [list_page("all", number) for number in range(1, MAX_LIST_PAGES + 1)]
    assert again.rows == listed.rows


# ── One page of a list ─────────────────────────────────────────


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


def test_a_page_read_in_pieces_has_no_etag_and_is_asked_in_full_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    """Its mark says so, and a refresh does not send an ETag it never had."""

    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.GH_API_MAX_BYTES", 16_000)
    full, half = _sized_path(100, 1), _sized_path(50, 1)
    too_large = [generated_item(number) for number in range(30, 0, -1)]
    entries = {full: ok(full, too_large), half: ok(half, [generated_item(1)])}
    _answer(tmp_path, monkeypatch, _answers(entries))
    listed = asyncio.run(refresh_pull_list(repository, "all"))
    assert listed.etags[0].etag is None
    _asked(tmp_path)
    asyncio.run(refresh_pull_list(repository, "all"))
    conditional = [
        call for call in _asked(tmp_path) if any(arg.startswith("If-None-Match") for arg in call)
    ]
    assert conditional == []


# ── When a refresh may start ───────────────────────────────────


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
        # A reset time inside the window does not shorten the window.
        ({"outcome": "rate_limited", "reset_at": "2026-09-17T12:00:10Z"}, 30, False),
    ],
)
def test_an_automatic_refresh_waits_a_window_and_for_a_reset(
    stamp: dict[str, Any] | None, seconds: int, due: bool
) -> None:
    kept = None if stamp is None else PullRefreshStamp(at="2026-09-17T12:00:00Z", **stamp)
    assert refresh_is_due(kept, now=FETCHED_AT + timedelta(seconds=seconds)) is due


def test_a_stamp_the_cache_will_not_take_is_kept_for_the_process(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without it an unwritable cache would ask gh on every poll, and report nothing."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("read-only")

    stamp = PullRefreshStamp(outcome="cache_unwritable", at="2026-09-17T12:00:00Z")
    monkeypatch.setattr(pull_list, "write_refresh_stamp", refuse)
    write_list_refresh(home, SOURCE.slug, "all", stamp)
    assert read_list_refresh(home, SOURCE.slug, "all") == stamp
    assert not refresh_is_due(read_list_refresh(home, SOURCE.slug, "all"), now=FETCHED_AT)
    monkeypatch.undo()
    written = PullRefreshStamp(outcome="succeeded", at="2026-09-17T12:00:00Z")
    write_list_refresh(home, SOURCE.slug, "all", written)
    assert read_list_refresh(home, SOURCE.slug, "all") == written


@pytest.mark.parametrize(
    "params",
    [
        {"state": "merged"},
        {"limit": "-1"},
        {"limit": "1001"},
        {"limit": "ten"},
        {"after": "0"},
        {"after": "1x"},
        {"after": "99999999999"},
    ],
)
def test_a_window_outside_its_bounds_is_refused(params: dict[str, str]) -> None:
    with pytest.raises(ListRequestError):
        list_window(params)


@pytest.mark.parametrize(
    "body",
    [{"state": "merged"}, {"more": "yes"}, {"retry": 1}, {"number": 7}, {"state": None}],
)
def test_a_refresh_request_outside_its_shape_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(ListRequestError):
        refresh_request(body)


def test_a_mirror_of_another_host_lists_nothing() -> None:
    """A transcript of this needs a mirror that is not GitHub's and a request; this is the rule."""

    def mirror(address: str) -> Any:
        source = GitSource(transport="https", form="url", normalized=address)
        served = StoreMirror(
            home=Path("/nonexistent"),
            store_key="0" * 64,
            store_id=f"sha256:{'0' * 64}",
            source=source,
            slug="demo-0000",
        )
        return SimpleNamespace(mirror=served)

    assert listed_repository(None) is None
    assert listed_repository(mirror("https://gitlab.example/octo/demo")) is None
    found = listed_repository(mirror(CANONICAL))
    assert found is not None and (found.owner, found.repo, found.slug) == (
        "octo",
        "demo",
        "demo-0000",
    )


def test_a_one_shot_command_follows_a_status_route_with_its_query() -> None:
    """Which list a refresh was of is in the route, so the query has to survive."""

    answered = ApiResponse(
        202, json.dumps({"status_route": f"{PULLS}?state=open&limit=0"}).encode()
    )
    follow = api_cli._follow_route(REFRESH, answered)  # pyright: ignore[reportPrivateUsage]
    assert follow == f"{PULLS}?state=open&limit=0"
    elsewhere = ApiResponse(202, json.dumps({"status_route": "https://e.x/"}).encode())
    assert api_cli._follow_route(REFRESH, elsewhere) is None  # pyright: ignore[reportPrivateUsage]


# ── The routes on a served mirror ──────────────────────────────


@pytest.fixture
def served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> Iterator[tuple[TestClient, PublishedSource]]:
    """A mirror of the repository, served as a one-shot command serves it."""

    cache = tmp_path / "served-home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(cache))
    _allow_installed_git(monkeypatch)
    local = pull_origin.url
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: local if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    _answer(tmp_path, monkeypatch, scenario(pull_origin))
    source = GitSource(transport="https", form="url", normalized=CANONICAL)
    published = asyncio.run(acquire_source(source, home=cache))
    serve_published(published)
    _asked(tmp_path)
    try:
        with TestClient(app) as client:
            yield client, published
    finally:
        serve_mirror(None)


def _settle(client: TestClient, state: str = "all") -> dict[str, Any]:
    for _attempt in range(2500):
        answer = client.get(f"{PULLS}?state={state}&limit=0").json()
        if not answer["refreshing"]:
            return answer
        threading.Event().wait(0.02)
    raise AssertionError("the refresh did not finish")


def _held_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[threading.Event, list[tuple[str, bool]]]:
    """Each job's first read waits for the event, and then runs against the fake ``gh``."""

    release = threading.Event()
    runs: list[tuple[str, bool]] = []
    real = pull_list_refresh.refresh_pull_list

    async def held(repository: ListedRepository, name: Any, *, more: bool = False) -> PullList:
        runs.append((name, more))
        await asyncio.to_thread(release.wait, 30)
        return await real(repository, name, more=more)

    monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
    return release, runs


def test_a_request_while_a_refresh_runs_joins_it(
    served: tuple[TestClient, PublishedSource], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A one-shot command ends each job before its next request, so it can never join."""

    client, _published = served
    release, runs = _held_refresh(monkeypatch)
    try:
        first = client.post(REFRESH, json={}, headers=_JSON)
        assert (first.status_code, first.headers["cache-control"]) == (202, "no-store")
        assert first.json()["refresh"] == "started"
        assert first.json()["pulls"]["state"] == "pending"
        again = client.post(REFRESH, json={"state": "all", "retry": True}, headers=_JSON)
        assert (again.status_code, again.json()["refresh"]) == (202, "joined")
        # Each list is its own job.
        other = client.post(REFRESH, json={"state": "open"}, headers=_JSON)
        assert other.json()["refresh"] == "started"
        assert client.get(f"{PULLS}?limit=0").json()["refreshing"] is True
    finally:
        release.set()
    _settle(client)
    _settle(client, "open")
    assert sorted(runs) == [("all", False), ("open", False)]


def test_a_more_that_joins_a_refresh_extends_the_list_after_it(
    served: tuple[TestClient, PublishedSource], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A reader's **Load more** during the list's automatic refresh is not lost.

    The whole of it is one job, so ``refreshing`` stays true until the page is in the list.
    """

    client, _published = served
    release, runs = _held_refresh(monkeypatch)
    try:
        assert client.post(REFRESH, json={}, headers=_JSON).json()["refresh"] == "started"
        joined = client.post(REFRESH, json={"more": True}, headers=_JSON)
        assert (joined.status_code, joined.json()["refresh"]) == (202, "joined")
        assert client.get(f"{PULLS}?limit=0").json()["refreshing"] is True
    finally:
        release.set()
    after = _settle(client)
    assert runs == [("all", False), ("all", True)]
    assert (after["fetched"], after["complete"]) == (102, True)
    assert _api_paths(_asked(tmp_path)) == [list_page("all", 1), list_page("all", 2)]

    # It was asked of that job alone: the next job extends nothing.
    assert client.post(REFRESH, json={"retry": True}, headers=_JSON).json()["refresh"] == "started"
    _settle(client)
    assert runs == [("all", False), ("all", True), ("all", False)]


def test_a_more_that_joins_a_more_is_the_same_page(
    served: tuple[TestClient, PublishedSource], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two clicks while one page is being read ask for that page, and not for two."""

    client, _published = served
    release, runs = _held_refresh(monkeypatch)
    try:
        assert client.post(REFRESH, json={"more": True}, headers=_JSON).json()["refresh"] == (
            "started"
        )
        assert client.post(REFRESH, json={"more": True}, headers=_JSON).json()["refresh"] == (
            "joined"
        )
    finally:
        release.set()
    _settle(client)
    assert runs == [("all", True)]


def test_a_more_that_joins_a_refresh_that_fails_runs_nothing_further(
    served: tuple[TestClient, PublishedSource],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pull_origin: Origin,
) -> None:
    """The stamp says the refresh failed, which is the answer the reader's **Retry** is for."""

    client, _published = served
    _answer(
        tmp_path,
        monkeypatch,
        scenario(pull_origin) | {"auth": {"stdout": '{"hosts":{}}\n', "exit": 0}},
    )
    release, runs = _held_refresh(monkeypatch)
    try:
        client.post(REFRESH, json={}, headers=_JSON)
        client.post(REFRESH, json={"more": True}, headers=_JSON)
    finally:
        release.set()
    after = _settle(client)
    assert runs == [("all", False)]
    assert after["last_refresh"]["outcome"] == "not_logged_in"


def test_a_more_that_joins_a_refresh_that_completes_the_list_reads_nothing_further(
    served: tuple[TestClient, PublishedSource],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pull_origin: Origin,
) -> None:
    """The list the job ended with has no next page, so there is nothing to extend it with."""

    client, _published = served
    path = list_page("all", 1)
    answers = scenario(pull_origin)
    answers["api"] = {**answers["api"], path: ok(path, [generated_item(7)])}
    _answer(tmp_path, monkeypatch, answers)
    release, runs = _held_refresh(monkeypatch)
    try:
        client.post(REFRESH, json={}, headers=_JSON)
        client.post(REFRESH, json={"more": True}, headers=_JSON)
    finally:
        release.set()
    after = _settle(client)
    assert runs == [("all", False)]
    assert (after["fetched"], after["complete"]) == (1, True)


def test_a_read_never_starts_anything(
    served: tuple[TestClient, PublishedSource], tmp_path: Path
) -> None:
    """Following a link cannot fetch. A golden lists no gh for one command; this asks twice."""

    client, _published = served
    for route in (PULLS, f"{PULLS}?state=open", f"{PULLS}?state=closed&limit=0"):
        for _again in range(2):
            answer = client.get(route).json()
            assert (answer["state"], answer["refreshing"]) == ("absent", False)
    assert _asked(tmp_path) == []


def test_the_route_answers_an_unchanged_list_with_a_304(
    served: tuple[TestClient, PublishedSource],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pull_origin: Origin,
) -> None:
    """A one-shot command sends no ``If-None-Match``, and a page polls with one."""

    client, _published = served
    client.post(REFRESH, json={}, headers=_JSON)
    _settle(client)
    answer = client.get(f"{PULLS}?limit=2")
    tag = answer.headers["etag"]
    assert answer.headers["cache-control"] == "no-store"
    unchanged = client.get(f"{PULLS}?limit=2", headers={"if-none-match": tag})
    assert (unchanged.status_code, unchanged.content) == (304, b"")
    # Another window of the same list is another answer.
    other = {"if-none-match": tag}
    assert client.get(f"{PULLS}?limit=2&after=105", headers=other).status_code == 200
    assert client.get(f"{PULLS}?limit=3", headers=other).status_code == 200
    # A refresh within the same second replaces the file, and the tag with it.
    client.post(REFRESH, json={"retry": True}, headers=_JSON)
    _settle(client)
    assert client.get(f"{PULLS}?limit=2", headers=other).status_code == 200


def test_the_route_parses_a_list_again_only_when_it_changed(
    served: tuple[TestClient, PublishedSource], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The memo a poll relies on: no transcript can see a parse that did not happen."""

    client, _published = served
    client.post(REFRESH, json={}, headers=_JSON)
    _settle(client)
    parsed: list[str] = []
    real = pull_list_route.read_pull_list

    def counted(home: Path, slug: str, name: Any) -> Any:
        parsed.append(name)
        return real(home, slug, name)

    monkeypatch.setattr(pull_list_route, "read_pull_list", counted)
    client.get(PULLS)
    first = len(parsed)
    client.get(PULLS)
    client.get(f"{PULLS}?limit=1&after=50")
    assert len(parsed) == first
    client.post(REFRESH, json={"retry": True}, headers=_JSON)
    _settle(client)
    client.get(PULLS)
    assert len(parsed) > first


def test_the_refresh_route_refuses_what_is_not_a_refresh_request(
    served: tuple[TestClient, PublishedSource],
) -> None:
    """Route safety: content cannot reach it with a link, an image, or a form."""

    client, _published = served
    assert client.get(REFRESH).status_code == 405
    for content, status in (
        (b"[]", 400),
        (b"{", 400),
        (b'{"state": "merged"}', 400),
        (b'{"more": 1}', 400),
        (b'{"x": "' + b"y" * 2000 + b'"}', 413),
    ):
        refused = client.post(REFRESH, content=content, headers=_JSON)
        assert (refused.status_code, refused.json()["code"]) == (status, "invalid_request")
    other = {**_JSON, "origin": "https://example.invalid"}
    assert client.post(REFRESH, json={}, headers=other).status_code == 403
    plain = {"content-type": "text/plain"}
    assert client.post(REFRESH, content=b"{}", headers=plain).status_code == 415
    outdated = client.post(REFRESH, json={}, headers={**_JSON, PIN_HEADER: "0" * 40})
    assert (outdated.status_code, outdated.json()["code"]) == (409, "pin_changed")
