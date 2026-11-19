"""Plugin modes: diagnostics for the plugin discovery layer.

Three modes on the ``metab`` CLI (parsing lives in
:mod:`metabrowser.cli.main`):

* ``metab --plugins``: table of every discovered plugin.
* ``metab --plugin NAME``: full manifest dump for one plugin.
* ``metab --doctor``: sanity-check every plugin, validating the
  manifest, confirming sidekick handlers import, and checking for
  asset and kind-id collisions across plugins and for view keys the
  server drops from a kind's merged views. It also checks the
  packaged cache record contracts. Exit code != 0 when any plugin
  or contract is broken. After the verdict it reports each
  repository provider's tools, GitHub CLI's path, version,
  account, and scopes, which never change the exit code.

These modes answer the operator question 'is my plugin loaded?'
without having to start the server. They use the same discovery
sources serving does, including ``METABROWSER_PLUGINS_DIRS`` from
the process environment, so serving and ``--plugins`` agree by
default; there is no need to repeat ``--plugins-dir`` flags between
invocations. A ``.env`` file cannot name a plugin directory: see
``metabrowser.dotenv``.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.errors import CLIError
from metabrowser.keymap import check_view_keys
from metabrowser.plugin_loader.discovery import LoadedPlugin, discover_plugins
from metabrowser.plugin_loader.manifest import DataHookSpec, merge_views, view_entry

if TYPE_CHECKING:
    from metabrowser.cache.providers import ProviderStatus
    from metabrowser.cli.doctor import Check


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
        notes = ["default"] if v.default else []
        if v.key is not None:
            notes.append(f"key {v.key.upper()}")
        suffix = f" ({', '.join(notes)})" if notes else ""
        typer.echo(f"  - {v.kind}/{v.id} '{v.label}'{suffix}")
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


def _cache_contract_problems() -> list[str]:
    """Return what is wrong with the cache record contracts this installation ships.

    The repository cache validates every record it reads and writes against these
    packaged schemas, so a damaged or incomplete installation fails here rather than at
    the first acquisition. The import is local because this module loads on every
    ``metab`` start, and the contract registry pulls in the schema libraries that
    ``--version`` and ``import metabrowser`` are tested not to load.
    """
    from metabrowser.cache.contracts import cache_contract_registry, check_packaged_schemas

    problems: list[str] = []
    try:
        cache_contract_registry()
    except (OSError, RuntimeError, ValueError) as exc:
        problems.append(f"cache record contracts: {exc}")
    try:
        drifted = check_packaged_schemas()
    except (OSError, RuntimeError, ValueError) as exc:
        problems.append(f"cache record schemas: {exc}")
    else:
        # Each entry is "<schema file>: <diff>"; the file name is what a reader can act on.
        problems.extend(
            f"cache record schema '{entry.partition(':')[0]}' does not match its model"
            for entry in drifted
        )
    return problems


def _view_key_problems(plugins: list[LoadedPlugin]) -> list[str]:
    """Return the view keys the server drops from each kind's merged view list.

    The server serves the first view's key and drops a later duplicate or a key the
    shell reserves for the kind, without refusing the plugin, so this is where an
    author learns of it. The list is merged as the server merges it, from the built-in
    registry and the discovered manifests in discovery order. Each problem names the
    plugin whose view lost its key and, for a duplicate, the plugin whose view holds
    it. A view's plugin is the last manifest to declare its id, because an override
    replaces the earlier entry, so a plugin that overrides a built-in view and takes a
    letter is named as the holder. The registry import is local for the reason
    ``_cache_contract_problems`` gives: ``file_kinds`` loads the frontmatter parser that
    ``--version`` is tested not to load, and only ``--doctor`` needs the registry here.
    """
    from metabrowser.file_kinds import VIEW_REGISTRY

    plugin_views: dict[str, list[dict[str, Any]]] = {}
    owners: dict[tuple[str, str], str] = {}
    for plugin in plugins:
        for view in plugin.manifest.view:
            plugin_views.setdefault(view.kind, []).append(view_entry(view))
            owners[(view.kind, view.id)] = plugin.name
    problems: list[str] = []
    for kind in sorted(VIEW_REGISTRY.keys() | plugin_views.keys()):
        merged = merge_views(VIEW_REGISTRY.get(kind, []), plugin_views.get(kind, []))
        for problem in check_view_keys(kind, merged).problems:
            owner = owners.get((kind, problem.view_id))
            holder = owners.get((kind, problem.holder)) if problem.holder is not None else None
            line = problem.describe(holder)
            problems.append(f"plugin '{owner}': {line}" if owner else line)
    return problems


def _provider_sections() -> tuple[ProviderStatus, ...]:
    """Each repository provider's report on its own tools, such as GitHub CLI's sign-in.

    A report, not a check: only a provider's URLs need its tools, so no state of one
    changes the doctor's exit status. Imported here, as ``_view_key_problems`` imports the
    registry, so ``--version`` loads none of it.
    """
    from metabrowser.cache.providers import provider_statuses

    return asyncio.run(provider_statuses())


def doctor_plugins(plugins_dir: list[Path] | None = None, *, as_json: bool = False) -> None:
    """Validate every discovered plugin and the packaged cache record contracts, report
    where ``--present`` opens a target, report each repository provider's tools, such as
    GitHub CLI's sign-in, and run the setup checks of :mod:`metabrowser.cli.doctor`.

    Exit non-zero on any plugin, contract, or preference problem, or a setup check's
    ``problem``; a provider's state and a check's ``warning`` never change it.
    The provider sections and the checks follow the verdict, on stdout after a clean run
    and on stderr after the problems.
    """
    extra = resolve_extra_plugin_dirs(plugins_dir)
    result = discover_plugins(extra_dirs=extra)

    problems: list[str] = list(result.errors)
    problems.extend(_cache_contract_problems())

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

    # Cross-plugin: view keys stay clear of each other and the shell within a kind.
    problems.extend(_view_key_problems(result.plugins))

    providers = _provider_sections()
    # Where `--present` opens a target, and the app it would find (`cli/present.py`).
    from metabrowser.cli.present import doctor_open_in

    open_in = doctor_open_in()
    problems.extend(open_in.problems)
    # This metab, Git, and the two directories (`cli/doctor.py`); imported here, as the
    # registry is, so `--version` loads none of it.
    from metabrowser.cli.doctor import setup_checks

    checks = setup_checks(
        app_path=open_in.app_path,
        app_minimum=open_in.app_minimum_metab,
        looked_up=open_in.section.get("app") is not None,
    )
    problems.extend(check.problem for check in checks if check.problem is not None)

    if as_json:
        report: dict[str, object] = {
            "ok": not problems,
            "plugin_count": len(result.plugins),
            "problems": problems,
            "open_in": open_in.section,
        }
        report.update((section.name, dict(section.report)) for section in providers)
        report["checks"] = [check.to_json() for check in checks]
        typer.echo(json.dumps(report, indent=2))
        if problems:
            raise typer.Exit(code=1)
        return

    if problems:
        typer.echo(f"metab --doctor: {len(problems)} problem(s):", err=True)
        for problem in problems:
            typer.echo(f"  • {problem}", err=True)
        _echo_sections(providers, checks, err=True)
        raise typer.Exit(code=1)

    # A run with a problem writes nothing to stdout, so the preference's line is part of
    # the answer of a clean one.
    typer.echo(open_in.line)
    typer.echo(f"metab --doctor: {len(result.plugins)} plugin(s) OK")
    _echo_sections(providers, checks, err=False)


def _echo_sections(
    providers: tuple[ProviderStatus, ...], checks: tuple[Check, ...], *, err: bool
) -> None:
    for section in providers:
        for line in section.lines:
            typer.echo(line, err=err)
    for check in checks:
        for line in check.lines():
            typer.echo(line, err=err)


def _plugins_with_index_check(plugins: list[LoadedPlugin]) -> list[str]:
    """Return error messages for plugins whose index.js is missing on disk."""
    out: list[str] = []
    for p in plugins:
        if not (p.static_root / "index.js").is_file():
            out.append(f"plugin '{p.name}': index.js missing in {p.static_root}")
    return out
