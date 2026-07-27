"""Plugin modes: diagnostics for the plugin discovery layer.

Three modes on the ``metab`` CLI (parsing lives in
:mod:`metabrowser.cli.main`):

* ``metab --plugins``      — table of every discovered plugin.
* ``metab --plugin NAME``  — full manifest dump for one plugin.
* ``metab --doctor``       — sanity-check every plugin: validate the
  manifest, confirm sidekick handlers import, check for asset / kind-id
  collisions across plugins. Exit code != 0 when any plugin is broken.

These modes answer the operator question 'is my plugin loaded?'
without having to start the server. They use the same discovery
sources serving does, including the same ``.env`` / ``.env.local``
walk + ``METABROWSER_PLUGINS_DIRS`` env var, so serving and
``--plugins`` agree by default — no need to repeat ``--plugins-dir``
flags between invocations.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import typer

from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.errors import CLIError
from metabrowser.plugin_loader.discovery import LoadedPlugin, discover_plugins
from metabrowser.plugin_loader.manifest import DataHookSpec


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


def _active_data_hooks(plugin: LoadedPlugin) -> list[DataHookSpec]:
    """Return only hooks the server will register for this plugin source."""
    if plugin.source.startswith("local:"):
        return []
    return list(plugin.manifest.data_hook)


def _disabled_data_hooks(plugin: LoadedPlugin) -> list[DataHookSpec]:
    """Return hooks suppressed by the operator-directory trust boundary."""
    if plugin.source.startswith("local:"):
        return list(plugin.manifest.data_hook)
    return []


def _plugin_summary(plugin: LoadedPlugin) -> dict[str, object]:
    """Return the stable plugin summary used by registry listings."""
    return {
        "name": plugin.name,
        "display_name": plugin.manifest.plugin.display_name,
        "version": plugin.manifest.plugin.version,
        "source": plugin.source,
        "static_root": str(plugin.static_root),
        "kinds": sorted({kind.id for kind in plugin.manifest.kind}),
        "views": [view.id for view in plugin.manifest.view],
        "view_count": len(plugin.manifest.view),
        "data_hooks": [hook.route for hook in _active_data_hooks(plugin)],
        "disabled_data_hooks": [hook.route for hook in _disabled_data_hooks(plugin)],
    }


def _plugin_assets(plugin: LoadedPlugin) -> list[str]:
    """Return sorted asset paths relative to the plugin root."""
    if not plugin.static_root.is_dir():
        return []
    return [
        child.relative_to(plugin.static_root).as_posix()
        for child in sorted(plugin.static_root.rglob("*"))
        if child.is_file()
    ]


def _plugin_details(plugin: LoadedPlugin) -> dict[str, object]:
    """Return the resolved plugin details exposed by ``--plugin NAME --json``."""
    return {
        "name": plugin.name,
        "display_name": plugin.manifest.plugin.display_name,
        "version": plugin.manifest.plugin.version,
        "sdk_version": plugin.manifest.plugin.sdk_version,
        "source": plugin.source,
        "static_root": str(plugin.static_root),
        "kinds": [kind.model_dump(mode="json", exclude_none=True) for kind in plugin.manifest.kind],
        "views": [view.model_dump(mode="json") for view in plugin.manifest.view],
        "data_hooks": [hook.model_dump(mode="json") for hook in _active_data_hooks(plugin)],
        "disabled_data_hooks": [
            hook.model_dump(mode="json") for hook in _disabled_data_hooks(plugin)
        ],
        "assets": _plugin_assets(plugin),
    }


def _echo_discovery_errors(errors: list[str]) -> None:
    """Write human-readable discovery failures to stderr."""
    typer.echo("", err=True)
    typer.echo("Discovery errors:", err=True)
    for error in errors:
        typer.echo(f"  • {error}", err=True)


def list_plugins(plugins_dir: list[Path] | None = None, *, as_json: bool = False) -> None:
    """List every discovered plugin (name, source, kinds, view count, hooks)."""
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    if as_json:
        out = {
            "plugins": [_plugin_summary(plugin) for plugin in result.plugins],
            "errors": result.errors,
        }
        typer.echo(json.dumps(out, indent=2))
        if result.errors:
            raise typer.Exit(code=1)
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
                ",".join(h.route for h in _active_data_hooks(p)) or "-",
            ]
        )
    headers = ["NAME", "SOURCE", "KINDS", "VIEWS", "HOOKS"]
    if rows:
        typer.echo(_format_table(rows, headers))
    else:
        typer.echo("(no plugins discovered)")
    if result.errors:
        _echo_discovery_errors(result.errors)
        raise typer.Exit(code=1)


def show_plugin(name: str, plugins_dir: list[Path] | None = None, *, as_json: bool = False) -> None:
    """Print the full resolved manifest for one plugin."""
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    plugin = next((p for p in result.plugins if p.name == name), None)
    if plugin is None:
        names = sorted(p.name for p in result.plugins)
        message = (
            f"plugin '{name}' not discovered. Found: {', '.join(names) if names else '(none)'}"
        )
        if as_json:
            typer.echo(
                json.dumps(
                    {"error": message, "discovery_errors": result.errors},
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=1)
        raise CLIError(message)

    if as_json:
        typer.echo(
            json.dumps(
                {"plugin": _plugin_details(plugin), "errors": result.errors},
                indent=2,
            )
        )
        if result.errors:
            raise typer.Exit(code=1)
        return

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
    active_hooks = _active_data_hooks(plugin)
    disabled_hooks = _disabled_data_hooks(plugin)
    for h in active_hooks:
        methods = ",".join(h.methods)
        typer.echo(f"  - {h.route} [{methods}] -> {h.sidekick}")
    if disabled_hooks:
        routes = ", ".join(h.route for h in disabled_hooks)
        typer.echo(f"  (disabled for operator-directory plugins: {routes})")
    elif not active_hooks:
        typer.echo("  (none)")
    typer.echo("")
    typer.echo("assets in static_root:")
    for asset in _plugin_assets(plugin):
        typer.echo(f"  - {asset}")
    if result.errors:
        _echo_discovery_errors(result.errors)
        raise typer.Exit(code=1)


def doctor_plugins(plugins_dir: list[Path] | None = None, *, as_json: bool = False) -> None:
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

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "ok": not problems,
                    "plugin_count": len(result.plugins),
                    "problems": problems,
                },
                indent=2,
            )
        )
        if problems:
            raise typer.Exit(code=1)
        return

    if problems:
        typer.echo(f"metab --doctor: {len(problems)} problem(s):", err=True)
        for problem in problems:
            typer.echo(f"  • {problem}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"metab --doctor: {len(result.plugins)} plugin(s) OK")


def _plugins_with_index_check(plugins: list[LoadedPlugin]) -> list[str]:
    """Return error messages for plugins whose index.js is missing on disk."""
    out: list[str] = []
    for p in plugins:
        if not (p.static_root / "index.js").is_file():
            out.append(f"plugin '{p.name}': index.js missing in {p.static_root}")
    return out
