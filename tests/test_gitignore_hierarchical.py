"""Gitignore verdicts come from each path's ancestor chain, read on demand.

The first directory rows must not wait for anything but the root. The former
design walked the whole repository for nested ``.gitignore`` files before the
indexing walk could start; on a real repository that visited 40,832
directories to find 25 files and held back the first rows for 9-34 s. These
tests pin the replacement: verdicts match git, building the matcher traverses
nothing, a verdict reads only its ancestors' files, and the root's rows land
while a deeper directory has not been read.
"""

from __future__ import annotations

import asyncio
import os
import random
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

from metabrowser import ignore_filter, tree
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.ignore_filter import HierarchicalGitIgnore
from metabrowser.inventory_engine.contract import DirectoryProjection, DirectoryQuery, ReadRequest
from metabrowser.tree import build_gitignore_check
from tests.inventory_harness import inventory_harness


def _write(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    return root


def test_nested_patterns_are_relative_to_their_own_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root / ".gitignore", "node_modules/\n*.pyc\n")
    _write(root / "src" / "generated" / ".gitignore", "*.gen\n/build/\n")
    check = HierarchicalGitIgnore(root)

    assert check("src/generated/out.gen") is True
    # An unanchored nested pattern applies at any depth below its directory.
    assert check("src/generated/deep/more/out.gen") is True
    # An anchored nested pattern applies only directly under its directory.
    assert check("src/generated/build", is_dir=True) is True
    assert check("src/generated/deep/build", is_dir=True) is False
    # Nested patterns never govern paths outside their directory.
    assert check("src/out.gen") is False
    assert check("src/thing.pyc") is True
    assert check("node_modules", is_dir=True) is True


def test_a_deeper_file_overrides_a_shallower_one(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root / ".gitignore", "*.log\n")
    _write(root / "logs" / ".gitignore", "!important.log\n")
    check = HierarchicalGitIgnore(root)

    assert check("logs/important.log") is False
    assert check("logs/debug.log") is True
    assert check("important.log") is True


def test_nothing_inside_an_ignored_directory_is_reincluded(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root / ".gitignore", "node_modules/\n")
    _write(root / "node_modules" / ".gitignore", "!keep-me.py\n")
    check = HierarchicalGitIgnore(root)

    assert check("node_modules/keep-me.py") is True
    assert check("node_modules/pkg/deep/index.js") is True
    # Git never reads a .gitignore inside an ignored directory; neither do we.
    assert "node_modules" not in check._specs


def test_building_the_check_traverses_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _write(root / ".gitignore", "*.log\n")
    _write(root / "runs" / "a" / "b" / ".gitignore", "*.tmp\n")
    tree._IGNORE_CACHE.clear()

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("building the gitignore check must not traverse the tree")

    monkeypatch.setattr(os, "walk", refuse)
    monkeypatch.setattr(os, "scandir", refuse)
    try:
        check, git_root = build_gitignore_check(root)
        assert git_root == root.resolve()
        assert check(root.resolve() / "app.log") is True
    finally:
        tree._IGNORE_CACHE.clear()


def test_a_verdict_reads_only_its_ancestor_chain(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    for directory in ("", "runs", "runs/a", "runs/a/b", "docs", "vendor"):
        _write(root / directory / ".gitignore", "*.tmp\n")
    check = HierarchicalGitIgnore(root)

    check("README.md")
    assert set(check._specs) == {""}

    check("runs/a/b/output.tmp")
    assert set(check._specs) == {"", "runs", "runs/a", "runs/a/b"}


def _fixture_git_environment() -> dict[str, str]:
    """The environment for git run against a fixture repository.

    The repository-pinning variables are scrubbed because the pre-push gate runs
    this file inside a githook, where a linked worktree exports ``GIT_DIR``. It
    outranks ``-C``, and inherited here, ``git init`` wrote ``core.bare = true``
    into the developer's shared repository configuration instead of creating the
    fixture. ``tests/conftest.py`` scrubs the session too; this does not rely on
    it. The developer's global and system configuration are excluded so their
    ignore rules cannot change git's verdicts.
    """

    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return env


def _git_verdicts(root: Path, paths: list[tuple[str, bool]]) -> dict[tuple[str, bool], bool]:
    env = _fixture_git_environment()
    queries = [f"{path}/" if is_dir else path for path, is_dir in paths]
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "--stdin", "-v", "-n"],
        input="\n".join(queries) + "\n",
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    verdicts: dict[tuple[str, bool], bool] = {}
    for line, key in zip(result.stdout.splitlines(), paths, strict=True):
        source_and_pattern, _tab, _path = line.partition("\t")
        pattern = source_and_pattern.split(":", 2)[2] if source_and_pattern.count(":") >= 2 else ""
        # -n prints non-matching paths with an empty source; a matching
        # negation ("!pattern") means the path is not ignored.
        verdicts[key] = bool(pattern) and not pattern.startswith("!")
    return verdicts


def _init_fixture_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
        capture_output=True,
        env=_fixture_git_environment(),
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_verdicts_match_git_check_ignore(tmp_path: Path) -> None:
    rng = random.Random(0x6A7)
    root = tmp_path / "repo"
    root.mkdir()
    _init_fixture_repository(root)
    names = ["build", "logs", "src", "a", "b", "node_modules", "keep", "data"]
    patterns = [
        "*.log",
        "!important.log",
        "build/",
        "/build/",
        "logs",
        "*.tmp",
        "!keep/",
        "data/*.csv",
        "**/cache",
        "node_modules/",
        "a/**/b",
        "!*.md",
        "*.md",
        "/a",
    ]
    directories = [""]
    for _ in range(40):
        parent = rng.choice(directories)
        child = f"{parent}/{rng.choice(names)}" if parent else rng.choice(names)
        if child not in directories:
            directories.append(child)
    paths: list[tuple[str, bool]] = []
    for directory in directories:
        if directory:
            paths.append((directory, True))
        for leaf in ("x.log", "important.log", "y.tmp", "z.csv", "readme.md", "plain.txt", "cache"):
            file_path = f"{directory}/{leaf}" if directory else leaf
            paths.append((file_path, False))
        if rng.random() < 0.5:
            lines = rng.sample(patterns, rng.randint(1, 4))
            _write(root / directory / ".gitignore", "\n".join(lines) + "\n")
    for directory in directories:
        (root / directory).mkdir(parents=True, exist_ok=True)

    check = HierarchicalGitIgnore(root)
    expected = _git_verdicts(root, paths)
    actual = {(path, is_dir): check(path, is_dir=is_dir) for path, is_dir in paths}
    mismatches = {
        key: (actual[key], expected[key]) for key in paths if actual[key] != expected[key]
    }
    assert not mismatches, (
        f"{len(mismatches)} verdicts differ from git: {list(mismatches.items())[:5]}"
    )


def test_root_rows_land_before_a_deeper_directory_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first directory rows depend on the root alone.

    A deep directory's scan is held open. Its nested ``.gitignore`` is exactly
    what an eager prewalk would have had to read first, so under that design no
    root row could appear until the scan was released.
    """

    root = _repo(tmp_path / "repo")
    _write(root / ".gitignore", "*.log\n")
    _write(root / "README.md", "# repo\n")
    _write(root / "docs" / "guide.md", "# guide\n")
    blocked = root / "runs" / "deep" / "deeper"
    _write(blocked / ".gitignore", "*.tmp\n")
    _write(blocked / "out.txt")
    tree._IGNORE_CACHE.clear()

    release = threading.Event()
    real_scandir = os.scandir

    def gated_scandir(path: str | os.PathLike[str] = ".") -> Any:
        if Path(os.fsdecode(path)).resolve() == blocked.resolve():
            release.wait(timeout=30)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", gated_scandir)
    monkeypatch.setattr(ignore_filter.os, "scandir", gated_scandir)

    async def read_root_rows_while_blocked() -> tuple[set[str], bool]:
        async with inventory_harness(root, settle=False) as harness:
            names: set[str] = set()
            try:
                for _ in range(1000):
                    read = await harness.runtime.coordinator.read(
                        ReadRequest(
                            queries=(
                                DirectoryQuery(query_id="root", path="", max_depth=1, max_rows=200),
                            )
                        )
                    )
                    projection = read.result.completed_projection("root")
                    assert isinstance(projection, DirectoryProjection)
                    names = {entry.path for entry in projection.entries}
                    if {"README.md", "docs", "runs"} <= names:
                        break
                    await asyncio.sleep(0.01)
                still_blocked = not release.is_set()
            finally:
                release.set()
            return names, still_blocked

    try:
        names, still_blocked = asyncio.run(read_root_rows_while_blocked())
    finally:
        release.set()
        tree._IGNORE_CACHE.clear()

    assert {"README.md", "docs", "runs"} <= names
    assert still_blocked, "root rows appeared only after the deep scan was released"
