"""A first clone reports its phases, and a provider can refuse it before anything is written."""

from __future__ import annotations

import asyncio
import io
import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import RepositoryTooLargeError, acquire_source
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.cli import acquire_cli
from metabrowser.git.process import UnsupportedGitVersionError
from tests.github_origin import github_origin
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]


def _source(tmp_path: Path) -> GitSource:
    source = classify_root_argument(f"file://{github_origin(tmp_path).resolve()}")
    assert isinstance(source, GitSource)
    return source


def test_a_first_clone_reports_each_phase_and_a_hit_reports_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    source = _source(tmp_path)
    phases: list[str] = []
    asyncio.run(acquire_source(source, home=tmp_path / "home", on_phase=phases.append))
    assert phases == [
        "reading the default branch",
        "fetching every object",
        "validating",
        "publishing",
        "done",
    ]
    hit: list[str] = []
    asyncio.run(acquire_source(source, home=tmp_path / "home", on_phase=hit.append))
    assert hit == []


def test_a_provider_refusal_writes_nothing_and_runs_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    source = _source(tmp_path)

    async def too_large(checked: GitSource) -> None:
        raise RepositoryTooLargeError(checked.normalized, detail="measured")

    async def no_git(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("a refused first clone runs no Git")

    monkeypatch.setattr(acquire_module, "check_first_clone", too_large)
    monkeypatch.setattr(acquire_module, "_run", no_git)
    home = tmp_path / "home"
    with pytest.raises(RepositoryTooLargeError, match=r"\(too_large\); measured"):
        asyncio.run(acquire_source(source, home=home))
    assert not home.exists()


def test_phases_reach_a_terminal_only(monkeypatch: pytest.MonkeyPatch) -> None:
    source = GitSource(transport="https", form="url", normalized="https://github.com/o/r")

    class _Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    terminal = _Terminal()
    monkeypatch.setattr("sys.stderr", terminal)
    report = acquire_cli.terminal_phase_reporter(source)
    assert report is not None
    report("fetching every object")
    assert terminal.getvalue().startswith("cloning https://github.com/o/r: fetching every object (")
    assert terminal.getvalue().rstrip().endswith(" s)")
    monkeypatch.setattr("sys.stderr", io.StringIO())
    assert acquire_cli.terminal_phase_reporter(source) is None


def test_a_below_floor_git_is_refused_before_any_provider_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def below_floor() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.43.0", "2.43.7")

    async def no_check(_source: GitSource) -> None:
        raise AssertionError("the provider check ran before the Git floor")

    monkeypatch.setattr(acquire_module, "require_acquisition_git", below_floor)
    monkeypatch.setattr(acquire_module, "check_first_clone", no_check)
    source = GitSource(transport="https", form="url", normalized="https://github.com/o/r")
    home = tmp_path / "home"
    with pytest.raises(UnsupportedGitVersionError):
        asyncio.run(acquire_source(source, home=home))
    assert not home.exists()
