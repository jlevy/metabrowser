"""Every CLI mode that acquires maps Git failures to the same path-free ``CLIError``.

``--no-serve`` and cache ``--api`` acquire through ``acquire_cli``; the Git-pin
``--show``, non-cache ``--api``, ``--check-api``, and serve modes acquire through
``git_pin_cli``. A raw ``GitError`` escaping any of them tracebacks at the real entry
point and prints the argument vector, which names the staging path (mb-sumg).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metabrowser.cache import acquire as acquire_module
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
    "pin-check-api": ["--check-api"],
    "pin-serve": ["--no-open"],
}
PIN_MODES = ("pin-show", "pin-api", "pin-check-api", "pin-serve")

KINDS = ("timeout", "too-large", "unavailable", "command")


@pytest.fixture(autouse=True)
def _never_serve(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Every case here fails before serving; if one did not, it must not bind or block."""

    monkeypatch.setattr("metabrowser.cli.serve._QuietForceExitServer", _UnexpectedServe)
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)


class _UnexpectedServe:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("a refused acquisition reached the server")


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
    url = _file_url(_origin(tmp_path, allow_filter=False))
    real_run = acquire_module._run
    messages: dict[str, str] = {}
    for kind in KINDS:

        async def fail_init(
            args: list[str],
            *,
            cwd: Path | None = None,
            git_dir: Path | None = None,
            kind: str = kind,
        ) -> bytes:
            if args[0] == "init":
                raise _git_failure(kind, args)
            return await real_run(args, cwd=cwd, git_dir=git_dir)

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
    url = _file_url(_origin(tmp_path, allow_filter=False))
    real_run = acquire_module._run

    async def time_out_init(
        args: list[str],
        *,
        cwd: Path | None = None,
        git_dir: Path | None = None,
    ) -> bytes:
        if args[0] == "init":
            raise _git_failure("timeout", args)
        return await real_run(args, cwd=cwd, git_dir=git_dir)

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
    url = _file_url(_origin(tmp_path, allow_filter=False))
    result = runner.invoke(_app, [url, *MODES[mode]])
    assert isinstance(result.exception, CLIError), (mode, result.exception)
    assert isinstance(result.exception.__cause__, UnsupportedGitVersionError)
    assert "unsupported Git version" in str(result.exception)
    assert "2.43.7" in str(result.exception)
    if home_exists:
        assert list(home.iterdir()) == []
    else:
        assert not home.exists()


@pytest.mark.parametrize("mode", PIN_MODES)
def test_a_path_bearing_git_error_while_opening_the_pin_is_path_free(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))

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


@pytest.mark.parametrize("mode", PIN_MODES)
def test_log_level_debug_prints_a_pin_open_failure(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure after acquisition, while opening the pin, is logged at debug too."""

    home = _isolate_home(tmp_path, monkeypatch)
    url = _file_url(_origin(tmp_path, allow_filter=False))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "")
    monkeypatch.delenv("METABROWSER_LOG_LEVEL")

    async def fail_open(**_kwargs: object) -> object:
        raise GitUnavailableError(f"repository store is not a directory: {home}/stores/x")

    monkeypatch.setattr(git_pin_cli, "open_revision", fail_open)
    result = runner.invoke(_app, [url, *MODES[mode], "--log-level", "debug"])
    assert isinstance(result.exception, CLIError), result.exception
    assert "opening the pinned revision failed" in result.output
