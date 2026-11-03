"""What the transcripts of the changed-files routes cannot show.

``tests/test_cli_github_pull_files_golden.py`` and
``tests/golden/cli-github-pull-files.tryscript.md`` pin what the routes answer. These add the
evidence a transcript has no way to give: that GitHub's list runs no Git and needs no store,
that a path reaches nothing but the list's file, what never reaches a written file, that
every list written can be read back, what a reader sees between pages, the bound on jobs,
and the freshness rule on a force-push. Each says why it is here.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list, pull_record
from metabrowser.builtin_plugins.github.gh_lists import PullDataError
from metabrowser.builtin_plugins.github.pull_files_refresh import refresh_pull_files
from metabrowser.builtin_plugins.github.pull_files_route import (
    FilesRefreshRequest,
    FilesRequestError,
    FilesView,
    FilesWindow,
    files_refresh_request,
    files_refresh_wanted,
    files_window,
    pull_files_envelope,
    start_files_refresh,
)
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_FILE_PATH_BYTES,
    MAX_PULL_FILES,
    PULL_FILES_SCHEMA,
    ListedRepository,
    LocalComparison,
    PullFileList,
    PullFileRow,
    read_pull_files,
    serialize_pull_files,
    write_files_refresh,
    write_pull_files,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.mirror_refresh import MAX_PULL_JOBS
from tests.cache_home_fixture import (
    FixtureSource,
    _stage_and_publish_source,  # pyright: ignore[reportPrivateUsage]
    build_empty_home,
)
from tests.diff_fixture_repo import build_diff_fixture, git
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    TREE_PULL,
    account,
    file_item,
    file_pages,
    files_page,
    install_fake_gh,
    tree_files,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script")

SOURCE = FixtureSource("https", CANONICAL)
_SECRET = "ghp_exampleSecretTokenValue0123456789"


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


def _answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pages: dict[str, Any], **more: Any
) -> None:
    answers = {"auth": account(), "api": pages, "api_failure": None, **more}
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)


@contextlib.asynccontextmanager
async def _free() -> AsyncGenerator[object]:
    yield None


def _watching(home: Path, number: int, seen: list[PullFileList | str]) -> Callable[[], Any]:
    """A slot that reads the list's file each time it is taken, between gh requests."""

    @contextlib.asynccontextmanager
    async def slot() -> AsyncGenerator[object]:
        seen.append(read_pull_files(home, SOURCE.slug, number))  # pyright: ignore[reportArgumentType]
        yield None

    return slot


def _refresh(
    repository: ListedRepository, number: int, slot: Callable[[], Any] = _free
) -> PullFileList:
    return asyncio.run(refresh_pull_files(repository, number, local=None, slot=slot))


# ── No Git, no store, and paths that reach nothing ─────────────


def test_github_list_succeeds_for_a_source_with_no_store_and_runs_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """The independent evidence that GitHub's list touches no Git, and a path no file.

    A ``git`` that fails and logs is first on ``PATH``, and there is no store. The paths are
    a pull request author's text, here built to escape the cache if anything joined one to a
    directory; the only files the job leaves are the list and its stamp.
    """

    bin_directory = tmp_path / "no-git"
    bin_directory.mkdir()
    git_log = tmp_path / "git-calls.log"
    git = bin_directory / "git"
    git.write_text(f'#!/bin/sh\necho "$*" >> {git_log}\nexit 1\n', encoding="utf-8")
    git.chmod(0o755)
    hostile = ["../../../escape.txt", "/etc/hosts-copy", "a/../../b.txt", "x/\u0000y"]
    items = [file_item(path) for path in hostile] + tree_files()[:3]
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, items))
    monkeypatch.setenv("PATH", f"{bin_directory}{os.pathsep}{os.environ['PATH']}")
    before = set(tmp_path.rglob("*"))

    listed = _refresh(repository, TREE_PULL)

    assert [row.path for row in listed.rows][:4] == hostile
    assert not git_log.exists()
    assert not list((home / "repository-stores").iterdir())
    added = {path for path in tmp_path.rglob("*") if path not in before}
    pulls = home / "sources" / SOURCE.slug / "pulls"
    assert {path for path in added if not path.name.startswith("fake-gh")} == {
        pulls,
        pulls / f"{TREE_PULL}.files.json",
        pulls / f"{TREE_PULL}.files.refresh.json",
    }


def test_no_written_file_carries_a_credential_or_a_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """The patch GitHub embeds, and a token in a header, never reach the cache."""

    items = [{**file_item("docs/a.md"), "patch": f"@@ -1 +1 @@\n-{_SECRET}\n+x\n"}]
    pages = {
        path: {**entry, "headers": {**entry["headers"], "Authorization": f"token {_SECRET}"}}
        for path, entry in file_pages(TREE_PULL, items).items()
    }
    _answer(tmp_path, monkeypatch, pages)
    _refresh(repository, TREE_PULL)
    for path in (home / "sources").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert _SECRET not in text and "@@" not in text and "blob_url" not in text, path


# ── Bounds ──────────────────────────────────────────────────────


def test_a_list_of_the_worst_rows_the_bounds_allow_can_be_read_back(home: Path) -> None:
    """The measurement beside ``MAX_PULL_FILES_BYTES``: every list written can be read."""

    control = "\x01" * ((MAX_FILE_PATH_BYTES - 16) // 6)
    rows = tuple(
        PullFileRow(
            path=f"{control}{index:05d}",
            previous_path=f"{control}p{index:05d}",
            status="unchanged",
            additions=10**9,
            deletions=10**9,
        )
        for index in range(MAX_PULL_FILES)
    )
    worst = PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        source=CANONICAL,
        number=1,
        listed_from="comparison",
        fetched_at="2026-09-17T12:00:00Z",
        reader=None,
        head="0" * 40,
        pages=0,
        last_page=None,
        complete=True,
        capped=False,
        truncated=False,
        marks=(),
        rows=rows,
    )
    assert pull_record.escaped_size(rows[0].path) <= MAX_FILE_PATH_BYTES
    data = serialize_pull_files(worst)
    assert len(data) < pull_list.MAX_PULL_FILES_BYTES
    write_pull_files(home, SOURCE.slug, worst)
    assert read_pull_files(home, SOURCE.slug, 1) == worst


def test_a_path_past_its_bound_is_left_out_and_said(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    """A cut path would name another file, so a long one is left out, never cut."""

    long = "d/" + "\x01" * (MAX_FILE_PATH_BYTES // 6 + 1)
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, [file_item("a.md"), file_item(long)]))
    listed = _refresh(repository, TREE_PULL)
    assert [row.path for row in listed.rows] == ["a.md"]
    assert listed.truncated and listed.marks[0].truncated


# ── Between pages ───────────────────────────────────────────────


def test_a_first_fill_is_published_page_by_page_and_a_reread_at_the_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """What a reader of the GET sees while a list fills, and while a whole one is reread.

    The slot is taken before each gh request, so what it reads is what has been published
    by then: the first fill grows, page by page, and a reread of a whole list leaves that
    list in place until the end, so a tree never shrinks under a reader.
    """

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()))
    seen: list[PullFileList | str] = []
    _refresh(repository, TREE_PULL, _watching(home, TREE_PULL, seen))
    assert [
        (len(item.rows), item.complete, item.last_page) if isinstance(item, PullFileList) else item
        for item in seen
    ] == ["not_cached", "not_cached", (100, False, 3), (200, False, 3), (200, False, 3)]

    seen.clear()
    _refresh(repository, TREE_PULL, _watching(home, TREE_PULL, seen))
    assert all(isinstance(item, PullFileList) and len(item.rows) == 249 for item in seen)


def test_a_retry_after_a_stop_does_not_shrink_what_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    pages = file_pages(TREE_PULL, tree_files())
    broken = {**pages, files_page(TREE_PULL, 3): {"status": 502, "body": {"message": "Bad"}}}
    _answer(tmp_path, monkeypatch, broken)
    with pytest.raises(PullDataError):
        _refresh(repository, TREE_PULL)
    stopped = read_pull_files(home, SOURCE.slug, TREE_PULL)
    assert isinstance(stopped, PullFileList) and (len(stopped.rows), stopped.complete) == (
        200,
        False,
    )
    _answer(tmp_path, monkeypatch, broken)
    seen: list[PullFileList | str] = []
    with pytest.raises(PullDataError):
        _refresh(repository, TREE_PULL, _watching(home, TREE_PULL, seen))
    assert all(isinstance(item, PullFileList) and len(item.rows) == 200 for item in seen)


# ── What starts a job ───────────────────────────────────────────


class _Coordinator:
    """The coordinator's start and running, holding every job it starts as running."""

    def __init__(self) -> None:
        self.started: list[str] = []

    def running(self, key: str) -> bool:
        return key in self.started

    def start(self, key: str, work: object, *, network: bool = True) -> str:
        assert network is False, "a file-list job takes a slot per request, not for its whole run"
        self.started.append(key)
        return "started"

    def slot(self) -> object:
        return _free()


def test_past_the_bound_on_jobs_a_request_is_refused_and_starts_nothing(
    repository: ListedRepository,
) -> None:
    coordinator = _Coordinator()
    for number in range(1, MAX_PULL_JOBS + 2):
        view = FilesView(number, repository, coordinator, False, None)  # pyright: ignore[reportArgumentType]
        answer = start_files_refresh(
            view, FilesRefreshRequest(number, True), wanted=True, local=None
        )
        assert answer == ("started" if number <= MAX_PULL_JOBS else "too_many"), number
    assert len(coordinator.started) == MAX_PULL_JOBS
    # One already running is joined, bound or not.
    view = FilesView(1, repository, coordinator, True, None)  # pyright: ignore[reportArgumentType]
    assert (
        start_files_refresh(view, FilesRefreshRequest(1, True), wanted=True, local=None) == "joined"
    )


def test_a_local_list_is_not_held_by_github_s_limit(
    repository: ListedRepository, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The comparison needs no GitHub, so a limit GitHub set does not hold it."""

    limited = PullRefreshStamp(
        outcome="rate_limited", reset_at="2026-09-18T00:00:00Z", at="2026-09-17T12:00:00Z"
    )
    write_files_refresh(home, SOURCE.slug, 7, limited)
    view = FilesView(7, repository, None, False, home)
    ask = FilesRefreshRequest(7, True)
    assert files_refresh_wanted(view, ask) == (False, None)
    comparison = SimpleNamespace(base="b" * 40, head="c" * 40)
    record = SimpleNamespace(
        comparison=comparison, pull=SimpleNamespace(updated_at=None, head=None)
    )
    facts = SimpleNamespace(head="c" * 40, updated_at=None, record=record)
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_files_route._facts", lambda *_: facts
    )
    wanted, local = files_refresh_wanted(view, ask)
    assert wanted and local == LocalComparison(home, "b" * 40, "c" * 40)


def test_a_comparison_git_cannot_list_falls_through_to_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    """A store that does not answer for the commits is no reason to list nothing."""

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    local = LocalComparison(tmp_path / "no-such-store.git", "b" * 40, "c" * 40)
    listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (listed.listed_from, len(listed.rows)) == ("github", 2)


@pytest.mark.parametrize("lender", ["lender_missing", "commits_unavailable"])
def test_a_borrowed_store_that_can_no_longer_read_the_comparison_falls_through_to_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, lender: str
) -> None:
    """A mirror that borrows objects reads the record's commits through its checkout.

    Once the checkout is gone (``lender_missing``) or has collected the head
    (``commits_unavailable``), Git refuses them, and the list is GitHub's rather than none.
    ``base_uncertain`` and ``parent_unavailable`` never reach this read: the first leaves a
    record with no comparison, the second answers only one commit's diff, and the list asks
    for neither a merge base nor a parent.
    """

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    base, head = build_diff_fixture(checkout)
    store = tmp_path / "store.git"
    git(tmp_path, "init", "-q", "--bare", str(store))
    (store / "objects" / "info" / "alternates").write_text(f"{checkout / '.git' / 'objects'}\n")
    local = LocalComparison(store, base, head)
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    borrowed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert borrowed.listed_from == "comparison"
    if lender == "lender_missing":
        shutil.rmtree(checkout)
    else:
        git(checkout, "reset", "-q", "--hard", base)
        git(checkout, "reflog", "expire", "--expire=now", "--all")
        git(checkout, "gc", "-q", "--prune=now")
        with pytest.raises(subprocess.CalledProcessError):
            git(checkout, "cat-file", "-e", f"{head}^{{commit}}")
    listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (listed.listed_from, len(listed.rows)) == ("github", 2)


# ── Freshness ───────────────────────────────────────────────────


def test_a_force_push_makes_either_list_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """GitHub's list goes stale when ``updated_at`` passes it, a local one when the head moves."""

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    _refresh(repository, TREE_PULL)
    view = FilesView(TREE_PULL, repository, None, False, None)
    window = FilesWindow(TREE_PULL, limit=0)
    route = "metabrowser.builtin_plugins.github.pull_files_route._facts"

    def facts(head: str | None, updated_at: str | None) -> SimpleNamespace:
        return SimpleNamespace(head=head, updated_at=updated_at, record=None)

    monkeypatch.setattr(route, lambda *_: facts(None, "2026-09-17T11:59:59Z"))
    assert pull_files_envelope(view, window)["state"] == "current"
    monkeypatch.setattr(route, lambda *_: facts(None, "2026-09-17T12:00:01Z"))
    assert pull_files_envelope(view, window)["state"] == "stale"

    local = PullFileList.model_validate(
        {
            **json.loads(serialize_pull_files(read_pull_files(home, SOURCE.slug, TREE_PULL))),  # pyright: ignore[reportArgumentType]
            "listed_from": "comparison",
            "reader": None,
            "head": "a" * 40,
            "pages": 0,
            "last_page": None,
            "marks": [],
        }
    )
    write_pull_files(home, SOURCE.slug, local)
    monkeypatch.setattr(route, lambda *_: facts("a" * 40, "2026-09-17T13:00:00Z"))
    assert pull_files_envelope(view, window)["state"] == "current"
    monkeypatch.setattr(route, lambda *_: facts("f" * 40, None))
    assert pull_files_envelope(view, window)["state"] == "stale"


# ── Requests ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"number": "0"},
        {"number": "x"},
        {"number": "7", "limit": "3001"},
        {"number": "7", "offset": "-1"},
    ],
)
def test_a_window_outside_its_bounds_is_refused(params: dict[str, str]) -> None:
    with pytest.raises(FilesRequestError):
        files_window(params)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"number": "7"},
        {"number": True},
        {"number": 7, "retry": "yes"},
        {"number": 7, "more": True},
    ],
)
def test_a_refresh_request_outside_its_shape_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(FilesRequestError):
        files_refresh_request(body)
