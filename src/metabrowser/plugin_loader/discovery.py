"""Plugin discovery — walks the configured plugin locations at server startup.

Discovery has three sources, in this order:

1. **Built-in plugins** — every subdirectory of
   ``metabrowser/src/metabrowser/builtin_plugins/`` that contains a
   ``manifest.toml``. These ship with metabrowser; always loaded.
2. **Python entry-point plugins** — every ``metabrowser.plugins`` entry
   point declared in any installed Python package's ``pyproject.toml``.
   The entry point's value is a ``module:callable`` reference; the callable
   returns the directory containing ``manifest.toml``.
3. **Operator-supplied plugin directories** — every subdirectory of
   each path in ``extra_dirs`` that contains a ``manifest.toml``. The
   CLI populates this list from the ``--plugins-dir`` flag (repeatable)
   and the ``METABROWSER_PLUGINS_DIRS`` env var (``os.pathsep``-separated
   list, read from the process environment only: a ``.env`` file cannot
   supply it, see :mod:`metabrowser.dotenv`).

**Trust model**: built-in and entry-point plugins are deliberately
installed (they ship with the package or are pip-installed). Source 3
requires the operator to name a directory explicitly — viewed data
cannot opt itself into running JS in the metabrowser page. Auto-
discovery from the served root or the user's home is **not** a source.

Invalid plugins are logged and skipped — they don't take down the server.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.resources
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from metabrowser.plugin_loader.manifest import PluginManifest, load_manifest

LOG = logging.getLogger(__name__)


ENTRY_POINT_GROUP = "metabrowser.plugins"


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """A discovered, validated plugin ready for the server to mount.

    ``static_root`` is the absolute filesystem path to the plugin's
    directory (where ``manifest.toml`` lives). The shell serves files
    from there under ``/plugin-static/<plugin-name>/...``.

    ``manifest`` is the parsed, validated ``manifest.toml``.

    ``source`` records where the plugin was discovered, for logging /
    debugging only — it's not part of the runtime contract.
    """

    name: str
    static_root: Path
    manifest: PluginManifest
    source: str  # "builtin" | "entry-point:<dist>" | "local:<path>"


@dataclass
class DiscoveryResult:
    """The set of plugins discovered at startup, plus any errors.

    Errors are surfaced separately so the server log can show them in one
    place; a partial discovery is preferable to a server that won't start
    because a single plugin's manifest has a typo.
    """

    plugins: list[LoadedPlugin] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _try_load_plugin(plugin_dir: Path, source: str) -> LoadedPlugin | str | None:
    """Load and validate a plugin directory.

    Returns:
      - LoadedPlugin on success;
      - str (error message) on a malformed manifest (treated as a hard error);
      - None if the directory simply doesn't contain a plugin yet (no
        manifest.toml — silent skip; happens with empty scaffolds).
    """
    manifest_path = plugin_dir / "manifest.toml"
    if not manifest_path.is_file():
        return None  # not a plugin; quietly skip
    index_js = plugin_dir / "index.js"
    if not index_js.is_file():
        return f"{plugin_dir}: manifest.toml present but index.js missing"
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        return f"{manifest_path}: {exc}"
    name = manifest.plugin.name
    return LoadedPlugin(
        name=name,
        static_root=plugin_dir.resolve(),
        manifest=manifest,
        source=source,
    )


def _discover_builtin_plugins() -> list[LoadedPlugin | str]:
    """Find every plugin folder under ``metabrowser.builtin_plugins``."""
    try:
        anchor = importlib.resources.files("metabrowser.builtin_plugins")
    except (ImportError, ModuleNotFoundError):
        return []
    builtin_root = Path(str(anchor))
    if not builtin_root.is_dir():
        return []
    found: list[LoadedPlugin | str] = []
    for child in sorted(builtin_root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if not (child / "manifest.toml").is_file():
            continue  # Not every subdir is a plugin (e.g. shared helpers)
        result = _try_load_plugin(child, source="builtin")
        if result is not None:
            found.append(result)
    return found


def _discover_entry_point_plugins() -> list[LoadedPlugin | str]:
    """Find every ``metabrowser.plugins`` entry point in installed distributions."""
    eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    found: list[LoadedPlugin | str] = []
    for ep in eps:
        try:
            module_name, _, attr = ep.value.partition(":")
            if not module_name or not attr:
                raise ValueError(
                    f"invalid value {ep.value!r}; expected an importable module:callable"
                )
            module = importlib.import_module(module_name)
            factory_obj = getattr(module, attr)
            if not callable(factory_obj):
                raise TypeError(f"{ep.value} is not callable")
            factory = cast(Callable[[], str | Path], factory_obj)
            plugin_dir = Path(factory()).expanduser().resolve()
        except Exception as exc:
            found.append(f"entry-point {ep.name}: {exc}")
            continue
        result = _try_load_plugin(plugin_dir, source=f"entry-point:{ep.name}")
        if result is None:
            found.append(f"entry-point {ep.name}: {plugin_dir}/manifest.toml missing")
        else:
            found.append(result)
    return found


def _discover_local_plugins(roots: list[Path]) -> list[LoadedPlugin | str]:
    """Find every plugin folder under one of *roots* (filesystem walk).

    Each root's subdirectories are scanned for ``manifest.toml``. Roots
    that don't exist are silently skipped — the per-project / per-user
    locations are conventionally absent.
    """
    found: list[LoadedPlugin | str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
                continue
            if not (child / "manifest.toml").is_file():
                continue
            result = _try_load_plugin(child, source=f"local:{child}")
            if result is not None:
                found.append(result)
    return found


def discover_plugins(
    *,
    extra_dirs: list[Path] | None = None,
) -> DiscoveryResult:
    """Run every discovery source and return the merged result.

    Discovery order (later sources override earlier ones when plugin
    names collide):

    1. Built-in plugins shipped with metabrowser (``builtin_plugins/``).
    2. Python entry-point plugins under the ``metabrowser.plugins`` group.
    3. Plugins under any directory in *extra_dirs*.

    *extra_dirs* contains operator-supplied plugin parents — the CLI
    populates it from ``--plugins-dir`` flags (repeatable) plus the
    ``METABROWSER_PLUGINS_DIRS`` env var (``os.pathsep``-separated list,
    from the process environment only). Each parent directory's
    subdirectories are scanned for ``manifest.toml``. A later plugin with
    an already-loaded name replaces it, in its place in the order, and the
    replacement is logged.

    A replacement that cannot be used does not take the name away. One whose manifest is
    invalid never replaces anything, and one whose ``requires`` cannot be met
    (:func:`resolve_requirements`) is refused and the plugin it would have replaced is
    kept and resolved again, with the refusal reported. Otherwise a typo in an operator's
    manifest would remove a built-in and refuse every plugin that requires it, which can
    leave the directory kind with no plugin: far more than the operator asked for.

    **Auto-discovery from the served root or the user's home is not a
    source**: served data must not be able to opt itself into running JS
    in the Metabrowser page. The trusted sources are built-in,
    entry-point, and operator-named. See
    ``docs/project/architecture/arch-plugin-system.md``.
    """
    candidates: list[LoadedPlugin | str] = []
    candidates.extend(_discover_builtin_plugins())
    candidates.extend(_discover_entry_point_plugins())

    if extra_dirs:
        candidates.extend(_discover_local_plugins(list(extra_dirs)))

    result = DiscoveryResult()
    # Every valid candidate for each name, in discovery order; the last is the one in use.
    seen: dict[str, list[LoadedPlugin]] = {}

    for cand in candidates:
        if isinstance(cand, str):
            result.errors.append(cand)
            LOG.warning("metabrowser plugin discovery error: %s", cand)
            continue
        overridden = seen.setdefault(cand.name, [])
        if overridden:
            LOG.info(
                "metabrowser plugin '%s' overridden: %s -> %s",
                cand.name,
                overridden[-1].source,
                cand.source,
            )
        overridden.append(cand)

    # The server logs each refusal and the CLI modes print it, as for any discovery error.
    while True:
        in_use = [stack[-1] for stack in seen.values()]
        reasons = _requirement_refusals(in_use)
        restored = [name for name in reasons if len(seen[name]) > 1]
        if not restored:
            break
        # Resolve again with each refused replacement's predecessor back in its place,
        # since what the replacement's refusal carried to its dependents no longer holds.
        for name in restored:
            seen[name].pop()
            result.errors.append(
                f"{reasons[name]}; the plugin it overrides ({seen[name][-1].source}) is kept"
            )
    result.plugins = [plugin for plugin in in_use if plugin.name not in reasons]
    result.errors.extend(reasons.values())
    return result


def resolve_requirements(plugins: list[LoadedPlugin]) -> tuple[list[LoadedPlugin], list[str]]:
    """Keep the plugins whose ``requires`` can be met, in their order, and say why each
    other one is refused.

    A plugin on a cycle of requirements is refused: a provider's exports exist only once
    its module has run, so two modules that each wait for the other's never finish. So is
    one that requires a plugin that was not discovered or was itself refused, which
    carries a refusal to everything that depends on it, directly or not. The order is
    untouched: it is the discovery index that breaks kind priority ties, and a dependent
    loads a provider when it asks for one (``metabrowser.plugins.load`` in
    ``static/plugin-sdk.js``).

    Refusals are listed causes first: a plugin's line comes after the line of the
    provider whose refusal it carries, so ``metab --doctor`` reads top down.
    """
    reasons = _requirement_refusals(plugins)
    return [plugin for plugin in plugins if plugin.name not in reasons], list(reasons.values())


def _requirement_refusals(plugins: list[LoadedPlugin]) -> dict[str, str]:
    """Each refused plugin's name and the reason, in the order the reasons were found:
    cycles, then each refusal after the one it follows from (:func:`resolve_requirements`).
    """
    by_name = {plugin.name: plugin for plugin in plugins}
    reasons: dict[str, str] = {}
    for plugin in plugins:
        cycle = _requirement_cycle(plugin.name, by_name)
        if cycle is not None:
            reasons[plugin.name] = (
                f"plugin '{plugin.name}' is refused: its requirements form a cycle, "
                + " -> ".join(cycle)
            )
    changed = True
    while changed:
        changed = False
        for plugin in plugins:
            if plugin.name in reasons:
                continue
            for provider in plugin.manifest.plugin.requires:
                if provider not in by_name:
                    cause = "which was not discovered"
                elif provider in reasons:
                    cause = "which was refused"
                else:
                    continue
                reasons[plugin.name] = (
                    f"plugin '{plugin.name}' is refused: it requires '{provider}', {cause}"
                )
                changed = True
                break
    return reasons


def _requirement_cycle(name: str, by_name: Mapping[str, LoadedPlugin]) -> list[str] | None:
    """The shortest chain of requirements from *name* back to itself, or None.

    Breadth first over discovered plugins only; a missing provider ends its branch, and
    :func:`resolve_requirements` refuses it separately.
    """
    previous: dict[str, str] = {}
    frontier = [name]
    while frontier:
        following: list[str] = []
        for current in frontier:
            for provider in by_name[current].manifest.plugin.requires:
                if provider == name:
                    chain = [current]
                    while chain[-1] != name:
                        chain.append(previous[chain[-1]])
                    return [*reversed(chain), name]
                if provider in by_name and provider not in previous:
                    previous[provider] = current
                    following.append(provider)
        frontier = following
    return None
