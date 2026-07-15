"""metabrowser — local web UI for browsing run logs, JSONL streams, and structured artifacts.

Pluggable via JS modules dynamically discovered at server startup. See
``metabrowser.plugin_loader`` for the discovery mechanism.

Public API for plugin authors (typically only relevant to Python sidekicks
— pure-JS plugins use ``window.metabrowser`` in the browser):
"""

from importlib.metadata import PackageNotFoundError, version

from metabrowser.errors import CLIError
from metabrowser.logutil.parsing import LogEvent, LogParser, register_log_adapter
from metabrowser.plugin_loader.discovery import (
    LoadedPlugin,
    discover_plugins,
)
from metabrowser.plugin_loader.manifest import (
    DataHookSpec,
    KindMatch,
    KindRule,
    PluginInfo,
    PluginManifest,
    ViewSpec,
    load_manifest,
)

try:
    __version__ = version("metabrowser")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "CLIError",
    "DataHookSpec",
    "KindMatch",
    "KindRule",
    "LoadedPlugin",
    "LogEvent",
    "LogParser",
    "PluginInfo",
    "PluginManifest",
    "ViewSpec",
    "__version__",
    "discover_plugins",
    "load_manifest",
    "register_log_adapter",
]
