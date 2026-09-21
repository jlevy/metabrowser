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
    ArtifactContractSpec,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
    ArtifactValidationContext,
    BrowserParserSpec,
    CapabilitySet,
    CollectionPaginationPolicy,
    ConformanceCorpusSpec,
    JsonlParseLimitError,
    LogEvent,
    LogParser,
    ResourceCollectionSpec,
    ResourceProfileSpec,
    ResourceTargetClass,
    detect_adapter,
    extract_agent_charts_cached,
    register_log_adapter,
    register_root_callback,
    relativize_path,
    resolve_directory,
    resolve_path,
    served_root,
)

try:
    __version__ = version("metabrowser")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "ArtifactContractSpec",
    "ArtifactValidationContext",
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "BrowserParserSpec",
    "CapabilitySet",
    "CLIError",
    "CollectionPaginationPolicy",
    "ConformanceCorpusSpec",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "MAX_CONTAINER_INNER_DEPTH",
    "ResourceCollectionSpec",
    "ResourceProfileSpec",
    "ResourceTargetClass",
    "__version__",
    "detect_adapter",
    "extract_agent_charts_cached",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
    "served_root",
]
