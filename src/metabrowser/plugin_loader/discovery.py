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
   list, optionally loaded from ``.env`` / ``.env.local``).

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
from collections.abc import Callable
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
    optionally loaded from a ``.env`` / ``.env.local`` file). Each
    parent directory's subdirectories are scanned for ``manifest.toml``.
    Collisions with already-loaded plugin names are logged.

    **Auto-discovery from the served root is not a source.** Project-
    local and user-home plugin directories were trust-asymmetric (the
    served data could opt itself into running JS in the metabrowser
    page). The cut: trusted = built-in + entry-point + operator-named.
    """
    candidates: list[LoadedPlugin | str] = []
    candidates.extend(_discover_builtin_plugins())
    candidates.extend(_discover_entry_point_plugins())

    if extra_dirs:
        candidates.extend(_discover_local_plugins(list(extra_dirs)))

    result = DiscoveryResult()
    seen: dict[str, LoadedPlugin] = {}

    for cand in candidates:
        if isinstance(cand, str):
            result.errors.append(cand)
            LOG.warning("metabrowser plugin discovery error: %s", cand)
            continue
        prior = seen.get(cand.name)
        if prior is not None:
            LOG.info(
                "metabrowser plugin '%s' overridden: %s -> %s",
                cand.name,
                prior.source,
                cand.source,
            )
        seen[cand.name] = cand

    result.plugins = list(seen.values())
    return result
