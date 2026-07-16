"""metabrowser — local web UI for browsing run logs, JSONL streams, and structured artifacts.

Pluggable via JS modules dynamically discovered at server startup. See
``metabrowser.plugin_loader`` for the discovery mechanism.

Public API for plugin authors (typically only relevant to Python sidekicks
— pure-JS plugins use ``window.metabrowser`` in the browser):
"""

from importlib.metadata import PackageNotFoundError, version

from metabrowser.errors import CLIError
from metabrowser.plugin_api import (
    ArtifactPath,
    LogEvent,
    LogParser,
    detect_adapter,
    extract_agent_charts_cached,
    register_log_adapter,
    register_root_callback,
    relativize_path,
    resolve_directory,
    resolve_path,
)
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
    "ArtifactPath",
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
    "detect_adapter",
    "extract_agent_charts_cached",
    "load_manifest",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
]
