"""metabrowser plugins — diagnostic CLI for the plugin discovery layer.

Three subcommands:

* ``metabrowser plugins list``  — table of every discovered plugin.
* ``metabrowser plugins show``  — full manifest dump for one plugin.
* ``metabrowser plugins doctor`` — sanity-check every plugin: validate the
  manifest, confirm sidekick handlers import, check for asset / kind-id
  collisions across plugins. Exit code != 0 when any plugin is broken.

These commands answer the operator question 'is my plugin loaded?'
without having to start the server. They use the same discovery
sources ``serve`` does, including the same ``.env`` / ``.env.local``
walk + ``METABROWSER_PLUGINS_DIRS`` env var, so ``serve`` and
``plugins list`` agree by default — no need to repeat ``--plugins-dir``
flags between commands.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import typer

from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.errors import CLIError
from metabrowser.plugin_loader.discovery import LoadedPlugin, discover_plugins

plugins_app = typer.Typer(
    name="plugins",
    add_completion=False,
    help="Inspect metabrowser plugin discovery (list / show / doctor).",
    no_args_is_help=True,
)


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    """Render a plain-text table (no external dep). Right-pad columns to width."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    lines = [fmt.format(*headers)]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


@plugins_app.command("list")
def cmd_list(
    plugins_dir: list[Path] | None = typer.Option(
        None,
        "--plugins-dir",
        help=(
            "Extra directory to scan for plugins. Each subdirectory containing "
            "manifest.toml is loaded. May be passed multiple times. Combines "
            "additively with the METABROWSER_PLUGINS_DIRS env var (loaded from "
            "the nearest .env / .env.local)."
        ),
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List every discovered plugin (name, source, kinds, view count, hooks)."""
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    if as_json:
        out = {
            "plugins": [
                {
                    "name": p.name,
                    "display_name": p.manifest.plugin.display_name,
                    "version": p.manifest.plugin.version,
                    "source": p.source,
                    "static_root": str(p.static_root),
                    "kinds": sorted({k.id for k in p.manifest.kind}),
                    "views": [view.id for view in p.manifest.view],
                    "view_count": len(p.manifest.view),
                    "data_hooks": [h.route for h in p.manifest.data_hook],
                }
                for p in result.plugins
            ],
            "errors": result.errors,
        }
        typer.echo(json.dumps(out, indent=2))
        return

    rows: list[list[str]] = []
    for p in result.plugins:
        kinds = sorted({k.id for k in p.manifest.kind})
        rows.append(
            [
                p.name,
                p.source,
                ",".join(kinds) if kinds else "-",
                str(len(p.manifest.view)),
                ",".join(h.route for h in p.manifest.data_hook) or "-",
            ]
        )
    headers = ["NAME", "SOURCE", "KINDS", "VIEWS", "HOOKS"]
    if rows:
        typer.echo(_format_table(rows, headers))
    else:
        typer.echo("(no plugins discovered)")
    if result.errors:
        typer.echo("", err=True)
        typer.echo("Discovery errors:", err=True)
        for err in result.errors:
            typer.echo(f"  • {err}", err=True)


@plugins_app.command("show")
def cmd_show(
    name: str = typer.Argument(..., help="Plugin name to show."),
    plugins_dir: list[Path] | None = typer.Option(
        None,
        "--plugins-dir",
        help="Extra plugin directory; may repeat. Combines with METABROWSER_PLUGINS_DIRS.",
    ),
) -> None:
    """Print the full resolved manifest for one plugin."""
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    plugin = next((p for p in result.plugins if p.name == name), None)
    if plugin is None:
        names = sorted(p.name for p in result.plugins)
        raise CLIError(
            f"plugin '{name}' not discovered. Found: {', '.join(names) if names else '(none)'}"
        )

    typer.echo(f"name:         {plugin.name}")
    typer.echo(f"display_name: {plugin.manifest.plugin.display_name or '(none)'}")
    typer.echo(f"version:      {plugin.manifest.plugin.version}")
    typer.echo(f"sdk_version:  {plugin.manifest.plugin.sdk_version}")
    typer.echo(f"source:       {plugin.source}")
    typer.echo(f"static_root:  {plugin.static_root}")
    typer.echo("")
    typer.echo("kinds:")
    for k in plugin.manifest.kind:
        match = k.match.model_dump(exclude_none=True)
        typer.echo(f"  - id={k.id} priority={k.priority} match={match}")
    typer.echo("")
    typer.echo("views:")
    for v in plugin.manifest.view:
        default = " (default)" if v.default else ""
        typer.echo(f"  - {v.kind}/{v.id} '{v.label}'{default}")
    typer.echo("")
    typer.echo("data hooks:")
    for h in plugin.manifest.data_hook:
        methods = ",".join(h.methods)
        typer.echo(f"  - {h.route} [{methods}] -> {h.sidekick}")
    typer.echo("")
    typer.echo("assets in static_root:")
    if plugin.static_root.is_dir():
        for child in sorted(plugin.static_root.rglob("*")):
            if child.is_file():
                rel = child.relative_to(plugin.static_root)
                typer.echo(f"  - {rel}")


@plugins_app.command("doctor")
def cmd_doctor(
    plugins_dir: list[Path] | None = typer.Option(
        None,
        "--plugins-dir",
        help="Extra plugin directory; may repeat. Combines with METABROWSER_PLUGINS_DIRS.",
    ),
) -> None:
    """Validate every discovered plugin. Exit non-zero on any problem."""
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    problems: list[str] = list(result.errors)

    # Cross-plugin: check kind ids declared at priority 100+ aren't claimed by
    # multiple plugins simultaneously (built-ins at priority 0 are allowed to
    # be overridden, that's the point).
    kind_owners: dict[str, list[str]] = {}
    for p in result.plugins:
        for k in p.manifest.kind:
            if k.priority < 100:
                continue
            kind_owners.setdefault(k.id, []).append(p.name)
    for kind_id, owners in kind_owners.items():
        if len(set(owners)) > 1:
            problems.append(
                f"kind '{kind_id}' claimed at priority>=100 by multiple plugins: {sorted(set(owners))}"
            )

    # Per-plugin: sidekick imports resolve.
    for p in result.plugins:
        if p.source.startswith("local:") and p.manifest.data_hook:
            problems.append(
                f"plugin '{p.name}' declares Python data hooks, but operator-directory "
                "plugins are JavaScript-only; package the plugin behind an installed "
                "metabrowser.plugins entry point"
            )
            continue
        for hook in p.manifest.data_hook:
            module_name, _, attr = hook.sidekick.partition(":")
            try:
                mod = importlib.import_module(module_name)
            except ImportError as exc:
                problems.append(
                    f"plugin '{p.name}' data_hook '{hook.route}': "
                    f"cannot import '{module_name}': {exc}"
                )
                continue
            if not hasattr(mod, attr):
                problems.append(
                    f"plugin '{p.name}' data_hook '{hook.route}': "
                    f"module '{module_name}' has no attribute '{attr}'"
                )
            elif not callable(getattr(mod, attr)):
                problems.append(
                    f"plugin '{p.name}' data_hook '{hook.route}': "
                    f"'{module_name}:{attr}' is not callable"
                )

    # Per-plugin: index.js exists.
    for p in _plugins_with_index_check(result.plugins):
        problems.append(p)

    if problems:
        typer.echo(f"metabrowser plugins doctor: {len(problems)} problem(s):")
        for prob in problems:
            typer.echo(f"  • {prob}")
        raise typer.Exit(code=1)

    typer.echo(f"metabrowser plugins doctor: {len(result.plugins)} plugin(s) OK")


def _plugins_with_index_check(plugins: list[LoadedPlugin]) -> list[str]:
    """Return error messages for plugins whose index.js is missing on disk."""
    out: list[str] = []
    for p in plugins:
        if not (p.static_root / "index.js").is_file():
            out.append(f"plugin '{p.name}': index.js missing in {p.static_root}")
    return out


def main() -> None:
    """Console-script entry point for `metabrowser-plugins`."""
    try:
        plugins_app()
    except CLIError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
