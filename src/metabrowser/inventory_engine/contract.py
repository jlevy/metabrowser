"""Sealed semantic contract implemented by inventory providers.

The application owns this vocabulary. Providers implement it without exposing their
retained-index types, concurrency model, or transport details. Every potentially large
query carries an explicit output bound, and every read returns its state and version at
the same observation boundary as its projections.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol, runtime_checkable

from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.wire_models import NavigationTallies, RollupResult

MAX_CHANGE_PATHS = 1_024
MAX_COMMAND_PATHS = 1_024
MAX_QUERIES_PER_READ = 1_024
# Keep lifecycle diagnostics within the same fixed envelope as change delivery.
MAX_INVENTORY_ISSUES = MAX_CHANGE_PATHS
# Bound provider-supplied diagnostic text before it crosses an FFI boundary.
MAX_ISSUE_DETAIL_BYTES = 4_096


def _require_nonempty(value: str, name: str) -> None:
    if not value:
        raise ValueError(f"{name} must not be empty")


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_nonnegative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def require_canonical_inventory_path(
    value: str,
    name: str,
    *,
    allow_root: bool,
) -> None:
    """Validate the lossless POSIX-relative identity shared by all providers."""

    if value == "":
        if allow_root:
            return
        raise ValueError(f"{name} must be a canonical POSIX-relative path below the root")
    pure = PurePosixPath(value)
    if (
        "\\" in value
        or "\x00" in value
        or pure.is_absolute()
        or pure.as_posix() != value
        or "." in pure.parts
        or ".." in pure.parts
    ):
        raise ValueError(f"{name} must be a canonical POSIX-relative path")


def catalog_terminal_suffix(name: str) -> str:
    """Return the lowercase terminal suffix defined by the provider contract.

    The final dot starts a suffix only when it is neither the first nor final
    character. Thus `.gitignore` and `notes.` have no suffix, while `..foo` has
    `.foo`. Spelling the rule here keeps provider answers independent of path-library
    versions.
    """

    dot = name.rfind(".")
    if dot <= 0 or dot + 1 == len(name):
        return ""
    return name[dot:].lower()


@dataclass(frozen=True, slots=True)
class InventoryConfig:
    """Semantic scope plus provider execution policy for one root session."""

    max_files: int = 500_000
    max_depth: int = 20
    hidden_allowlist: tuple[str, ...] = (LOGS_DIR, STATE_DIR)
    registry_fingerprint: str = "builtin"
    change_queue_size: int = 1_024
    watch_mode: Literal["auto", "native", "poll", "off"] = "auto"

    def __post_init__(self) -> None:
        _require_positive(self.max_files, "max_files")
        _require_positive(self.max_depth, "max_depth")
        _require_positive(self.change_queue_size, "change_queue_size")
        _require_nonempty(self.registry_fingerprint, "registry_fingerprint")
        if self.watch_mode not in {"auto", "native", "poll", "off"}:
            raise ValueError("watch_mode must be auto, native, poll, or off")
        if len(set(self.hidden_allowlist)) != len(self.hidden_allowlist):
            raise ValueError("hidden_allowlist entries must be unique")
        if any(
            not name.startswith(".")
            or name in {".", ".."}
            or "/" in name
            or "\\" in name
            or "\x00" in name
            for name in self.hidden_allowlist
        ):
            raise ValueError("hidden_allowlist entries must be exact hidden path-component names")


def inventory_scope_fingerprint(config: InventoryConfig) -> str:
    """Return the portable digest for filesystem scope semantics.

    The canonical JSON array contains sorted ``[name, value]`` string pairs. Values
    with internal structure are themselves compact canonical JSON so Rust and Python
    adapters can reproduce the exact byte sequence without depending on object reprs.
    """

    components = (
        (
            "hidden_allowlist",
            json.dumps(
                sorted(config.hidden_allowlist),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
        ("max_depth", str(config.max_depth)),
        ("max_files", str(config.max_files)),
    )
    payload = json.dumps(sorted(components), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EngineVersion:
    """Opaque identity for one coherent provider state.

    The semantic fingerprint covers every non-scope rule or reducer that can change a
    complete answer. Providers with several native fingerprints combine them before
    returning the version.
    """

    session: str
    sequence: int
    scope_fingerprint: str
    semantic_fingerprint: str

    def __post_init__(self) -> None:
        _require_nonempty(self.session, "session")
        _require_nonnegative(self.sequence, "sequence")
        _require_nonempty(self.scope_fingerprint, "scope_fingerprint")
        _require_nonempty(self.semantic_fingerprint, "semantic_fingerprint")

    @property
    def cursor(self) -> ChangeCursor:
        """The change-stream position at this observation boundary."""

        return ChangeCursor.from_version(self)


@dataclass(frozen=True, slots=True)
class ChangeCursor:
    """Resume point in one provider session's ordered change stream."""

    session: str
    sequence: int

    def __post_init__(self) -> None:
        _require_nonempty(self.session, "session")
        _require_nonnegative(self.sequence, "sequence")

    @classmethod
    def from_version(cls, version: EngineVersion) -> ChangeCursor:
        """Derive the only valid cursor for *version*."""

        return cls(session=version.session, sequence=version.sequence)


class LifecyclePhase(StrEnum):
    OPENING_CACHE = "opening_cache"
    DISCOVERING = "discovering"
    RECONCILING = "reconciling"
    READY = "ready"
    WATCHING = "watching"
    STOPPED = "stopped"
    FAILED = "failed"


ALLOWED_PHASE_TRANSITIONS: Mapping[LifecyclePhase, frozenset[LifecyclePhase]] = {
    LifecyclePhase.OPENING_CACHE: frozenset(
        {
            LifecyclePhase.DISCOVERING,
            LifecyclePhase.RECONCILING,
            LifecyclePhase.READY,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }
    ),
    LifecyclePhase.DISCOVERING: frozenset(
        {
            LifecyclePhase.RECONCILING,
            LifecyclePhase.READY,
            LifecyclePhase.WATCHING,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }
    ),
    LifecyclePhase.RECONCILING: frozenset(
        {
            LifecyclePhase.READY,
            LifecyclePhase.WATCHING,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }
    ),
    LifecyclePhase.WATCHING: frozenset(
        {
            LifecyclePhase.RECONCILING,
            LifecyclePhase.READY,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }
    ),
    LifecyclePhase.READY: frozenset(
        {
            LifecyclePhase.RECONCILING,
            LifecyclePhase.WATCHING,
            LifecyclePhase.STOPPED,
            LifecyclePhase.FAILED,
        }
    ),
    LifecyclePhase.STOPPED: frozenset(),
    LifecyclePhase.FAILED: frozenset({LifecyclePhase.STOPPED}),
}


class CoverageReason(StrEnum):
    BUILDING = "building"
    BUDGET = "budget"
    CANCELLED = "cancelled"
    INACCESSIBLE = "inaccessible"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Coverage:
    complete: bool
    reason: CoverageReason | None = None

    def __post_init__(self) -> None:
        if self.complete and self.reason is not None:
            raise ValueError("complete coverage cannot carry a partial-coverage reason")
        if not self.complete and self.reason is None:
            raise ValueError("partial coverage requires a reason")


class Freshness(StrEnum):
    FRESH = "fresh"
    RECONCILING = "reconciling"
    STALE = "stale"
    PARTIAL = "partial"


class SourceKind(StrEnum):
    SCANNED = "scanned"
    REVALIDATED = "revalidated"
    JOURNAL_SCOPED = "journal_scoped"
    CACHED = "cached"


@dataclass(frozen=True, slots=True)
class IndexProgress:
    entries_observed: int = 0
    directories_observed: int = 0
    estimated_entries: int | None = None

    def __post_init__(self) -> None:
        _require_nonnegative(self.entries_observed, "entries_observed")
        _require_nonnegative(self.directories_observed, "directories_observed")
        if self.estimated_entries is not None:
            _require_nonnegative(self.estimated_entries, "estimated_entries")


class IssueCode(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    DISAPPEARED = "disappeared"
    INVALID_METADATA = "invalid_metadata"
    FILESYSTEM_BOUNDARY = "filesystem_boundary"
    WATCHER_GAP = "watcher_gap"
    RESOURCE_BUDGET = "resource_budget"
    PROVIDER_FAILURE = "provider_failure"


@dataclass(frozen=True, slots=True)
class InventoryIssue:
    code: IssueCode
    detail: str
    path: str | None = None
    transient: bool = False

    def __post_init__(self) -> None:
        _require_nonempty(self.detail, "detail")
        if len(self.detail.encode("utf-8")) > MAX_ISSUE_DETAIL_BYTES:
            raise ValueError(f"issue detail must be at most {MAX_ISSUE_DETAIL_BYTES} UTF-8 bytes")
        if self.path is not None:
            require_canonical_inventory_path(self.path, "issue path", allow_root=True)


@dataclass(frozen=True, slots=True)
class IndexState:
    phase: LifecyclePhase
    coverage: Coverage
    freshness: Freshness
    source: SourceKind
    progress: IndexProgress = field(default_factory=IndexProgress)
    issues: tuple[InventoryIssue, ...] = ()

    def __post_init__(self) -> None:
        if len(self.issues) > MAX_INVENTORY_ISSUES:
            raise ValueError(f"index state accepts at most {MAX_INVENTORY_ISSUES} issues")

    def can_transition_to(self, other: IndexState) -> bool:
        """Whether *other* is a legal next lifecycle state for this session."""

        return other.phase == self.phase or other.phase in ALLOWED_PHASE_TRANSITIONS[self.phase]


@dataclass(frozen=True, slots=True)
class WorkCounters:
    """Measured request work, with exact CPU time when the provider can measure it."""

    entries_visited: int = 0
    directories_visited: int = 0
    rows_returned: int = 0
    bytes_copied: int = 0
    lock_wait_ns: int = 0
    cpu_time_ns: int | None = None
    wall_time_ns: int = 0

    def __post_init__(self) -> None:
        for name in (
            "entries_visited",
            "directories_visited",
            "rows_returned",
            "bytes_copied",
            "lock_wait_ns",
            "wall_time_ns",
        ):
            _require_nonnegative(getattr(self, name), name)
        if self.cpu_time_ns is not None:
            _require_nonnegative(self.cpu_time_ns, "cpu_time_ns")


@dataclass(frozen=True, slots=True)
class ProviderDiagnostics:
    """Constant-size provider facts consumed by the host and performance tools."""

    provider: str
    contract: str
    files_indexed: int
    directories_indexed: int
    watch_mode: str
    watch_state: str
    watch_reason: str
    read_requests: int
    cumulative_work: WorkCounters

    def __post_init__(self) -> None:
        for name in ("provider", "contract", "watch_mode", "watch_state", "watch_reason"):
            _require_nonempty(getattr(self, name), name)
        for name in ("files_indexed", "directories_indexed", "read_requests"):
            _require_nonnegative(getattr(self, name), name)


class EntryType(StrEnum):
    FILE = "file"
    DIRECTORY = "dir"
    SYMLINK = "symlink"


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    """Provider-owned filesystem facts for one served-root-relative path."""

    path: str
    parent: str
    name: str
    type: EntryType
    ext: str
    size: int
    mtime_ns: int
    gitignored: bool = False
    total_files: int | None = None
    total_size: int | None = None
    unignored_files: int | None = None
    unignored_size: int | None = None
    newest_mtime_ns: int | None = None
    empty: bool | None = None

    def __post_init__(self) -> None:
        require_canonical_inventory_path(self.path, "path", allow_root=True)
        require_canonical_inventory_path(self.parent, "parent", allow_root=True)
        if self.path:
            expected_parent, separator, expected_name = self.path.rpartition("/")
            if not separator:
                expected_parent = ""
                expected_name = self.path
            if self.parent != expected_parent or self.name != expected_name:
                raise ValueError("entry path, parent, and name must describe one identity")
        elif self.parent:
            raise ValueError("the root entry must have the root as its parent")
        _require_nonnegative(self.size, "size")

    @property
    def logical_extension(self) -> str:
        return self.ext

    @classmethod
    def for_observed_file(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        size: int,
        mtime_ns: int,
        gitignored: bool = False,
    ) -> InventoryEntry:
        from metabrowser.fs_paths import derive_ext

        return cls(
            path=path,
            parent=parent,
            name=name,
            type=EntryType.FILE,
            ext=derive_ext(name),
            size=size,
            mtime_ns=mtime_ns,
            gitignored=gitignored,
        )

    @classmethod
    def for_observed_dir(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        gitignored: bool = False,
    ) -> InventoryEntry:
        return cls(
            path=path,
            parent=parent,
            name=name,
            type=EntryType.DIRECTORY,
            ext="",
            size=0,
            mtime_ns=0,
            gitignored=gitignored,
        )

    @classmethod
    def for_observed_symlink(
        cls,
        *,
        path: str,
        parent: str,
        name: str,
        size: int,
        mtime_ns: int,
        gitignored: bool = False,
    ) -> InventoryEntry:
        return cls(
            path=path,
            parent=parent,
            name=name,
            type=EntryType.SYMLINK,
            ext="",
            size=size,
            mtime_ns=mtime_ns,
            gitignored=gitignored,
        )


class QueryKind(StrEnum):
    ENTRY = "entry"
    DIRECTORY = "directory"
    FILTERED_TREE = "filtered_tree"
    ROLLUP = "rollup"
    NAVIGATION = "navigation"
    RECENT = "recent"
    CATALOG = "catalog"
    DIAGNOSTICS = "diagnostics"


@dataclass(frozen=True, slots=True)
class EntryQuery:
    query_id: str
    path: str
    kind: Literal[QueryKind.ENTRY] = field(init=False, default=QueryKind.ENTRY)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        require_canonical_inventory_path(self.path, "path", allow_root=True)


@dataclass(frozen=True, slots=True)
class DirectoryQuery:
    query_id: str
    path: str = ""
    max_depth: int = 2
    max_rows: int = 10_000
    after: str | None = None
    include_ignored: bool = True
    kind: Literal[QueryKind.DIRECTORY] = field(init=False, default=QueryKind.DIRECTORY)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        require_canonical_inventory_path(self.path, "path", allow_root=True)
        _require_positive(self.max_depth, "max_depth")
        _require_positive(self.max_rows, "max_rows")


@dataclass(frozen=True, slots=True)
class InventoryFilter:
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    type_families: tuple[str, ...] = ()
    recency_seconds: float | None = None
    minimum_size: int | None = None
    include_ignored: bool = True
    as_of_ns: int | None = None

    def __post_init__(self) -> None:
        if self.recency_seconds is not None and self.recency_seconds <= 0:
            raise ValueError("recency_seconds must be positive")
        if self.minimum_size is not None:
            _require_nonnegative(self.minimum_size, "minimum_size")
        if self.recency_seconds is not None and self.as_of_ns is None:
            raise ValueError("a recency filter requires as_of_ns")
        if self.as_of_ns is not None:
            _require_positive(self.as_of_ns, "as_of_ns")


@dataclass(frozen=True, slots=True)
class FilteredTreeQuery:
    query_id: str
    path: str = ""
    max_depth: int = 2
    max_rows: int = 10_000
    after: str | None = None
    filter: InventoryFilter = field(default_factory=InventoryFilter)
    kind: Literal[QueryKind.FILTERED_TREE] = field(init=False, default=QueryKind.FILTERED_TREE)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        require_canonical_inventory_path(self.path, "path", allow_root=True)
        _require_positive(self.max_depth, "max_depth")
        _require_positive(self.max_rows, "max_rows")


@dataclass(frozen=True, slots=True)
class RollupQuery:
    query_id: str
    path: str = ""
    max_depth: int = 4
    max_nodes: int = 50_000
    top: int = 40
    extension_top: int = 100
    remaining_top: int = 20
    filename_top: int = 20
    rank: Literal["bytes", "dual"] = "bytes"
    kind: Literal[QueryKind.ROLLUP] = field(init=False, default=QueryKind.ROLLUP)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        require_canonical_inventory_path(self.path, "path", allow_root=True)
        _require_positive(self.max_nodes, "max_nodes")
        for name in ("max_depth", "top", "extension_top", "remaining_top", "filename_top"):
            _require_nonnegative(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class NavigationQuery:
    query_id: str
    presets: tuple[tuple[str, tuple[str, ...]], ...] = ()
    recency_windows: tuple[tuple[str, float], ...] = ()
    max_rows: int = 200
    as_of_ns: int | None = None
    kind: Literal[QueryKind.NAVIGATION] = field(init=False, default=QueryKind.NAVIGATION)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_positive(self.max_rows, "max_rows")
        if self.recency_windows and self.as_of_ns is None:
            raise ValueError("recency windows require as_of_ns")
        if self.as_of_ns is not None:
            _require_positive(self.as_of_ns, "as_of_ns")
        if any(seconds <= 0 for _name, seconds in self.recency_windows):
            raise ValueError("recency window durations must be positive")


@dataclass(frozen=True, slots=True)
class RecentQuery:
    query_id: str
    max_rows: int
    as_of_ns: int
    prefix: str = ""
    extensions: tuple[str, ...] = ()
    within_seconds: float | None = None
    include_ignored: bool = False
    kind: Literal[QueryKind.RECENT] = field(init=False, default=QueryKind.RECENT)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_positive(self.max_rows, "max_rows")
        _require_positive(self.as_of_ns, "as_of_ns")
        if self.within_seconds is not None and self.within_seconds <= 0:
            raise ValueError("within_seconds must be positive")


@dataclass(frozen=True, slots=True)
class CatalogQuery:
    query_id: str
    max_rows: int
    after: str | None = None
    include_ignored: bool = False
    terminal_extensions: tuple[str, ...] = ()
    ancestor_names: tuple[str, ...] = ()
    size_less_than: int | None = None
    kind: Literal[QueryKind.CATALOG] = field(init=False, default=QueryKind.CATALOG)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_positive(self.max_rows, "max_rows")
        if len(set(self.terminal_extensions)) != len(self.terminal_extensions):
            raise ValueError("terminal_extensions entries must be unique")
        if any(not value.startswith(".") for value in self.terminal_extensions):
            raise ValueError("terminal_extensions entries must start with a dot")
        if any(value != value.lower() for value in self.terminal_extensions):
            raise ValueError("terminal_extensions entries must be lowercase")
        if any(
            len(value) < 2 or "/" in value or "\\" in value or "." in value[1:]
            for value in self.terminal_extensions
        ):
            raise ValueError("terminal_extensions entries must be canonical terminal suffixes")
        if len(set(self.ancestor_names)) != len(self.ancestor_names):
            raise ValueError("ancestor_names entries must be unique")
        if any(
            not name or name in {".", ".."} or "/" in name or "\\" in name
            for name in self.ancestor_names
        ):
            raise ValueError("ancestor_names entries must be exact path-component names")
        if self.size_less_than is not None:
            _require_positive(self.size_less_than, "size_less_than")


@dataclass(frozen=True, slots=True)
class DiagnosticsQuery:
    query_id: str
    kind: Literal[QueryKind.DIAGNOSTICS] = field(init=False, default=QueryKind.DIAGNOSTICS)

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")


type ReadQuery = (
    EntryQuery
    | DirectoryQuery
    | FilteredTreeQuery
    | RollupQuery
    | NavigationQuery
    | RecentQuery
    | CatalogQuery
    | DiagnosticsQuery
)

REGISTERED_QUERY_TYPES: tuple[type[ReadQuery], ...] = (
    EntryQuery,
    DirectoryQuery,
    FilteredTreeQuery,
    RollupQuery,
    NavigationQuery,
    RecentQuery,
    CatalogQuery,
    DiagnosticsQuery,
)

QUERY_TYPE_BY_KIND: Mapping[str, type[ReadQuery]] = {
    QueryKind.ENTRY.value: EntryQuery,
    QueryKind.DIRECTORY.value: DirectoryQuery,
    QueryKind.FILTERED_TREE.value: FilteredTreeQuery,
    QueryKind.ROLLUP.value: RollupQuery,
    QueryKind.NAVIGATION.value: NavigationQuery,
    QueryKind.RECENT.value: RecentQuery,
    QueryKind.CATALOG.value: CatalogQuery,
    QueryKind.DIAGNOSTICS.value: DiagnosticsQuery,
}


@dataclass(frozen=True, slots=True)
class ReadRequest:
    queries: tuple[ReadQuery, ...] = ()
    at_version: EngineVersion | None = None

    def __post_init__(self) -> None:
        if len(self.queries) > MAX_QUERIES_PER_READ:
            raise ValueError(f"a read request accepts at most {MAX_QUERIES_PER_READ} queries")
        query_ids = [query.query_id for query in self.queries]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("query_id values must be unique within a read request")


class EntryPresence(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EntryProjection:
    query_id: str
    presence: EntryPresence
    entry: InventoryEntry | None

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        if (self.presence is EntryPresence.PRESENT) != (self.entry is not None):
            raise ValueError("present entry projections require exactly one entry")


@dataclass(frozen=True, slots=True)
class DirectoryProjection:
    query_id: str
    entries: tuple[InventoryEntry, ...]
    next_page: str | None = None
    remaining_rows: int = 0

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_nonnegative(self.remaining_rows, "remaining_rows")
        if self.next_page is not None:
            _require_nonempty(self.next_page, "next_page")
            if not self.entries:
                raise ValueError("a tree continuation requires a nonempty page")
        if (self.next_page is None) != (self.remaining_rows == 0):
            raise ValueError("tree continuation and remaining_rows must describe the same suffix")


@dataclass(frozen=True, slots=True)
class FilteredTreeProjection:
    query_id: str
    entries: tuple[InventoryEntry, ...]
    matching_leaves: int
    matching_files: int
    matching_bytes: int
    next_page: str | None = None
    remaining_rows: int = 0

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_nonnegative(self.matching_leaves, "matching_leaves")
        _require_nonnegative(self.matching_files, "matching_files")
        _require_nonnegative(self.matching_bytes, "matching_bytes")
        _require_nonnegative(self.remaining_rows, "remaining_rows")
        if self.next_page is not None:
            _require_nonempty(self.next_page, "next_page")
            if not self.entries:
                raise ValueError("a tree continuation requires a nonempty page")
        if (self.next_page is None) != (self.remaining_rows == 0):
            raise ValueError("tree continuation and remaining_rows must describe the same suffix")


@dataclass(frozen=True, slots=True)
class RollupProjection:
    query_id: str
    payload: RollupResult | None

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")


@dataclass(frozen=True, slots=True)
class NavigationProjection:
    query_id: str
    payload: NavigationTallies
    valid_until_ns: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        if self.valid_until_ns is not None:
            _require_positive(self.valid_until_ns, "valid_until_ns")


@dataclass(frozen=True, slots=True)
class RecentProjection:
    query_id: str
    entries: tuple[InventoryEntry, ...]
    total_matches: int
    gitignored_directories: tuple[str, ...] = ()
    valid_until_ns: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_nonnegative(self.total_matches, "total_matches")
        if self.total_matches < len(self.entries):
            raise ValueError("total_matches cannot be smaller than returned entries")
        if len(self.gitignored_directories) != len(set(self.gitignored_directories)):
            raise ValueError("gitignored_directories entries must be unique")
        for path in self.gitignored_directories:
            require_canonical_inventory_path(path, "gitignored directory", allow_root=False)
        if self.valid_until_ns is not None:
            _require_positive(self.valid_until_ns, "valid_until_ns")

    @property
    def truncated(self) -> bool:
        """Whether the query bound omitted matching rows."""

        return self.total_matches > len(self.entries)


@dataclass(frozen=True, slots=True)
class CatalogRecord:
    path: str
    logical_extension: str
    size: int
    mtime_ns: int

    def __post_init__(self) -> None:
        require_canonical_inventory_path(self.path, "path", allow_root=False)
        _require_nonnegative(self.size, "size")


@dataclass(frozen=True, slots=True)
class CatalogProjection:
    query_id: str
    records: tuple[CatalogRecord, ...]
    total_matches: int
    next_page: str | None = None
    remaining_rows: int = 0

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")
        _require_nonnegative(self.total_matches, "total_matches")
        _require_nonnegative(self.remaining_rows, "remaining_rows")
        if self.total_matches < len(self.records):
            raise ValueError("total_matches cannot be smaller than returned records")
        if self.next_page is not None:
            _require_nonempty(self.next_page, "next_page")
            if not self.records:
                raise ValueError("a catalog continuation requires a nonempty page")
        if (self.next_page is None) != (self.remaining_rows == 0):
            raise ValueError(
                "catalog continuation and remaining_rows must describe the same suffix"
            )
        if self.remaining_rows > self.total_matches - len(self.records):
            raise ValueError("catalog remaining_rows cannot exceed unreturned matches")


@dataclass(frozen=True, slots=True)
class DiagnosticsProjection:
    query_id: str
    payload: ProviderDiagnostics

    def __post_init__(self) -> None:
        _require_nonempty(self.query_id, "query_id")


type ProjectionResult = (
    EntryProjection
    | DirectoryProjection
    | FilteredTreeProjection
    | RollupProjection
    | NavigationProjection
    | RecentProjection
    | CatalogProjection
    | DiagnosticsProjection
)


@dataclass(frozen=True, slots=True)
class ReadResult:
    version: EngineVersion
    cursor: ChangeCursor
    state: IndexState
    projections: tuple[ProjectionResult, ...]
    work: WorkCounters

    def __post_init__(self) -> None:
        if self.version.session != self.cursor.session:
            raise ValueError("version and cursor must describe the same session")
        if self.version.sequence != self.cursor.sequence:
            raise ValueError("version and cursor must describe the same observation boundary")
        query_ids = [projection.query_id for projection in self.projections]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("projection query_id values must be unique")

    def projection(self, query_id: str) -> ProjectionResult:
        for projection in self.projections:
            if projection.query_id == query_id:
                return projection
        raise KeyError(query_id)


@dataclass(frozen=True, slots=True)
class ChangeBatch:
    cursor: ChangeCursor
    version: EngineVersion
    state: IndexState
    dirty_paths: tuple[str, ...] = ()
    dirty_queries: frozenset[QueryKind] = frozenset()
    all_dirty: bool = False
    reset: bool = False
    work: WorkCounters = field(default_factory=WorkCounters)

    def __post_init__(self) -> None:
        if self.version.session != self.cursor.session:
            raise ValueError("version and cursor must describe the same session")
        if self.version.sequence != self.cursor.sequence:
            raise ValueError("version and cursor must describe the same change boundary")
        if self.all_dirty and self.dirty_paths:
            raise ValueError("all_dirty replaces individual dirty paths")
        if self.reset and (self.all_dirty or self.dirty_paths or self.dirty_queries):
            raise ValueError("reset replaces dirty paths and projections")
        if len(self.dirty_paths) > MAX_CHANGE_PATHS:
            raise ValueError("a change batch accepts at most 1024 dirty paths")
        if len(self.dirty_paths) != len(set(self.dirty_paths)):
            raise ValueError("change-batch dirty paths must be unique")
        for path in self.dirty_paths:
            require_canonical_inventory_path(path, "dirty path", allow_root=True)


class RefreshReason(StrEnum):
    FILESYSTEM_HINT = "filesystem_hint"
    ACTIVITY_OBSERVATION = "activity_observation"
    GITIGNORE_CHANGE = "gitignore_change"
    RECONCILIATION = "reconciliation"
    USER_REQUEST = "user_request"


class ObservationKind(StrEnum):
    """Best-effort source label for a path that the provider must verify."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RefreshObservation:
    """One served-root-relative filesystem hint."""

    path: str
    kind: ObservationKind = ObservationKind.UNKNOWN

    def __post_init__(self) -> None:
        require_canonical_inventory_path(self.path, "path", allow_root=False)


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    observations: tuple[RefreshObservation, ...]
    reason: RefreshReason = RefreshReason.FILESYSTEM_HINT

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("refresh requires at least one path")
        if len(self.observations) > MAX_COMMAND_PATHS:
            raise ValueError("refresh accepts at most 1024 paths")
        paths = self.paths
        if len(paths) != len(set(paths)):
            raise ValueError("refresh paths must be unique")

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(observation.path for observation in self.observations)


@dataclass(frozen=True, slots=True)
class RefreshReceipt:
    version: EngineVersion
    accepted_paths: tuple[str, ...]
    rejected_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.accepted_paths) + len(self.rejected_paths) > MAX_COMMAND_PATHS:
            raise ValueError(f"refresh receipt accepts at most {MAX_COMMAND_PATHS} paths")
        if len(self.accepted_paths) != len(set(self.accepted_paths)):
            raise ValueError("accepted refresh paths must be unique")
        if len(self.rejected_paths) != len(set(self.rejected_paths)):
            raise ValueError("rejected refresh paths must be unique")
        if set(self.accepted_paths) & set(self.rejected_paths):
            raise ValueError("refresh paths cannot be both accepted and rejected")
        for path in (*self.accepted_paths, *self.rejected_paths):
            require_canonical_inventory_path(path, "refresh receipt path", allow_root=False)


@dataclass(frozen=True, slots=True)
class PriorityRequest:
    paths: tuple[str, ...]
    max_depth: int = 2

    def __post_init__(self) -> None:
        if not self.paths:
            raise ValueError("priority requires at least one path")
        if len(self.paths) > MAX_COMMAND_PATHS:
            raise ValueError("priority accepts at most 1024 paths")
        if len(self.paths) != len(set(self.paths)):
            raise ValueError("priority paths must be unique")
        for path in self.paths:
            require_canonical_inventory_path(path, "priority path", allow_root=False)
        _require_positive(self.max_depth, "max_depth")


class InventoryContractError(Exception):
    """Base class for failures exposed at the provider boundary."""


class InventoryClosedError(InventoryContractError):
    """The opened-root handle has already closed."""


class VersionUnavailableError(InventoryContractError):
    """The requested coherent version is no longer retained."""


@runtime_checkable
class InventoryHandle(Protocol):
    async def read(self, request: ReadRequest) -> ReadResult: ...

    def changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]: ...

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt: ...

    async def prioritize(self, request: PriorityRequest) -> None: ...

    async def close(self) -> None: ...


@runtime_checkable
class InventoryBackend(Protocol):
    async def open(self, root: Path, config: InventoryConfig) -> InventoryHandle: ...
