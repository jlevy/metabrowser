"""Metabrowser CLI with `serve`, `plugins`, `remote`, and `walk` subcommands.

The canonical command is `metab`; `metabrowser` is a compatibility alias.
The single-argument form `metab ./runs` is forwarded to ``serve`` when no subcommand is
named.

Examples:
    metab path/to/run-dir              # browse a specific run directory
    metab path/to/file.jsonl           # open file directly (sets root to parent)
    metab run-dir --path .logs/predict/ALPHA.jsonl   # open file within run

    metab plugins list                 # what's discovered?
    metab plugins show example         # one plugin's manifest
    metab plugins doctor               # validate all plugins

    metab remote my-vm --path /mnt/filestore/runs   # SSH-tunnel from a remote host
    metab remote my-vm --gcp --path /mnt/filestore/runs
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import webbrowser
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO, cast
from urllib.parse import quote

import typer
import uvicorn

from metabrowser import __version__
from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.cli.plugins import plugins_app
from metabrowser.cli.remote import remote as _remote_command
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.server_utils import (
    MAX_TCP_PORT,
    find_available_local_port,
    port_search_range,
)
from metabrowser.settings import DEFAULT_BROWSER_PORT
from metabrowser.walk import DETAIL_LEVELS, FORMATS, dump_tree, stream_dump_lines, walk_report


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except (webbrowser.Error, OSError) as exc:
        typer.echo(f"Could not auto-open browser ({exc}); visit {url} manually.", err=True)


def _wait_for_http_ok_then_open(
    host: str,
    port: int,
    url: str,
    *,
    timeout_s: float = 10.0,
) -> None:
    """Poll the index route until it serves HTTP OK, then open the URL.

    Polls every 50 ms up to ``timeout_s``. A bare TCP accept is not
    enough: the probe requires a non-error HTTP response from the index
    route, preventing auto-open before uvicorn is ready.
    On timeout or 4xx/5xx, print the URL and leave the browser closed.
    """
    wait_for_http_ok_then(
        host,
        port,
        url,
        on_ready=lambda: _open_browser(url),
        on_error=lambda message: typer.echo(message, err=True),
        timeout_s=timeout_s,
    )


_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _validate_format(value: str) -> str:
    if value not in FORMATS:
        raise typer.BadParameter(f"must be one of {', '.join(FORMATS)}")
    return value


def _validate_detail(value: str) -> str:
    if value not in DETAIL_LEVELS:
        raise typer.BadParameter(f"must be one of {', '.join(DETAIL_LEVELS)}")
    return value


def _validate_log_level(value: str | None) -> str:
    if not value:
        return ""
    upper = value.upper()
    if upper not in _VALID_LOG_LEVELS:
        raise typer.BadParameter(f"must be one of {', '.join(_VALID_LOG_LEVELS)}")
    return upper


def _shutdown_noise_filter(record: logging.LogRecord) -> bool:
    """Drop Uvicorn's expected cancellation records during local shutdown.

    `serve` cancels open SSE streams on Ctrl-C. Uvicorn reports those expected
    cancellations as errors even though no actionable server failure occurred.
    """
    if record.exc_info is not None and isinstance(record.exc_info[1], asyncio.CancelledError):
        return False
    return "timeout graceful shutdown exceeded" not in record.getMessage()


def _validate_contained_path(root: Path, requested: str) -> Path:
    """Require a requested path to exist within the resolved root."""
    target = (root / requested).resolve()
    if not target.is_relative_to(root):
        raise CLIError(f"--path target is outside the served root: {requested}")
    if not target.exists():
        raise CLIError(f"--path target does not exist: {target}")
    return target


def _apply_log_level(level: str | None) -> None:
    """Export ``METABROWSER_LOG_LEVEL`` so the logging setup at server
    import (``server._setup_perf_logging``) and the walk command pick
    up the requested verbosity. ``--log-level debug`` is the general
    knob for tracing the walker — e.g. every ``rewalk_subtree`` target
    and its resolved path — without a feature-specific flag.
    """

    # ``isinstance str`` guard: when ``serve`` is invoked as a plain
    # function (some tests do this) rather than through Typer, unpassed
    # options arrive as ``OptionInfo`` sentinels instead of resolved
    # strings. Treat anything non-string / empty as "no level set".
    if not isinstance(level, str) or not level:
        return
    upper = level.upper()
    if upper not in _VALID_LOG_LEVELS:
        raise CLIError(
            f"invalid --log-level {level!r}; expected one of {', '.join(_VALID_LOG_LEVELS)}"
        )
    os.environ["METABROWSER_LOG_LEVEL"] = upper


_app = typer.Typer(
    name="metab",
    add_completion=False,
    help=(
        "Browse local files from your web browser, with extensible plugin-based "
        "rendering of Markdown, code, JSON, YAML, logs, and other files."
    ),
    epilog=(
        "Examples:\n"
        "  metab ./path/to/artifacts\n"
        "  metab serve ./path/to/artifacts --no-open\n"
        "  metab plugins --help"
    ),
    no_args_is_help=False,
)
_app.add_typer(plugins_app, name="plugins")
_app.command("remote")(_remote_command)


@_app.command("serve")
def serve(
    root: Path = typer.Argument(..., help="Root directory (or file) to serve"),
    path: str = typer.Option("", "--path", help="Relative path from root to select on launch"),
    port: int = typer.Option(
        DEFAULT_BROWSER_PORT,
        "--port",
        min=1,
        max=MAX_TCP_PORT,
        help="Server port",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open browser"),
    plugins_dir: list[Path] | None = typer.Option(
        None,
        "--plugins-dir",
        help=(
            "Extra plugin directory; each subdirectory containing manifest.toml "
            "is loaded. May be passed multiple times. Combines additively with "
            "the METABROWSER_PLUGINS_DIRS env var (env-var dirs first, then CLI; "
            "deduped)."
        ),
    ),
    log_level: str = typer.Option(
        "",
        "--log-level",
        callback=_validate_log_level,
        metavar="LEVEL",
        help="Log verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
        "DEBUG traces the inventory walker (rewalk targets + resolved paths). "
        "Overrides METABROWSER_LOG_LEVEL.",
    ),
) -> None:
    """Launch a local web server to browse a directory's files.

    If ROOT is a file, automatically split into parent directory + --path.
    Use --path to deep-link directly to a file within the root directory.
    """
    # Dotenv is operator configuration for the entire command. Apply it before
    # log-level selection, plugin discovery, or path expansion so values such
    # as HOME affect every bootstrap step consistently with ``walk``.
    _load_dotenv_chain()

    # Must run before ``from metabrowser import server`` below — the
    # server module configures logging at import time from the env var.
    _apply_log_level(log_level)

    # Resolve file-as-ROOT shorthand before server initialization.
    resolved = root.expanduser().resolve()
    if resolved.is_file():
        if path:
            raise typer.BadParameter(
                f"{resolved} is a file — cannot combine with --path. "
                "Use the parent directory as ROOT instead.",
                param_hint="--path",
            )
        path = resolved.name
        resolved = resolved.parent

    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    # Normalize env/CLI plugin directories before the discovery layer first
    # runs at server-module import. This is the same path resolution and
    # validation used by ``metab plugins``.
    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    if path:
        _validate_contained_path(resolved, path)

    # Server import performs logging setup and plugin discovery. Keep it after
    # dotenv loading, CLI log-level application, and plugin-dir merging so all
    # startup configuration is visible on the first import.
    from metabrowser import server

    try:
        actual_port = find_available_local_port(host, port_search_range(port))
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    server._set_root_dir(resolved)

    url = f"http://{host}:{actual_port}"
    if path:
        url += f"#{quote(path)}"

    typer.echo(f"Serving {resolved} at {url}")
    if server._LOADED_PLUGINS:
        names = ", ".join(p.name for p in server._LOADED_PLUGINS)
        typer.echo(f"Plugins: {names}")

    # Race fix: open the browser only AFTER uvicorn is accepting
    # connections. The poll-then-open helper runs on a daemon thread
    # so uvicorn keeps signal handling in the main thread (Ctrl-C
    # still works).
    if not no_open:
        threading.Thread(
            target=_wait_for_http_ok_then_open,
            args=(host, actual_port, url),
            daemon=True,
        ).start()

    # Browser tabs hold open SSE streams, so cancel in-flight local requests rather
    # than waiting indefinitely for graceful shutdown after Ctrl-C.
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger.addFilter(_shutdown_noise_filter)
    try:
        uvicorn.run(
            server.app,
            host=host,
            port=actual_port,
            log_level="warning",
            timeout_graceful_shutdown=0,
        )
    finally:
        uvicorn_logger.removeFilter(_shutdown_noise_filter)


@_app.command("walk")
def walk(
    root: Path = typer.Argument(..., help="Directory to walk"),
    fmt: str = typer.Option(
        "text",
        "--format",
        callback=_validate_format,
        metavar="FORMAT",
        help="Output format: text (human report) | json | yaml. "
        "json/yaml dump the exact data the nav panel consumes.",
    ),
    stream: bool = typer.Option(
        False,
        "--stream/--all-at-once",
        help="Streaming emits one walker record per line (json→JSONL, yaml→doc stream), "
        "in walk order — the SSE upsert surface. All-at-once emits the full /api/tree "
        "envelope. Ignored for --format text.",
    ),
    subpath: str = typer.Option(
        "",
        "--path",
        help="Subtree (relative to root) for a JSON/YAML all-at-once tree envelope.",
    ),
    detail: str = typer.Option(
        "all",
        "--detail",
        callback=_validate_detail,
        metavar="LEVEL",
        help="Text-report detail: summary | dirs | all (only with --format text)",
    ),
    log_level: str = typer.Option(
        "",
        "--log-level",
        callback=_validate_log_level,
        metavar="LEVEL",
        help="Log verbosity (DEBUG traces every walker step). Overrides METABROWSER_LOG_LEVEL.",
    ),
    max_depth: int = typer.Option(20, "--max-depth", min=0, help="Max walk depth"),
    max_files: int = typer.Option(
        500_000,
        "--max-files",
        min=1,
        help="Max files before truncation",
    ),
) -> None:
    """Walk a directory with the inventory walker and dump the result.

    Runs the *same* walker + tree builder the server uses, with no HTTP
    server and no browser — the web UI only renders what these produce,
    so this is the full walk → analyze → build pipeline under test.

    \b
    Formats:
      --format text             human report (symlinks flagged, never followed)
      --format json             /api/tree envelope as JSON (what the nav fetches)
      --format yaml             same, as YAML
      --format json --stream    JSONL of every walker record, in walk order
      --format yaml --stream    YAML document stream of every walker record

    Pair with ``--log-level debug`` to trace the walk.
    """

    _load_dotenv_chain()
    _apply_log_level(log_level)
    with _walk_logging():
        _run_walk(root, fmt, stream, subpath, detail, max_depth, max_files)


def _run_walk(
    root: Path,
    fmt: str,
    stream: bool,
    subpath: str,
    detail: str,
    max_depth: int,
    max_files: int,
) -> None:
    """Execute a validated walk while the command logging scope is active."""

    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")
    if fmt not in FORMATS:
        raise CLIError(f"invalid --format {fmt!r}; expected one of {', '.join(FORMATS)}")
    if subpath and (fmt == "text" or stream):
        raise typer.BadParameter(
            "requires --format json or yaml with --all-at-once",
            param_hint="--path",
        )
    if subpath:
        target = _validate_contained_path(resolved, subpath)
        if not target.is_dir():
            raise CLIError(f"--path target is not a directory: {target}")

    if fmt == "text":
        if detail not in DETAIL_LEVELS:
            raise CLIError(
                f"invalid --detail {detail!r}; expected one of {', '.join(DETAIL_LEVELS)}"
            )
        typer.echo(
            walk_report(resolved, detail=detail, max_depth=max_depth, max_files=max_files),
            nl=False,
        )
        return

    if stream:
        # True streaming: print each record as the walker yields it.
        async def _emit() -> None:
            async for line in stream_dump_lines(
                resolved, fmt=fmt, max_depth=max_depth, max_files=max_files
            ):
                typer.echo(line)

        asyncio.run(_emit())
        return

    typer.echo(
        dump_tree(resolved, fmt=fmt, subpath=subpath, max_depth=max_depth, max_files=max_files),
        nl=False,
    )


@contextmanager
def _walk_logging() -> Generator[None]:
    """Scope a stderr handler to one ``walk`` command invocation.

    Attach the handler at the configured level so ``walk --log-level debug`` prints
    walker traces. Mirrors ``server._setup_perf_logging`` but stays lightweight (no
    server/plugin import). Restore process-global logger state so repeated in-process
    commands never retain a closed standard-error stream.
    """

    level_name = os.environ.get("METABROWSER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("metabrowser")
    previous_level = logger.level
    previous_propagate = logger.propagate
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


@_app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
    show_version: bool = typer.Option(
        False,
        "--version",
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Root selection is explicit; the empty command shows help."""
    if show_version:
        typer.echo(f"{ctx.info_name or 'metab'} {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


_KNOWN_SUBCOMMANDS = frozenset({"serve", "plugins", "remote", "walk"})


def _rewrite_bare_form(argv: list[str]) -> list[str]:
    """If the first positional looks like a path (not a subcommand or flag),
    prepend ``serve`` so ``metab <root>`` works.

    Examples:
      ``metab ./runs`` → ``metab serve ./runs``
      ``metab /tmp --no-open`` → ``metab serve /tmp --no-open``
      ``metab plugins list`` → unchanged (plugins is a known subcommand)
      ``metab --help`` → unchanged (flag, not a path)
      ``metab`` → unchanged (no positional; root is required)
    """
    if not argv:
        return argv
    first = argv[0]
    if first.startswith("-"):
        return argv  # flag (--help, -v, etc.)
    if first in _KNOWN_SUBCOMMANDS:
        return argv
    # Anything else is a positional that the user expects ``serve`` to handle.
    return ["serve", *argv]


class _PipeTrackingStream:
    """Delegate a text stream while recording downstream pipe closure."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.broken_pipe = False

    def write(self, data: str) -> int:
        try:
            return self.stream.write(data)
        except BrokenPipeError:
            self.broken_pipe = True
            raise

    def flush(self) -> None:
        try:
            self.stream.flush()
        except BrokenPipeError:
            self.broken_pipe = True
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


def _silence_broken_pipe(stream: TextIO) -> None:
    """Redirect a closed standard stream before interpreter finalization."""
    try:
        stream_fd = stream.fileno()
        null_fd = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError):
        return
    try:
        os.dup2(null_fd, stream_fd)
    finally:
        os.close(null_fd)


def _run_cli(argv: list[str], *, prog_name: str | None = None) -> None:
    """Run the canonical CLI with explicit arguments and shared error handling."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout = _PipeTrackingStream(original_stdout)
    stderr = _PipeTrackingStream(original_stderr)
    sys.stdout = cast(TextIO, stdout)
    sys.stderr = cast(TextIO, stderr)
    try:
        try:
            _app(args=_rewrite_bare_form(argv), prog_name=prog_name)
        except CLIError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from None
    except SystemExit as exc:
        if exc.code == 1 and (stdout.broken_pipe or stderr.broken_pipe):
            if stdout.broken_pipe:
                _silence_broken_pipe(original_stdout)
            if stderr.broken_pipe:
                _silence_broken_pipe(original_stderr)
            return
        raise
    except BrokenPipeError:
        if not (stdout.broken_pipe or stderr.broken_pipe):
            raise
        if stdout.broken_pipe:
            _silence_broken_pipe(original_stdout)
        if stderr.broken_pipe:
            _silence_broken_pipe(original_stderr)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def main() -> None:
    """Console-script entry point for `metab` and its `metabrowser` alias."""
    _run_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
