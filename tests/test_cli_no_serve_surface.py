"""CLI surface for --no-serve: mode selection, local paths, and fail-closed remotes."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from metabrowser.cli.main import _app
from metabrowser.errors import CLIError
from tests.test_cli_main import _plain_output

runner = CliRunner()


def test_cli_help_lists_no_serve() -> None:
    result = runner.invoke(_app, ["--help"])
    assert result.exit_code == 0
    assert "--no-serve" in _plain_output(result)


def test_no_serve_requires_root() -> None:
    result = runner.invoke(_app, ["--no-serve"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "ROOT is required" in output
    assert "--no-serve" in output


def test_no_serve_is_mutually_exclusive_with_walk() -> None:
    result = runner.invoke(_app, [".", "--no-serve", "--walk"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "mutually exclusive" in output
    assert "--no-serve" in output
    assert "--walk" in output


def test_port_is_not_valid_with_no_serve() -> None:
    result = runner.invoke(_app, ["file:///srv/git/repo.git", "--no-serve", "--port", "9000"])
    output = " ".join(_plain_output(result).split())
    assert result.exit_code == 2
    assert "--port not valid with --no-serve" in output


def test_no_serve_rejects_a_local_path(tmp_path: Path) -> None:
    result = runner.invoke(_app, [str(tmp_path), "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "ROOT is a local path" in str(result.exception)
    assert "file://" in str(result.exception)


def test_https_no_serve_is_not_acquired() -> None:
    result = runner.invoke(_app, ["https://example.com/owner/repo.git", "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "https Git sources are not acquired yet" in str(result.exception)


def test_ssh_no_serve_is_not_acquired() -> None:
    result = runner.invoke(_app, ["ssh://git@example.com/owner/repo.git", "--no-serve"])
    assert isinstance(result.exception, CLIError)
    assert "ssh Git sources are not acquired yet" in str(result.exception)


def test_https_api_cache_is_not_acquired() -> None:
    result = runner.invoke(
        _app, ["https://example.com/owner/repo.git", "--api", "/api/cache/layout"]
    )
    assert isinstance(result.exception, CLIError)
    assert "https Git sources are not acquired yet" in str(result.exception)
