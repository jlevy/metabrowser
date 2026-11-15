"""The kept answer to whether a configuration names a textconv driver (review of #449).

Each case is the reviewer's ``cache_probe.py``: a configuration that names none is read and
kept, then something Git reads changes so that it names one, and the kept answer must not
still say "none". Where the answer cannot be sure what Git reads, nothing is kept at all.
"""

from __future__ import annotations

import asyncio
import os
import pwd
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from metabrowser.diff.adapters import textconv
from metabrowser.git.process import GitLocation, as_location, repository_store_target
from tests.required_tools import needs_git

pytestmark = needs_git

DRIVER = '[diff "x"]\n\ttextconv = cat\n'


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A home of its own, no system file, and a global file named and empty."""
    textconv.forget()
    for name in ("GIT_CONFIG_SYSTEM", "XDG_CONFIG_HOME", "GIT_CONFIG_COUNT", "GIT_CONFIG"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "home" / "global"))
    yield tmp_path
    textconv.forget()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    return repo


def _kept_after(
    location: GitLocation, change: Callable[[], Any]
) -> tuple[bool | None, bool | None, bool | None]:
    """The answer read, the kept answer once *change* ran, and Git's answer then."""

    async def run() -> tuple[bool | None, bool | None, bool | None]:
        first = await textconv.read_textconv_named(location)
        change()
        kept = await textconv.textconv_named(location)
        return first, kept, await textconv.read_textconv_named(location)

    return asyncio.run(run())


def _never_stale(location: GitLocation, change: Callable[[], Any]) -> None:
    first, kept, truth = _kept_after(location, change)
    assert (first, truth) == (False, True)
    assert kept is None, "the kept answer still said no driver is named"


def test_a_worktree_file_that_appears_is_seen(home: Path) -> None:
    repo = _repo(home)
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _never_stale(
        as_location(repo), lambda: _git(repo, "config", "--worktree", "diff.x.textconv", "cat")
    )


def test_a_system_file_that_appears_or_gains_a_driver_is_seen(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(home)
    system = home / "system"
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system))
    _never_stale(as_location(repo), lambda: system.write_text(DRIVER))
    system.write_text("# nothing yet\n")
    textconv.forget()
    _never_stale(as_location(repo), lambda: system.write_text(DRIVER))


def test_a_global_file_that_appears_is_seen(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(home)
    monkeypatch.delenv("GIT_CONFIG_GLOBAL")
    xdg = home / "home" / ".config" / "git" / "config"

    def appear() -> None:
        xdg.parent.mkdir(parents=True)
        xdg.write_text(DRIVER)

    _never_stale(as_location(repo), appear)


def test_an_included_file_that_appears_or_changes_is_seen(home: Path) -> None:
    repo = _repo(home)
    _git(repo, "config", "include.path", "inc")
    _never_stale(as_location(repo), lambda: (repo / ".git" / "inc").write_text(DRIVER))
    textconv.forget()
    other = _repo(home / "nested")
    (other / ".git" / "sub").mkdir()
    (other / ".git" / "sub" / "a").write_text("[include]\n\tpath = b\n")
    (other / ".git" / "sub" / "b").write_text("[x]\n\ty = 1\n")
    _git(other, "config", "include.path", "sub/a")
    _git(other, "config", f"includeIf.gitdir:{other}/.path", str(home / "cond"))
    first, kept, truth = _kept_after(
        as_location(other), lambda: (other / ".git" / "sub" / "b").write_text(DRIVER)
    )
    assert (first, truth) == (False, True) and kept is None
    (other / ".git" / "sub" / "b").write_text("[x]\n\ty = 2\n")
    _never_stale(as_location(other), lambda: (home / "cond").write_text(DRIVER))


@pytest.mark.parametrize("path", ["%(prefix)/etc/review-449", "~{user}/review-449-inc"])
def test_an_include_it_cannot_place_is_never_kept(home: Path, path: str) -> None:
    """Git places these by its install and by the password database, which a stamp of
    paths does not follow."""
    path = path.format(user=pwd.getpwuid(os.getuid()).pw_name)
    repo = _repo(home)
    _git(repo, "config", "include.path", path)
    first, kept, _truth = _kept_after(as_location(repo), lambda: None)
    assert first is False and kept is None


def test_an_include_that_follows_the_branch_is_never_kept(home: Path) -> None:
    repo = _repo(home)
    _git(repo, "config", "includeIf.onbranch:main.path", "inc")
    first, kept, _truth = _kept_after(as_location(repo), lambda: None)
    assert first is False and kept is None


def test_a_file_that_changes_while_it_is_read_is_not_kept(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(home)
    real = textconv.run_git_at

    async def changing(args: list[str], location: GitLocation, **kwargs: Any) -> bytes:
        out = await real(args, location, **kwargs)
        if args[:1] == ["config"]:
            _git(repo, "config", "core.review449", "true")
        return out

    monkeypatch.setattr(textconv, "run_git_at", changing)
    first, kept, _truth = _kept_after(as_location(repo), lambda: None)
    assert first is False and kept is None


def test_git_config_naming_another_file_says_nothing(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`GIT_CONFIG` points `git config` at a file `git diff` never reads."""
    repo = _repo(home)
    monkeypatch.setenv("GIT_CONFIG", str(home / "elsewhere"))
    assert asyncio.run(textconv.read_textconv_named(as_location(repo))) is None


def test_a_stores_answer_is_kept_whatever_is_written_to_dev_null(home: Path) -> None:
    """A store's global file is `/dev/null`, whose time moves on every write to it."""
    repo = _repo(home)
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-q",
         "--allow-empty", "-m", "x")  # fmt: skip
    store = GitLocation.revision(
        repository_store_target(git_dir=repo / ".git"), _git(repo, "rev-parse", "HEAD")
    )

    def write() -> None:
        with open(os.devnull, "w") as null:
            null.write("x")

    first, kept, truth = _kept_after(store, write)
    assert first is False and kept is False and truth is False
    _never_stale(store, lambda: _git(repo, "config", "diff.x.textconv", "cat"))
