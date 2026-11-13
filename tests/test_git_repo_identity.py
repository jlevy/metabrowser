"""Past its TTL, a repository identity is checked against the refs, not discovered again.

Discovery is three Git processes (``rev-parse --show-toplevel``, ``symbolic-ref HEAD``,
``rev-parse --verify HEAD``). A request that came after the TTL used to pay them inline,
about 55 ms at the server, so a page that asked the server less often moved the cost
onto a hover or a first commit (exp-081). These tests hold the replacement: an unchanged
refs' state keeps the identity with no Git process, a change is still discovered, and an
old identity is rediscovered off the request that found it.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from metabrowser.git import process as git_process
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
)


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

    What the refs' state does not cover (the reader's global configuration, Git going
    missing) is checked this way, so no request waits for it.
    """

    async def scenario() -> tuple[Any, Any, list[tuple[str, ...]]]:
        first, _ = await repo_info(repo)
        clock.advance(GIT_REPO_INFO_MAX_AGE_S + 1)
        spawns.calls.clear()
        again, _ = await repo_info(repo)
        during = spawns.identity()
        await asyncio.gather(*list(git_repo._REFRESHING.values()))
        return first, again, during

    first, again, during = asyncio.run(scenario())
    assert again is first
    assert during == [], "the request waited for the rediscovery"
    assert spawns.identity(), "nothing was rediscovered in the background"
    entry = git_repo._REPO_CACHE[git_repo.as_location(repo).identity]
    assert entry.context is not first, "the background discovery did not replace the entry"
    assert entry.discovered_at >= clock.monotonic() - 1
