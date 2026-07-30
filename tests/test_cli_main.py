"""Tests for the flat single-command Metabrowser CLI.

``metab ROOT`` serves by default; ``--walk``, ``--remote``, ``--plugins``,
``--plugin``, and ``--doctor`` select the other modes. Exactly one mode
applies per invocation, and explicitly-passed options that do not apply
to the selected mode are usage errors (exit 2).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Protocol
from unittest.mock import patch

import pytest
import uvicorn
from click import unstyle
from typer.testing import CliRunner

from metabrowser import __version__
from metabrowser.cli.main import _app, main
from metabrowser.cli.serve import _QuietForceExitServer, _shutdown_noise_filter
from metabrowser.errors import CLIError
from metabrowser.server_utils import MAX_TCP_PORT

runner = CliRunner()


class _ResultWithOutput(Protocol):
    """Structural result type shared by Click and Typer test runners."""

    @property
    def output(self) -> str:
        """Return captured terminal output."""
        ...


def _plain_output(result: _ResultWithOutput) -> str:
    """Strip ANSI escape codes from a CliRunner result for substring asserts.

    Rich-rendered Typer help on narrow terminals (e.g. GitHub Actions) inserts
    color/style codes mid-word, which breaks literal substring searches like
    ``"--path" in result.output``. ``click.unstyle`` removes them.
    """
    return unstyle(result.output)


# ── Top-level surface ──────────────────────────────────────────


def test_cli_help_shows_modes_and_examples() -> None:
    result = runner.invoke(_app, ["--help"])
    output = _plain_output(result)
    compact_output = " ".join(output.split())
    assert result.exit_code == 0
    assert "[ROOT]" in compact_output
    assert "--walk" in output
    assert "--remote" in output
    assert "--plugins" in output
    assert "--plugin" in output
    assert "--doctor" in output
    assert "--version" in output
    assert "metab ." in compact_output
    assert "metab --remote my-vm --path /srv/runs" in compact_output


def test_cli_version_uses_installed_package_metadata() -> None:
    result = runner.invoke(_app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"metab {__version__}"


def test_cli_empty_command_shows_help_instead_of_serving_default_root() -> None:
    result = runner.invoke(_app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output
    assert "--walk" in _plain_output(result)


def test_cli_old_subcommand_spelling_is_rejected() -> None:
    """``metab serve .`` is not a subcommand anymore; the extra positional
    is a usage error rather than silently serving a directory named `serve`.
    """
    result = runner.invoke(_app, ["serve", "."])
    assert result.exit_code == 2
    assert "unexpected extra argument" in _plain_output(result).lower()


# ── Mode selection and option applicability ────────────────────


def test_cli_mode_flags_are_mutually_exclusive() -> None:
    result = runner.invoke(_app, [".", "--walk", "--plugins"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "mutually exclusive" in output
    assert "--walk" in output
    assert "--plugins" in output


@pytest.mark.parametrize(
    ("args", "rejected", "mode"),
    [
        ([".", "--walk", "--port", "9000"], "--port", "--walk"),
        ([".", "--walk", "--no-open"], "--no-open", "--walk"),
        ([".", "--format", "json"], "--format", "serve mode"),
        ([".", "--detail", "summary"], "--detail", "serve mode"),
        ([".", "--json"], "--json", "serve mode"),
        (["--plugins", "--port", "9000"], "--port", "--plugins"),
        (["--doctor", "--log-level", "debug"], "--log-level", "--doctor"),
        (["--remote", "vm", "--path", "/runs", "--port", "9000"], "--port", "--remote"),
        (["--remote", "vm", "--path", "/runs", "--json"], "--json", "--remote"),
    ],
)
def test_cli_rejects_options_outside_selected_mode(
    args: list[str], rejected: str, mode: str
) -> None:
    result = runner.invoke(_app, args)
    output = " ".join(_plain_output(result).split())
    assert result.exit_code == 2
    assert f"{rejected} not valid with {mode}" in output


def test_cli_defaulted_options_never_trigger_mode_rejection(tmp_path: Path) -> None:
    """Only explicitly-passed options are applicability-checked: a plain
    walk must not trip over serve-option defaults."""
    result = runner.invoke(_app, [str(tmp_path), "--walk", "--max-depth", "0"])
    assert result.exit_code == 0, result.output


def test_cli_serve_requires_root() -> None:
    result = runner.invoke(_app, ["--no-open"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "ROOT is required" in output


def test_cli_walk_requires_root() -> None:
    result = runner.invoke(_app, ["--walk"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "ROOT is required" in output


@pytest.mark.parametrize(
    "args",
    [
        [".", "--plugins"],
        [".", "--plugin", "markdown"],
        [".", "--doctor"],
        [".", "--remote", "vm", "--path", "/runs"],
    ],
)
def test_cli_root_rejected_outside_serve_and_walk(args: list[str]) -> None:
    result = runner.invoke(_app, args)
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "ROOT is not used" in output


def test_cli_remote_requires_explicit_path() -> None:
    result = runner.invoke(_app, ["--remote", "my-vm"])
    output = _plain_output(result)
    assert result.exit_code == 2
    assert "--path" in output


# ── Value validation during parsing ────────────────────────────


@pytest.mark.parametrize(
    "args",
    [
        [".", "--walk", "--format", "xml"],
        [".", "--walk", "--detail", "verbose"],
        [".", "--walk", "--log-level", "trace"],
        [".", "--walk", "--max-depth", "-1"],
        [".", "--walk", "--max-files", "0"],
        [".", "--port", "0", "--no-open"],
        [".", "--port", str(MAX_TCP_PORT + 1), "--no-open"],
        [".", "--log-level", "trace", "--no-open"],
    ],
)
def test_cli_rejects_invalid_option_values_during_parsing(args: list[str]) -> None:
    result = runner.invoke(_app, args)

    assert result.exit_code == 2
    assert "Invalid value" in _plain_output(result)


# ── Console entry point ────────────────────────────────────────


def test_console_entry_point_reports_expected_errors_without_tracebacks(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    result = subprocess.run(
        [sys.executable, "-m", "metabrowser.cli.main", str(missing), "--no-open"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    assert f"Error: {missing} is not a directory" in result.stderr
    assert "Traceback" not in result.stderr


def test_console_entry_point_treats_closed_output_pipe_as_success(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    # Exceed a typical pipe buffer so the producer is still writing after the
    # consumer reads one record and closes its end of the pipe.
    for index in range(1_000):
        (root / f"artifact-{index:04d}.txt").write_text("payload")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "metabrowser.cli.main",
            str(root),
            "--walk",
            "--format",
            "json",
            "--stream",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    assert process.stdout.readline().startswith("{")
    process.stdout.close()
    stderr = process.stderr.read()
    returncode = process.wait(timeout=30)

    assert returncode == 0, stderr
    assert "BrokenPipeError" not in stderr


def test_console_entry_point_does_not_hide_unrelated_broken_pipe(monkeypatch) -> None:
    def _raise_unrelated_broken_pipe(**_kwargs: object) -> None:
        raise BrokenPipeError("internal pipe failed")

    monkeypatch.setattr("metabrowser.cli.main._app", _raise_unrelated_broken_pipe)

    with pytest.raises(BrokenPipeError, match="internal pipe failed"):
        main()


def test_server_module_execution_delegates_to_canonical_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "metabrowser.server", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--plugins" in result.stdout
    assert "--remote" in result.stdout
    assert "--walk" in result.stdout


# ── Serve mode ─────────────────────────────────────────────────


def test_shutdown_noise_filter_drops_expected_cancellation_only() -> None:
    cancelled = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        0,
        "Exception in ASGI application",
        (),
        (asyncio.CancelledError, asyncio.CancelledError(), None),
    )
    timeout = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        0,
        "Cancel 1 running task(s), timeout graceful shutdown exceeded",
        (),
        None,
    )
    unexpected = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        0,
        "Exception in ASGI application",
        (),
        (RuntimeError, RuntimeError("unexpected"), None),
    )

    assert not _shutdown_noise_filter(cancelled)
    assert not _shutdown_noise_filter(timeout)
    assert _shutdown_noise_filter(unexpected)


def test_force_exit_silences_uvicorn_error_logger() -> None:
    """A first Ctrl-C shuts down gracefully with logging intact; a second
    (force exit) abandons the lifespan, whose cancellation uvicorn reports
    as a pre-formatted error record, so the logger goes quiet instead."""

    async def dummy_app(scope: object, receive: object, send: object) -> None: ...

    # Construct first: ``uvicorn.Config`` reconfigures logging levels.
    server = _QuietForceExitServer(uvicorn.Config(app=dummy_app))
    uvicorn_logger = logging.getLogger("uvicorn.error")
    original_level = uvicorn_logger.level
    try:
        server.handle_exit(signal.SIGINT, None)
        assert server.should_exit and not server.force_exit
        assert uvicorn_logger.level == original_level

        server.handle_exit(signal.SIGINT, None)
        assert server.force_exit
        assert uvicorn_logger.level == logging.CRITICAL
    finally:
        uvicorn_logger.setLevel(original_level)


def test_cli_bare_path_routes_to_serve() -> None:
    """A bare path positional serves: a nonexistent directory fails on the
    directory check, not on argument routing."""
    result = runner.invoke(_app, ["/this/path/does/not/exist/anywhere"])
    assert "No such command" not in result.output

    assert isinstance(result.exception, CLIError)
    assert "not a directory" in str(result.exception)


def test_serve_expands_home_relative_root(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    root = home / "artifacts"
    root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_cls,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, ["~/artifacts", "--no-open"])

    assert result.exit_code == 0, result.exception
    server_cls.assert_called_once()
    config = server_cls.call_args.args[0]
    assert config.timeout_graceful_shutdown == 0
    server_cls.return_value.run.assert_called_once_with()
    assert _shutdown_noise_filter not in logging.getLogger("uvicorn.error").filters
    assert f"Serving {root.resolve()}" in result.output


def test_serve_removes_shutdown_filter_when_uvicorn_fails(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger.removeFilter(_shutdown_noise_filter)

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_cls,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        server_cls.return_value.run.side_effect = RuntimeError("server stopped")
        result = runner.invoke(_app, [str(root), "--no-open"])

    assert isinstance(result.exception, RuntimeError)
    assert _shutdown_noise_filter not in uvicorn_logger.filters


def test_serve_loads_dotenv_before_expanding_home_relative_root(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "dotenv-home"
    root = home / "artifacts"
    root.mkdir(parents=True)
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / ".env").write_text(f"HOME={home}\n")
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("HOME", raising=False)

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_cls,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = runner.invoke(_app, ["~/artifacts", "--no-open"])

    assert result.exit_code == 0, result.exception
    server_cls.assert_called_once()
    assert f"Serving {root.resolve()}" in result.output


def test_serve_rejects_deep_links_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (root / "outside-link").symlink_to(outside)

    for path in ("../outside.txt", "outside-link"):
        with (
            patch("metabrowser.cli.serve._QuietForceExitServer") as server_cls,
            patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
        ):
            result = runner.invoke(
                _app,
                [str(root), "--path", path, "--no-open"],
            )

        assert isinstance(result.exception, CLIError)
        assert "outside the served root" in str(result.exception)
        server_cls.assert_not_called()


def test_serve_rejects_file_root_with_path_as_usage_error(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("payload")

    result = runner.invoke(
        _app,
        [str(artifact), "--path", "nested", "--no-open"],
    )

    assert result.exit_code == 2
    output = " ".join(_plain_output(result).split())
    assert "cannot" in output
    assert "combine with --path" in output


def test_serve_wildcard_bind_uses_loopback_url_and_keeps_host_validation(
    tmp_path: Path,
) -> None:
    """--host 0.0.0.0 binds every interface but prints and probes loopback.

    Regression: the Host-validation middleware rejected ``Host: 0.0.0.0``,
    so the printed URL was unusable and auto-open never fired. The wildcard
    bind must never be added to the allowlist (that would disable the
    DNS-rebinding guard); the local URL uses loopback instead.
    """
    from metabrowser import server

    with patch("metabrowser.cli.serve._QuietForceExitServer") as server_cls:
        result = runner.invoke(_app, [str(tmp_path), "--no-open", "--host", "0.0.0.0"])
    assert result.exit_code == 0, _plain_output(result)
    assert "http://127.0.0.1:" in _plain_output(result)
    assert "http://0.0.0.0" not in _plain_output(result)
    assert server_cls.call_args.args[0].host == "0.0.0.0"
    assert not server._EXTRA_ALLOWED_HOSTS & {"0.0.0.0", "::", "[::]"}


def test_serve_concrete_bind_host_is_permitted_by_middleware(tmp_path: Path) -> None:
    """A concrete --host value is registered with the Host allowlist."""
    from metabrowser import server

    try:
        with patch("metabrowser.cli.serve._QuietForceExitServer"):
            result = runner.invoke(_app, [str(tmp_path), "--no-open", "--host", "127.0.0.1"])
        assert result.exit_code == 0, _plain_output(result)
        assert "127.0.0.1" in server._EXTRA_ALLOWED_HOSTS
        # A non-loopback concrete host registers its normalized name. Use the
        # registration helper directly for a LAN-style name so the test does
        # not depend on binding a real non-local interface.
        server._register_allowed_host("build-box.lan:9000")
        assert "build-box.lan" in server._EXTRA_ALLOWED_HOSTS
    finally:
        server._EXTRA_ALLOWED_HOSTS.discard("build-box.lan")
        server._EXTRA_ALLOWED_HOSTS.discard("127.0.0.1")


# ── Walk mode ──────────────────────────────────────────────────


def test_walk_restores_process_logging_state(tmp_path: Path) -> None:
    logger = logging.getLogger("metabrowser")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate

    result = runner.invoke(_app, [str(tmp_path), "--walk", "--max-depth", "0"])

    assert result.exit_code == 0, result.exception
    assert logger.handlers == original_handlers
    assert logger.level == original_level
    assert logger.propagate is original_propagate


def test_walk_rejects_subpaths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (root / "outside-link").symlink_to(outside)

    for path in ("../outside.txt", "outside-link"):
        result = runner.invoke(
            _app,
            [str(root), "--walk", "--format", "json", "--path", path],
        )

        assert isinstance(result.exception, CLIError)
        assert "outside the served root" in str(result.exception)


def test_walk_rejects_path_in_modes_that_cannot_scope_to_a_subtree(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    (root / "nested").mkdir(parents=True)

    for args in (
        [str(root), "--walk", "--path", "nested"],
        [str(root), "--walk", "--format", "json", "--stream", "--path", "nested"],
    ):
        result = runner.invoke(_app, args)

        assert result.exit_code == 2
        output = " ".join(_plain_output(result).split())
        assert "--path" in output
        assert "requires --format json or yaml with --all-at-once" in output


def test_walk_rejects_file_subpaths(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "artifact.json").write_text("{}")

    result = runner.invoke(
        _app,
        [str(root), "--walk", "--format", "json", "--path", "artifact.json"],
    )

    assert isinstance(result.exception, CLIError)
    assert "--path target is not a directory" in str(result.exception)


# ── Plugin modes ───────────────────────────────────────────────


def test_cli_plugins_list_works() -> None:
    result = runner.invoke(_app, ["--plugins"])
    assert result.exit_code == 0
    # Built-in plugins should always be discovered.
    assert "agent-log" in result.output
    assert "markdown" in result.output
