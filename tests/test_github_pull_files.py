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
import sys
from collections.abc import AsyncGenerator, Callable
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from metabrowser.builtin_plugins.github import gh_lists, pull_files_refresh, pull_list, pull_record
from metabrowser.builtin_plugins.github.gh import GhError, GhResponse
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
    read_files_refresh,
    read_pull_files,
    serialize_pull_files,
    write_files_refresh,
    write_pull_files,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.cache.paths import source_pull_files
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
        generation="1" * 32,
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
    first = _refresh(repository, TREE_PULL, _watching(home, TREE_PULL, seen))
    assert {item.generation for item in seen if isinstance(item, PullFileList)} == {
        first.generation
    }
    assert [
        (len(item.rows), item.complete, item.last_page) if isinstance(item, PullFileList) else item
        for item in seen
    ] == [
        "not_cached",
        "not_cached",
        "not_cached",
        (100, False, 3),
        (100, False, 3),
        (200, False, 3),
        (200, False, 3),
    ]

    seen.clear()
    second = _refresh(repository, TREE_PULL, _watching(home, TREE_PULL, seen))
    assert second.fetched_at == first.fetched_at
    assert second.generation != first.generation
    assert {item.generation for item in seen if isinstance(item, PullFileList)} == {
        first.generation
    }
    assert len(seen) == 5
    assert all(isinstance(item, PullFileList) and len(item.rows) == 249 for item in seen)


def test_concurrent_same_second_refreshes_keep_distinct_persisted_generations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    """Real overlapping page jobs each mint once; new-process cache reads keep the winner."""

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()))
    minted: list[str] = []
    real_uuid4 = pull_files_refresh.uuid4

    def mint() -> UUID:
        value = real_uuid4()
        minted.append(value.hex)
        return value

    monkeypatch.setattr(pull_files_refresh, "uuid4", mint)

    async def overlap() -> tuple[PullFileList, PullFileList]:
        entered = 0
        both_started = asyncio.Event()

        @contextlib.asynccontextmanager
        async def slot() -> AsyncGenerator[object]:
            nonlocal entered
            entered += 1
            if entered == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=5)
            yield None

        first, second = await asyncio.gather(
            refresh_pull_files(repository, TREE_PULL, local=None, slot=slot),
            refresh_pull_files(repository, TREE_PULL, local=None, slot=slot),
        )
        return first, second

    first, second = asyncio.run(overlap())
    assert first.fetched_at == second.fetched_at
    assert first.rows == second.rows
    assert first.generation != second.generation
    assert minted == [first.generation, second.generation]
    kept = read_pull_files(home, SOURCE.slug, TREE_PULL)
    assert isinstance(kept, PullFileList) and kept.generation in minted
    before = (home / source_pull_files(SOURCE.slug, TREE_PULL)).read_bytes()
    view, window = FilesView(TREE_PULL, repository, None, False, None), FilesWindow(TREE_PULL)
    assert [pull_files_envelope(view, window)["generation"] for _ in range(2)] == [
        kept.generation,
        kept.generation,
    ]
    # A separate interpreter has no route or model cache and performs only private reads.
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json, sys
from pathlib import Path
from metabrowser.builtin_plugins.github.pull_list import read_pull_files
record = read_pull_files(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
print(json.dumps(record.model_dump()))
""",
            str(home),
            SOURCE.slug,
            str(TREE_PULL),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(child.stdout) == kept.model_dump(mode="json")
    assert (home / source_pull_files(SOURCE.slug, TREE_PULL)).read_bytes() == before
    assert len(minted) == 2


def test_old_file_list_schema_is_a_nonmutating_miss_then_refetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, home: Path
) -> None:
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, [file_item("before.js")]))
    previous = _refresh(repository, TREE_PULL)
    payload = previous.model_dump()
    payload["schema_version"] = PULL_FILES_SCHEMA - 1
    del payload["generation"]
    path = home / source_pull_files(SOURCE.slug, TREE_PULL)
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    view, window = FilesView(TREE_PULL, repository, None, False, None), FilesWindow(TREE_PULL)
    absent = pull_files_envelope(view, window)
    assert (absent["state"], absent["reason"], absent["generation"]) == (
        "absent",
        "schema_mismatch",
        None,
    )
    assert read_pull_files(home, SOURCE.slug, TREE_PULL) == "schema_mismatch"
    assert path.read_bytes() == before
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, [file_item("after.js")]))
    current = _refresh(repository, TREE_PULL)
    assert current.generation != previous.generation
    assert current.rows[0].path == "after.js"
    assert read_pull_files(home, SOURCE.slug, TREE_PULL) == current


@pytest.mark.parametrize("generation", [None, "", "1" * 31, "1" * 33, "../escape", "G" * 32])
def test_invalid_file_generation_is_not_adopted_or_rewritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    home: Path,
    generation: object,
) -> None:
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, [file_item("a.py")]))
    payload = _refresh(repository, TREE_PULL).model_dump()
    payload["generation"] = generation
    path = home / source_pull_files(SOURCE.slug, TREE_PULL)
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    assert read_pull_files(home, SOURCE.slug, TREE_PULL) == "unreadable"
    assert path.read_bytes() == before


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


@pytest.mark.parametrize(
    ("switch_at", "fail_at", "outcome", "fetched"),
    [
        (1, None, "account_changed", 0),
        (2, 3, "account_changed", 100),
        (None, None, "succeeded", 250),
        (None, 3, "network_error", 200),
    ],
)
def test_progressive_prefixes_stay_with_the_verified_account(
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    switch_at: int | None,
    fail_at: int | None,
    outcome: str,
    fetched: int,
) -> None:
    """A later page failure cannot make an unchecked, mixed-account prefix current."""

    login = "reader-a"
    account_reads: list[str] = []
    requests: list[str] = []

    async def active() -> str:
        account_reads.append(login)
        return login

    async def response(path: str, *, etag: str | None = None, now: object = None) -> GhResponse:
        nonlocal login
        requests.append(path)
        page = len(requests)
        assert path == files_page(TREE_PULL, page)
        if page == switch_at:
            login = "reader-b"
        if page == fail_at:
            raise GhError("the controlled next page is offline", state="network_error")
        headers = {"etag": f'"{login}-page-{page}"'}
        if page < 3:
            headers["link"] = (
                f"<https://api.github.com/repos/octo/demo/pulls/{TREE_PULL}/files"
                f'?page={page + 1}>; rel="next"'
            )
        rows = [
            {
                "filename": f"{login}/page-{page}/{index}.txt",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
            }
            for index in range(50 if page == 3 else 100)
        ]
        return GhResponse(200, headers, json.dumps(rows).encode())

    monkeypatch.setattr(pull_files_refresh, "active_account", active)
    monkeypatch.setattr(gh_lists, "gh_api", response)
    if outcome == "succeeded":
        _refresh(repository, TREE_PULL)
    else:
        with pytest.raises(PullDataError) as caught:
            _refresh(repository, TREE_PULL)
        assert caught.value.state == outcome
    listed = read_pull_files(repository.home, repository.slug, TREE_PULL)
    envelope = pull_files_envelope(
        FilesView(TREE_PULL, repository, None, False, None), FilesWindow(TREE_PULL)
    )
    last_refresh = envelope["last_refresh"]
    assert last_refresh is not None and last_refresh["outcome"] == outcome
    assert envelope["fetched"] == fetched
    if fetched:
        assert isinstance(listed, PullFileList) and listed.reader == "gh:reader-a"
        assert {row.path.split("/")[0] for row in listed.rows} == {"reader-a"}
        assert all(mark.etag and mark.etag.startswith('"reader-a-') for mark in listed.marks)
        assert listed.complete is (outcome == "succeeded")
        assert envelope["state"] == ("stale" if outcome == "account_changed" else "current")
    else:
        assert listed == "not_cached" and envelope["state"] == "absent"
    assert len(requests) == (switch_at if switch_at is not None else 3)
    assert len(account_reads) <= len(requests) + 1


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
    assert (borrowed.base, borrowed.head) == (base, head)
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
    """GitHub's list follows provider updates; a local list follows resolved endpoints."""

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    _refresh(repository, TREE_PULL)
    view = FilesView(TREE_PULL, repository, None, False, None)
    window = FilesWindow(TREE_PULL, limit=0)
    route = "metabrowser.builtin_plugins.github.pull_files_route._facts"

    def facts(head: str | None, updated_at: str | None) -> SimpleNamespace:
        record = (
            SimpleNamespace(comparison=SimpleNamespace(base="b" * 40, head=head))
            if head is not None
            else None
        )
        return SimpleNamespace(updated_at=updated_at, record=record)

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
            "base": "b" * 40,
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


def test_local_list_retarget_and_unknown_old_base_are_stale(
    home: Path, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unchanged head cannot make rows from a different base current or block refresh."""

    listed = PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        generation="1" * 32,
        source=CANONICAL,
        number=7,
        listed_from="comparison",
        fetched_at="2026-09-17T12:00:00Z",
        reader=None,
        base="b" * 40,
        head="c" * 40,
        pages=0,
        last_page=None,
        complete=True,
        capped=False,
        truncated=False,
        marks=(),
        rows=(),
    )
    write_pull_files(home, SOURCE.slug, listed)
    record = SimpleNamespace(comparison=SimpleNamespace(base=listed.base, head=listed.head))
    facts = SimpleNamespace(updated_at=None, record=record)
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_files_route._facts", lambda *_: facts
    )
    view, window = FilesView(7, repository, None, False, home), FilesWindow(7)
    assert pull_files_envelope(view, window)["state"] == "current"
    assert files_refresh_wanted(view, FilesRefreshRequest(7, False))[0] is False

    record.comparison.base = "d" * 40
    assert pull_files_envelope(view, window)["state"] == "stale"
    assert files_refresh_wanted(view, FilesRefreshRequest(7, False)) == (
        True,
        LocalComparison(home, "d" * 40, "c" * 40),
    )
    record.comparison = None
    assert pull_files_envelope(view, window)["state"] == "stale"
    record.comparison = SimpleNamespace(base=listed.base, head=listed.head)
    old_payload = listed.model_dump()
    del old_payload["base"]
    # A cache missing comparison identity cannot prove freshness.
    (home / source_pull_files(SOURCE.slug, 7)).write_text(json.dumps(old_payload), encoding="utf-8")
    old = read_pull_files(home, SOURCE.slug, 7)
    assert isinstance(old, PullFileList) and old.base is None
    assert pull_files_envelope(view, window)["state"] == "stale"
    assert files_refresh_wanted(view, FilesRefreshRequest(7, False))[0] is True


def test_github_list_freshness_stays_with_provider_updates_and_account(
    tmp_path: Path, home: Path, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later local comparison does not replace the provider's own freshness evidence."""

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    listed = _refresh(repository, TREE_PULL)
    assert listed.base is None and listed.head is None
    record = SimpleNamespace(comparison=SimpleNamespace(base="b" * 40, head="c" * 40))
    facts = SimpleNamespace(updated_at="2026-09-17T11:59:59Z", record=record)
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_files_route._facts", lambda *_: facts
    )
    view, window = FilesView(TREE_PULL, repository, None, False, home), FilesWindow(TREE_PULL)
    assert pull_files_envelope(view, window)["state"] == "current"
    record.comparison.base = "d" * 40
    assert pull_files_envelope(view, window)["state"] == "current"
    facts.updated_at = "2026-09-17T12:00:01Z"
    assert pull_files_envelope(view, window)["state"] == "stale"
    facts.updated_at = "2026-09-17T11:59:59Z"
    write_files_refresh(
        home,
        SOURCE.slug,
        TREE_PULL,
        PullRefreshStamp(
            outcome="account_changed", reader="gh:another-reader", at="2026-09-17T12:00:02Z"
        ),
    )
    assert pull_files_envelope(view, window)["state"] == "stale"


def test_github_list_names_the_head_it_was_read_for_and_follows_it(
    tmp_path: Path, home: Path, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A comment leaves a list current; a push or a retargeted base makes it stale.

    The head is observed before the first page, so a push during the read can only make a
    list look older than it is. A list or a source that names no head falls back to the
    provider's ``updated_at``.
    """

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    observed: list[str] = []

    def known() -> tuple[str | None, str | None]:
        observed.append("asked")
        return "c" * 40, "topic"

    listed = asyncio.run(
        refresh_pull_files(repository, TREE_PULL, local=None, slot=_free, known_head=known)
    )
    assert observed == ["asked"]
    assert (listed.head, listed.base_ref, listed.base) == ("c" * 40, "topic", None)
    facts = SimpleNamespace(
        updated_at="2026-09-17T13:00:00Z", record=None, head="c" * 40, base_ref="topic"
    )
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_files_route._facts", lambda *_: facts
    )
    view, window = FilesView(TREE_PULL, repository, None, False, home), FilesWindow(TREE_PULL)
    envelope = pull_files_envelope(view, window)
    # Updated an hour after the read, by a comment, and still current.
    assert (envelope["state"], envelope["head"], envelope["base_ref"]) == (
        "current",
        "c" * 40,
        "topic",
    )
    assert files_refresh_wanted(view, FilesRefreshRequest(TREE_PULL, False))[0] is False
    facts.head = "d" * 40
    assert pull_files_envelope(view, window)["state"] == "stale"
    assert files_refresh_wanted(view, FilesRefreshRequest(TREE_PULL, False))[0] is True
    facts.head, facts.base_ref = "c" * 40, "main"
    assert pull_files_envelope(view, window)["state"] == "stale"
    # A newest source that names no head leaves the provider's update time to decide.
    facts.head = facts.base_ref = None
    assert pull_files_envelope(view, window)["state"] == "stale"
    facts.updated_at = "2026-09-17T11:59:59Z"
    assert pull_files_envelope(view, window)["state"] == "current"


def test_the_newest_of_record_and_row_names_the_head(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_files_route

    record = SimpleNamespace(
        pull=SimpleNamespace(
            updated_at="2026-09-17T12:00:00Z",
            head=SimpleNamespace(sha="a" * 40),
            base=SimpleNamespace(ref="topic"),
        )
    )
    row = SimpleNamespace(updated_at="2026-09-17T12:00:00Z", head_oid=None, base_ref="topic")
    monkeypatch.setattr(pull_files_route, "PullRecord", SimpleNamespace)
    monkeypatch.setattr(pull_files_route, "cached_pull_record", lambda *_: (record, None, None))
    monkeypatch.setattr(pull_files_route, "cached_list_row", lambda *_: row)
    # A tie keeps the record, which names its head, unless the row names another
    # (review A5): a push within the record's second leaves the times equal.
    assert pull_files_route.known_head(home, SOURCE.slug, 7) == ("a" * 40, "topic")
    row.head_oid = "a" * 40
    assert pull_files_route.known_head(home, SOURCE.slug, 7) == ("a" * 40, "topic")
    row.head_oid = "b" * 40
    assert pull_files_route.known_head(home, SOURCE.slug, 7) == ("b" * 40, "topic")
    row.updated_at = "2026-09-17T12:05:00Z"
    assert pull_files_route.known_head(home, SOURCE.slug, 7) == ("b" * 40, "topic")
    row.head_oid = None
    assert pull_files_route.known_head(home, SOURCE.slug, 7) == (None, "topic")


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


def _comparison_for_limit_test(tmp_path: Path) -> LocalComparison:
    work = tmp_path / "work"
    work.mkdir()
    base, head = build_diff_fixture(work)
    store = tmp_path / "store.git"
    git(tmp_path, "clone", "-q", "--bare", str(work), str(store))
    return LocalComparison(store, base, head)


@pytest.mark.parametrize("failure", ["missing", "truncated"])
def test_failed_local_listing_honors_rate_limit_before_github_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    failure: str,
) -> None:
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    local = LocalComparison(tmp_path / "missing.git", "b" * 40, "c" * 40)
    if failure == "truncated":
        local = _comparison_for_limit_test(tmp_path)
        monkeypatch.setattr("metabrowser.diff.adapters.git.MAX_MANIFEST_FILES", 1)
    limited = PullRefreshStamp(
        outcome="rate_limited",
        message="GitHub said to wait",
        reset_at="2026-09-18T00:00:00Z",
        at="2026-09-17T12:00:00Z",
        reader="gh:reader",
    )
    write_files_refresh(repository.home, repository.slug, TREE_PULL, limited)
    with pytest.raises(PullDataError) as held:
        asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (held.value.state, held.value.reset_at) == ("rate_limited", limited.reset_at)
    assert read_files_refresh(repository.home, repository.slug, TREE_PULL) == limited
    assert not Path(os.environ["FAKE_GH_LOG"]).exists(), (
        "the rate limit must hold account reads too"
    )
    assert read_pull_files(repository.home, repository.slug, TREE_PULL) == "not_cached"

    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(days=1))
    listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (listed.listed_from, len(listed.rows)) == ("github", 2)
    assert Path(os.environ["FAKE_GH_LOG"]).read_text()


def test_usable_local_listing_needs_no_github_while_rate_limited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    _answer(tmp_path, monkeypatch, {})
    local = _comparison_for_limit_test(tmp_path)
    limited = PullRefreshStamp(
        outcome="rate_limited", reset_at="2026-09-18T00:00:00Z", at="2026-09-17T12:00:00Z"
    )
    write_files_refresh(repository.home, repository.slug, TREE_PULL, limited)
    listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert listed.listed_from == "comparison" and listed.rows
    assert not Path(os.environ["FAKE_GH_LOG"]).exists()


@pytest.mark.parametrize("failure", ["missing", "truncated"])
def test_successive_local_lists_keep_network_hold_until_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    failure: str,
) -> None:
    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    local = _comparison_for_limit_test(tmp_path)
    limited = PullRefreshStamp(
        outcome="rate_limited",
        message="GitHub said to wait",
        reset_at="2026-09-18T00:00:00Z",
        at="2026-09-17T12:00:00Z",
        reader="gh:reader",
    )
    write_files_refresh(repository.home, repository.slug, TREE_PULL, limited)
    # A real local success must report its own outcome/time, without erasing a
    # network hold that still applies if this store later cannot supply the list.
    for seconds in (1, 61):
        now = FETCHED_AT + timedelta(seconds=seconds)
        monkeypatch.setattr(pull_list, "utc_now", lambda now=now: now)
        listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
        assert listed.listed_from == "comparison" and listed.rows
        succeeded = read_files_refresh(repository.home, repository.slug, TREE_PULL)
        assert succeeded is not None
        assert (succeeded.outcome, succeeded.at, succeeded.reader, succeeded.reset_at) == (
            "succeeded",
            listed.fetched_at,
            None,
            limited.reset_at,
        )
        assert pull_list.rate_limit_holds(succeeded, now=now)
    log = Path(os.environ["FAKE_GH_LOG"])
    assert not log.exists()

    record = SimpleNamespace(comparison=SimpleNamespace(base=local.base, head=local.head))
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_files_route._facts",
        lambda *_: SimpleNamespace(updated_at=None, record=record),
    )
    view = FilesView(TREE_PULL, repository, None, False, None)
    envelope = pull_files_envelope(view, FilesWindow(TREE_PULL))
    assert envelope["state"] == "current" and envelope["rows"]
    assert envelope["last_refresh"] == {
        "outcome": "succeeded",
        "message": None,
        "reset_at": limited.reset_at,
        "at": listed.fetched_at,
    }
    assert files_refresh_wanted(view, FilesRefreshRequest(TREE_PULL, True)) == (False, None)

    if failure == "missing":
        local = LocalComparison(tmp_path / "missing.git", local.base, local.head)
    else:
        monkeypatch.setattr("metabrowser.diff.adapters.git.MAX_MANIFEST_FILES", 1)
    with pytest.raises(PullDataError) as held:
        asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (held.value.state, held.value.reset_at) == ("rate_limited", limited.reset_at)
    assert not log.exists(), "even account reads must wait for the original reset"
    assert read_files_refresh(repository.home, repository.slug, TREE_PULL) == succeeded
    assert read_pull_files(repository.home, repository.slug, TREE_PULL) == listed
    # The skipped fallback has not replaced the valid local rows or their successful
    # refresh outcome; the envelope still describes this exact cached comparison.
    assert pull_files_envelope(view, FilesWindow(TREE_PULL)) == envelope

    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(hours=12))
    fallback = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    assert (fallback.listed_from, len(fallback.rows)) == ("github", 2)
    assert len(log.read_text().splitlines()) == 3
    finished = read_files_refresh(repository.home, repository.slug, TREE_PULL)
    assert finished is not None and finished.outcome == "succeeded"
    assert finished.reset_at is None


def test_local_cache_failure_keeps_the_network_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    _answer(tmp_path, monkeypatch, {})
    local = _comparison_for_limit_test(tmp_path)
    limited = PullRefreshStamp(
        outcome="rate_limited", reset_at="2026-09-18T00:00:00Z", at="2026-09-17T12:00:00Z"
    )
    write_files_refresh(repository.home, repository.slug, TREE_PULL, limited)

    async def refuse(*_: object) -> None:
        raise PullDataError("cache_unwritable", "the list could not be written")

    monkeypatch.setattr("metabrowser.builtin_plugins.github.pull_files_refresh._write", refuse)
    with pytest.raises(PullDataError, match="could not be written"):
        asyncio.run(refresh_pull_files(repository, TREE_PULL, local=local, slot=_free))
    failed = read_files_refresh(repository.home, repository.slug, TREE_PULL)
    assert failed is not None and failed.outcome == "cache_unwritable"
    assert failed.reset_at == limited.reset_at
    with pytest.raises(PullDataError) as held:
        asyncio.run(refresh_pull_files(repository, TREE_PULL, local=None, slot=_free))
    assert (held.value.state, held.value.reset_at) == ("rate_limited", limited.reset_at)
    assert not Path(os.environ["FAKE_GH_LOG"]).exists()


@pytest.mark.parametrize("reset", ["not-a-timestamp", "2026-13-17T12:00:00Z"])
def test_malformed_saved_reset_does_not_become_a_network_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository, reset: str
) -> None:
    from metabrowser.cache.paths import source_pull_files_refresh

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()[:2]))
    valid = PullRefreshStamp(outcome="succeeded", at="2026-09-17T12:00:00Z")
    write_files_refresh(repository.home, repository.slug, TREE_PULL, valid)
    path = repository.home / source_pull_files_refresh(repository.slug, TREE_PULL)
    path.write_text(json.dumps({**valid.model_dump(), "reset_at": reset}), encoding="utf-8")
    assert read_files_refresh(repository.home, repository.slug, TREE_PULL) is None
    listed = asyncio.run(refresh_pull_files(repository, TREE_PULL, local=None, slot=_free))
    assert (listed.listed_from, len(listed.rows)) == ("github", 2)
    assert len(Path(os.environ["FAKE_GH_LOG"]).read_text().splitlines()) == 3


def test_memory_only_file_refusal_does_not_mask_a_later_shared_rate_hold(
    home: Path, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another process's durable deadline still holds after a local admission refusal."""

    from metabrowser.cache.paths import source_pull_files_refresh

    refused = PullRefreshStamp(
        outcome="cache_unwritable", at="2026-09-17T12:00:00Z", message="cache refused"
    )
    write_files_refresh(home, repository.slug, TREE_PULL, refused, persist=False)
    relative = source_pull_files_refresh(repository.slug, TREE_PULL)
    assert not (home / relative).exists()
    held = PullRefreshStamp(
        outcome="rate_limited", at="2026-09-17T12:00:00Z", reset_at="2026-09-17T12:05:00Z"
    )
    # The canonical disk writer models another process, which has no local memory entry.
    pull_record.write_refresh_stamp(home, repository.slug, relative, held)
    assert read_files_refresh(home, repository.slug, TREE_PULL) == held
    write_files_refresh(home, repository.slug, TREE_PULL, refused, persist=False)
    remembered = read_files_refresh(home, repository.slug, TREE_PULL)
    assert remembered is not None and remembered.outcome == "cache_unwritable"
    assert remembered.reset_at == held.reset_at
    assert pull_record.read_refresh_stamp(home, relative) == held
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(minutes=6))
    succeeded = PullRefreshStamp(outcome="succeeded", at="2026-09-17T12:06:00Z")
    write_files_refresh(home, repository.slug, TREE_PULL, succeeded)
    assert read_files_refresh(home, repository.slug, TREE_PULL) == succeeded


def test_newer_memory_file_refusal_keeps_a_later_shared_deadline(
    home: Path, repository: ListedRepository
) -> None:
    """A delayed older publication must retain its hold, not replace the latest outcome."""

    from metabrowser.cache.paths import source_pull_files_refresh

    refused = PullRefreshStamp(
        outcome="cache_unwritable", at="2026-09-17T12:00:01Z", message="cache refused"
    )
    write_files_refresh(home, repository.slug, TREE_PULL, refused, persist=False)
    held = PullRefreshStamp(
        outcome="rate_limited", at="2026-09-17T12:00:00Z", reset_at="2026-09-17T12:05:00Z"
    )
    relative = source_pull_files_refresh(repository.slug, TREE_PULL)
    # Another process captured its outcome earlier but finishes publication later.
    pull_record.write_refresh_stamp(home, repository.slug, relative, held)
    view = FilesView(TREE_PULL, repository, None, False, None)
    envelope = pull_files_envelope(view, FilesWindow(TREE_PULL))
    assert envelope["last_refresh"] == {
        "outcome": refused.outcome,
        "message": refused.message,
        "at": refused.at,
        "reset_at": held.reset_at,
    }
    for retry in (False, True):
        wanted, _local = files_refresh_wanted(view, FilesRefreshRequest(TREE_PULL, retry))
        assert not wanted
    assert pull_record.read_refresh_stamp(home, relative) == held


def test_expired_equal_time_file_hold_keeps_the_memory_outcome(
    home: Path, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An expired deadline does not change the existing equal-time memory precedence."""

    from metabrowser.cache.paths import source_pull_files_refresh

    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT + timedelta(minutes=6))
    refused = PullRefreshStamp(
        outcome="cache_unwritable", at="2026-09-17T12:00:00Z", message="cache refused"
    )
    write_files_refresh(home, repository.slug, TREE_PULL, refused, persist=False)
    held = PullRefreshStamp(outcome="rate_limited", at=refused.at, reset_at="2026-09-17T12:05:00Z")
    relative = source_pull_files_refresh(repository.slug, TREE_PULL)
    pull_record.write_refresh_stamp(home, repository.slug, relative, held)
    assert read_files_refresh(home, repository.slug, TREE_PULL) == refused


@pytest.mark.parametrize("absence", ["not_cached", "unreadable", "schema_mismatch"])
@pytest.mark.parametrize("outcome", ["succeeded", "network_error", "rate_limited"])
def test_absent_file_cache_repairs_a_recent_success_but_preserves_failure_holds(
    home: Path,
    repository: ListedRepository,
    absence: str,
    outcome: str,
) -> None:
    """A success stamp is not a substitute for readable rows; failures still back off."""

    if absence != "not_cached":
        path = home / source_pull_files(SOURCE.slug, TREE_PULL)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        path.write_text("{" if absence == "unreadable" else '{"schema_version": 0}')
        path.chmod(0o600)
    assert read_pull_files(home, SOURCE.slug, TREE_PULL) == absence
    write_files_refresh(
        home,
        SOURCE.slug,
        TREE_PULL,
        PullRefreshStamp(
            outcome=outcome,
            at="2026-09-17T12:00:00Z",
            reset_at="2026-09-17T12:05:00Z" if outcome == "rate_limited" else None,
        ),
    )
    view = FilesView(TREE_PULL, repository, None, False, None)
    assert files_refresh_wanted(view, FilesRefreshRequest(TREE_PULL, False)) == (
        outcome == "succeeded",
        None,
    )
