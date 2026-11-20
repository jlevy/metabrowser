"""Metabrowser: an extensible, web-based file browser.

Browse local files from your web browser, with extensible plugin-based rendering
of Markdown, code, JSON, YAML, logs, and other files.

Pluggable via JS modules dynamically discovered at server startup. See
``metabrowser.plugin_loader`` for the discovery mechanism.

Public API for plugin authors (typically only relevant to Python sidekicks
— pure-JS plugins use ``window.metabrowser`` in the browser):
"""

from importlib.metadata import PackageNotFoundError, version

from metabrowser.errors import CLIError
from metabrowser.plugin_api import (
    MAX_CONTAINER_INNER_DEPTH,
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
    ContentReadError,
    ContentRef,
    ContentStat,
    ContentUnavailableError,
    ContentWindow,
    JsonlParseLimitError,
    LogEvent,
    LogParser,
    PluginCacheUnavailableError,
    SourceCapabilities,
    UnsupportedSourceCapabilityError,
    detect_adapter,
    extract_agent_charts_bytes,
    extract_agent_charts_cached,
    jsonl_parse_max_bytes,
    lookup_agent_charts,
    open_content,
    plugin_cache_directory,
    read_content_window,
    register_log_adapter,
    register_root_callback,
    registered_log_adapters,
    relativize_path,
    remember_agent_charts,
    require_source_capability,
    resolve_content,
    resolve_content_container,
    resolve_directory,
    resolve_path,
    served_root,
    source_capabilities,
    stat_content,
)

try:
    __version__ = version("metabrowser")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "CLIError",
    "ContentReadError",
    "ContentRef",
    "ContentStat",
    "ContentUnavailableError",
    "ContentWindow",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "MAX_CONTAINER_INNER_DEPTH",
    "PluginCacheUnavailableError",
    "SourceCapabilities",
    "UnsupportedSourceCapabilityError",
    "__version__",
    "detect_adapter",
    "extract_agent_charts_bytes",
    "extract_agent_charts_cached",
    "jsonl_parse_max_bytes",
    "lookup_agent_charts",
    "open_content",
    "plugin_cache_directory",
    "read_content_window",
    "register_log_adapter",
    "register_root_callback",
    "registered_log_adapters",
    "relativize_path",
    "remember_agent_charts",
    "require_source_capability",
    "resolve_content",
    "resolve_content_container",
    "resolve_directory",
    "resolve_path",
    "served_root",
    "source_capabilities",
    "stat_content",
]
