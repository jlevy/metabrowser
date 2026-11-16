"""What each pull request's cached changed-files list sums to, for its Pulls row (mb-d0a3).

``GET /api/plugin/github/pull-files-summary`` is what the brief change line under a Pulls row
reads (:mod:`metabrowser.builtin_plugins.github.pull_files_summary`). These hold it to its
contract: a list summed by GitHub's status words and its line totals, a sum read once for each
version of the list's file, each reason a list sums to nothing, the request's byte budget,
``listing`` from a running refresh and from the prefetch lane, the request's shape, its tag,
the bound on the sums kept, and that it starts no process at all.
``tests/test_cli_github_pull_files_summary_golden.py`` drives it through ``metab --api``; the
recorder at the end writes what the Pulls tab's browserless session replays.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import threading
import time
from collections import Counter
from collections.abc import AsyncGenerator, Iterator
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import pull_files_refresh, pull_files_summary, pull_list
from metabrowser.builtin_plugins.github.pull_files_refresh import refresh_pull_files
from metabrowser.builtin_plugins.github.pull_files_summary import (
    MAX_SUMMARY_NUMBERS,
    SummaryRequestError,
    clear_kept_summaries,
    files_summary,
    summary_numbers,
)
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_FILE_PATH_BYTES,
    PULL_FILES_SCHEMA,
    FilePageMark,
    FileStatus,
    ListedRepository,
    PullFileList,
    PullFileRow,
    write_pull_files,
)
from metabrowser.builtin_plugins.github.pull_prefetch import Item, lane_of
from metabrowser.builtin_plugins.github.pull_route import pull_host
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_files
from metabrowser.server import app
from tests.cache_home_fixture import (
    FixtureSource,
    _stage_and_publish_source,  # pyright: ignore[reportPrivateUsage]
    build_empty_home,
)
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    TREE_PULL,
    account,
    file_item,
    file_pages,
    files_page,
    install_fake_gh,
    scenario,
    tree_files,
)
from tests.required_tools import needs_git
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

ROUTE = "/api/plugin/github/pull-files-summary"
REFRESH = "/api/plugin/github/pull-files-refresh"
FILES = "/api/plugin/github/pull-files"
SOURCE = FixtureSource("https", CANONICAL)
JSON_BODY = {"content-type": "application/json"}


@pytest.fixture(autouse=True)
def _forget_sums() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """The sums are kept per process, so no test starts with another's."""

    clear_kept_summaries()
    yield
    clear_kept_summaries()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ListedRepository:
    """An application home with one source directory, published with no store."""

    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The numbers whose list file the summary parses, in order, from here on."""

    read: list[int] = []
    real = pull_files_summary.read_pull_files

    def counted(home: Path, slug: str, number: int, **kwargs: Any) -> Any:
        read.append(number)
        return real(home, slug, number, **kwargs)

    monkeypatch.setattr(pull_files_summary, "read_pull_files", counted)
    return read


def _spawned(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every process this one starts from here on: gh, Git, or any other.

    Every child Python starts goes through ``subprocess.Popen``, asyncio's included, so a
    request that starts none leaves this empty.
    """

    started: list[Any] = []
    real = subprocess.Popen.__init__

    def recording(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        started.append(args)
        real(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", recording)
    return started


def _answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pages: dict[str, Any]) -> None:
    answers = {"auth": account(), "api": pages, "api_failure": None}
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)


@contextlib.asynccontextmanager
async def _free() -> AsyncGenerator[object]:
    yield None


def _refresh(repository: ListedRepository, number: int) -> PullFileList:
    """The product's own refresh of GitHub's list, against the fake gh."""

    return asyncio.run(refresh_pull_files(repository, number, local=None, slot=_free))


def _gh_log() -> Path:
    return Path(os.environ["FAKE_GH_LOG"])


def _row(
    path: str, status: FileStatus = "modified", additions: int | None = 1, deletions: int | None = 0
) -> PullFileRow:
    return PullFileRow(
        path=path, previous_path=None, status=status, additions=additions, deletions=deletions
    )


def _github(
    number: int,
    rows: list[PullFileRow],
    *,
    complete: bool = True,
    capped: bool = False,
    truncated: bool = False,
    last_page: int | None = None,
) -> PullFileList:
    """GitHub's list as the refresh writes it: one mark for each page of 100 rows it holds."""

    pages = [rows[start : start + 100] for start in range(0, len(rows), 100)] or [[]]
    return PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        generation="1" * 32,
        source=CANONICAL,
        number=number,
        listed_from="github",
        fetched_at="2026-09-17T12:00:00Z",
        reader="gh:octo-reader",
        head=None,
        pages=len(pages),
        last_page=last_page or len(pages),
        complete=complete,
        capped=capped,
        truncated=truncated,
        marks=tuple(
            FilePageMark(etag=None, rows=len(page), places=len(page), truncated=False)
            for page in pages
        ),
        rows=tuple(rows),
    )


def _comparison(number: int, rows: list[PullFileRow]) -> PullFileList:
    """The local comparison's list, which is whole and names its head and merge base."""

    return PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        generation="2" * 32,
        source=CANONICAL,
        number=number,
        listed_from="comparison",
        fetched_at="2026-09-17T12:00:00Z",
        reader=None,
        head="c" * 40,
        base="b" * 40,
        pages=0,
        last_page=None,
        complete=True,
        capped=False,
        truncated=False,
        marks=(),
        rows=tuple(rows),
    )


def _summed(
    repository: ListedRepository, *numbers: int, listing: frozenset[int] = frozenset()
) -> dict[int, dict[str, Any]]:
    """Each named pull request's answer, by number, checked to come in the request's order."""

    envelope = asyncio.run(files_summary(repository, listing, numbers))
    assert envelope["source"] == CANONICAL
    assert [row["number"] for row in envelope["rows"]] == list(numbers)
    return {row["number"]: dict(row) for row in envelope["rows"]}


def _absent(number: int, reason: str, *, listing: bool = False) -> dict[str, Any]:
    return {
        "number": number,
        "state": "absent",
        "reason": reason,
        "listing": listing,
        "listed_from": None,
        "generation": None,
        "head": None,
        "files": None,
        "additions": None,
        "deletions": None,
        "exact": False,
        "statuses": [],
    }


def _stamp(repository: ListedRepository, number: int) -> tuple[int, int, int]:
    status = (repository.home / source_pull_files(repository.slug, number)).stat()
    return status.st_ino, status.st_mtime_ns, status.st_size


def _write_raw(repository: ListedRepository, number: int, data: bytes) -> None:
    path = repository.home / source_pull_files(repository.slug, number)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)


# ── Sums ────────────────────────────────────────────────────────


def test_a_whole_list_is_summed_by_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: ListedRepository
) -> None:
    """Pull request 106's list, read from the fake gh's full-size pages of real items.

    The expected sums are counted here from GitHub's items themselves, not from the list
    the refresh wrote, so a refresh and a summary that agreed on a mistake would still fail.
    """

    _answer(tmp_path, monkeypatch, file_pages(TREE_PULL, tree_files()))
    listed = _refresh(repository, TREE_PULL)
    _gh_log().unlink()
    items = tree_files()
    statuses = Counter(item["status"] for item in items)
    assert sorted(statuses.items()) == [
        ("added", 3),
        ("modified", 243),
        ("removed", 1),
        ("renamed", 2),
    ]
    assert (sum(item["additions"] for item in items), sum(item["deletions"] for item in items)) == (
        1093,
        493,
    )
    assert _summed(repository, TREE_PULL)[TREE_PULL] == {
        "number": TREE_PULL,
        "state": "listed",
        "reason": None,
        "listing": False,
        "listed_from": "github",
        "generation": listed.generation,
        "head": listed.head,
        "files": 249,
        "additions": 1093,
        "deletions": 493,
        "exact": True,
        "statuses": [
            {"status": "added", "count": 3},
            {"status": "modified", "count": 243},
            {"status": "removed", "count": 1},
            {"status": "renamed", "count": 2},
        ],
    }
    assert not _gh_log().exists(), "a summary asked gh"


def test_a_count_the_local_comparison_lacks_counts_as_none_and_the_sums_are_not_exact(
    repository: ListedRepository,
) -> None:
    """A binary file in the local comparison has no line counts: it counts as none, and the
    sums say they are not exact, as a stack's do (:mod:`.pull_change_sums`). A list of no
    files sums to none of each, exactly, and is listed.
    """

    write_pull_files(
        repository.home,
        repository.slug,
        _comparison(
            7,
            [
                _row("assets/logo.png", "modified", None, None),
                _row("docs/new.md", "added", 2, 0),
                _row("src/app.txt", "modified", 3, 1),
            ],
        ),
    )
    write_pull_files(
        repository.home,
        repository.slug,
        _comparison(8, [_row("a.txt", "added", 5, None), _row("b.txt", "modified", 1, 2)]),
    )
    write_pull_files(repository.home, repository.slug, _comparison(9, []))
    summed = _summed(repository, 7, 8, 9)
    assert summed[7] == {
        "number": 7,
        "state": "listed",
        "reason": None,
        "listing": False,
        "listed_from": "comparison",
        "generation": "2" * 32,
        "head": "c" * 40,
        "files": 3,
        "additions": 5,
        "deletions": 1,
        "exact": False,
        "statuses": [{"status": "added", "count": 1}, {"status": "modified", "count": 2}],
    }
    eight = summed[8]
    assert (eight["files"], eight["additions"], eight["deletions"], eight["exact"]) == (
        2,
        6,
        2,
        False,
    )
    assert summed[9]["state"] == "listed"
    nine = summed[9]
    assert (nine["files"], nine["additions"], nine["deletions"], nine["exact"]) == (0, 0, 0, True)
    assert summed[9]["statuses"] == []


def test_a_row_sums_as_a_stack_of_one_does(repository: ListedRepository) -> None:
    """One list summed as a stack's members are (:func:`.pull_change_sums.accumulate`): a
    copy is added, a changed or unchanged file is modified, and the sums are that function's
    of the one list, so a stack of one pull request says what its row says."""

    from metabrowser.builtin_plugins.github.pull_change_sums import accumulate

    listed = _github(
        11,
        [
            _row("a.txt", "added", 4, 0),
            _row("b.txt", "copied", 2, 0),
            _row("c.txt", "changed", 0, 0),
            _row("d.txt", "unchanged", 0, 0),
            _row("e.txt", "removed", 0, 9),
            PullFileRow(
                path="g.txt", previous_path="f.txt", status="renamed", additions=1, deletions=1
            ),
            _row("h.txt", "modified", 3, 2),
        ],
    )
    write_pull_files(repository.home, repository.slug, listed)
    row = _summed(repository, 11)[11]
    assert row["statuses"] == [
        {"status": "added", "count": 2},
        {"status": "modified", "count": 3},
        {"status": "removed", "count": 1},
        {"status": "renamed", "count": 1},
    ]
    sums = accumulate([listed])
    assert (row["files"], row["additions"], row["deletions"], row["exact"]) == (
        sums.files,
        sums.additions,
        sums.deletions,
        sums.exact,
    )
    assert [(entry["status"], entry["count"]) for entry in row["statuses"]] == list(sums.statuses)


def test_a_sum_is_kept_by_its_files_stamp_and_read_again_once_replaced(
    repository: ListedRepository, reads: list[int]
) -> None:
    """A list read once is a stat after; an atomic replacement, a new inode, is read again."""

    write_pull_files(repository.home, repository.slug, _github(5, [_row("a.md")]))
    first = _summed(repository, 5)
    assert reads == [5] and first[5]["files"] == 1
    reads.clear()
    assert _summed(repository, 5) == first
    assert reads == [], "a list unchanged since it was summed was parsed again"
    before = _stamp(repository, 5)
    write_pull_files(
        repository.home, repository.slug, _github(5, [_row("a.md"), _row("b.md", "added", 7, 0)])
    )
    assert _stamp(repository, 5)[0] != before[0], "the write did not replace the file"
    replaced = _summed(repository, 5)
    assert reads == [5]
    assert (replaced[5]["files"], replaced[5]["additions"]) == (2, 8)
    # The same bytes written again are a new file all the same, and are read again.
    reads.clear()
    write_pull_files(
        repository.home, repository.slug, _github(5, [_row("a.md"), _row("b.md", "added", 7, 0)])
    )
    assert _summed(repository, 5) == replaced and reads == [5]


# ── Absences ────────────────────────────────────────────────────


def test_each_list_that_sums_to_nothing_says_why(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: ListedRepository,
    reads: list[int],
) -> None:
    """Every reason a summary gives no sums, each from a list file as the cache holds it.

    The truncated list is the product's own: GitHub's page names a path past its bound,
    which the refresh leaves out and says so. A list still filling is kept by its stamp like
    any other, and summed once its last page replaces it.
    """

    long = "d/" + "\x01" * (MAX_FILE_PATH_BYTES // 6 + 1)
    _answer(tmp_path, monkeypatch, file_pages(6, [file_item("a.md"), file_item(long)]))
    assert _refresh(repository, 6).truncated
    _write_raw(repository, 2, json.dumps({"schema_version": PULL_FILES_SCHEMA - 1}).encode())
    _write_raw(repository, 3, b"{not json")
    rows = [_row(f"f{index:03d}.txt") for index in range(100)]
    write_pull_files(
        repository.home, repository.slug, _github(4, rows, complete=False, last_page=3)
    )
    write_pull_files(repository.home, repository.slug, _github(5, rows, capped=True))
    _gh_log().unlink()
    summed = _summed(repository, 1, 2, 3, 4, 5, 6)
    assert summed == {
        1: _absent(1, "not_cached"),
        2: _absent(2, "schema_mismatch"),
        3: _absent(3, "unreadable"),
        4: _absent(4, "filling"),
        5: _absent(5, "too_large"),
        6: _absent(6, "too_large"),
    }
    assert reads == [2, 3, 4, 5, 6], "a pull request with no list file was read"
    reads.clear()
    # Kept by its stamp too, a list of another schema or one that cannot be read included,
    # so it does not hold every later list of a request past the budget, request after request.
    assert _summed(repository, 2, 3, 4, 5, 6) == {n: summed[n] for n in (2, 3, 4, 5, 6)}
    assert reads == [], "a list that sums to nothing was parsed again unchanged"
    write_pull_files(repository.home, repository.slug, _github(4, [*rows, _row("last.txt")]))
    filled = _summed(repository, 4)[4]
    assert (filled["state"], filled["files"], reads) == ("listed", 101, [4])
    assert not _gh_log().exists(), "a summary asked gh"


def test_past_the_requests_byte_budget_the_rest_is_deferred(
    repository: ListedRepository, reads: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first list is read whatever its size; past the budget the rest wait for the next.

    With a budget of one byte, each request reads exactly one list it has not summed, and
    each kept one is a stat, so three requests sum three lists. A pull request with no list
    file costs nothing and is never deferred.
    """

    for number in (1, 2, 3):
        write_pull_files(repository.home, repository.slug, _github(number, [_row("a.md")]))
    whole = _summed(repository, 1, 2, 3)
    assert reads == [1, 2, 3], "the real budget did not read three small lists in one request"
    clear_kept_summaries()
    reads.clear()
    monkeypatch.setattr(pull_files_summary, "MAX_SUMMARY_BYTES", 1)
    first = _summed(repository, 1, 2, 3, 4)
    assert reads == [1]
    assert first == {
        1: whole[1],
        2: _absent(2, "deferred"),
        3: _absent(3, "deferred"),
        4: _absent(4, "not_cached"),
    }
    reads.clear()
    second = _summed(repository, 1, 2, 3, 4)
    assert reads == [2] and second[2] == whole[2] and second[3] == _absent(3, "deferred")
    reads.clear()
    third = _summed(repository, 1, 2, 3, 4)
    assert reads == [3] and [third[n] for n in (1, 2, 3)] == [whole[n] for n in (1, 2, 3)]
    reads.clear()
    assert _summed(repository, 1, 2, 3, 4) == third and reads == []


def test_the_sums_kept_are_bounded_least_recently_used_out_first(
    repository: ListedRepository, reads: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pull_files_summary, "MAX_KEPT_SUMMARIES", 2)
    for number in (1, 2, 3):
        write_pull_files(repository.home, repository.slug, _github(number, [_row("a.md")]))

    def read_for(number: int) -> list[int]:
        reads.clear()
        _summed(repository, number)
        return list(reads)

    assert [read_for(n) for n in (1, 2)] == [[1], [2]]
    # 1 used again is the most recent, so 3 puts out 2, the least recent.
    assert read_for(1) == []
    assert read_for(3) == [3]
    assert read_for(1) == []
    assert read_for(2) == [2]
    assert read_for(3) == [3]
    assert len(pull_files_summary._KEPT) == 2  # pyright: ignore[reportPrivateUsage]


# ── Requests ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("1", (1,)),
        ("3,1,2", (3, 1, 2)),
        (str(MAX_PULL_REQUEST_NUMBER), (MAX_PULL_REQUEST_NUMBER,)),
        (
            ",".join(str(n) for n in range(1, MAX_SUMMARY_NUMBERS + 1)),
            tuple(range(1, MAX_SUMMARY_NUMBERS + 1)),
        ),
    ],
)
def test_a_request_names_its_pull_requests_in_its_order(
    text: str, numbers: tuple[int, ...]
) -> None:
    assert summary_numbers({"numbers": text}) == numbers


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"number": "1"},
        {"numbers": "1", "extra": "1"},
        {"numbers": ""},
        {"numbers": "0"},
        {"numbers": "01"},
        {"numbers": "-1"},
        {"numbers": "+1"},
        {"numbers": "1.0"},
        {"numbers": "x"},
        {"numbers": " 1"},
        {"numbers": "1, 2"},
        {"numbers": "1,"},
        {"numbers": ",1"},
        {"numbers": "1,,2"},
        {"numbers": "1;2"},
        # A pattern's ``$`` matches before a last newline.
        {"numbers": "1\n"},
        {"numbers": "1,2\n"},
        # An Arabic-Indic one, which ``\\d`` would take for a digit.
        {"numbers": "١"},
        {"numbers": "1,1"},
        {"numbers": "1,2,1"},
        {"numbers": ",".join(str(n) for n in range(1, MAX_SUMMARY_NUMBERS + 2))},
        {"numbers": str(MAX_PULL_REQUEST_NUMBER + 1)},
    ],
)
def test_a_request_outside_its_shape_is_refused(params: dict[str, str]) -> None:
    with pytest.raises(SummaryRequestError):
        summary_numbers(params)


# ── The route ───────────────────────────────────────────────────


def _get(client: TestClient, numbers: str, **headers: str) -> Any:
    return client.get(ROUTE, params={"numbers": numbers}, headers=headers)


def _rows(client: TestClient, numbers: str) -> dict[int, dict[str, Any]]:
    response = _get(client, numbers)
    assert response.status_code == 200, response.text
    return {row["number"]: row for row in response.json()["rows"]}


def test_the_route_answers_from_the_cache_with_its_tag_and_starts_no_process(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The served mirror's lists summed through the app: no gh, no Git, no process at all."""

    stand, client = pinned_pull
    home, slug = stand.published.home, stand.published.slug
    write_pull_files(home, slug, _github(106, [_row("a.md"), _row("b.md", "added", 4, 0)]))
    stand.calls()
    spawned = _spawned(monkeypatch)
    first = _get(client, "106,104")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    body = first.json()
    assert body["source"] == CANONICAL
    assert [(row["number"], row["state"], row["reason"]) for row in body["rows"]] == [
        (106, "listed", None),
        (104, "absent", "not_cached"),
    ]
    assert body["rows"][0]["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    again = _get(client, "106,104")
    assert again.content == first.content and again.headers["etag"] == first.headers["etag"]
    unchanged = _get(client, "106,104", **{"if-none-match": first.headers["etag"]})
    assert (unchanged.status_code, unchanged.content) == (304, b"")
    assert unchanged.headers["etag"] == first.headers["etag"]
    # Another order is another answer.
    assert _get(client, "104,106").headers["etag"] != first.headers["etag"]
    write_pull_files(home, slug, _github(106, [_row("a.md")]))
    moved = _get(client, "106,104", **{"if-none-match": first.headers["etag"]})
    assert moved.status_code == 200 and moved.headers["etag"] != first.headers["etag"]
    assert moved.json()["rows"][0]["files"] == 1
    assert spawned == [], f"a summary started a process: {spawned}"
    assert stand.calls() == [], "a summary asked GitHub"


def test_the_route_refuses_a_request_outside_its_shape(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    stand.calls()
    spawned = _spawned(monkeypatch)
    too_many = ",".join(str(n) for n in range(1, MAX_SUMMARY_NUMBERS + 2))
    for query in (
        {},
        {"numbers": "106", "extra": "1"},
        {"numbers": "106,x"},
        {"numbers": "106,106"},
        {"numbers": too_many},
        {"numbers": str(MAX_PULL_REQUEST_NUMBER + 1)},
    ):
        response = client.get(ROUTE, params=query)
        assert response.status_code == 400, query
        assert response.json()["code"] == "invalid_request", query
    # A parameter named twice would be read as its last value alone.
    twice = client.get(f"{ROUTE}?numbers=106&numbers=105")
    assert (twice.status_code, twice.json()["code"]) == (400, "invalid_request")
    # A number as long as GitHub's grammar allows is a pull request the cache has no list of.
    assert _rows(client, str(MAX_PULL_REQUEST_NUMBER)) == {
        MAX_PULL_REQUEST_NUMBER: _absent(MAX_PULL_REQUEST_NUMBER, "not_cached")
    }
    assert spawned == [] and stand.calls() == []


def test_listing_says_a_refresh_runs_or_the_prefetch_lane_holds_one(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``listing`` is read from memory: the coordinator's files job, and the lane's items.

    The refresh runs through ``POST pull-files-refresh``, its work held at a gate, so the
    coordinator holds the job under the key the route asks it of. The lane is the served
    repository's own (:func:`lane_of`), with an item queued or running; a record item is not
    a list's, and says nothing.
    """

    stand, client = pinned_pull
    stand.calls()
    lane = lane_of(pull_host(app).pulls)  # pyright: ignore[reportOptionalMemberAccess]
    assert _rows(client, "104,103") == {
        104: _absent(104, "not_cached"),
        103: _absent(103, "not_cached"),
    }
    idle = _get(client, "104,103").headers["etag"]
    lane.queue.extend([Item("files", 104), Item("record", 103)])
    try:
        held = _get(client, "104,103")
        assert [row["listing"] for row in held.json()["rows"]] == [True, False]
        assert held.headers["etag"] != idle
    finally:
        lane.queue.clear()
    lane.running = Item("files", 103)
    try:
        assert _rows(client, "104,103")[103]["listing"] is True
    finally:
        lane.running = None
    assert [row["listing"] for row in _rows(client, "104,103").values()] == [False, False]

    gate = threading.Event()

    async def waiting(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.to_thread(gate.wait, 30)

    monkeypatch.setattr(pull_files_refresh, "refresh_pull_files", waiting)
    try:
        started = client.post(REFRESH, json={"number": 104}, headers=JSON_BODY)
        assert started.status_code == 202 and started.json()["refresh"] == "started"
        assert _rows(client, "104,103")[104] == _absent(104, "not_cached", listing=True)
    finally:
        gate.set()
    deadline = time.monotonic() + 30
    while _rows(client, "104")[104]["listing"]:
        assert time.monotonic() < deadline, "the held refresh did not end"
        time.sleep(0.02)
    assert _get(client, "104,103").headers["etag"] == idle
    assert stand.calls() == [], "listing asked GitHub"


def test_without_a_github_repository_there_is_nothing_to_sum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import server

    assert asyncio.run(files_summary(None, frozenset(), (1, 2))) == {"source": None, "rows": []}
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    plain = tmp_path / "plain"
    plain.mkdir()
    server._set_root_dir(plain)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        spawned = _spawned(monkeypatch)
        response = _get(client, "106,7")
        assert response.status_code == 200
        assert response.json() == {"source": None, "rows": []}
        assert (
            _get(client, "106,7", **{"if-none-match": response.headers["etag"]}).status_code == 304
        )
        assert client.get(ROUTE, params={"numbers": "106", "extra": "1"}).status_code == 400
    assert spawned == [], f"a summary with no repository started a process: {spawned}"


# ── The recording the Pulls tab's session replays ──────────────

RECORDING = "github-pull-files-summary-responses.json"
# The tryscript golden that pins the browserless session reading the recording; the name is
# only the hint a stale recording prints.
TRANSCRIPT = "cli-ui-github-pulls-row-lines.tryscript.md"


def _recorded(response: Any) -> dict[str, Any]:
    """One answer as the Pulls tab sees it: its status and body, its tag left out, which is
    scoped to the build."""

    return {"status": response.status_code, "body": response.json()}


def _refreshed(client: TestClient, number: int, *, retry: bool = False) -> None:
    """Pull request *number*'s list through the product's own refresh, to its end. *retry* is
    a reader's own Retry, which starts one within the window a failure holds."""

    body: dict[str, Any] = {"number": number, **({"retry": True} if retry else {})}
    started = client.post(REFRESH, json=body, headers=JSON_BODY)
    assert started.status_code == 202, started.text
    deadline = time.monotonic() + 50
    while client.get(FILES, params={"number": number, "limit": 0}).json()["refreshing"]:
        assert time.monotonic() < deadline, f"the refresh of {number}'s list did not end"
        time.sleep(0.02)


def test_recording_pull_files_summary_answers_real_routes(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the route answers for the four stories the Pulls row's change line tells.

    ``summed`` names 106, GitHub's list of the stand-in's tree of 249 files in four statuses;
    105, a list of one file; 104, of which nothing is cached; and 103, whose list stopped at
    its third page, so it holds 200 of its 249 files and is ``filling``. Each list is read by
    ``POST pull-files-refresh`` from the fake gh's full-size pages of real items. ``listing``
    is 104 while the prefetch lane holds a files item for it; ``relisted`` is 104 and 103 once
    their lists are read, 104's a list of two files and 103's read again to its end;
    ``refused`` a request that names more than its pull requests, and ``not_github`` a server
    with no GitHub repository.
    """

    from metabrowser import server
    from metabrowser.mirror_refresh import serve_mirror
    from tests.golden_harness import check_recording

    stand, client = pinned_pull
    generations = count(1)
    monkeypatch.setattr(pull_files_refresh, "uuid4", lambda: UUID(int=next(generations)))
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    answers = scenario(stand.origin)
    pages = {
        **file_pages(106, tree_files()),
        **file_pages(105, [file_item("CHANGELOG.md", "modified", None, 3, 1)]),
        **file_pages(103, tree_files()),
        files_page(103, 3): {"status": 502, "body": {"message": "Server Error"}},
    }
    stand.answer({**answers, "api": {**answers["api"], **pages}})
    for number in (106, 105, 103):
        _refreshed(client, number)
    stand.calls()
    spawned = _spawned(monkeypatch)
    recorded = {"summed": _recorded(_get(client, "106,105,104,103"))}
    rows = recorded["summed"]["body"]["rows"]
    assert [(row["number"], row["state"], row["reason"]) for row in rows] == [
        (106, "listed", None),
        (105, "listed", None),
        (104, "absent", "not_cached"),
        (103, "absent", "filling"),
    ]
    assert (rows[0]["files"], rows[0]["additions"], rows[0]["deletions"]) == (249, 1093, 493)
    assert (rows[1]["files"], rows[1]["additions"], rows[1]["deletions"]) == (1, 3, 1)
    lane = lane_of(pull_host(app).pulls)  # pyright: ignore[reportOptionalMemberAccess]
    lane.queue.append(Item("files", 104))
    try:
        recorded["listing"] = _recorded(_get(client, "104"))
    finally:
        lane.queue.clear()
    assert recorded["listing"]["body"]["rows"] == [_absent(104, "not_cached", listing=True)]
    assert spawned == [], f"a summary started a process: {spawned}"
    assert stand.calls() == [], "a summary asked GitHub"
    # The lane lists 104, and 103's list is read again to its end.
    relisted_pages = {
        **pages,
        **file_pages(
            104,
            [
                file_item("docs/new.md", "added", None, 12, 0),
                file_item("src/app.txt", "modified", None, 4, 2),
            ],
        ),
        files_page(103, 3): file_pages(103, tree_files())[files_page(103, 3)],
    }
    stand.answer({**answers, "api": {**answers["api"], **relisted_pages}})
    _refreshed(client, 104)
    _refreshed(client, 103, retry=True)
    stand.calls()
    spawned.clear()
    recorded["relisted"] = _recorded(_get(client, "104,103"))
    relisted = recorded["relisted"]["body"]["rows"]
    assert [(row["number"], row["state"], row["files"]) for row in relisted] == [
        (104, "listed", 2),
        (103, "listed", 249),
    ]
    recorded["refused"] = _recorded(client.get(ROUTE, params={"numbers": "106", "extra": "1"}))
    assert recorded["refused"]["status"] == 400
    assert spawned == [], f"a summary started a process: {spawned}"
    assert stand.calls() == [], "a summary asked GitHub"
    server._set_root_dir(stand.tmp_path / "plain")  # pyright: ignore[reportPrivateUsage]
    (stand.tmp_path / "plain").mkdir()
    serve_mirror(None)
    with TestClient(server.app) as plain:
        recorded["not_github"] = _recorded(_get(plain, "106,105,104,103"))
    assert recorded["not_github"]["body"] == {"source": None, "rows": []}
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)
