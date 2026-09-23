"""Every CLI mode that acquires maps Git failures to the same path-free ``CLIError``.

``--no-serve`` and cache ``--api`` acquire through ``acquire_cli``; the Git-pin
``--show`` and non-cache ``--api`` modes acquire through ``git_pin_cli``. A raw
``GitError`` escaping any of them tracebacks at the real entry point and prints the
argument vector, which names the staging path (mb-sumg).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.atomic import RecordError
from metabrowser.cache.paths import SOURCES, STAGING
from metabrowser.cli import git_pin_cli
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from metabrowser.git.process import (
    GitError,
    GitUnavailableError,
    UnsupportedGitVersionError,
)
from metabrowser.git.tree_source import GitPath
from tests.test_cache_acquire import _origin
from tests.test_cli_acquire import _file_url, _git_failure, _isolate_home

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

runner = CliRunner()

README_WIRE = GitPath.from_segments(b"README").to_wire()

MODES: dict[str, list[str]] = {
    "no-serve": ["--no-serve"],
    "cache-api": ["--api", "/api/cache/sources"],
    "pin-show": ["--show", "README"],
    "pin-api": ["--api", f"/api/file?path={README_WIRE}"],
}

KINDS = ("timeout", "too-large", "unavailable", "command")


def _assert_path_free(message: str, *paths: Path) -> None:
    for path in paths:
        assert str(path) not in message
        assert str(path.resolve()) not in message
    assert "repository.git" not in message
    assert "Traceback" not in message


@pytest.mark.parametrize("mode", sorted(MODES))
def test_git_failures_during_acquisition_are_the_same_cli_error_in_every_mode(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    real_run = acquire_module._run
    messages: dict[str, str] = {}
    for kind in KINDS:

        async def fail_init(
            args: list[str],
            *,
            cwd: Path | None = None,
            git_dir: Path | None = None,
            timeout_s: float | None = None,
            kind: str = kind,
        ) -> bytes:
            if args[0] == "init":
                raise _git_failure(kind, args)
            return await real_run(args, cwd=cwd, git_dir=git_dir, timeout_s=timeout_s)

        monkeypatch.setattr(acquire_module, "_run", fail_init)
        result = runner.invoke(_app, [url, *MODES[mode]])
        assert isinstance(result.exception, CLIError), (mode, kind, result.exception)
        assert isinstance(result.exception.__cause__, GitError)
        message = str(result.exception)
        _assert_path_free(message, tmp_path, home)
        _assert_path_free(result.output, tmp_path, home)
        assert list((home / STAGING).iterdir()) == []
        assert list((home / SOURCES).iterdir()) == []
        messages[kind] = message
    assert len(set(messages.values())) == len(messages)
    assert "900" in messages["timeout"]


def test_every_mode_reports_one_message_per_failure_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The four modes share one mapper, so the same failure reads the same way."""

    _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    real_run = acquire_module._run

    async def time_out_init(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
        timeout_s: float | None = None,
    ) -> bytes:
        if args[0] == "init":
            raise _git_failure("timeout", args)
        return await real_run(args, cwd=cwd, git_dir=git_dir, timeout_s=timeout_s)

    monkeypatch.setattr(acquire_module, "_run", time_out_init)
    messages = {
        mode: str(runner.invoke(_app, [url, *args]).exception) for mode, args in MODES.items()
    }
    assert len(set(messages.values())) == 1, messages


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("home_exists", [False, True])
def test_below_floor_git_is_refused_in_every_mode_without_writing_the_home(
    mode: str, home_exists: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    if home_exists:
        home.mkdir()
    monkeypatch.setenv("METABROWSER_HOME", str(home))

    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.5", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", refuse)
    url = _file_url(_origin(tmp_path))
    result = runner.invoke(_app, [url, *MODES[mode]])
    assert isinstance(result.exception, CLIError), (mode, result.exception)
    assert isinstance(result.exception.__cause__, UnsupportedGitVersionError)
    assert "unsupported Git version" in str(result.exception)
    assert "2.43.7" in str(result.exception)
    if home_exists:
        assert list(home.iterdir()) == []
    else:
        assert not home.exists()


@pytest.mark.parametrize("mode", ["pin-show", "pin-api"])
def test_a_path_bearing_git_error_while_opening_the_pin_is_path_free(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))

    async def fail_open(**_kwargs: object) -> object:
        raise GitUnavailableError(f"repository store is not a directory: {home}/stores/x")

    monkeypatch.setattr(git_pin_cli, "open_revision", fail_open)
    result = runner.invoke(_app, [url, *MODES[mode]])
    assert isinstance(result.exception, CLIError), result.exception
    assert isinstance(result.exception.__cause__, GitUnavailableError)
    _assert_path_free(str(result.exception), tmp_path, home)


@pytest.mark.parametrize("mode", sorted(MODES))
def test_log_level_debug_prints_gits_own_failure_text(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The error message promises ``--log-level debug`` shows Git's text; keep it true."""

    _isolate_home(tmp_path, monkeypatch)
    missing = tmp_path / "missing"
    # ``apply_log_level`` writes ``os.environ`` directly; register the name so
    # monkeypatch restores it after the command sets it.
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "")
    monkeypatch.delenv("METABROWSER_LOG_LEVEL")
    result = runner.invoke(
        _app, [_file_url(missing), *MODES[mode], "--log-level", "debug"], catch_exceptions=True
    )
    assert isinstance(result.exception, CLIError), (mode, result.exception)
    assert "does not appear to be a git repository" in result.output


@pytest.mark.parametrize("mode", ["pin-show", "pin-api"])
def test_log_level_debug_prints_a_pin_open_failure(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure after acquisition, while opening the pin, is logged at debug too."""

    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "")
    monkeypatch.delenv("METABROWSER_LOG_LEVEL")

    async def fail_open(**_kwargs: object) -> object:
        raise GitUnavailableError(f"repository store is not a directory: {home}/stores/x")

    monkeypatch.setattr(git_pin_cli, "open_revision", fail_open)
    result = runner.invoke(_app, [url, *MODES[mode], "--log-level", "debug"])
    assert isinstance(result.exception, CLIError), result.exception
    assert "opening the pinned revision failed" in result.output


def _plant_an_earlier_build_record(home: Path) -> None:
    """Rewrite the store records the way an earlier v0.12 development build wrote them."""

    (store,) = (home / "cache" / "repository-stores").iterdir()
    record = store / "store.yml"
    text = record.read_text(encoding="utf-8")
    record.write_text(
        text.replace("    git_version:", "    strategy: blobless\n    git_version:"),
        encoding="utf-8",
    )
    state = store / "state.yml"
    text = state.read_text(encoding="utf-8")
    state.write_text(
        text.replace("  last_fetch_at:", "  object_state: converging\n  last_fetch_at:")
    )


@pytest.mark.parametrize("mode", sorted(MODES))
def test_a_home_an_earlier_build_wrote_is_one_repair_message_in_every_mode(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path))
    assert runner.invoke(_app, [url, "--no-serve"]).exit_code == 0
    _plant_an_earlier_build_record(home)
    before = sorted(str(path.relative_to(home)) for path in home.rglob("*"))

    result = runner.invoke(_app, [url, *MODES[mode]])

    assert isinstance(result.exception, CLIError), (mode, result.exception)
    assert isinstance(result.exception.__cause__, RecordError)
    message = str(result.exception)
    assert "earlier v0.12 development build" in message
    assert "METABROWSER_HOME" in message
    _assert_path_free(message, tmp_path, home)
    _assert_path_free(result.output, tmp_path, home)
    assert sorted(str(path.relative_to(home)) for path in home.rglob("*")) == before
