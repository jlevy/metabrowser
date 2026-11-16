"""A native stack's combined change: its top's head against its base branch (mb-9ekj).

The Pulls tab's stack heading says it as a brief change line, so the route that sums it is
held here to the comparison it names, to its cache, and to every refusal it answers. The
stand-in's pull request 7 is the stack's bottom, and its top, 11, is one commit on 7's head
that changes the same two files again: summing the two layers' own counts would say four
files where the stack changes two. The stack's base is the stand-in's default branch,
``topic``, which the store mirrors; its change runs from where the top's head meets it.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import pull_route, pull_stack_change
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    Comparison,
    PullRecord,
    PullRefreshStamp,
    read_pull_record,
    write_pull_record,
)
from metabrowser.builtin_plugins.github.pull_route import PullHost
from metabrowser.builtin_plugins.github.pull_stacks import (
    NativeStack,
    StackPage,
    StackSnapshot,
    publish_stacks,
    read_stacks,
)
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.git import process as git_process
from tests.github_pull_fixture import DEFAULT_BRANCH, git_env
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand

ROUTE = "/api/plugin/github/stack-change"
STAMP = "2026-09-17T12:00:00Z"


def _repository(stand: _Stand) -> ListedRepository:
    return ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")


def _publish(
    stand: _Stand, *stacks: tuple[int, tuple[int, ...]], base_ref: str = DEFAULT_BRANCH
) -> None:
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
                    NativeStack(number=number, base_ref=base_ref, open=True, pulls=pulls)
                    for number, pulls in stacks
                ),
            ),
        ),
    )
    stamp = PullRefreshStamp(outcome="succeeded", at=STAMP, reader="gh:octo-reader")
    assert publish_stacks(repository, read_stacks(repository), snapshot, stamp)


def _commit_on(
    stand: _Stand, parent: str, files: dict[str, str], ref: str = "refs/test/stack-top"
) -> str:
    """One commit on *parent* in the store, as a fetch of a newer layer would leave it."""

    stream = f"commit {ref}\n"
    stream += "committer Origin <origin@example.invalid> 1789000000 +0000\n"
    stream += f"data 9\nstack top\nfrom {parent}\n"
    for name, body in files.items():
        stream += f"M 100644 inline {name}\ndata {len(body.encode())}\n{body}\n"
    git_dir = stand.published.git_dir
    subprocess.run(
        ["git", "--git-dir", str(git_dir), "fast-import", "--quiet"],
        check=True,
        capture_output=True,
        input=stream.encode(),
        env=git_env(stand.tmp_path),
    )
    return subprocess.run(
        ["git", "--git-dir", str(git_dir), "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(stand.tmp_path),
    ).stdout.strip()


def _layer(stand: _Stand, bottom: PullRecord, number: int, base: str, head: str) -> PullRecord:
    """A record of the layer *number* above *bottom*: its comparison runs *base* to *head*."""

    record = bottom.model_copy(
        update={
            "number": number,
            "pull": bottom.pull.model_copy(update={"number": number}),
            "comparison": Comparison(base=base, head=head, base_commit=base, base_from="base_sha"),
        }
    )
    return write_pull_record(stand.published.home, stand.published.slug, record)


@pytest.fixture
def stacked(pinned_pull: tuple[_Stand, TestClient]) -> Iterator[tuple[_Stand, TestClient, str]]:
    """Pull request 7, and 11 on its head, a stack #286 of the two, bottom first."""

    stand, client = pinned_pull
    bottom = stand.record(7)
    assert isinstance(bottom, PullRecord) and bottom.comparison is not None
    fork_head = stand.origin["fork_head"]
    assert bottom.comparison.head == fork_head
    top = _commit_on(
        stand, fork_head, {"src/app.txt": "one\ntwo\nthree\n", "docs/new.md": "# New\n\nMore.\n"}
    )
    _layer(stand, bottom, 11, fork_head, top)
    _publish(stand, (286, (7, 11)), (300, (7,)), (400, (7, 12)))
    # What fetching pull request 7 asked of GitHub; from here on nothing may.
    stand.calls()
    yield stand, client, top


def _git(stand: _Stand, *args: str) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(stand.published.git_dir), *args],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(stand.tmp_path),
    ).stdout


def test_a_stacks_change_is_its_tops_head_against_its_base_branch(
    stacked: tuple[_Stand, TestClient, str],
) -> None:
    stand, client, top = stacked
    bottom = stand.record(7)
    assert isinstance(bottom, PullRecord) and bottom.comparison is not None
    # Where the top's head meets the base branch the store mirrors.
    meets = _git(stand, "merge-base", f"refs/remotes/origin/{DEFAULT_BRANCH}", top).strip()
    assert meets == bottom.comparison.base
    response = client.get(ROUTE, params={"number": 286})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body == {
        "state": "current",
        "reason": None,
        "number": 286,
        "bottom": 7,
        "top": 11,
        "base": meets,
        "head": top,
        "fresh_for_s": 300.0,
        "files": 2,
        "additions": 5,
        "deletions": 0,
        "exact": True,
        "statuses": [{"status": "added", "count": 1}, {"status": "modified", "count": 1}],
    }
    # Git's own count of the same comparison, from the merge base.
    stat = _git(stand, "diff", "--numstat", f"{bottom.comparison.base}...{top}")
    assert sorted(line.split("\t")[2] for line in stat.splitlines()) == [
        "docs/new.md",
        "src/app.txt",
    ]
    assert sum(int(line.split("\t")[0]) for line in stat.splitlines()) == body["additions"]
    # Each layer's own change touches both files: summing them would say four files.
    for base, head in (
        (bottom.comparison.base, stand.origin["fork_head"]),
        (stand.origin["fork_head"], top),
    ):
        assert len(_git(stand, "diff", "--name-only", f"{base}...{head}").split()) == 2
    # A stack of one pull request is that pull request's own comparison.
    alone = client.get(ROUTE, params={"number": 300}).json()
    assert (alone["base"], alone["head"]) == (bottom.comparison.base, bottom.comparison.head)
    assert alone["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    assert stand.calls() == [], "a stack change asked GitHub"


def _listings(spawned: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The Git processes that listed a comparison, of those *spawned*."""

    return [args for args in spawned if "diff" in args]


def test_a_stacks_change_is_summed_once_and_validated(
    stacked: tuple[_Stand, TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client, _top = stacked
    monkeypatch.setattr(pull_stack_change, "_KEPT", type(pull_stack_change._KEPT)())  # pyright: ignore[reportPrivateUsage]
    spawned: list[tuple[str, ...]] = []
    real = git_process.spawn_git_process

    async def counted(args: Any, **kwargs: Any) -> Any:
        spawned.append(tuple(args))
        return await real(args, **kwargs)

    monkeypatch.setattr(git_process, "spawn_git_process", counted)
    first = client.get(ROUTE, params={"number": 286})
    assert first.status_code == 200 and _listings(spawned), "a first stack change listed nothing"
    spawned.clear()
    again = client.get(ROUTE, params={"number": 286})
    assert again.content == first.content
    # The left end is found again, in the store, and the sums are kept: nothing is listed.
    assert spawned and _listings(spawned) == [], f"a repeated stack change listed: {spawned}"
    assert again.headers["etag"] == first.headers["etag"]
    unchanged = client.get(
        ROUTE, params={"number": 286}, headers={"if-none-match": first.headers["etag"]}
    )
    assert unchanged.status_code == 304 and unchanged.content == b""
    assert _listings(spawned) == []
    # A base branch that moves on, and leaves the merge base where it was, lists nothing.
    meets = first.json()["base"]
    moved_base = _commit_on(
        stand, stand.origin["topic"], {"src/other.txt": "elsewhere\n"}, "refs/test/base-moves"
    )
    _git(stand, "update-ref", f"refs/remotes/origin/{DEFAULT_BRANCH}", moved_base)
    spawned.clear()
    assert client.get(ROUTE, params={"number": 286}).json()["base"] == meets
    assert _listings(spawned) == [], "a base branch that moved past the merge base relisted"
    # A layer whose head moves names another comparison, which is summed afresh.
    bottom = stand.record(7)
    assert isinstance(bottom, PullRecord) and bottom.comparison is not None
    _layer(stand, bottom, 11, stand.origin["fork_head"], stand.origin["fork_earlier"])
    moved = client.get(ROUTE, params={"number": 286}).json()
    assert moved["head"] == stand.origin["fork_earlier"] and _listings(spawned)
    assert client.get(ROUTE, params={"number": 286, "extra": "1"}).status_code == 400
    assert client.get(ROUTE).status_code == 400
    assert client.get(ROUTE, params={"number": "x"}).status_code == 400


def test_a_stack_whose_change_cannot_be_had_says_why(
    stacked: tuple[_Stand, TestClient, str],
) -> None:
    stand, client, _top = stacked

    def reason(number: int) -> Any:
        body = client.get(ROUTE, params={"number": number}).json()
        assert body["state"] == "absent" and body["statuses"] == [] and body["files"] is None
        return body["reason"]

    assert reason(999) == "not_stacked"
    # Pull request 12, the top, has no record.
    assert reason(400) == "not_cached"
    # A base branch the store does not mirror, and one that is no branch name at all.
    for base_ref in ("gone", "no..name"):
        _publish(stand, (286, (7, 11)), base_ref=base_ref)
        assert reason(286) == "no_base_branch"
    _publish(stand, (286, (7, 11)))
    top = read_pull_record(stand.published.home, stand.published.slug, 11)
    assert isinstance(top, PullRecord)
    write_pull_record(
        stand.published.home, stand.published.slug, top.model_copy(update={"comparison": None})
    )
    assert reason(286) == "no_comparison"
    # Ends the store cannot compare: a commit it does not have.
    _layer(stand, top, 11, "a" * 40, "b" * 40)
    assert reason(286) == "unavailable"
    assert stand.calls() == [], "a stack change asked GitHub"


def test_a_stack_of_one_open_pull_request_is_summed_from_its_kept_comparison(
    stacked: tuple[_Stand, TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stack of one pull request has that pull request's own comparison, which the
    comparison route keeps once a page has read it: it is summed from that, listing nothing
    (review of #484, A6)."""

    stand, client, _top = stacked
    monkeypatch.setattr(pull_stack_change, "_KEPT", type(pull_stack_change._KEPT)())  # pyright: ignore[reportPrivateUsage]
    route = client.get("/api/plugin/github/pull?number=7").json()["comparison_route"]
    assert client.get(route).status_code == 200
    stand.calls()

    async def forbidden(_source: GitDiffSource, _resolved: Any) -> Any:
        raise AssertionError("a kept comparison was listed again")

    monkeypatch.setattr(GitDiffSource, "manifest", forbidden)
    alone = client.get(ROUTE, params={"number": 300}).json()
    assert alone["state"] == "current", alone
    assert alone["statuses"] == [
        {"status": "added", "count": 1},
        {"status": "modified", "count": 1},
    ]
    assert stand.calls() == [], "a stack change asked GitHub"


def test_a_stack_change_with_no_store_is_no_store(
    stacked: tuple[_Stand, TestClient, str],
) -> None:
    """A repository listed before its store is attached, as a served checkout's can be, has
    no store to compare in (review of #484, A7)."""

    stand, _client, _top = stacked
    body = asyncio.run(pull_stack_change.stack_change(_listed_host(stand), _repository(stand), 286))
    assert (body["state"], body["reason"]) == ("absent", "no_store")
    assert stand.calls() == [], "a stack change asked GitHub"


def _listed_host(stand: _Stand) -> PullHost:
    """The stand's pull requests as a server has them before their store is attached."""

    def never(_number: int) -> Any:
        raise AssertionError("a stack change started a refresh")

    return PullHost(ServedPulls(_repository(stand)), running=lambda _number: False, start=never)


def test_a_stack_change_without_a_github_repository_is_not_github(tmp_path: Path) -> None:
    from metabrowser import server

    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        response = client.get(ROUTE, params={"number": 286})
    assert response.status_code == 200
    assert response.json()["reason"] == "not_github"


def test_a_stack_change_too_large_to_sum_is_not_summed(
    stacked: tuple[_Stand, TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client, _top = stacked
    monkeypatch.setattr(pull_stack_change, "_KEPT", type(pull_stack_change._KEPT)())  # pyright: ignore[reportPrivateUsage]
    from metabrowser.diff.adapters import git as adapter

    monkeypatch.setattr(adapter, "MAX_MANIFEST_FILES", 1)
    body = client.get(ROUTE, params={"number": 286}).json()
    assert (body["state"], body["reason"]) == ("absent", "too_large")


def test_a_stack_change_past_the_git_read_cap_is_too_large_and_kept(
    stacked: tuple[_Stand, TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listing past ``GIT_SUBPROCESS_MAX_BYTES`` is more files than a manifest holds: it
    is ``too_large``, as a listing past ``MAX_MANIFEST_FILES`` is, and kept, so it is not
    listed again (review of #484, A8)."""

    _stand, client, _top = stacked
    monkeypatch.setattr(pull_stack_change, "_KEPT", type(pull_stack_change._KEPT)())  # pyright: ignore[reportPrivateUsage]
    listed: list[object] = []

    async def overflowing(_source: GitDiffSource, resolved: Any) -> Any:
        listed.append(resolved)
        raise git_process.GitOutputTooLargeError("git diff listed more than 1 bytes on stdout")

    monkeypatch.setattr(GitDiffSource, "manifest", overflowing)
    for _ in range(2):
        body = client.get(ROUTE, params={"number": 286}).json()
        assert (body["state"], body["reason"]) == ("absent", "too_large"), body
    assert len(listed) == 1, "a listing past the read cap was not kept"


RECORDING = "github-stack-change-responses.json"
TRANSCRIPT = "cli-ui-github-pulls-stack-lines.tryscript.md"


def _recorded(response: Any) -> dict[str, Any]:
    """One answer as the Pulls tab sees it: its status and body, its tag left out, which is
    scoped to the build."""

    return {"status": response.status_code, "body": response.json()}


def test_recording_stack_change_answers_real_routes(
    stacked: tuple[_Stand, TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``tests/dom/github-pulls-stack-lines-session.js`` replays what the route answers.

    The stacks are numbered as the recorded stack snapshot's shared answer numbers them
    (``github-stacks-responses.json``), #286 and #290, so the session's headings and its
    answers name the same stacks: #286's change is the chain above, and #290's top has no
    record. A server with no GitHub repository refuses every stack, and so does one whose
    repository has no store attached.
    """

    from metabrowser import server
    from metabrowser.mirror_refresh import serve_mirror
    from tests.golden_harness import check_recording

    stand, client, _top = stacked
    _publish(stand, (286, (7, 11)), (290, (7, 12)))
    recorded = {
        "current": _recorded(client.get(ROUTE, params={"number": 286})),
        "not_cached": _recorded(client.get(ROUTE, params={"number": 290})),
        "not_stacked": _recorded(client.get(ROUTE, params={"number": 999})),
    }
    assert recorded["current"]["body"]["state"] == "current"
    assert recorded["not_cached"]["body"]["reason"] == "not_cached"
    # The repository listed with no store attached, as a served checkout's is before its
    # store is acquired.
    with monkeypatch.context() as listed_only:
        listed_only.setattr(pull_route, "pull_host", lambda _app: _listed_host(stand))
        recorded["no_store"] = _recorded(client.get(ROUTE, params={"number": 286}))
    assert recorded["no_store"]["body"]["reason"] == "no_store"
    server._set_root_dir(stand.tmp_path / "plain")  # pyright: ignore[reportPrivateUsage]
    (stand.tmp_path / "plain").mkdir()
    serve_mirror(None)
    with TestClient(server.app) as plain:
        recorded["not_github"] = _recorded(plain.get(ROUTE, params={"number": 286}))
    assert recorded["not_github"]["body"]["reason"] == "not_github"
    assert stand.calls() == [], "a stack change asked GitHub"
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)
