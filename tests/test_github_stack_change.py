"""A native stack's combined change: its members' own changes, accumulated (mb-9ekj).

The Pulls tab's stack heading says it as a brief change line, so the route that accumulates
it is held here to the rule it composes each file's status by, to its cache, and to every
refusal it answers. A stack's members are its pull requests, and each member's change is
its cached list of changed files, the one its expanded row shows: the stand-in's pull
request 7 adds ``docs/new.md`` and edits ``src/app.txt``, and 11, above it, edits both again,
so summing the two layers' own counts would say four files where the stack changes two.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import pull_change_sums, pull_list, pull_stack_change
from metabrowser.builtin_plugins.github.pull_list import (
    PULL_FILES_SCHEMA,
    FilePageMark,
    ListedRepository,
    PullFileList,
    PullFileRow,
    write_pull_files,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.builtin_plugins.github.pull_stacks import (
    NativeStack,
    StackPage,
    StackSnapshot,
    publish_stacks,
    read_stacks,
)
from metabrowser.git import process as git_process
from tests.github_pull_fixture import DEFAULT_BRANCH
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand

ROUTE = "/api/plugin/github/stack-change"
STAMP = "2026-09-17T12:00:00Z"


def _repository(stand: _Stand) -> ListedRepository:
    return ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")


def _publish(stand: _Stand, *stacks: tuple[int, tuple[int, ...]]) -> None:
    repository = _repository(stand)
    snapshot = StackSnapshot(
        source=repository.source,
        reader="gh:octo-reader",
        fetched_at=STAMP,
        complete=True,
        pages=(
            StackPage(
                etag=None,
                has_next=False,
                stacks=tuple(
                    NativeStack(number=number, base_ref=DEFAULT_BRANCH, open=True, pulls=pulls)
                    for number, pulls in stacks
                ),
            ),
        ),
    )
    stamp = PullRefreshStamp(outcome="succeeded", at=STAMP, reader="gh:octo-reader")
    assert publish_stacks(repository, read_stacks(repository), snapshot, stamp)


def _row(
    path: str,
    status: pull_list.FileStatus,
    additions: int | None,
    deletions: int | None = 0,
    previous: str | None = None,
) -> PullFileRow:
    return PullFileRow(
        path=path, previous_path=previous, status=status, additions=additions, deletions=deletions
    )


def _listed(number: int, *rows: PullFileRow, truncated: bool = False) -> PullFileList:
    """Pull request *number*'s list as its local comparison's refresh writes it."""

    return PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        source="https://github.com/octo/demo",
        number=number,
        listed_from="comparison",
        generation=f"{number:032x}",
        fetched_at=STAMP,
        reader=None,
        head=f"{number:040x}",
        base="f" * 40,
        pages=0,
        last_page=None,
        complete=True,
        capped=False,
        truncated=truncated,
        marks=(),
        rows=rows,
    )


def _from_github(
    number: int, *rows: PullFileRow, complete: bool = True, capped: bool = False
) -> PullFileList:
    """Pull request *number*'s list as GitHub's refresh writes it, one page."""

    return PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        source="https://github.com/octo/demo",
        number=number,
        listed_from="github",
        generation=f"{number:032x}",
        fetched_at=STAMP,
        reader="gh:octo-reader",
        head=f"{number:040x}",
        base_ref=DEFAULT_BRANCH,
        pages=1,
        last_page=2 if not complete else 1,
        complete=complete,
        capped=capped,
        truncated=False,
        marks=(FilePageMark(etag=None, rows=len(rows), places=len(rows), truncated=False),),
        rows=rows,
    )


def _cache(stand: _Stand, listed: PullFileList) -> None:
    write_pull_files(stand.published.home, stand.published.slug, listed)


@pytest.fixture
def stacked(pinned_pull: tuple[_Stand, TestClient]) -> Iterator[tuple[_Stand, TestClient]]:
    """Pull requests 7 and 11's lists cached, and stacks #286 of the two, #300 of 7 alone,
    and #400 of 7 and 12, whose list nothing has fetched."""

    stand, client = pinned_pull
    _cache(stand, _listed(7, _row("docs/new.md", "added", 1), _row("src/app.txt", "modified", 1)))
    _cache(
        stand, _listed(11, _row("docs/new.md", "modified", 2), _row("src/app.txt", "modified", 1))
    )
    _publish(stand, (286, (7, 11)), (300, (7,)), (400, (7, 12)))
    # What fetching pull request 7 asked of GitHub; from here on nothing may.
    stand.calls()
    yield stand, client


def _no_git(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    spawned: list[tuple[str, ...]] = []
    real = git_process.spawn_git_process

    async def counted(args: Any, **kwargs: Any) -> Any:
        spawned.append(tuple(args))
        return await real(args, **kwargs)

    monkeypatch.setattr(git_process, "spawn_git_process", counted)
    return spawned


def test_a_stacks_change_is_its_members_changes_accumulated(
    stacked: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = stacked
    spawned = _no_git(monkeypatch)
    response = client.get(ROUTE, params={"number": 286})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    revision = body.pop("revision")
    assert isinstance(revision, str) and len(revision) == 32
    # Each file once: 7 added docs/new.md and 11 edited it, so it is added; both edited
    # src/app.txt. The lines are each layer's own, summed.
    assert body == {
        "state": "current",
        "reason": None,
        "number": 286,
        "pulls": [7, 11],
        "files": 2,
        "additions": 5,
        "deletions": 0,
        "exact": True,
        "statuses": [{"status": "added", "count": 1}, {"status": "modified", "count": 1}],
    }
    # A stack of one pull request is that pull request's own list.
    alone = client.get(ROUTE, params={"number": 300}).json()
    assert (alone["pulls"], alone["files"], alone["additions"]) == ([7], 2, 2)
    assert alone["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    assert spawned == [], f"a stack change ran Git: {spawned}"
    assert stand.calls() == [], "a stack change asked GitHub"


def test_each_file_counts_once_with_its_composed_status() -> None:
    """The rule the module states, file by file, with the layers bottom first."""

    sums = pull_change_sums.accumulate(
        [
            _listed(
                1,
                _row("added-then-edited", "added", 3),
                _row("edited-then-removed", "modified", 1, 1),
                _row("added-then-removed", "added", 2),
                _row("old-name", "modified", 1),
                _row("added-then-moved", "added", 4),
                _row("removed-then-added", "removed", 0, 5),
                _row("edited-twice", "modified", 1, 1),
                _row("binary", "modified", None, None),
            ),
            _listed(
                2,
                _row("added-then-edited", "modified", 1, 1),
                _row("edited-then-removed", "removed", 0, 9),
                _row("added-then-removed", "removed", 0, 2),
                _row("new-name", "renamed", 0, 0, previous="old-name"),
                _row("moved-there", "renamed", 1, 0, previous="added-then-moved"),
                _row("removed-then-added", "added", 6),
                _row("edited-twice", "modified", 2, 0),
            ),
        ]
    )
    # A rename carries the file to its new path: old-name and added-then-moved are gone.
    assert sums.files == 8
    assert dict(sums.statuses) == {
        # added-then-edited, moved-there (added, then renamed)
        "added": 2,
        # edited-then-removed, added-then-removed
        "removed": 2,
        # new-name
        "renamed": 1,
        # removed-then-added, edited-twice, binary
        "modified": 3,
    }
    # Each layer's own lines, summed: the first layer's 12 and 7, the second's 10 and 12.
    assert (sums.additions, sums.deletions) == (12 + 10, 7 + 12)
    # The binary file's list has no line counts, so the totals are not exact.
    assert sums.exact is False
    assert not sums.short
    # A list that stops short makes the accumulation short.
    assert pull_change_sums.accumulate([_from_github(1, _row("a", "added", 1), capped=True)]).short


def test_a_stacks_change_is_accumulated_once_and_validated(
    stacked: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = stacked
    monkeypatch.setattr(pull_stack_change, "_KEPT", type(pull_stack_change._KEPT)())  # pyright: ignore[reportPrivateUsage]
    parsed: list[int] = []
    real = pull_list.read_pull_files

    def counted(home: Path, slug: str, number: int, **kwargs: Any) -> Any:
        parsed.append(number)
        return real(home, slug, number, **kwargs)

    monkeypatch.setattr(pull_list, "read_pull_files", counted)
    first = client.get(ROUTE, params={"number": 286})
    assert first.status_code == 200 and parsed == [7, 11]
    parsed.clear()
    again = client.get(ROUTE, params={"number": 286})
    assert again.content == first.content
    assert parsed == [], "a repeated stack change read its lists again"
    assert again.headers["etag"] == first.headers["etag"]
    unchanged = client.get(
        ROUTE, params={"number": 286}, headers={"if-none-match": first.headers["etag"]}
    )
    assert unchanged.status_code == 304 and unchanged.content == b""
    # A member whose list is refreshed names another accumulation, which is read afresh.
    _cache(stand, _listed(11, _row("src/app.txt", "removed", 0, 3)))
    moved = client.get(ROUTE, params={"number": 286}).json()
    assert parsed == [7, 11]
    assert moved["statuses"] == [{"status": "added", "count": 1}, {"status": "removed", "count": 1}]
    assert moved["revision"] != first.json()["revision"]
    assert client.get(ROUTE, params={"number": 286, "extra": "1"}).status_code == 400
    assert client.get(ROUTE).status_code == 400
    assert client.get(ROUTE, params={"number": "x"}).status_code == 400


def test_a_stack_whose_change_cannot_be_had_says_why(
    stacked: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = stacked

    def reason(number: int) -> Any:
        body = client.get(ROUTE, params={"number": number}).json()
        assert body["state"] == "absent" and body["statuses"] == [] and body["files"] is None
        assert body["pulls"] == [] and body["revision"] is None
        return body["reason"]

    assert reason(999) == "not_stacked"
    # Pull request 12 has no list.
    assert reason(400) == "not_cached"
    # Its list is filling: GitHub's next page is not read yet.
    _cache(stand, _from_github(12, _row("docs/more.md", "added", 1), complete=False))
    assert reason(400) == "not_cached"
    # Whole, it is accumulated.
    _cache(stand, _from_github(12, _row("docs/more.md", "added", 1)))
    assert client.get(ROUTE, params={"number": 400}).json()["files"] == 3
    # GitHub's most for one pull request, or a list that left a file out, is short.
    _cache(stand, _from_github(12, _row("docs/more.md", "added", 1), capped=True))
    assert reason(400) == "too_large"
    _cache(stand, _listed(12, _row("docs/more.md", "added", 1), truncated=True))
    assert reason(400) == "too_large"
    # And so are members' lists that together pass the bound, before any is read.
    monkeypatch.setattr(pull_stack_change, "MAX_STACK_LIST_BYTES", 100)
    assert reason(286) == "too_large"
    assert stand.calls() == [], "a stack change asked GitHub"


def test_a_stack_change_without_a_github_repository_is_not_github(tmp_path: Path) -> None:
    from metabrowser import server

    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        response = client.get(ROUTE, params={"number": 286})
    assert response.status_code == 200
    assert response.json()["reason"] == "not_github"
    assert asyncio.run(pull_stack_change.stack_change(None, 286))["reason"] == "not_github"


RECORDING = "github-stack-change-responses.json"
TRANSCRIPT = "cli-ui-github-pulls-stack-lines.tryscript.md"


def _recorded(response: Any) -> dict[str, Any]:
    """One answer as the Pulls tab sees it: its status and body, its tag left out, which is
    scoped to the build."""

    return {"status": response.status_code, "body": response.json()}


def test_recording_stack_change_answers_real_routes(
    stacked: tuple[_Stand, TestClient],
) -> None:
    """``tests/dom/github-pulls-stack-lines-session.js`` replays what the route answers.

    The stacks are numbered as the recorded stack snapshot's shared answer numbers them
    (``github-stacks-responses.json``), #286 and #290, so the session's headings and its
    answers name the same stacks: #286's change is the two layers above, and #290 has a
    member with no list. A server with no GitHub repository refuses every stack.
    """

    from metabrowser import server
    from metabrowser.mirror_refresh import serve_mirror
    from tests.golden_harness import check_recording

    stand, client = stacked
    _publish(stand, (286, (7, 11)), (290, (7, 12)))
    recorded = {
        "current": _recorded(client.get(ROUTE, params={"number": 286})),
        "not_cached": _recorded(client.get(ROUTE, params={"number": 290})),
        "not_stacked": _recorded(client.get(ROUTE, params={"number": 999})),
    }
    assert recorded["current"]["body"]["state"] == "current"
    assert recorded["not_cached"]["body"]["reason"] == "not_cached"
    server._set_root_dir(stand.tmp_path / "plain")  # pyright: ignore[reportPrivateUsage]
    (stand.tmp_path / "plain").mkdir()
    serve_mirror(None)
    with TestClient(server.app) as plain:
        recorded["not_github"] = _recorded(plain.get(ROUTE, params={"number": 286}))
    assert recorded["not_github"]["body"]["reason"] == "not_github"
    assert stand.calls() == [], "a stack change asked GitHub"
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)
