"""metabrowser CLI — `serve` + `plugins` + `remote` subcommands.

The legacy single-arg invocation `metabrowser ./runs` still works; it's
forwarded to ``serve`` by the top-level callback when no subcommand is
named.

Examples:
    metabrowser path/to/run-dir              # browse a specific run directory
    metabrowser path/to/file.jsonl           # open file directly (sets root to parent)
    metabrowser run-dir --path .logs/predict/ALPHA.jsonl   # open file within run

    metabrowser plugins list                 # what's discovered?
    metabrowser plugins show example         # one plugin's manifest
    metabrowser plugins doctor               # validate all plugins

    metabrowser remote my-vm --path /mnt/filestore/runs   # SSH-tunnel from a remote host
    metabrowser remote my-vm --gcp --path /mnt/filestore/runs
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote

import typer
import uvicorn

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.cli.plugins import plugins_app
from metabrowser.cli.remote import remote as _remote_command
from metabrowser.dotenv import load_dotenv_chain as _load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.server_utils import (
    DEFAULT_PORT_SEARCH_COUNT,
    find_available_local_port,
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

    Closes the racy auto-open path: webbrowser.open() used to fire before
    uvicorn finished binding the socket, so the browser's first GET could
    land on connection-refused (which renders as a "site can't be
    reached" / 404-shaped error in Chrome) — refresh worked because by
    then uvicorn was up.

    Polls every 50 ms up to ``timeout_s``. A bare TCP accept is not
    enough: the probe requires a non-error HTTP response from the index
    route so auto-open never puts the operator in a broken browser tab.
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


def _validate_contained_path(root: Path, requested: str) -> None:
    """Require a requested path to exist within the resolved root."""
    target = (root / requested).resolve()
    if not target.is_relative_to(root):
        raise CLIError(f"--path target is outside the served root: {requested}")
    if not target.exists():
        raise CLIError(f"--path target does not exist: {target}")


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
    name="metabrowser",
    add_completion=False,
    help="Local web UI for browsing run logs and structured artifacts.",
    no_args_is_help=False,
)
_app.add_typer(plugins_app, name="plugins")
_app.command("remote")(_remote_command)


@_app.command("serve")
def serve(
    root: Path = typer.Argument(..., help="Root directory (or file) to serve"),
    path: str = typer.Option("", "--path", help="Relative path from root to select on launch"),
    port: int = typer.Option(DEFAULT_BROWSER_PORT, "--port", help="Server port"),
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
        help="Log verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
        "DEBUG traces the inventory walker (rewalk targets + resolved paths). "
        "Overrides METABROWSER_LOG_LEVEL.",
    ),
) -> None:
    """Launch a local web server to browse run logs and results.

    If ROOT is a file, automatically split into parent directory + --path.
    Use --path to deep-link directly to a file within the root directory.
    """
    # Must run before ``from metabrowser import server`` below — the
    # server module configures logging at import time from the env var.
    _apply_log_level(log_level)

    # Resolve file-as-ROOT shorthand before server initialization.
    resolved = root.expanduser().resolve()
    if resolved.is_file():
        if path:
            raise CLIError(
                f"{resolved} is a file — cannot combine with --path. "
                "Use the parent directory as ROOT instead."
            )
        path = resolved.name
        resolved = resolved.parent

    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    # Load the dotenv chain and normalize env/CLI plugin directories before
    # the discovery layer first runs at server-module import. This is the same
    # path resolution and validation used by ``metabrowser plugins``.
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
        actual_port = find_available_local_port(host, range(port, port + DEFAULT_PORT_SEARCH_COUNT))
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

    uvicorn.run(server.app, host=host, port=actual_port, log_level="warning")


@_app.command("walk")
def walk(
    root: Path = typer.Argument(..., help="Directory to walk"),
    fmt: str = typer.Option(
        "text",
        "--format",
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
        help="Text-report detail: summary | dirs | all (only with --format text)",
    ),
    log_level: str = typer.Option(
        "",
        "--log-level",
        help="Log verbosity (DEBUG traces every walker step). Overrides METABROWSER_LOG_LEVEL.",
    ),
    max_depth: int = typer.Option(20, "--max-depth", help="Max walk depth"),
    max_files: int = typer.Option(500_000, "--max-files", help="Max files before truncation"),
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
    _configure_walk_logging()

    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")
    if fmt not in FORMATS:
        raise CLIError(f"invalid --format {fmt!r}; expected one of {', '.join(FORMATS)}")
    if subpath and (fmt == "text" or stream):
        raise CLIError("--path requires --format json or yaml with --all-at-once")
    if subpath:
        _validate_contained_path(resolved, subpath)

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

        import asyncio

        asyncio.run(_emit())
        return

    typer.echo(
        dump_tree(resolved, fmt=fmt, subpath=subpath, max_depth=max_depth, max_files=max_files),
        nl=False,
    )


def _configure_walk_logging() -> None:
    """Attach a stdout handler to the ``metabrowser`` logger at the
    configured level so ``walk --log-level debug`` actually prints the
    walker traces. Mirrors ``server._setup_perf_logging`` but stays
    lightweight (no server/plugin import)."""

    level_name = os.environ.get("METABROWSER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    lg = logging.getLogger("metabrowser")
    lg.setLevel(level)
    tag = "metabrowser-walk"
    if not any(getattr(h, "name", None) == tag for h in lg.handlers):
        handler = logging.StreamHandler()
        handler.set_name(tag)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s | %(message)s", datefmt="%H:%M:%S")
        )
        lg.addHandler(handler)
    lg.propagate = False


@_app.callback(invoke_without_command=True)
def _main_callback(ctx: typer.Context) -> None:
    """Root selection is explicit; the empty command shows help."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


_KNOWN_SUBCOMMANDS = frozenset({"serve", "plugins", "remote", "walk"})


def _rewrite_bare_form(argv: list[str]) -> list[str]:
    """If the first positional looks like a path (not a subcommand or flag),
    prepend ``serve`` so ``metabrowser <root>`` keeps working.

    Examples:
      ``metabrowser ./runs`` → ``metabrowser serve ./runs``
      ``metabrowser /tmp --no-open`` → ``metabrowser serve /tmp --no-open``
      ``metabrowser plugins list`` → unchanged (plugins is a known subcommand)
      ``metabrowser --help`` → unchanged (flag, not a path)
      ``metabrowser`` → unchanged (no positional; root is required)
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


def main() -> None:
    """Console-script entry point for `metabrowser`."""

    try:
        _app(args=_rewrite_bare_form(sys.argv[1:]))
    except CLIError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
