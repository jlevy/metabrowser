"""Provisional Python helpers for installed Metabrowser plugin sidekicks.

Plugin data hooks run inside the Metabrowser server process. They need the
same served-root containment, transparent artifact reads, log-adapter
detection, and cache lifecycle as built-in handlers. This module exposes that
small 0.x contract without requiring plugins to import private implementation
names. Names can evolve before 1.0, with release notes documenting changes.
"""

from __future__ import annotations

from pathlib import Path

from metabrowser.gz_io import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.jsonl_view import JsonlParseLimitError
from metabrowser.logutil.parsing import LogEvent, LogParser, detect_adapter, register_log_adapter
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
    FIELD_TYPES,
    FILTER_OPS,
    MAX_SAFE_INTEGER,
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_GROUPS,
    TABLE_PAGE_ROWS_DEFAULT,
    TABLE_PAGE_ROWS_MAX,
    TABLE_RECORD_VALUE_BYTES,
    TABLE_REQUEST_DEADLINE_SECONDS,
    TABLE_TOKEN_MAX_CHARS,
    VALUELESS_OPS,
    BackrefCount,
    Budget,
    Cell,
    FieldRef,
    FieldType,
    Filter,
    FilterOp,
    NoTableSourceError,
    OpenedTableSource,
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
    TablePathNotFoundError,
    TableQuery,
    TableQueryError,
    TableRecord,
    TableRow,
    TableSchema,
    TableSource,
    TableSourceAdapter,
    TableSourceDeclaration,
    TableSourceError,
    card_wire,
    check_table_query,
    coerce_filter_value,
    content_generation,
    cut_utf8,
    decode_cursor,
    decode_key,
    encode_cursor,
    encode_key,
    error_wire,
    field_wire,
    integer_cell,
    open_table_source,
    page_columns,
    page_wire,
    parse_position_key,
    parse_positional_cursor,
    parse_table_query,
    position_key,
    positional_cursor,
    real_cell,
    record_wire,
    schema_wire,
    stat_generation,
    stored_cell,
    table_address,
    tables_wire,
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
    "FIELD_TYPES",
    "FILTER_OPS",
    "FieldRef",
    "FieldType",
    "Filter",
    "FilterOp",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "MAX_CONTAINER_INNER_DEPTH",
    "MAX_SAFE_INTEGER",
    "NoTableSourceError",
    "OpenedTableSource",
    "Order",
    "PageReason",
    "RecordNotFoundError",
    "RefFilter",
    "SourceCapabilities",
    "SourceUnreadableError",
    "TABLE_CARD_MAX_FIELDS",
    "TABLE_CELL_PREVIEW_CHARS",
    "TABLE_GROUPS",
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
    "TablePathNotFoundError",
    "TableQuery",
    "TableQueryError",
    "TableRecord",
    "TableRow",
    "TableSchema",
    "TableSource",
    "TableSourceAdapter",
    "TableSourceDeclaration",
    "TableSourceError",
    "UnsupportedSourceCapabilityError",
    "VALUELESS_OPS",
    "card_wire",
    "check_table_query",
    "coerce_filter_value",
    "content_generation",
    "cut_utf8",
    "decode_cursor",
    "decode_key",
    "detect_adapter",
    "encode_cursor",
    "encode_key",
    "error_wire",
    "extract_agent_charts_cached",
    "field_wire",
    "integer_cell",
    "open_content",
    "open_table_source",
    "page_columns",
    "page_wire",
    "parse_position_key",
    "parse_positional_cursor",
    "parse_table_query",
    "position_key",
    "positional_cursor",
    "read_content_window",
    "real_cell",
    "record_wire",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "require_source_capability",
    "resolve_content",
    "resolve_content_container",
    "resolve_directory",
    "resolve_path",
    "schema_wire",
    "served_root",
    "source_capabilities",
    "stat_content",
    "stat_generation",
    "stored_cell",
    "table_address",
    "tables_wire",
    "text_cell",
]
