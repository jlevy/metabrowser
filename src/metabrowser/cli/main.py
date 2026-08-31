"""The ``metab`` CLI: one flat command whose default operation is serving.

``metab .`` serves the current directory the way ``open .`` opens it on
macOS. Every other operation is a mode flag on the same command:

    metab path/to/directory            # browse a directory
    metab path/to/example.txt          # open file directly (root = parent)
    metab path/to/directory --path documents/report.pdf  # deep-link within root

    metab . --walk --format json       # inventory walk, no server
    metab . --check-api                # exercise navigation APIs, no browser
    metab --remote example-host --path /srv/shared-files  # SSH-tunnel a remote host
    metab --plugins                    # what's discovered?
    metab --plugin example             # one plugin's manifest
    metab --doctor                     # validate all plugins

Exactly one mode applies per invocation. Options that do not apply to
the selected mode are rejected with a usage error, using Click's
parameter-source tracking so defaults never trigger false rejections.
The canonical command is ``metab``; ``metabrowser`` is an alias.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO, cast

import typer

from metabrowser import __version__
from metabrowser.build_version import display_version_line
from metabrowser.cli.common import PipeTrackingStream, silence_broken_pipe, validate_log_level
from metabrowser.cli.diff_cli import run_diff
from metabrowser.cli.plugins import doctor_plugins, list_plugins, show_plugin
from metabrowser.cli.remote import run_remote
from metabrowser.cli.serve import run_serve
from metabrowser.cli.walk_cli import (
    RECENCY_WINDOW_CHOICES,
    run_walk,
    validate_age,
    validate_detail,
    validate_format,
    validate_min_size,
)
from metabrowser.errors import CLIError
from metabrowser.server_utils import MAX_TCP_PORT
from metabrowser.settings import DEFAULT_BROWSER_PORT

_PANEL_MODES = "Modes (default: serve ROOT)"
_PANEL_SHARED = "Shared by multiple modes (each option names its modes)"
_PANEL_SERVE = "Serve"
_PANEL_WALK = "Walk (--walk)"
_PANEL_DIFF = "Diff (--diff SPEC)"
_PANEL_API = "API (--api ROUTE)"
_PANEL_CHECK_API = "API check (--check-api)"
_PANEL_REMOTE = "Remote (--remote)"
_PANEL_PLUGINS = "Plugins (--plugins / --plugin / --doctor)"

# Which explicitly-passed options each mode accepts, keyed by Click
# parameter name. Options outside every set (ROOT, --version, the mode
# selectors) are never applicability-checked.
_MODE_OPTIONS: dict[str, frozenset[str]] = {
    "serve": frozenset({"path", "port", "host", "no_open", "plugins_dir", "log_level"}),
    "walk": frozenset(
        {
            "fmt",
            "stream",
            "path",
            "detail",
            "max_depth",
            "max_files",
            "log_level",
            "filter_type",
            "filter_age",
            "filter_min_size",
            "filter_ignored",
        }
    ),
    "diff": frozenset({"fmt", "diff_patch", "diff_check", "log_level"}),
    "api": frozenset({"fmt", "data", "plugins_dir", "log_level", "index_timeout"}),
    "show": frozenset({"fmt", "plugins_dir", "log_level", "index_timeout"}),
    "check-api": frozenset({"plugins_dir", "log_level", "index_timeout"}),
    "remote": frozenset({"path", "base_port", "no_open", "ssh_options", "gcp", "zone", "project"}),
    "plugins": frozenset({"plugins_dir", "as_json"}),
    "plugin": frozenset({"plugins_dir", "as_json"}),
    "doctor": frozenset({"plugins_dir", "as_json"}),
}

_MODE_LABELS: dict[str, str] = {
    "serve": "serve mode (the default)",
    "walk": "--walk",
    "diff": "--diff",
    "api": "--api",
    "show": "--show",
    "check-api": "--check-api",
    "remote": "--remote",
    "plugins": "--plugins",
    "plugin": "--plugin",
    "doctor": "--doctor",
}

_OPTION_LABELS: dict[str, str] = {
    "path": "--path",
    "port": "--port",
    "host": "--host",
    "no_open": "--no-open",
    "plugins_dir": "--plugins-dir",
    "log_level": "--log-level",
    "fmt": "--format",
    "diff_patch": "--diff-patch",
    "diff_check": "--diff-check",
    "stream": "--stream/--all-at-once",
    "detail": "--detail",
    "max_depth": "--max-depth",
    "max_files": "--max-files",
    "filter_type": "--type",
    "filter_age": "--age",
    "filter_min_size": "--min-size",
    "filter_ignored": "--ignored/--no-ignored",
    "data": "--data",
    "index_timeout": "--index-timeout",
    "base_port": "--base-port",
    "ssh_options": "--ssh-options",
    "gcp": "--gcp",
    "zone": "--zone",
    "project": "--project",
    "as_json": "--json",
}


def _version_callback(ctx: typer.Context, value: bool) -> None:
    if value:
        # Annotated when this is a checkout rather than an installed release,
        # so a dev build cannot be mistaken for the tag it is sitting past.
        # See metabrowser.build_version.
        typer.echo(display_version_line(ctx.info_name or "metab", __version__))
        raise typer.Exit()


def _explicit_params(ctx: typer.Context) -> frozenset[str]:
    """Parameter names the user passed on the command line (not defaults).

    Sources are compared by name because Typer vendors Click: importing
    ``ParameterSource`` from the standalone ``click`` package would compare
    members of a different enum and never match.
    """
    explicit: set[str] = set()
    for name in ctx.params:
        source = ctx.get_parameter_source(name)
        if source is not None and source.name == "COMMANDLINE":
            explicit.add(name)
    return frozenset(explicit)


def _resolve_mode(
    ctx: typer.Context,
    *,
    walk: bool,
    diff: str | None,
    api: str | None,
    show: str | None,
    check_api: bool,
    remote: str | None,
    plugins: bool,
    plugin: str | None,
    doctor: bool,
) -> str:
    """Pick the single mode for this invocation or reject conflicting flags."""
    selected = [
        label
        for label, on in (
            ("--walk", walk),
            ("--diff", diff is not None),
            ("--api", api is not None),
            ("--show", show is not None),
            ("--check-api", check_api),
            ("--remote", remote is not None),
            ("--plugins", plugins),
            ("--plugin", plugin is not None),
            ("--doctor", doctor),
        )
        if on
    ]
    if len(selected) > 1:
        ctx.fail(f"mode flags are mutually exclusive; got {' and '.join(selected)}")
    if not selected:
        return "serve"
    return selected[0].lstrip("-")


# Formats each mode can actually produce. An envelope has no text rendering and
# --show's report has no YAML form, so a coerced value would be a flag that
# looks accepted while being ignored -- which is what the rest of this CLI
# promises never to do.
_MODE_FORMATS: dict[str, frozenset[str]] = {
    "api": frozenset({"json", "yaml"}),
    "show": frozenset({"text", "json"}),
}


def _check_format_applicability(
    ctx: typer.Context, mode: str, fmt: str, explicit: frozenset[str]
) -> None:
    allowed = _MODE_FORMATS.get(mode)
    if allowed is None or "fmt" not in explicit or fmt in allowed:
        return
    ctx.fail(
        f"--format {fmt} is not valid with {_MODE_LABELS[mode]}; "
        f"choose {' or '.join(sorted(allowed))}"
    )


def _check_option_applicability(ctx: typer.Context, mode: str, explicit: frozenset[str]) -> None:
    """Reject explicitly-passed options that do not apply to the mode."""
    checkable = frozenset().union(*_MODE_OPTIONS.values())
    stray = sorted((explicit & checkable) - _MODE_OPTIONS[mode])
    if stray:
        labels = ", ".join(_OPTION_LABELS[name] for name in stray)
        ctx.fail(f"{labels} not valid with {_MODE_LABELS[mode]}")


def _require_root(ctx: typer.Context, root: Path | None, mode: str) -> Path:
    if root is None:
        hints = {
            "serve": "e.g. `metab .`",
            "walk": "e.g. `metab . --walk`",
            "api": "e.g. `metab . --api /api/tree`",
            "show": "e.g. `metab . --show README.md`",
            "check-api": "e.g. `metab . --check-api`",
        }
        hint = hints.get(mode, "pass the required root")
        ctx.fail(f"ROOT is required for {_MODE_LABELS[mode]}; {hint}")
    return root


def _reject_root(ctx: typer.Context, root: Path | None, mode: str) -> None:
    if root is not None:
        message = f"ROOT is not used with {_MODE_LABELS[mode]}"
        if mode == "remote":
            message += "; pass the remote directory with --path"
        ctx.fail(message)


_app = typer.Typer(add_completion=False)


@_app.command(
    name="metab",
    epilog=(
        "Examples:\n\n"
        "metab .\n\n"
        "metab ./path/to/directory --no-open\n\n"
        "metab . --walk --format json\n\n"
        "metab . --api '/api/tree?depth=2'\n\n"
        "metab . --show README.md\n\n"
        "metab . --check-api\n\n"
        "metab --remote example-host --path /srv/shared-files\n\n"
        "metab --plugins\n\n"
        "Guide: https://github.com/jlevy/metabrowser/blob/main/docs/command-line.md"
    ),
)
def _metab(
    ctx: typer.Context,
    root: Path | None = typer.Argument(
        None,
        help=(
            "Root directory to serve, check, or walk; a file may be served directly. "
            "With no ROOT and no mode, prints help."
        ),
        show_default=False,
    ),
    # ── Mode selectors ─────────────────────────────────────────────
    walk: bool = typer.Option(
        False,
        "--walk",
        help="Walk ROOT with the inventory walker and dump the result (no server).",
        rich_help_panel=_PANEL_MODES,
    ),
    diff: str | None = typer.Option(
        None,
        "--diff",
        metavar="SPEC",
        help=(
            "Show a change set: BASE..TARGET, one revision (against its first "
            "parent), or a .patch/.diff file under ROOT."
        ),
        rich_help_panel=_PANEL_MODES,
    ),
    diff_patch: str | None = typer.Option(
        None,
        "--diff-patch",
        metavar="PATH",
        help="Print one changed file's hunks from the comparison (--diff only).",
        rich_help_panel=_PANEL_DIFF,
    ),
    diff_check: bool = typer.Option(
        False,
        "--diff-check",
        help="Run the apply oracle: rebuild the target tree and compare hashes (--diff only).",
        rich_help_panel=_PANEL_DIFF,
    ),
    api: str | None = typer.Option(
        None,
        "--api",
        metavar="ROUTE",
        help="Issue one /api/ route through the real request stack and print the "
        "normalized envelope (no browser, no listening port).",
        rich_help_panel=_PANEL_MODES,
    ),
    show: str | None = typer.Option(
        None,
        "--show",
        metavar="PATH",
        help="Report the four layers for one selection: route, kind, views, and a model summary.",
        rich_help_panel=_PANEL_MODES,
    ),
    data: Path | None = typer.Option(
        None,
        "--data",
        metavar="FILE",
        help="Send FILE as the request body, making the request a POST (--api only).",
        rich_help_panel=_PANEL_API,
    ),
    check_api: bool = typer.Option(
        False,
        "--check-api",
        help="Run the navigation API scenario without a browser or listening port.",
        rich_help_panel=_PANEL_MODES,
    ),
    remote: str | None = typer.Option(
        None,
        "--remote",
        metavar="HOST",
        help="SSH into HOST, start metab there, and tunnel it to localhost. "
        "Pass the remote directory with --path.",
        rich_help_panel=_PANEL_MODES,
        show_default=False,
    ),
    plugins: bool = typer.Option(
        False,
        "--plugins",
        help="List every discovered plugin.",
        rich_help_panel=_PANEL_MODES,
    ),
    plugin: str | None = typer.Option(
        None,
        "--plugin",
        metavar="NAME",
        help="Print the full resolved manifest for one plugin.",
        rich_help_panel=_PANEL_MODES,
        show_default=False,
    ),
    doctor: bool = typer.Option(
        False,
        "--doctor",
        help="Validate every discovered plugin; exit non-zero on any problem.",
        rich_help_panel=_PANEL_MODES,
    ),
    # ── Shared options ─────────────────────────────────────────────
    path: str = typer.Option(
        "",
        "--path",
        help="Serve: relative path from ROOT to select on launch. "
        "Walk: subtree for a JSON/YAML all-at-once tree envelope. "
        "Remote: remote directory to serve (required).",
        rich_help_panel=_PANEL_SHARED,
        show_default=False,
    ),
    no_open: bool = typer.Option(
        False,
        "--no-open",
        help="Don't auto-open the browser (serve and remote modes).",
        rich_help_panel=_PANEL_SHARED,
    ),
    plugins_dir: list[Path] | None = typer.Option(
        None,
        "--plugins-dir",
        help="Extra plugin directory; each subdirectory containing manifest.toml "
        "is loaded. May be passed multiple times. Combines additively with "
        "the METABROWSER_PLUGINS_DIRS env var (env-var dirs first, then CLI; "
        "deduped). Applies when serving, checking APIs, issuing --api or --show, and to the plugin modes.",
        rich_help_panel=_PANEL_SHARED,
        show_default=False,
    ),
    log_level: str = typer.Option(
        "",
        "--log-level",
        callback=validate_log_level,
        metavar="LEVEL",
        help="Log verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
        "DEBUG traces the inventory walker (rewalk targets + resolved paths). "
        "Overrides METABROWSER_LOG_LEVEL. Applies when serving, walking, issuing --api or --show, or checking APIs.",
        rich_help_panel=_PANEL_SHARED,
        show_default=False,
    ),
    # ── Serve options ──────────────────────────────────────────────
    port: int = typer.Option(
        DEFAULT_BROWSER_PORT,
        "--port",
        min=1,
        max=MAX_TCP_PORT,
        help="Server port.",
        rich_help_panel=_PANEL_SERVE,
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind to. A concrete value is automatically permitted by "
        "the Host-header allowlist; wildcard binds (0.0.0.0, ::) use "
        "loopback for the local URL, and additional trusted names can be "
        "allowed with METABROWSER_ALLOWED_HOSTS (see SECURITY.md).",
        rich_help_panel=_PANEL_SERVE,
    ),
    # ── Walk options ───────────────────────────────────────────────
    fmt: str = typer.Option(
        "text",
        "--format",
        callback=validate_format,
        metavar="FORMAT",
        help="Output format: text (human report) | json | yaml. "
        "Walk and diff: json/yaml dump the exact data the browser consumes. "
        "Show: json reports the four layers as an object. "
        "Api: json (default) or yaml renders the envelope.",
        rich_help_panel=_PANEL_SHARED,
    ),
    stream: bool = typer.Option(
        False,
        "--stream/--all-at-once",
        help="Streaming emits one walker record per line (json→JSONL, yaml→doc stream), "
        "in walk order (the SSE upsert surface). All-at-once emits the full /api/tree "
        "envelope. Ignored for --format text.",
        rich_help_panel=_PANEL_WALK,
    ),
    detail: str = typer.Option(
        "all",
        "--detail",
        callback=validate_detail,
        metavar="LEVEL",
        help="Text-report detail: summary | dirs | all (only with --format text).",
        rich_help_panel=_PANEL_WALK,
    ),
    max_depth: int = typer.Option(
        20,
        "--max-depth",
        min=0,
        help="Max walk depth.",
        rich_help_panel=_PANEL_WALK,
    ),
    max_files: int = typer.Option(
        500_000,
        "--max-files",
        min=1,
        help="Max files before truncation.",
        rich_help_panel=_PANEL_WALK,
    ),
    # ── Walk filter options ───────────────────────────────────────
    # The nav filter bar's own vocabulary, so "which folders survive this
    # filter, and what do they add up to" is answerable from a terminal
    # instead of from a browser. Same projection the /api/tree route uses.
    filter_type: list[str] = typer.Option(
        [],
        "--type",
        metavar="TOKEN",
        help="Keep only files of this type: an extension (.md, .min.js) or a whole "
        "filename (README). Repeatable, or comma-separated.",
        rich_help_panel=_PANEL_WALK,
    ),
    filter_age: str = typer.Option(
        "",
        "--age",
        callback=validate_age,
        metavar="WINDOW",
        help=f"Keep only files modified within a window: {', '.join(RECENCY_WINDOW_CHOICES)}.",
        rich_help_panel=_PANEL_WALK,
    ),
    filter_min_size: str = typer.Option(
        "",
        "--min-size",
        callback=validate_min_size,
        metavar="SIZE",
        help="Keep only files at least this large. Plain bytes or a k/m/g suffix (10m).",
        rich_help_panel=_PANEL_WALK,
    ),
    filter_ignored: bool = typer.Option(
        True,
        "--ignored/--no-ignored",
        help="Include gitignored entries in the filtered result.",
        rich_help_panel=_PANEL_WALK,
    ),
    # ── API check options ─────────────────────────────────────────
    index_timeout: float = typer.Option(
        60.0,
        "--index-timeout",
        min=0.1,
        metavar="SECONDS",
        help="Maximum time to wait for the inventory to finish. "
        "Applies to --api, --show, and --check-api.",
        rich_help_panel=_PANEL_SHARED,
    ),
    # ── Remote options ─────────────────────────────────────────────
    base_port: int = typer.Option(
        DEFAULT_BROWSER_PORT,
        "--base-port",
        min=1,
        max=MAX_TCP_PORT,
        help="Starting port for local + remote port search (walks upward).",
        rich_help_panel=_PANEL_REMOTE,
    ),
    ssh_options: str = typer.Option(
        "",
        "--ssh-options",
        help="Extra SSH flags (e.g. '-i ~/.ssh/mykey').",
        rich_help_panel=_PANEL_REMOTE,
        show_default=False,
    ),
    gcp: bool = typer.Option(
        False,
        "--gcp",
        help="Use gcloud compute ssh instead of plain ssh.",
        rich_help_panel=_PANEL_REMOTE,
    ),
    zone: str = typer.Option(
        "us-central1-b",
        "--zone",
        help="GCP zone (only with --gcp).",
        rich_help_panel=_PANEL_REMOTE,
    ),
    project: str = typer.Option(
        "",
        "--project",
        help="GCP project (only with --gcp).",
        rich_help_panel=_PANEL_REMOTE,
        show_default=False,
    ),
    # ── Plugin options ─────────────────────────────────────────────
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit structured JSON (plugin modes).",
        rich_help_panel=_PANEL_PLUGINS,
    ),
    # ── General ────────────────────────────────────────────────────
    show_version: bool = typer.Option(
        False,
        "--version",
        is_eager=True,
        callback=_version_callback,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Browse local files from your web browser, with extensible plugin-based
    rendering of Markdown, code, JSON, YAML, logs, and other files.

    Serving is the default: `metab .` serves the current directory and opens
    it in your browser. Select another operation with a mode flag.

    Data modes read the same server the browser reads, without a browser or a
    listening port: --api issues one route, --show reports the four layers
    behind one selection, --walk dumps the inventory, --diff shows a change
    set. Diagnostics: --check-api, --plugins, --plugin, --doctor. Remote
    serving: --remote.
    """
    mode = _resolve_mode(
        ctx,
        walk=walk,
        diff=diff,
        api=api,
        show=show,
        check_api=check_api,
        remote=remote,
        plugins=plugins,
        plugin=plugin,
        doctor=doctor,
    )
    explicit = _explicit_params(ctx)
    _check_option_applicability(ctx, mode, explicit)
    _check_format_applicability(ctx, mode, fmt, explicit)

    if mode == "serve":
        if root is None and not explicit:
            typer.echo(ctx.get_help())
            raise typer.Exit()
        run_serve(
            _require_root(ctx, root, mode),
            path=path,
            port=port,
            host=host,
            no_open=no_open,
            plugins_dir=plugins_dir,
            log_level=log_level,
        )
    elif mode == "walk":
        run_walk(
            _require_root(ctx, root, mode),
            fmt=fmt,
            stream=stream,
            subpath=path,
            detail=detail,
            max_depth=max_depth,
            max_files=max_files,
            log_level=log_level,
            types=tuple(filter_type),
            age=filter_age,
            min_size=filter_min_size,
            include_ignored=filter_ignored,
        )
    elif mode == "diff":
        assert diff is not None
        run_diff(
            _require_root(ctx, root, mode),
            spec=diff,
            fmt=fmt,
            patch_path=diff_patch,
            check=diff_check,
        )
    elif mode == "api":
        assert api is not None
        from metabrowser.cli.api_cli import run_api

        run_api(
            _require_root(ctx, root, mode),
            route=api,
            # Only the unset default is reinterpreted; an explicit --format text
            # is refused above rather than silently becoming json.
            fmt="json" if fmt == "text" else fmt,
            data=data,
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout,
        )
    elif mode == "show":
        assert show is not None
        from metabrowser.cli.show_cli import run_show

        run_show(
            _require_root(ctx, root, mode),
            path=show,
            fmt=fmt,
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout,
        )
    elif mode == "check-api":
        from metabrowser.cli.check_api import run_api_check

        run_api_check(
            _require_root(ctx, root, mode),
            plugins_dir=plugins_dir,
            log_level=log_level,
            index_timeout_s=index_timeout,
        )
    elif remote is not None:
        _reject_root(ctx, root, mode)
        if not path:
            ctx.fail("--remote requires --path with the remote directory to serve")
        run_remote(
            remote,
            path=path,
            base_port=base_port,
            no_open=no_open,
            ssh_options=ssh_options,
            gcp=gcp,
            zone=zone,
            project=project,
        )
    elif plugin is not None:
        _reject_root(ctx, root, mode)
        show_plugin(plugin, plugins_dir, as_json=as_json)
    elif mode == "plugins":
        _reject_root(ctx, root, mode)
        list_plugins(plugins_dir, as_json=as_json)
    else:
        _reject_root(ctx, root, mode)
        doctor_plugins(plugins_dir, as_json=as_json)


def _run_cli(argv: list[str], *, prog_name: str | None = None) -> None:
    """Run the CLI with explicit arguments and shared error handling."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout = PipeTrackingStream(original_stdout)
    stderr = PipeTrackingStream(original_stderr)
    sys.stdout = cast(TextIO, stdout)
    sys.stderr = cast(TextIO, stderr)
    try:
        try:
            _app(args=argv, prog_name=prog_name)
        except CLIError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(1) from None
    except SystemExit as exc:
        if exc.code == 1 and (stdout.broken_pipe or stderr.broken_pipe):
            if stdout.broken_pipe:
                silence_broken_pipe(original_stdout)
            if stderr.broken_pipe:
                silence_broken_pipe(original_stderr)
            return
        raise
    except BrokenPipeError:
        if not (stdout.broken_pipe or stderr.broken_pipe):
            raise
        if stdout.broken_pipe:
            silence_broken_pipe(original_stdout)
        if stderr.broken_pipe:
            silence_broken_pipe(original_stderr)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def main() -> None:
    """Console-script entry point for `metab` and its `metabrowser` alias."""
    _run_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
