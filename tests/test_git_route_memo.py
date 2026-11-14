"""The Git routes keep their answers under the refs' state, and only under it.

``ref_state`` names a repository's refs from the filesystem, and the refs, summary, and
log routes answer a repeat from what they kept under that name: no Git process runs, and
a client holding the entity tag is answered 304. Each test here holds both halves of
that: a repeat under the same state starts no Git process, and every input the state
covers, moved once, is answered afresh. Fixtures are real repositories, because what the
state reads is Git's own layout on disk.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from starlette.testclient import TestClient

from metabrowser import paths_safe
from metabrowser.git import history as history_module
from metabrowser.git import process as git_process
from metabrowser.git import ref_state as ref_state_module
from metabrowser.git import repo as git_repo
from metabrowser.git.history import HISTORY_SESSIONS, clear_kept_scopes
from metabrowser.git.process import GitLocation, repository_store_target
from metabrowser.git.ref_state import clear_ref_state_cache, ref_state
from metabrowser.git.route_memo import GIT_ANSWERS, GitAnswerMemo
from metabrowser.git.tree_source import GitRevisionSubject, git_revision_subject
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from tests.required_tools import needs_git

pytestmark = needs_git

_PINNING = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


def _git(cwd: Path, *args: str) -> str:
    env = {name: value for name, value in os.environ.items() if name not in _PINNING}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Memo",
            "GIT_AUTHOR_EMAIL": "memo@example.invalid",
            "GIT_COMMITTER_NAME": "Memo",
            "GIT_COMMITTER_EMAIL": "memo@example.invalid",
            "GIT_CONFIG_GLOBAL": str(cwd / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(cwd / ".gitconfig-absent"),
        }
    )
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env
    )
    return result.stdout.decode().strip()


def _commit(root: Path, name: str) -> str:
    (root / name).write_text(f"{name}\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", name)
    return _git(root, "rev-parse", "HEAD")


def _forget_everything() -> None:
    GIT_ANSWERS.clear()
    clear_kept_scopes()
    clear_ref_state_cache()
    git_repo.clear_repo_cache()


def _git_version() -> tuple[int, int]:
    raw = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"(\d+)\.(\d+)", raw)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


# Both ref backends: a reftable repository keeps its refs, and a linked worktree's HEAD,
# in table files rather than one file a ref (review C of #368, C1).
REF_FORMATS = (
    pytest.param("files", id="files"),
    pytest.param(
        "reftable",
        id="reftable",
        marks=pytest.mark.skipif(
            _git_version() < (2, 45), reason="reftable repositories need Git 2.45 or later"
        ),
    ),
)


def _make_repo(root: Path, ref_format: str = "files") -> Path:
    root.mkdir()
    formats = ["--ref-format=reftable"] if ref_format == "reftable" else []
    _git(root, "init", "-q", *formats, "-b", "main")
    _commit(root, "first.txt")
    _commit(root, "second.txt")
    return root


@contextmanager
def _serving(root: Path) -> Generator[Path]:
    previous = paths_safe.ROOT_DIR
    paths_safe._set_root_dir(root)
    _forget_everything()
    # Repository identity is TTL-cached for five seconds; on a loaded machine two
    # requests can straddle that, and a rediscovery is Git processes this file counts.
    with mock.patch.object(git_repo, "GIT_REPO_INFO_TTL_S", 3600.0):
        try:
            yield root
        finally:
            asyncio.run(HISTORY_SESSIONS.close_all())
            paths_safe._set_root_dir(previous)
            _forget_everything()


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    with _serving(_make_repo(tmp_path / "repo")) as root:
        yield root


# The commands the history routes run. The server's inventory may run Git of its own
# while a test's requests are in flight, and that is not what these tests count.
_ROUTE_COMMANDS = frozenset({"rev-parse", "symbolic-ref", "for-each-ref", "rev-list", "log"})


class _Spawns:
    """Every Git process a history route starts, by its arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._original = git_process.spawn_git_process

    async def __call__(self, args: Any, **kwargs: Any) -> Any:
        argv = tuple(str(arg) for arg in args)
        if _ROUTE_COMMANDS.intersection(argv[:4]):
            self.calls.append(argv)
        return await self._original(args, **kwargs)


def _counting() -> tuple[_Spawns, Any]:
    spawns = _Spawns()
    return spawns, mock.patch.object(git_process, "spawn_git_process", spawns)


def _state(root: Path) -> str | None:
    return asyncio.run(ref_state(GitLocation.filesystem(root)))


# ── The state ────────────────────────────────────────────────


class _States:
    """The states one location has had; each move must name a state not seen before."""

    def __init__(self, root: Path) -> None:
        self.root = root
        first = _state(root)
        assert first is not None
        assert _state(root) == first, "nothing changed, so nothing may move"
        self.seen = [first]

    def moved(self, change: str) -> None:
        state = _state(self.root)
        assert state is not None, change
        assert state not in self.seen, f"{change} did not move the state"
        self.seen.append(state)


def _rewrite_packed_ref(common: Path, ref: str, old: str, new: str) -> None:
    """Point a packed ref elsewhere by rewriting ``packed-refs`` alone, as Git writes it.

    Git rewrites ``packed-refs`` through a lock file it renames over the old one, and
    takes a lock under ``refs/`` as it does, which moves the walk; a rewrite by any other
    tool touches nothing under ``refs/``. The new text is the old one's length, so only
    the file's identity and times say it changed.
    """

    packed = common / "packed-refs"
    text = packed.read_text()
    line = f"{old} {ref}\n"
    assert line in text, f"{ref} is not packed at {old}"
    lock = common / "packed-refs.lock"
    lock.write_text(text.replace(line, f"{new} {ref}\n"))
    os.replace(lock, packed)


@pytest.mark.parametrize("served", ["main", "linked"])
@pytest.mark.parametrize("ref_format", REF_FORMATS)
def test_the_state_holds_still_and_moves_with_every_input_it_covers(
    tmp_path: Path, ref_format: str, served: str
) -> None:
    """Every input the module says it covers, moved once, in a main or a linked worktree.

    The served worktree checks out and detaches; the shared refs, configuration, and
    common files are written from the main worktree, so a linked worktree's state has to
    read them from the common directory and its own ``HEAD`` and ``config.worktree`` from
    its own (review D of #368, D1).
    """

    repo = _make_repo(tmp_path / "repo", ref_format)
    root = repo
    if served == "linked":
        root = tmp_path / "linked"
        _git(repo, "worktree", "add", "-q", "-b", "linked", str(root))
    own = Path(_git(root, "rev-parse", "--absolute-git-dir"))
    common = Path(_git(repo, "rev-parse", "--absolute-git-dir"))
    assert (own == common) == (served == "main")
    states = _States(root)
    first = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    third = _commit(root, "third.txt")
    states.moved("a commit on the checked-out branch")
    _git(repo, "tag", "v1")
    states.moved("a new tag")
    _git(repo, "branch", "side")
    states.moved("a new branch")
    _git(root, "checkout", "-q", "side")
    states.moved("a checkout")
    _git(repo, "pack-refs", "--all")
    states.moved("packing the refs")
    _git(repo, "config", "branch.side.merge", "refs/heads/main")
    states.moved("an upstream named in config")
    _git(repo, "update-ref", "-d", "refs/tags/v1")
    states.moved("deleting a packed ref")
    _git(root, "checkout", "-q", "--detach")
    states.moved("detaching HEAD")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    states.moved("turning on per-worktree configuration")
    _git(root, "config", "--worktree", "metabrowser.probe", "1")
    assert (own / "config.worktree").is_file()
    states.moved("a per-worktree setting in config.worktree")
    _git(repo, "replace", "--graft", third, first)
    states.moved("a replace ref")
    # Git writes these two only on a fetch or a hand edit: written here as Git writes them.
    (common / "info").mkdir(exist_ok=True)
    (common / "info" / "grafts").write_text(f"{third} {first}\n")
    states.moved("info/grafts")
    (common / "shallow").write_text(f"{first}\n")
    states.moved("a shallow boundary")
    if ref_format == "files":
        # Only the files backend reads packed-refs: a reftable repository has none.
        _git(repo, "tag", "v2", first)
        _git(repo, "pack-refs", "--all")
        states.moved("packing a new tag")
        assert not (common / "refs" / "tags" / "v2").exists()
        _rewrite_packed_ref(common, "refs/tags/v2", first, third)
        assert _git(repo, "rev-parse", "refs/tags/v2") == third
        states.moved("packed-refs rewritten in place, with nothing under refs/")


@pytest.mark.parametrize("ref_format", REF_FORMATS)
def test_a_linked_worktree_has_its_own_head_and_shares_the_refs(
    tmp_path: Path, ref_format: str
) -> None:
    """A linked worktree's own HEAD and refs, and the shared ones, each move its state.

    Under reftable a linked worktree's HEAD file is a stub, and its real HEAD and its
    per-worktree refs are tables in its own Git directory (review C of #368, C1).
    """

    repo = _make_repo(tmp_path / "repo", ref_format)
    _git(repo, "branch", "other")
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "-b", "linked", str(linked))
    states = _States(linked)
    _commit(linked, "linked.txt")
    states.moved("a commit on the worktree's own branch")
    _commit(repo, "main-only.txt")
    states.moved("a commit on a shared branch, made in the main worktree")
    _git(linked, "switch", "-q", "other")
    states.moved("a switch in the worktree")
    _git(linked, "switch", "-q", "--detach")
    states.moved("a detach in the worktree")
    _commit(linked, "detached.txt")
    states.moved("a detached commit in the worktree")
    _git(linked, "update-ref", "refs/worktree/probe", "HEAD")
    states.moved("a per-worktree ref")


@pytest.mark.parametrize("ref_format", REF_FORMATS)
def test_a_served_linked_worktree_answers_afresh_after_a_switch(
    tmp_path: Path, ref_format: str
) -> None:
    """Review C of #368, C1's reproduction, through the routes."""

    repo = _make_repo(tmp_path / "repo", ref_format)
    _git(repo, "branch", "other")
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "-b", "topic", str(linked))
    _commit(linked, "t1.txt")
    with _serving(linked), TestClient(app) as client:
        before = client.get("/api/git/log", params={"limit": "10"}).json()
        assert before["commits"][0]["subject"] == "t1.txt"
        assert client.get("/api/git/summary").json()["commit_count"] == 3
        _git(linked, "switch", "-q", "other")
        git_repo.clear_repo_cache()
        after = client.get("/api/git/log", params={"limit": "10"}).json()
        summary = client.get("/api/git/summary").json()
    assert after["page_cursor"] != before["page_cursor"]
    assert after["commits"][0]["subject"] == "second.txt"
    assert summary["commit_count"] == 2


def _fresh_summary(client: TestClient, params: dict[str, str]) -> dict[str, Any]:
    """The summary as a server with nothing kept answers it."""

    GIT_ANSWERS.clear()
    clear_kept_scopes()
    return client.get("/api/git/summary", params=params).json()


@pytest.mark.parametrize("served", ["main", "linked"])
def test_the_all_summary_reads_nothing_the_state_does_not_cover(
    tmp_path: Path, served: str
) -> None:
    """Commits on another worktree's detached HEAD change no kept summary's answer.

    ``rev-list --all`` adds every worktree's HEAD, which the state does not cover, so a
    kept answer went stale against a fresh one (review C of #368, C2). The summary now
    counts the scope the log walks, whose inputs the state covers.
    """

    repo = _make_repo(tmp_path / "repo")
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "--detach", str(linked))
    root, other = (repo, linked) if served == "main" else (linked, repo)
    with _serving(root), TestClient(app) as client:
        params = {"scope": "all"}
        kept_before = client.get("/api/git/summary", params=params).json()
        if served == "linked":
            _git(other, "switch", "-q", "--detach")
        _commit(other, "elsewhere-1.txt")
        _commit(other, "elsewhere-2.txt")
        kept_after = client.get("/api/git/summary", params=params).json()
        fresh = _fresh_summary(client, params)
        logged = client.get("/api/git/log", params={"limit": "1000", "scope": "all"}).json()
    assert kept_after == fresh, "a kept summary disagrees with a fresh one"
    assert fresh["commit_count"] == len(logged["commits"]), "the tally counts the list"
    assert kept_before["commit_count"] == fresh["commit_count"]


def test_a_served_folder_replaced_in_place_is_asked_about_again(tmp_path: Path) -> None:
    """Review C of #368, C3: a linked worktree's folder deleted and cloned again."""

    repo = _make_repo(tmp_path / "repo")
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "-b", "linked", str(linked))
    replaced = _state(linked)
    assert replaced is not None
    other = _make_repo(tmp_path / "other")
    _commit(other, "other-only.txt")
    shutil.rmtree(linked)
    _git(tmp_path, "clone", "-q", str(other), str(linked))
    now = _state(linked)
    clear_ref_state_cache()
    assert now == _state(linked), "the state is not the clone's"
    assert now != replaced


def test_the_state_gives_up_past_its_bound_and_remembers_it(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    for index in range(4):
        _git(repo, "update-ref", f"refs/heads/many-{index}", head)
    walks = mock.Mock(wraps=ref_state_module._read_state)
    with (
        mock.patch.object(ref_state_module, "MAX_REF_ENTRIES", 3),
        mock.patch.object(ref_state_module, "_read_state", walks),
    ):
        assert _state(repo) is None
        assert _state(repo) is None
        assert walks.call_count == 1, "a repository past the bound was walked again at once"
        with mock.patch.object(ref_state_module, "GIT_REPO_INFO_MAX_AGE_S", 0.0):
            clear_ref_state_cache()
            assert _state(repo) is None
            assert _state(repo) is None
        assert walks.call_count == 3, "the verdict outlived its period"
    clear_ref_state_cache()
    assert _state(repo) is not None


def test_only_the_latest_scope_is_kept_and_its_targets_are_bounded(repo: Path) -> None:
    """Review B of #368, B2: a moved state's scope goes at once, and targets are bounded."""

    location = GitLocation.filesystem(repo)

    async def scope_now(wants_all: bool) -> None:
        state = await ref_state(location)
        await history_module.current_history_scope(location, wants_all=wants_all, state=state)

    asyncio.run(scope_now(True))
    asyncio.run(scope_now(False))
    assert len(history_module._KEPT_SCOPES) == 2
    for index in range(3):
        _git(repo, "tag", f"moved-{index}")
        asyncio.run(scope_now(True))
    assert len(history_module._KEPT_SCOPES) == 2, "a moved state's scope was kept beside"
    with mock.patch.object(history_module, "_MAX_KEPT_SCOPE_ENTRY_TARGETS", 0):
        _git(repo, "tag", "moved-past-entry-bound")
        asyncio.run(scope_now(True))
    assert len(history_module._KEPT_SCOPES) == 1, "a scope past the entry bound was kept"
    with mock.patch.object(history_module, "_MAX_KEPT_SCOPE_TARGETS", 1):
        asyncio.run(scope_now(True))
    assert history_module.kept_scope_targets() <= 1


# ── The routes ───────────────────────────────────────────────


def test_a_repeat_runs_no_git_and_a_held_tag_is_answered_304(repo: Path) -> None:
    with TestClient(app) as client:
        first = {route: client.get(route) for route in ("/api/git/refs", "/api/git/summary")}
        for route, response in first.items():
            assert response.status_code == 200, route
            assert response.headers.get("etag"), route
            assert response.headers.get("cache-control") == "no-cache", route
        spawns, patch = _counting()
        with patch:
            again = {route: client.get(route) for route in first}
            held = {
                route: client.get(route, headers={"If-None-Match": response.headers["etag"]})
                for route, response in first.items()
            }
        assert spawns.calls == [], "a repeat under the same state ran Git"
        for route, response in again.items():
            assert response.status_code == 200, route
            assert response.content == first[route].content, route
            assert response.headers["etag"] == first[route].headers["etag"], route
        for route, response in held.items():
            assert response.status_code == 304, route
            assert response.content == b"", route


def test_a_moved_ref_is_answered_afresh_and_the_old_tag_is_not_honored(repo: Path) -> None:
    with TestClient(app) as client:
        refs = client.get("/api/git/refs")
        summary = client.get("/api/git/summary")
        assert summary.json()["commit_count"] == 2
        newer = _commit(repo, "third.txt")
        _git(repo, "tag", "v2")
        fresh_refs = client.get("/api/git/refs", headers={"If-None-Match": refs.headers["etag"]})
        fresh_summary = client.get(
            "/api/git/summary", headers={"If-None-Match": summary.headers["etag"]}
        )
    assert fresh_refs.status_code == 200
    assert fresh_refs.headers["etag"] != refs.headers["etag"]
    by_name = {ref["name"]: ref["revision"] for ref in fresh_refs.json()["refs"]}
    assert by_name == {"main": newer, "v2": newer}
    assert fresh_summary.status_code == 200
    assert fresh_summary.json()["commit_count"] == 3
    assert fresh_summary.headers["etag"] != summary.headers["etag"]


def test_a_first_page_repeats_from_its_session_until_any_ref_moves(repo: Path) -> None:
    with TestClient(app) as client:
        first = client.get("/api/git/log", params={"limit": "10"})
        assert first.status_code == 200
        spawns, patch = _counting()
        with patch:
            again = client.get("/api/git/log", params={"limit": "10"})
            held = client.get(
                "/api/git/log",
                params={"limit": "10"},
                headers={"If-None-Match": first.headers["etag"]},
            )
        assert spawns.calls == [], "a repeated first page ran Git"
        assert again.json() == first.json()
        assert held.status_code == 304

        # A tag is outside the default scope, so the walk is the same; but the page's
        # decorations name it, so a first page asked for now is another walk's.
        _git(repo, "tag", "v1")
        tagged = client.get(
            "/api/git/log",
            params={"limit": "10"},
            headers={"If-None-Match": first.headers["etag"]},
        )
    assert tagged.status_code == 200
    assert tagged.json()["page_cursor"] != first.json()["page_cursor"]
    assert tagged.headers["etag"] != first.headers["etag"]
    newest = tagged.json()["commits"][0]
    assert "v1" in {ref["name"] for ref in newest.get("refs", [])}


def test_later_pages_skip_scope_resolution_while_the_refs_hold(repo: Path) -> None:
    _commit(repo, "third.txt")
    with TestClient(app) as client:
        first = client.get("/api/git/log", params={"limit": "1"}).json()
        spawns, patch = _counting()
        with patch:
            second = client.get("/api/git/log", params={"limit": "1", "cursor": first["cursor"]})
        assert second.status_code == 200, second.text
        assert spawns.calls == [], "a later page under the same state resolved its scope"

        # A tag moves the state but not the default scope: the proof runs and passes.
        _git(repo, "tag", "later")
        third = client.get("/api/git/log", params={"limit": "1", "cursor": second.json()["cursor"]})
        assert third.status_code == 200, third.text

        # A commit on the checked-out branch moves the scope: the walk is stale.
        _commit(repo, "fourth.txt")
        stale = client.get("/api/git/log", params={"limit": "1", "cursor": first["cursor"]})
    assert stale.status_code == 409
    assert stale.json()["code"] == "history_stale"


def test_a_repository_past_the_state_bound_is_answered_uncached(repo: Path) -> None:
    with (
        mock.patch.object(ref_state_module, "MAX_REF_ENTRIES", 1),
        TestClient(app) as client,
    ):
        refs = client.get("/api/git/refs")
        summary = client.get("/api/git/summary")
        log = client.get("/api/git/log", params={"limit": "10"})
        log_again = client.get("/api/git/log", params={"limit": "10"})
    assert refs.status_code == summary.status_code == log.status_code == 200
    assert "etag" not in refs.headers
    assert "etag" not in summary.headers
    assert summary.json()["commit_count"] == 2
    assert len(GIT_ANSWERS) == 0
    # Without a state there is nothing to prove a session current by: each first page
    # is a new walk, as every first page was before.
    assert log.json()["page_cursor"] != log_again.json()["page_cursor"]


# ── A pinned revision ────────────────────────────────────────


@pytest.fixture
def pinned(tmp_path: Path) -> Iterator[tuple[Path, str, str]]:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    first = _commit(work, "first.txt")
    second = _commit(work, "second.txt")
    store = tmp_path / "store.git"
    _git(tmp_path, "clone", "-q", "--bare", "--template=", str(work), str(store))

    async def pin() -> GitRevisionSubject:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=first,
            store_identity="memo-fixture",
        )
        await subject.aclose()
        return subject

    subject = asyncio.run(pin())
    attach_subject(subject)
    _forget_everything()
    try:
        with mock.patch.object(git_repo, "GIT_REPO_INFO_TTL_S", 3600.0):
            yield store, first, second
    finally:
        asyncio.run(HISTORY_SESSIONS.close_all())
        asyncio.run(subject.aclose())
        reset_source_session()
        _forget_everything()


def test_a_pin_keeps_its_answers_until_its_store_moves(pinned: tuple[Path, str, str]) -> None:
    store, first, second = pinned
    with TestClient(app) as client:
        default = client.get("/api/git/summary")
        every = client.get("/api/git/summary", params={"scope": "all"})
        assert default.json()["commit_count"] == 1, "a pin's default history is the pin"
        assert every.json()["commit_count"] == 2
        spawns, patch = _counting()
        with patch:
            assert client.get("/api/git/summary", params={"scope": "all"}).content == every.content
        assert spawns.calls == []

        # A refresh moves the store's refs; the pin's own history cannot move.
        tree = _git(store, "rev-parse", f"{second}^{{tree}}")
        later = _git(store, "commit-tree", tree, "-p", second, "-m", "later")
        _git(store, "update-ref", "refs/heads/main", later)
        moved = client.get(
            "/api/git/summary",
            params={"scope": "all"},
            headers={"If-None-Match": every.headers["etag"]},
        )
        pinned_again = client.get("/api/git/summary")
        log = client.get("/api/git/log", params={"limit": "10"})
    assert moved.status_code == 200
    assert moved.json()["commit_count"] == 3
    assert pinned_again.json() == default.json()
    assert [commit["id"] for commit in log.json()["commits"]] == [first]


# ── The memo's bound ─────────────────────────────────────────


def test_the_memo_is_bounded_by_entries_and_by_bytes() -> None:
    memo = GitAnswerMemo(max_entries=3, max_bytes=100, max_entry_bytes=40)
    for index in range(4):
        memo.put(("refs", str(index)), b"x" * 10)
    assert len(memo) == 3
    assert memo.get(("refs", "0")) is None, "the oldest entry goes first"
    memo.get(("refs", "1"))
    memo.put(("refs", "big"), b"y" * 41)
    assert memo.get(("refs", "big")) is None, "an entry past its own bound is not kept"
    assert len(memo) == 3
    memo2 = GitAnswerMemo(max_entries=10, max_bytes=50, max_entry_bytes=40)
    for index in range(5):
        memo2.put(("summary", str(index)), b"z" * 20)
    assert memo2.total_bytes <= 50
    assert len(memo2) == 2
    memo2.put(("summary", "3"), b"w" * 5)
    assert memo2.total_bytes == 25
    memo2.clear()
    assert len(memo2) == 0
    assert memo2.total_bytes == 0
