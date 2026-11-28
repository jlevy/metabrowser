"""Provisional Python helpers for installed Metabrowser plugin sidekicks.

Plugin data hooks run inside the Metabrowser server process. They need the
same served-root containment, transparent artifact reads, log-adapter
detection, and cache lifecycle as built-in handlers. This module exposes that
small 0.x contract without requiring plugins to import private implementation
names. Names can evolve before 1.0, with release notes documenting changes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from metabrowser import jsonl_view
from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.jsonl_view import JsonlParseLimitError
from metabrowser.logutil.parsing import (
    LogEvent,
    LogParser,
    create_parser,
    detect_adapter,
    register_log_adapter,
    registered_log_adapters,
)
from metabrowser.paths_safe import (
    _relativize,
    _safe_path,
    _safe_path_from_identity,
    register_root_callback,
)
from metabrowser.projections import extract_agent_charts_cached
from metabrowser.source import (
    MAX_CONTAINER_INNER_DEPTH,
    ContentReadError,
    ContentRef,
    ContentStat,
    ContentUnavailableError,
    ContentWindow,
    SourceCapabilities,
    UnsupportedSourceCapabilityError,
    open_content,
    read_content_window,
    require_filesystem_hooks,
    require_source_capability,
    resolve_content,
    resolve_content_container,
    source_capabilities,
    stat_content,
)
from metabrowser.table_source import (
    MAX_SAFE_INTEGER,
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_PAGE_CELLS_MAX,
    TABLE_PAGE_ROWS_DEFAULT,
    TABLE_PAGE_ROWS_MAX,
    TABLE_RECORD_VALUE_BYTES,
    TABLE_REQUEST_DEADLINE_SECONDS,
    TABLE_TOKEN_MAX_CHARS,
    BackrefCount,
    Budget,
    Cell,
    FieldRef,
    FieldType,
    Filter,
    FilterOp,
    FolderTableHandle,
    FolderTableSourceAdapter,
    Order,
    PageReason,
    RecordNotFoundError,
    RefFilter,
    SourceUnreadableError,
    TableCard,
    TableField,
    TableGroup,
    TableHandle,
    TableInfo,
    TableNotFoundError,
    TablePage,
    TableQuery,
    TableQueryError,
    TableRecord,
    TableRow,
    TableSchema,
    TableSource,
    TableSourceAdapter,
    TableSourceError,
    blob_cell,
    coerce_filter_value,
    content_generation,
    cut_utf8,
    decode_cursor,
    decode_key,
    encode_cursor,
    encode_key,
    integer_cell,
    page_columns,
    page_row_limit,
    parse_position_key,
    parse_positional_cursor,
    position_key,
    positional_cursor,
    real_cell,
    stat_generation,
    stored_cell,
    text_cell,
)


def resolve_path(requested: str) -> Path | None:
    """Resolve a canonical inventory path without allowing traversal.

    An empty string returns the served root. A successful result may be a file
    or directory; use :func:`resolve_directory` when a directory is required.
    Filesystem-only: a non-filesystem subject raises
    :class:`UnsupportedSourceCapabilityError`.
    """
    require_filesystem_hooks()
    return _safe_path_from_identity(requested)


def resolve_directory(requested: str) -> Path | None:
    """Resolve a served-root-relative directory without allowing traversal."""
    target = resolve_path(requested)
    return target if target is not None and target.is_dir() else None


def relativize_path(raw: str | None) -> str | None:
    """Convert an absolute path under the served root to its client path."""
    relative = _relativize(raw)
    return canonical_inventory_path(relative) if relative else relative


def served_root() -> Path:
    """The folder this server is serving.

    Hooks that reason about the tree as a whole — a repository, an
    archive — need the root itself, which ``resolve_path("")`` also
    returns; this name says why the caller wants it.
    Filesystem-only: a non-filesystem subject raises
    :class:`UnsupportedSourceCapabilityError`.
    """
    require_filesystem_hooks()
    root = _safe_path("")
    if root is None:  # pragma: no cover - the served root always resolves
        raise RuntimeError("served root is unavailable")
    return root


def jsonl_parse_max_bytes() -> int:
    """The decompressed-byte ceiling of one JSONL parse.

    ``parse_jsonl_bytes`` and the chart extractors raise :class:`JsonlParseLimitError`
    past it, so a hook reading a log reads at most this many bytes. Read at call time,
    because the limit is a module constant tests lower.
    """
    return jsonl_view._JSONL_PARSE_MAX_BYTES


def extract_agent_charts_bytes(data: bytes) -> dict[str, Any]:
    """The agent-log chart projection of JSONL bytes, as the Charts view draws it.

    Raises :class:`JsonlParseLimitError` past :func:`jsonl_parse_max_bytes`. Blocking:
    call it off the event loop.
    """
    from metabrowser import charts

    return charts.extract_agent_charts_bytes(data)


def lookup_agent_charts(identity: str, fingerprint: str) -> dict[str, Any] | None:
    """A chart projection remembered for *identity* at *fingerprint*, or ``None``.

    *fingerprint* is the one :func:`resolve_content` reports, which changes exactly
    when the content can have, so a hook may consult this before reading the content.
    """
    from metabrowser import charts

    return charts.lookup_agent_charts(identity, fingerprint)


def remember_agent_charts(identity: str, fingerprint: str, payload: dict[str, Any]) -> None:
    """Remember a chart projection for :func:`lookup_agent_charts`."""
    from metabrowser import charts

    charts.remember_agent_charts(identity, fingerprint, payload)


class PluginCacheUnavailableError(Exception):
    """No owner-only plugin cache directory can be made. ``str()`` names no path."""


# The manifest's ``name`` pattern (``PluginManifest.name`` in plugin_loader/manifest.py),
# so a cache directory's name is always a plugin name and never a path.
_PLUGIN_NAME = re.compile(r"[a-z][a-z0-9_-]*")


def plugin_cache_directory(plugin_name: str) -> Path:
    """Create or verify the owner-only cache directory of one plugin, and return it.

    The directory is ``plugins/<plugin_name>`` under the application cache root
    (``METABROWSER_CACHE_DIR``, ``XDG_CACHE_HOME/metabrowser``, or
    ``~/.cache/metabrowser``). It is a cache: Metabrowser never reads it, a user may
    delete it at any time, and a plugin keys what it stores by what it was computed
    from, so a stale or missing entry is recomputed rather than trusted. Raises
    ``ValueError`` for a name that is not a plugin name, and
    :class:`PluginCacheUnavailableError` when no cache root is configured or it cannot
    be kept owner-only. Blocking: call it off the event loop.
    """
    if not _PLUGIN_NAME.fullmatch(plugin_name):
        raise ValueError(f"not a plugin name: {plugin_name!r}")
    # Imported here: a bare ``import metabrowser`` does not otherwise load the storage
    # helpers, and the CLI's startup-import tests hold it to that.
    from metabrowser.home import (
        PrivateStorageError,
        StorageDirectoryError,
        application_cache,
        ensure_private_directory,
        ensure_storage_root,
    )

    try:
        home = application_cache()
        ensure_storage_root(home)
        return ensure_private_directory(home, f"plugins/{plugin_name}")
    except (PrivateStorageError, StorageDirectoryError) as exc:
        raise PluginCacheUnavailableError(str(exc)) from exc


__all__ = [
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "BackrefCount",
    "Budget",
    "Cell",
    "ContentReadError",
    "ContentRef",
    "ContentStat",
    "ContentUnavailableError",
    "ContentWindow",
    "FieldRef",
    "FieldType",
    "FolderTableHandle",
    "FolderTableSourceAdapter",
    "Filter",
    "FilterOp",
    "JsonlParseLimitError",
    "PluginCacheUnavailableError",
    "LogEvent",
    "LogParser",
    "MAX_CONTAINER_INNER_DEPTH",
    "MAX_SAFE_INTEGER",
    "Order",
    "PageReason",
    "RecordNotFoundError",
    "RefFilter",
    "SourceCapabilities",
    "SourceUnreadableError",
    "TABLE_CARD_MAX_FIELDS",
    "TABLE_CELL_PREVIEW_CHARS",
    "TABLE_PAGE_CELLS_MAX",
    "TABLE_PAGE_ROWS_DEFAULT",
    "TABLE_PAGE_ROWS_MAX",
    "TABLE_RECORD_VALUE_BYTES",
    "TABLE_REQUEST_DEADLINE_SECONDS",
    "TABLE_TOKEN_MAX_CHARS",
    "TableCard",
    "TableField",
    "TableGroup",
    "TableHandle",
    "TableInfo",
    "TableNotFoundError",
    "TablePage",
    "TableQuery",
    "TableQueryError",
    "TableRecord",
    "TableRow",
    "TableSchema",
    "TableSource",
    "TableSourceAdapter",
    "TableSourceError",
    "UnsupportedSourceCapabilityError",
    "blob_cell",
    "coerce_filter_value",
    "content_generation",
    "create_parser",
    "cut_utf8",
    "decode_cursor",
    "decode_key",
    "detect_adapter",
    "encode_cursor",
    "encode_key",
    "extract_agent_charts_cached",
    "integer_cell",
    "open_content",
    "page_columns",
    "page_row_limit",
    "parse_position_key",
    "parse_positional_cursor",
    "position_key",
    "positional_cursor",
    "extract_agent_charts_bytes",
    "jsonl_parse_max_bytes",
    "lookup_agent_charts",
    "plugin_cache_directory",
    "read_content_window",
    "real_cell",
    "register_log_adapter",
    "registered_log_adapters",
    "remember_agent_charts",
    "require_source_capability",
    "register_root_callback",
    "relativize_path",
    "resolve_content",
    "resolve_content_container",
    "resolve_directory",
    "resolve_path",
    "served_root",
    "source_capabilities",
    "stat_content",
    "stat_generation",
    "stored_cell",
    "text_cell",
]
