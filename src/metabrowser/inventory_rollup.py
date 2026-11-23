"""Pure bounded subtree aggregation over an inventory snapshot."""

from __future__ import annotations

import heapq
from collections import Counter
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from metabrowser.file_type_registry import FileTypeRegistry, load_file_type_registry
from metabrowser.settings import (
    ROLLUP_FILE_TYPE_FILENAME_LIMIT,
    ROLLUP_FILE_TYPE_REMAINING_LIMIT,
)
from metabrowser.wire_models import (
    ExtensionTallyRow,
    FileTypeBreakdown,
    FileTypeExtensionBreakdown,
    FileTypeFamilyBreakdown,
    FileTypeFilenameBreakdown,
    FileTypeMeasure,
    FileTypeOthersBreakdown,
    FileTypePopulationMetrics,
    RollupDirNode,
    RollupResult,
)


class RollupEntry(Protocol):
    """Facts used by the pure rollup reducer. Mtime is optional on the wire."""

    @property
    def path(self) -> str: ...

    @property
    def parent(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def ext(self) -> str: ...

    @property
    def size(self) -> int: ...

    @property
    def mtime_ns(self) -> int: ...

    @property
    def gitignored(self) -> bool: ...

    @property
    def total_files(self) -> int | None: ...


ROLLUP_NO_EXT_KEY = "(none)"
ROLLUP_REST_EXT_KEY = ""

RollupRank = Literal["bytes", "dual"]
# Whether gitignored entries are emitted as children (and spend the node budget).
RollupIgnored = Literal["include", "exclude"]
# How a directory's file children are written: as objects among its ``children``, or
# as positional ``files`` entries (``RollupCompactFile`` in ``wire_models.py``).
RollupEncoding = Literal["json", "compact"]


@dataclass(frozen=True, slots=True)
class RollupOptions:
    """Bounds and ranking semantics for one rollup response.

    ``ignored="exclude"`` changes only which children are emitted, how the node budget
    is spent, and what a ``rest`` bucket counts; every total, tally, and breakdown stays
    as with ``"include"``. ``encoding="compact"`` changes only how file children are
    written.
    """

    depth: int
    top: int
    ext_top: int
    max_nodes: int
    remaining_top: int = ROLLUP_FILE_TYPE_REMAINING_LIMIT
    filename_top: int = ROLLUP_FILE_TYPE_FILENAME_LIMIT
    ext_rank: RollupRank = "bytes"
    omit_mtime: bool = False
    ignored: RollupIgnored = "include"
    encoding: RollupEncoding = "json"

    def __post_init__(self) -> None:
        if (
            min(
                self.depth,
                self.top,
                self.ext_top,
                self.max_nodes,
                self.remaining_top,
                self.filename_top,
            )
            < 0
        ):
            raise ValueError("rollup limits must be nonnegative")
        if self.ext_rank not in ("bytes", "dual"):
            raise ValueError(f"unknown extension ranking mode: {self.ext_rank!r}")
        if self.ignored not in ("include", "exclude"):
            raise ValueError(f"unknown ignored mode: {self.ignored!r}")
        if self.encoding not in ("json", "compact"):
            raise ValueError(f"unknown rollup encoding: {self.encoding!r}")
        if self.remaining_top > ROLLUP_FILE_TYPE_REMAINING_LIMIT:
            raise ValueError("remaining file-type limit exceeds the response contract")
        if self.filename_top > ROLLUP_FILE_TYPE_FILENAME_LIMIT:
            raise ValueError("filename file-type limit exceeds the response contract")


@dataclass(slots=True)
class _SubtreeAggregate:
    files_all: int = 0
    size_all: int = 0
    files_unignored: int = 0
    size_unignored: int = 0
    # Directories beneath, so a directory knows the nodes its whole expansion would
    # spend (``_emit_limit``).
    dirs_all: int = 0
    dirs_unignored: int = 0
    newest_mtime_ns: int = 0
    ext_files: Counter[str] = field(default_factory=Counter)
    ext_bytes: Counter[str] = field(default_factory=Counter)
    ext_files_unignored: Counter[str] = field(default_factory=Counter)
    ext_bytes_unignored: Counter[str] = field(default_factory=Counter)
    no_ext_files: Counter[str] = field(default_factory=Counter)
    no_ext_bytes: Counter[str] = field(default_factory=Counter)
    no_ext_files_unignored: Counter[str] = field(default_factory=Counter)
    no_ext_bytes_unignored: Counter[str] = field(default_factory=Counter)

    def absorb(self, other: _SubtreeAggregate) -> None:
        self.files_all += other.files_all
        self.size_all += other.size_all
        self.files_unignored += other.files_unignored
        self.size_unignored += other.size_unignored
        self.dirs_all += other.dirs_all
        self.dirs_unignored += other.dirs_unignored
        self.newest_mtime_ns = max(self.newest_mtime_ns, other.newest_mtime_ns)
        self.ext_files.update(other.ext_files)
        self.ext_bytes.update(other.ext_bytes)
        self.ext_files_unignored.update(other.ext_files_unignored)
        self.ext_bytes_unignored.update(other.ext_bytes_unignored)
        self.no_ext_files.update(other.no_ext_files)
        self.no_ext_bytes.update(other.no_ext_bytes)
        self.no_ext_files_unignored.update(other.no_ext_files_unignored)
        self.no_ext_bytes_unignored.update(other.no_ext_bytes_unignored)


# A caller-owned memo of per-directory subtree aggregates, keyed by directory
# path. The aggregate values stay opaque to holders: only this module reads or
# writes their fields. Owners are responsible for eviction — see
# ``build_rollup``.
SubtreeAggregate = _SubtreeAggregate
SubtreeAggregateCache = MutableMapping[str, SubtreeAggregate]


@dataclass(frozen=True, slots=True)
class _FileTypePartition:
    """One registry classification pass shared by every wire projection."""

    family_children: dict[str, dict[str, list[int]]]
    remaining_keys: set[str]
    has_no_extension: bool


def build_rollup(
    entries: Mapping[str, RollupEntry],
    children_by_parent: Mapping[str, Sequence[RollupEntry]],
    root_path: str,
    options: RollupOptions,
    ancestor_gitignored: bool,
    aggregates: SubtreeAggregateCache | None = None,
    registry: FileTypeRegistry | None = None,
) -> RollupResult | None:
    """Build a bounded node tree from a snapshot and its reusable child index.

    *aggregates* is an optional persistent memo of per-directory subtree
    aggregates, reused across calls. Callers that own one must invalidate a
    directory's whole ancestor chain whenever an entry beneath it changes;
    The Python provider does this on every write.
    Omit it for a self-contained, purely functional rollup.
    """

    root_entry = entries.get(root_path)
    if root_entry is None or root_entry.type != "dir":
        return None

    if aggregates is None:
        aggregates = {}
    root_ignored = ancestor_gitignored or root_entry.gitignored
    root_aggregate = _aggregate_subtree(
        root_path,
        root_ignored,
        children_by_parent,
        aggregates,
    )
    root_node = _emit_bounded_tree(
        root_entry,
        root_ignored,
        children_by_parent,
        aggregates,
        options,
    )
    active_registry = load_file_type_registry() if registry is None else registry
    selected = _select_extension_keys(root_aggregate, options.ext_top, options.ext_rank)
    file_types = _partition_file_types(root_aggregate, active_registry)
    return {
        "node": cast(RollupDirNode, root_node),
        "ext_tallies": _serialize_extension_tallies(root_aggregate, selected),
        "file_type_breakdown": _serialize_file_type_breakdown(
            root_aggregate,
            filename_limit=options.filename_top,
            remaining_limit=options.remaining_top,
            file_types=file_types,
            registry=active_registry,
        ),
    }


def group_rollup_children(
    entries: Mapping[str, RollupEntry],
) -> dict[str, tuple[RollupEntry, ...]]:
    """Index immutable child sequences for repeated subtree rollups."""

    grouped: dict[str, list[RollupEntry]] = {}
    for entry in entries.values():
        if entry.path == entry.parent:
            continue
        grouped.setdefault(entry.parent, []).append(entry)
    return {parent: tuple(children) for parent, children in grouped.items()}


def _aggregate_subtree(
    directory_path: str,
    parent_ignored: bool,
    children_by_parent: Mapping[str, Sequence[RollupEntry]],
    aggregates: SubtreeAggregateCache,
) -> _SubtreeAggregate:
    # ``aggregates`` doubles as a memo. A directory's aggregate is a pure
    # function of its subtree, and the inherited ignore state is fixed by
    # the real ancestor chain, so a present entry is reusable as-is. When
    # the caller passes a persistent cache (see
    # the Python provider's aggregate cache) an unchanged subtree costs one
    # dict lookup instead of a walk over every file beneath it — the
    # difference between O(subtree) and O(1) on each rollup request.
    cached = aggregates.get(directory_path)
    if cached is not None:
        return cached
    aggregate = _SubtreeAggregate()
    for child in children_by_parent.get(directory_path, ()):
        ignored = parent_ignored or child.gitignored
        if child.type == "dir":
            aggregate.absorb(
                _aggregate_subtree(child.path, ignored, children_by_parent, aggregates)
            )
            aggregate.dirs_all += 1
            if not ignored:
                aggregate.dirs_unignored += 1
            continue
        if child.type != "file":
            continue
        extension = child.ext or ROLLUP_NO_EXT_KEY
        aggregate.files_all += 1
        aggregate.size_all += child.size
        aggregate.newest_mtime_ns = max(aggregate.newest_mtime_ns, child.mtime_ns)
        aggregate.ext_files[extension] += 1
        aggregate.ext_bytes[extension] += child.size
        if not child.ext:
            aggregate.no_ext_files[child.name] += 1
            aggregate.no_ext_bytes[child.name] += child.size
        if not ignored:
            aggregate.files_unignored += 1
            aggregate.size_unignored += child.size
            aggregate.ext_files_unignored[extension] += 1
            aggregate.ext_bytes_unignored[extension] += child.size
            if not child.ext:
                aggregate.no_ext_files_unignored[child.name] += 1
                aggregate.no_ext_bytes_unignored[child.name] += child.size
    aggregates[directory_path] = aggregate
    return aggregate


def _file_node(entry: RollupEntry, parent_ignored: bool, options: RollupOptions) -> dict[str, Any]:
    node: dict[str, Any] = {
        "name": entry.name,
        "path": entry.path,
        "type": "file",
        "size": entry.size,
    }
    if not options.omit_mtime:
        node["mtime"] = entry.mtime_ns / 1_000_000_000.0
    node["ext"] = entry.ext
    node["gitignored"] = parent_ignored or entry.gitignored
    return node


def _compact_file(entry: RollupEntry, parent_ignored: bool, options: RollupOptions) -> list[Any]:
    """The file's ``[name, size, mtime, ext, gitignored]`` entry in its folder's ``files``.

    ``path`` is left out because a client derives it from the folder's, as
    ``dir.path ? dir.path + "/" + name : name``: every child emitted here is listed
    under its parent's path (``group_rollup_children``), whose canonical inventory path
    is the parent's plus ``/`` and the child's name. ``mtime`` is null where the JSON
    encoding omits it, and ``gitignored`` is 0 or 1.
    """

    return [
        entry.name,
        entry.size,
        None if options.omit_mtime else entry.mtime_ns / 1_000_000_000.0,
        entry.ext,
        1 if parent_ignored or entry.gitignored else 0,
    ]


def _directory_node(
    entry: RollupEntry,
    aggregate: _SubtreeAggregate,
    ignored: bool,
    options: RollupOptions,
) -> dict[str, Any]:
    ranked_extensions = sorted(
        aggregate.ext_files,
        key=lambda key: (-aggregate.ext_bytes[key], -aggregate.ext_files[key], key),
    )
    node: dict[str, Any] = {
        "name": entry.name,
        "path": entry.path,
        "type": "dir",
        "state": "pending" if entry.total_files is None else "complete",
        "total_files": aggregate.files_all,
        "total_size": aggregate.size_all,
        "unignored_files": aggregate.files_unignored,
        "unignored_size": aggregate.size_unignored,
    }
    if not options.omit_mtime:
        node["mtime"] = aggregate.newest_mtime_ns / 1_000_000_000.0
    node["gitignored"] = ignored
    node["dominant_ext"] = ranked_extensions[0] if ranked_extensions else ""
    return node


def _all_weight(entry: RollupEntry, aggregates: Mapping[str, _SubtreeAggregate]) -> int:
    return aggregates[entry.path].size_all if entry.type == "dir" else entry.size


def _unignored_weight(
    entry: RollupEntry,
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
) -> int:
    if entry.type == "dir":
        return aggregates[entry.path].size_unignored
    return 0 if parent_ignored or entry.gitignored else entry.size


def _ordered_children(
    children: Sequence[RollupEntry],
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
    emit_limit: int,
    *,
    visible_only: bool = False,
) -> list[RollupEntry]:
    """Return a prefix of the children in rollup order that holds *emit_limit* to emit.

    The order interleaves the all-file and visible-file rankings, with ties broken by path.
    Interleaving the first ``m`` of each ranking gives a prefix of that order at least
    ``m`` long. Only files and directories are emitted, so with ``m`` set to *emit_limit*
    plus the number of other children (symlinks), the prefix holds *emit_limit* files and
    directories or is every child. ``heapq.nsmallest`` selects each ranking's first ``m``
    in the order a full sort gives, in O(n log m) rather than O(n log n); the measurement
    is beside ``ROLLUP_MAX_DEPTH`` in ``settings.py``. *visible_only* ranks by the
    visible files alone, for a rollup that leaves ignored children out.
    """

    other_types = sum(1 for child in children if child.type not in ("dir", "file"))
    span = min(len(children), emit_limit + other_types)
    visible_ranked = heapq.nsmallest(
        span,
        children,
        key=lambda child: (-_unignored_weight(child, aggregates, parent_ignored), child.path),
    )
    if visible_only:
        return visible_ranked
    all_ranked = heapq.nsmallest(
        span, children, key=lambda child: (-_all_weight(child, aggregates), child.path)
    )
    ordered: list[RollupEntry] = []
    seen: set[str] = set()
    for index in range(span):
        for ranked in (all_ranked, visible_ranked):
            child = ranked[index]
            if child.path not in seen:
                ordered.append(child)
                seen.add(child.path)
    return ordered


def _emit_bounded_tree(
    root_entry: RollupEntry,
    root_ignored: bool,
    children_by_parent: Mapping[str, Sequence[RollupEntry]],
    aggregates: Mapping[str, _SubtreeAggregate],
    options: RollupOptions,
) -> dict[str, Any]:
    """Expand the heaviest pending directory first, under local and global budgets.

    A directory's weight is its largest share of the root: of files or bytes, among all
    files or among unignored ones, so the order serves either measure and either Show
    ignored setting. Spending the node budget heaviest first gives it to the directories a
    treemap has room to draw. Level by level, a wide shallow tree (a ``node_modules``) spent
    it all on tiny entries a few levels down, and large folders elsewhere came back
    unexpanded.

    Equal weights break by level, then path. Level first, so a tree whose weights are all
    zero (directories listed, no files counted yet) still expands level by level, which
    keeps truncation honest as ``inventory_engine/contract.py`` explains; path last, since
    paths are unique, makes the order total and the emitted tree deterministic.

    The order decides which directory expands next; ``_emit_limit`` decides how much of
    the budget it may spend, so a flat directory early in the order cannot spend the
    budget the ones after it need.
    """

    root_aggregate = aggregates[root_entry.path]
    exclude = options.ignored == "exclude"
    compact = options.encoding == "compact"

    def weight(aggregate: _SubtreeAggregate) -> float:
        visible = max(
            _share(aggregate.files_unignored, root_aggregate.files_unignored),
            _share(aggregate.size_unignored, root_aggregate.size_unignored),
        )
        if exclude:
            # The map that asks for this draws visible files only.
            return visible
        return max(
            _share(aggregate.files_all, root_aggregate.files_all),
            _share(aggregate.size_all, root_aggregate.size_all),
            visible,
        )

    def demand(aggregate: _SubtreeAggregate, level: int) -> tuple[int, int]:
        # The nodes expanding the whole directory would emit, among all entries and
        # among visible ones, or none past the depth.
        if level >= options.depth:
            return (0, 0)
        visible = aggregate.files_unignored + aggregate.dirs_unignored
        if exclude:
            return (visible, visible)
        return (aggregate.files_all + aggregate.dirs_all, visible)

    root_node = _directory_node(root_entry, root_aggregate, root_ignored, options)
    remaining_nodes = max(0, options.max_nodes - 1)
    # The demand of every directory still waiting to expand, the root's at first.
    waiting_all, waiting_visible = demand(root_aggregate, 0)
    pending: list[
        tuple[float, int, str, int, RollupEntry, dict[str, Any], bool, tuple[int, int]]
    ] = []
    sequence = 0
    heapq.heappush(
        pending,
        (
            -1.0,
            0,
            root_entry.path,
            sequence,
            root_entry,
            root_node,
            root_ignored,
            (waiting_all, waiting_visible),
        ),
    )
    while pending:
        _, level, _, _, entry, node, ignored, (own_all, own_visible) = heapq.heappop(pending)
        emit_limit = _emit_limit(
            options.top,
            remaining_nodes,
            (own_all, waiting_all),
            (own_visible, waiting_visible),
        )
        waiting_all -= own_all
        waiting_visible -= own_visible
        if level >= options.depth or remaining_nodes <= 0:
            node["children"] = None
            continue

        children = children_by_parent.get(entry.path, ())
        # Ignored children left out of the response: neither emitted nor in ``rest``.
        dropped: Sequence[RollupEntry] = ()
        if exclude:
            dropped = [child for child in children if ignored or child.gitignored]
            if dropped:
                children = [child for child in children if not (ignored or child.gitignored)]
        emitted: list[dict[str, Any]] = []
        files: list[list[Any]] = []
        emitted_entries: list[RollupEntry] = []
        # Children emitted, or passed over as neither file nor directory, before the
        # limit; every child after them folds into ``rest``.
        placed = 0
        for child in _ordered_children(
            children, aggregates, ignored, emit_limit, visible_only=exclude
        ):
            if len(emitted_entries) >= emit_limit:
                break
            placed += 1
            child_ignored = ignored or child.gitignored
            if child.type == "dir":
                child_aggregate = aggregates[child.path]
                child_node = _directory_node(child, child_aggregate, child_ignored, options)
                emitted.append(child_node)
                emitted_entries.append(child)
                sequence += 1
                child_demand = demand(child_aggregate, level + 1)
                waiting_all += child_demand[0]
                waiting_visible += child_demand[1]
                heapq.heappush(
                    pending,
                    (
                        -weight(child_aggregate),
                        level + 1,
                        child.path,
                        sequence,
                        child,
                        child_node,
                        child_ignored,
                        child_demand,
                    ),
                )
                remaining_nodes -= 1
            elif child.type == "file":
                if compact:
                    files.append(_compact_file(child, ignored, options))
                else:
                    emitted.append(_file_node(child, ignored, options))
                emitted_entries.append(child)
                remaining_nodes -= 1
        node["children"] = emitted
        if compact:
            node["files"] = files
        if placed < len(children):
            node["rest"] = _rest_bucket(
                aggregates[entry.path], children, emitted_entries, aggregates, ignored, dropped
            )
    return root_node


def _emit_limit(top: int, remaining_nodes: int, *demands: tuple[int, int]) -> int:
    """How many children the directory being expanded may emit: its share of the budget.

    A directory's demand is the nodes its whole expansion would emit, every file and
    directory beneath it. The budget left is shared among the directories waiting to
    expand in proportion to their demand, so each may emit up to the same fraction of its
    own: ``remaining_nodes * own / waiting``, rounded up, and at least one. Emitting that
    fraction of a flat directory leaves the fraction for the ones after it the same, so
    one flat directory early in the order cannot take the budget.

    Each of *demands* is one population's ``(own, waiting)``: all entries and visible
    ones when ignored entries are emitted, since one response serves either Show ignored
    setting, and visible ones twice when they are not. The directory takes the larger
    share. When the budget covers the waiting demand of every entry it may emit, the share
    is at least the directory's own demand, which is at least its child count, and the
    budget left still covers what waits after it, so the whole tree is emitted. *top*
    bounds every directory beside it. The measurement that chose this rule is beside
    ``ROLLUP_MAX_TOP`` in ``settings.py``.
    """

    share = max(
        -(-remaining_nodes * own // waiting) if waiting > 0 else 0 for own, waiting in demands
    )
    return min(top, remaining_nodes, max(1, share))


def _rest_bucket(
    aggregate: _SubtreeAggregate,
    children: Sequence[RollupEntry],
    emitted: Sequence[RollupEntry],
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
    dropped: Sequence[RollupEntry] = (),
) -> dict[str, int]:
    """Total the children that were not emitted, as the directory's aggregate less those.

    ``_aggregate_subtree`` makes a directory's aggregate the sum of its children, so
    subtracting the emitted ones costs O(top) where summing the omitted ones walked them
    all. Only the directory count reads every child, one type check each.

    *dropped* are the ignored children a rollup that excludes them left out of
    *children*; they are subtracted too, so ``rest`` counts only the unignored siblings
    that were omitted. An ignored child holds no unignored file, so only ``files`` and
    ``size`` change.
    """

    rest = {
        "dirs": sum(1 for child in children if child.type == "dir"),
        "files": aggregate.files_all,
        "size": aggregate.size_all,
        "unignored_files": aggregate.files_unignored,
        "unignored_size": aggregate.size_unignored,
    }
    for child in dropped:
        if child.type == "dir":
            rest["files"] -= aggregates[child.path].files_all
            rest["size"] -= aggregates[child.path].size_all
        elif child.type == "file":
            rest["files"] -= 1
            rest["size"] -= child.size
    for child in emitted:
        if child.type == "dir":
            child_aggregate = aggregates[child.path]
            rest["dirs"] -= 1
            rest["files"] -= child_aggregate.files_all
            rest["size"] -= child_aggregate.size_all
            rest["unignored_files"] -= child_aggregate.files_unignored
            rest["unignored_size"] -= child_aggregate.size_unignored
        else:
            rest["files"] -= 1
            rest["size"] -= child.size
            if not (parent_ignored or child.gitignored):
                rest["unignored_files"] -= 1
                rest["unignored_size"] -= child.size
    return rest


def _share(value: int, total: int) -> float:
    return value / total if total > 0 else 0.0


def _extension_scores(aggregate: _SubtreeAggregate, key: str) -> tuple[float, float, float]:
    file_score = max(
        _share(aggregate.ext_files[key], aggregate.files_all),
        _share(aggregate.ext_files_unignored[key], aggregate.files_unignored),
    )
    byte_score = max(
        _share(aggregate.ext_bytes[key], aggregate.size_all),
        _share(aggregate.ext_bytes_unignored[key], aggregate.size_unignored),
    )
    return max(file_score, byte_score), byte_score, file_score


def _all_extension_keys(aggregate: _SubtreeAggregate) -> set[str]:
    keys = set(aggregate.ext_files)
    keys.update(aggregate.ext_bytes)
    keys.update(aggregate.ext_files_unignored)
    keys.update(aggregate.ext_bytes_unignored)
    return keys


def _select_extension_keys(
    aggregate: _SubtreeAggregate,
    limit: int,
    rank_mode: RollupRank,
) -> list[str]:
    keys = _all_extension_keys(aggregate)
    if rank_mode == "dual":
        ordered = sorted(
            keys,
            key=lambda key: (*(-score for score in _extension_scores(aggregate, key)), key),
        )
    else:
        ordered = sorted(
            keys,
            key=lambda key: (
                -aggregate.ext_bytes[key],
                -aggregate.ext_bytes_unignored[key],
                -aggregate.ext_files[key],
                -aggregate.ext_files_unignored[key],
                key,
            ),
        )
    return ordered[:limit]


def _serialize_extension_tallies(
    aggregate: _SubtreeAggregate,
    selected_keys: Sequence[str],
) -> list[ExtensionTallyRow]:
    selected = set(selected_keys)
    rows: list[ExtensionTallyRow] = [
        (
            key,
            aggregate.ext_files[key],
            aggregate.ext_bytes[key],
            aggregate.ext_files_unignored[key],
            aggregate.ext_bytes_unignored[key],
        )
        for key in selected_keys
    ]
    omitted = _all_extension_keys(aggregate) - selected
    if omitted:
        rows.append(
            (
                ROLLUP_REST_EXT_KEY,
                sum(aggregate.ext_files[key] for key in omitted),
                sum(aggregate.ext_bytes[key] for key in omitted),
                sum(aggregate.ext_files_unignored[key] for key in omitted),
                sum(aggregate.ext_bytes_unignored[key] for key in omitted),
            )
        )
    return rows


def _population_metrics(
    all_files: int,
    all_bytes: int,
    unignored_files: int,
    unignored_bytes: int,
) -> FileTypePopulationMetrics:
    return {
        "all": FileTypeMeasure(files=all_files, bytes=all_bytes),
        "unignored": FileTypeMeasure(files=unignored_files, bytes=unignored_bytes),
    }


def _extension_metrics(aggregate: _SubtreeAggregate, key: str) -> FileTypePopulationMetrics:
    return _population_metrics(
        aggregate.ext_files[key],
        aggregate.ext_bytes[key],
        aggregate.ext_files_unignored[key],
        aggregate.ext_bytes_unignored[key],
    )


def _add_metrics(target: list[int], metrics: FileTypePopulationMetrics) -> None:
    target[0] += metrics["all"]["files"]
    target[1] += metrics["all"]["bytes"]
    target[2] += metrics["unignored"]["files"]
    target[3] += metrics["unignored"]["bytes"]


def _metrics_from_totals(totals: Sequence[int]) -> FileTypePopulationMetrics:
    return _population_metrics(totals[0], totals[1], totals[2], totals[3])


def _counter_scores(
    key: str,
    files_all: Counter[str],
    bytes_all: Counter[str],
    files_unignored: Counter[str],
    bytes_unignored: Counter[str],
    aggregate: _SubtreeAggregate,
) -> tuple[float, float, float]:
    file_score = max(
        _share(files_all[key], aggregate.files_all),
        _share(files_unignored[key], aggregate.files_unignored),
    )
    byte_score = max(
        _share(bytes_all[key], aggregate.size_all),
        _share(bytes_unignored[key], aggregate.size_unignored),
    )
    return max(file_score, byte_score), byte_score, file_score


def _select_counter_keys(
    keys: set[str],
    limit: int,
    files_all: Counter[str],
    bytes_all: Counter[str],
    files_unignored: Counter[str],
    bytes_unignored: Counter[str],
    aggregate: _SubtreeAggregate,
) -> list[str]:
    return sorted(
        keys,
        key=lambda key: (
            *(
                -score
                for score in _counter_scores(
                    key,
                    files_all,
                    bytes_all,
                    files_unignored,
                    bytes_unignored,
                    aggregate,
                )
            ),
            key,
        ),
    )[:limit]


def _others_metrics(
    omitted: set[str],
    files_all: Counter[str],
    bytes_all: Counter[str],
    files_unignored: Counter[str],
    bytes_unignored: Counter[str],
) -> FileTypeOthersBreakdown | None:
    if not omitted:
        return None
    return {
        "metrics": _population_metrics(
            sum(files_all[key] for key in omitted),
            sum(bytes_all[key] for key in omitted),
            sum(files_unignored[key] for key in omitted),
            sum(bytes_unignored[key] for key in omitted),
        ),
        "omitted_distinct_values": len(omitted),
    }


def _serialize_file_type_breakdown(
    aggregate: _SubtreeAggregate,
    *,
    filename_limit: int,
    remaining_limit: int,
    file_types: _FileTypePartition,
    registry: FileTypeRegistry,
) -> FileTypeBreakdown:
    """Build the conserved File Rollup Format hierarchy before presentation."""

    groups = []
    for group in registry.groups:
        families: list[FileTypeFamilyBreakdown] = []
        for family in registry.families:
            if family.group_id != group.id:
                continue
            raw_children = file_types.family_children.get(family.id)
            if not raw_children:
                continue
            family_totals = [0, 0, 0, 0]
            children: list[FileTypeExtensionBreakdown] = []
            for extension in family.extensions:
                totals = raw_children.get(extension)
                if totals is None:
                    continue
                metrics = _metrics_from_totals(totals)
                _add_metrics(family_totals, metrics)
                children.append({"extension": extension, "metrics": metrics})
            families.append(
                {
                    "id": family.id,
                    "metrics": _metrics_from_totals(family_totals),
                    "extensions": children,
                }
            )
        if families:
            groups.append({"id": group.id, "families": families})

    no_extension_keys = set(aggregate.no_ext_files) | set(aggregate.no_ext_bytes)
    no_extension_keys.update(aggregate.no_ext_files_unignored)
    no_extension_keys.update(aggregate.no_ext_bytes_unignored)
    selected_filenames = _select_counter_keys(
        no_extension_keys,
        filename_limit,
        aggregate.no_ext_files,
        aggregate.no_ext_bytes,
        aggregate.no_ext_files_unignored,
        aggregate.no_ext_bytes_unignored,
        aggregate,
    )
    filenames: list[FileTypeFilenameBreakdown] = [
        {
            "basename": basename,
            "metrics": _population_metrics(
                aggregate.no_ext_files[basename],
                aggregate.no_ext_bytes[basename],
                aggregate.no_ext_files_unignored[basename],
                aggregate.no_ext_bytes_unignored[basename],
            ),
        }
        for basename in selected_filenames
    ]

    selected_remaining = _select_counter_keys(
        file_types.remaining_keys,
        remaining_limit,
        aggregate.ext_files,
        aggregate.ext_bytes,
        aggregate.ext_files_unignored,
        aggregate.ext_bytes_unignored,
        aggregate,
    )
    remaining_extensions: list[FileTypeExtensionBreakdown] = [
        {"extension": key, "metrics": _extension_metrics(aggregate, key)}
        for key in selected_remaining
    ]
    no_extension_metrics = _extension_metrics(aggregate, ROLLUP_NO_EXT_KEY)
    remaining_totals = [0, 0, 0, 0]
    for key in file_types.remaining_keys:
        _add_metrics(remaining_totals, _extension_metrics(aggregate, key))
    return {
        "schema": "file-type-breakdown-v1",
        "registry": {
            "schema_version": registry.schema_version,
            "revision": registry.revision,
            "fingerprint": registry.fingerprint,
        },
        "metrics": _population_metrics(
            aggregate.files_all,
            aggregate.size_all,
            aggregate.files_unignored,
            aggregate.size_unignored,
        ),
        "groups": groups,
        "no_extension": {
            "metrics": no_extension_metrics,
            "filenames": filenames,
            "others": _others_metrics(
                no_extension_keys - set(selected_filenames),
                aggregate.no_ext_files,
                aggregate.no_ext_bytes,
                aggregate.no_ext_files_unignored,
                aggregate.no_ext_bytes_unignored,
            ),
        },
        "remaining_types": {
            "metrics": _metrics_from_totals(remaining_totals),
            "extensions": remaining_extensions,
            "others": _others_metrics(
                file_types.remaining_keys - set(selected_remaining),
                aggregate.ext_files,
                aggregate.ext_bytes,
                aggregate.ext_files_unignored,
                aggregate.ext_bytes_unignored,
            ),
        },
    }


def _partition_file_types(
    aggregate: _SubtreeAggregate,
    registry: FileTypeRegistry,
) -> _FileTypePartition:
    """Classify each distinct logical extension exactly once per rollup."""

    family_children: dict[str, dict[str, list[int]]] = {}
    remaining_keys: set[str] = set()
    extension_keys = _all_extension_keys(aggregate)
    for key in extension_keys - {ROLLUP_NO_EXT_KEY}:
        classification = registry.classify("", key)
        if classification.family_id is None:
            remaining_keys.add(key)
            continue
        canonical = classification.canonical_extension or key
        totals = family_children.setdefault(classification.family_id, {}).setdefault(
            canonical,
            [0, 0, 0, 0],
        )
        _add_metrics(totals, _extension_metrics(aggregate, key))
    return _FileTypePartition(
        family_children=family_children,
        remaining_keys=remaining_keys,
        has_no_extension=ROLLUP_NO_EXT_KEY in extension_keys,
    )


__all__ = [
    "ROLLUP_NO_EXT_KEY",
    "ROLLUP_REST_EXT_KEY",
    "RollupEncoding",
    "RollupIgnored",
    "RollupOptions",
    "RollupRank",
    "build_rollup",
    "group_rollup_children",
]
