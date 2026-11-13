"""Past its TTL, a repository identity is checked against the refs, not discovered again.

Discovery is three Git processes (``rev-parse --show-toplevel``, ``symbolic-ref HEAD``,
``rev-parse --verify HEAD``). A request that came after the TTL used to pay them inline,
about 55 ms at the server, so a page that asked the server less often moved the cost
onto a hover or a first commit (exp-081). These tests hold the replacement: an unchanged
refs' state keeps the identity with no Git process, a change is still discovered, and an
old identity is rediscovered off the request that found it.

They also hold what that depends on (review F of #368): the state is read before the
discovery, so a commit during it is still found; what the state does not cover shows
within the maximum age plus one TTL; a repository the reader does not own keeps the
plain TTL; a root swap cancels a background discovery; a failing one is retried once
per TTL; and a repository past the state's entry bound is not walked on every
rediscovery. ``GIT_TEST_ASSUME_DIFFERENT_OWNER`` makes Git refuse the repository, as it
does after a change of owner or a revoked ``safe.directory``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from metabrowser.git import process as git_process
from metabrowser.git import ref_state as git_ref_state
from metabrowser.git import repo as git_repo
from metabrowser.git.ref_state import clear_ref_state_cache
from metabrowser.git.repo import repo_info
from metabrowser.settings import GIT_REPO_INFO_MAX_AGE_S, GIT_REPO_INFO_TTL_S
from tests.required_tools import needs_git

pytestmark = needs_git

_PINNING = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_TEST_ASSUME_DIFFERENT_OWNER",
)

# Git refuses a repository whose owner differs from the reader while this is set.
_REFUSE = "GIT_TEST_ASSUME_DIFFERENT_OWNER"


def _git(cwd: Path, *args: str) -> str:
    env = {name: value for name, value in os.environ.items() if name not in _PINNING}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Identity",
            "GIT_AUTHOR_EMAIL": "identity@example.invalid",
            "GIT_COMMITTER_NAME": "Identity",
            "GIT_COMMITTER_EMAIL": "identity@example.invalid",
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


class _Clock:
    """``time`` for the identity cache alone, so the TTL can pass without waiting."""

    def __init__(self) -> None:
        self.offset = 0.0

    def monotonic(self) -> float:
        return time.monotonic() + self.offset

    def advance(self, seconds: float) -> None:
        self.offset += seconds


class _Spawns:
    """Every Git process started, by its arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._original = git_process.spawn_git_process

    async def __call__(self, args: Any, **kwargs: Any) -> Any:
        self.calls.append(tuple(str(arg) for arg in args))
        return await self._original(args, **kwargs)

    def identity(self) -> list[tuple[str, ...]]:
        """The calls that are the identity's own discovery commands."""

        return [
            argv
            for argv in self.calls
            if "--show-toplevel" in argv
            or "symbolic-ref" in argv
            or ("--verify" in argv and argv[-1] == "HEAD")
        ]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _commit(root, "first.txt")
    return root.resolve()


@pytest.fixture
def clock() -> Iterator[_Clock]:
    fake = _Clock()
    git_repo.clear_repo_cache()
    clear_ref_state_cache()
    with mock.patch.object(git_repo, "time", fake):
        yield fake
    git_repo.clear_repo_cache()
    clear_ref_state_cache()


@pytest.fixture
def spawns() -> Iterator[_Spawns]:
    counting = _Spawns()
    with mock.patch.object(git_process, "spawn_git_process", counting):
        yield counting


async def _drain() -> None:
    """Wait for every background discovery in flight; a failure is the task's own."""

    tasks = list(getattr(git_repo, "_REFRESHING", {}).values())
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _uid(path: Path) -> int:
    return path.stat().st_uid


def test_past_the_ttl_an_unchanged_identity_runs_no_git(
    repo: Path, clock: _Clock, spawns: _Spawns
) -> None:
    """The request after the TTL is answered from the kept identity, with no Git process."""

    async def scenario() -> tuple[Any, Any]:
        first, _ = await repo_info(repo)
        clock.advance(GIT_REPO_INFO_TTL_S + 1)
        spawns.calls.clear()
        again, _ = await repo_info(repo)
        return first, again

    first, again = asyncio.run(scenario())
    assert first is not None
    assert spawns.identity() == [], "an unchanged repository was discovered again"
    assert again is first


@pytest.mark.parametrize("change", ["commit", "switch"])
def test_past_the_ttl_a_moved_head_is_discovered_again(
    repo: Path, clock: _Clock, spawns: _Spawns, change: str
) -> None:
    """A commit or a branch switch moves the refs' state, so the identity is asked again."""

    async def before() -> Any:
        return await repo_info(repo)

    asyncio.run(before())
    if change == "commit":
        expected_revision = _commit(repo, "second.txt")
        expected_ref = "refs/heads/main"
    else:
        _git(repo, "switch", "-q", "-c", "other")
        expected_revision = _git(repo, "rev-parse", "HEAD")
        expected_ref = "refs/heads/other"
    clock.advance(GIT_REPO_INFO_TTL_S + 1)
    spawns.calls.clear()

    async def after() -> Any:
        return await repo_info(repo)

    _context, second = asyncio.run(after())
    assert spawns.identity(), "a moved HEAD was not discovered again"
    assert second["head"]["revision"] == expected_revision
    assert second["head"]["ref"] == expected_ref


def test_an_old_identity_is_rediscovered_off_the_request(
    repo: Path, clock: _Clock, spawns: _Spawns
) -> None:
    """Past the maximum age the request returns at once, and the discovery runs after it.

    What the refs' state does not cover (the Git installation, the reader's global and
    system configuration) is checked this way, so no request waits for it.
    """

    async def scenario() -> tuple[Any, Any, list[tuple[str, ...]]]:
        first, _ = await repo_info(repo)
        clock.advance(GIT_REPO_INFO_MAX_AGE_S + 1)
        spawns.calls.clear()
        again, _ = await repo_info(repo)
        during = spawns.identity()
        await _drain()
        return first, again, during

    first, again, during = asyncio.run(scenario())
    assert again is first
    assert during == [], "the request waited for the rediscovery"
    assert spawns.identity(), "nothing was rediscovered in the background"
    entry = git_repo._REPO_CACHE[git_repo.as_location(repo).identity]
    assert entry.context is not first, "the background discovery did not replace the entry"
    assert entry.discovered_at >= clock.monotonic() - 1


def test_a_commit_during_discovery_is_found_past_the_ttl(
    repo: Path, clock: _Clock, spawns: _Spawns
) -> None:
    """The state is read before the discovery, so a commit made during it moves the state.

    Read after it, the state would name the new commit while the identity names the old
    one, and the check past the TTL would keep the old ``HEAD``.
    """

    original = git_repo._discover_filesystem
    made: dict[str, str] = {}

    async def committing(location: Any) -> Any:
        found = await original(location)
        if not made:
            made["revision"] = _commit(repo, "during.txt")
        return found

    async def scenario() -> tuple[Any, Any]:
        with mock.patch.object(git_repo, "_discover_filesystem", committing):
            _, before = await repo_info(repo)
            clock.advance(GIT_REPO_INFO_TTL_S + 1)
            _, after = await repo_info(repo)
        return before, after

    before, after = asyncio.run(scenario())
    assert before["head"]["revision"] != made["revision"]
    assert after["head"]["revision"] == made["revision"], (
        "a commit made during discovery was hidden past the TTL"
    )


def test_a_refusal_the_state_misses_shows_within_the_age_bound(
    repo: Path, clock: _Clock, spawns: _Spawns, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git refusing a repository the reader owns shows within MAX_AGE plus one TTL.

    Nothing the state covers moves, as when the reader's global configuration or the Git
    installation changes, so only the background discovery can see it. Requests come
    every TTL and a half second; the first negative answer must come by the maximum age
    plus one TTL plus one such step.
    """

    step = GIT_REPO_INFO_TTL_S + 0.5

    async def scenario() -> list[tuple[float, bool]]:
        seen: list[tuple[float, bool]] = []
        await repo_info(repo)
        monkeypatch.setenv(_REFUSE, "1")
        elapsed = 0.0
        while elapsed < 2 * GIT_REPO_INFO_MAX_AGE_S:
            clock.advance(step)
            elapsed += step
            _, info = await repo_info(repo)
            seen.append((elapsed, info["is_repo"]))
            if not info["is_repo"]:
                break
            await _drain()
        return seen

    seen = asyncio.run(scenario())
    negative = [elapsed for elapsed, is_repo in seen if not is_repo]
    assert negative, "a repository Git refuses was never seen as refused"
    assert negative[0] <= GIT_REPO_INFO_MAX_AGE_S + GIT_REPO_INFO_TTL_S + step, seen


@pytest.mark.parametrize("reader", ["another_user", "no_geteuid"])
def test_a_repository_the_reader_does_not_own_keeps_the_plain_ttl(
    repo: Path,
    clock: _Clock,
    spawns: _Spawns,
    monkeypatch: pytest.MonkeyPatch,
    reader: str,
) -> None:
    """Git opens it only through ``safe.directory``, so it is discovered every TTL.

    The same holds where the platform has no ``os.geteuid`` to compare owners with. Git's
    refusal is then seen at the first request past the TTL, as before the state was kept.
    """

    if reader == "another_user":
        monkeypatch.setattr(os, "geteuid", lambda: _uid(repo) + 1, raising=False)
    else:
        monkeypatch.delattr(os, "geteuid", raising=False)

    async def scenario() -> tuple[Any, list[tuple[str, ...]], Any]:
        first, _ = await repo_info(repo)
        clock.advance(GIT_REPO_INFO_TTL_S + 1)
        spawns.calls.clear()
        await repo_info(repo)
        unchanged = spawns.identity()
        monkeypatch.setenv(_REFUSE, "1")
        clock.advance(GIT_REPO_INFO_TTL_S + 1)
        _, refused = await repo_info(repo)
        return first, unchanged, refused

    first, unchanged, refused = asyncio.run(scenario())
    assert first is not None
    assert unchanged, "a repository the reader does not own was kept without running Git"
    assert refused["is_repo"] is False, "Git's refusal was not seen at the TTL"


def test_an_owner_change_is_found_at_the_ttl(
    repo: Path, clock: _Clock, spawns: _Spawns, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kept identity whose owners stop being the reader's is discovered again at the TTL.

    The reader's user changes here rather than the files' owner, which a test cannot
    change; either way the owners no longer match, and Git refuses the repository.
    """

    async def scenario() -> tuple[Any, Any]:
        first, _ = await repo_info(repo)
        monkeypatch.setattr(os, "geteuid", lambda: _uid(repo) + 1, raising=False)
        monkeypatch.setenv(_REFUSE, "1")
        clock.advance(GIT_REPO_INFO_TTL_S + 1)
        _, refused = await repo_info(repo)
        return first, refused

    first, refused = asyncio.run(scenario())
    assert first is not None
    assert refused["is_repo"] is False, "a change of owner was not seen at the TTL"


def test_a_root_swap_cancels_a_background_discovery(
    repo: Path, clock: _Clock, spawns: _Spawns
) -> None:
    """``clear_repo_cache`` mid-discovery cancels it, and nothing is kept for the old root."""

    original = git_repo._discover_filesystem

    async def scenario() -> tuple[bool, int, int]:
        started = asyncio.Event()
        release = asyncio.Event()

        async def held(location: Any) -> Any:
            started.set()
            await release.wait()
            return await original(location)

        await repo_info(repo)
        clock.advance(GIT_REPO_INFO_MAX_AGE_S + 1)
        with mock.patch.object(git_repo, "_discover_filesystem", held):
            await repo_info(repo)
            (task,) = git_repo._REFRESHING.values()
            await started.wait()
            git_repo.clear_repo_cache()
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        return task.cancelled(), len(git_repo._REPO_CACHE), len(git_repo._REFRESHING)

    cancelled, kept, refreshing = asyncio.run(scenario())
    assert cancelled, "the background discovery outlived the root swap"
    assert kept == 0, "a discovery for the old root was kept after the swap"
    assert refreshing == 0


def test_a_failing_background_discovery_is_retried_once_per_ttl(
    repo: Path, clock: _Clock, spawns: _Spawns, caplog: pytest.LogCaptureFixture
) -> None:
    """Each failure is logged and the kept identity served; the retry waits a TTL."""

    async def failing(location: Any) -> Any:
        raise RuntimeError("discovery failed")

    seconds = 30

    async def scenario() -> tuple[int, int]:
        first, _ = await repo_info(repo)
        # The tasks themselves, held so a finished one's id is never reused for the next.
        scheduled: list[asyncio.Task[None]] = []
        with mock.patch.object(git_repo, "_discover_filesystem", failing):
            clock.advance(GIT_REPO_INFO_MAX_AGE_S + 1)
            for _ in range(seconds):
                context, _ = await repo_info(repo)
                assert context is first, "the kept identity was not served"
                for task in git_repo._REFRESHING.values():
                    if not any(task is seen for seen in scheduled):
                        scheduled.append(task)
                await _drain()
                clock.advance(1)
        return len(scheduled), len(git_repo._REFRESHING)

    with caplog.at_level(logging.WARNING, logger=git_repo.__name__):
        scheduled, left = asyncio.run(scenario())
    failures = [r for r in caplog.records if "background git rediscovery failed" in r.getMessage()]
    per_ttl = seconds / GIT_REPO_INFO_TTL_S
    assert per_ttl - 1 <= scheduled <= per_ttl + 1, f"{scheduled} tries in {seconds} s"
    assert len(failures) == scheduled, "a failure went unlogged"
    assert left == 0


def test_a_repository_past_the_entry_bound_is_walked_once_per_max_age(
    repo: Path, clock: _Clock, spawns: _Spawns
) -> None:
    """Its rediscoveries, one per TTL, do not each walk the refs to learn it is too big."""

    walks = {"count": 0}
    original = git_ref_state._read_state

    def counting(*args: Any) -> Any:
        walks["count"] += 1
        return original(*args)

    async def scenario() -> None:
        elapsed = 0.0
        while elapsed < GIT_REPO_INFO_MAX_AGE_S - GIT_REPO_INFO_TTL_S:
            await repo_info(repo)
            clock.advance(GIT_REPO_INFO_TTL_S + 1)
            elapsed += GIT_REPO_INFO_TTL_S + 1

    with (
        mock.patch.object(git_ref_state, "MAX_REF_ENTRIES", 1),
        mock.patch.object(git_ref_state, "time", clock),
        mock.patch.object(git_ref_state, "_read_state", counting),
    ):
        asyncio.run(scenario())
    assert len(spawns.identity()) >= 3 * 8, "the identity did not keep its plain TTL"
    assert walks["count"] == 1, f"{walks['count']} walks within one maximum age"
