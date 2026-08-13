"""Pure bounded subtree aggregation over an inventory snapshot."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

from metabrowser.wire_models import ExtensionTallyRow, RollupDirNode, RollupResult

if TYPE_CHECKING:
    from metabrowser.events import FsEntry


ROLLUP_NO_EXT_KEY = "(none)"
ROLLUP_REST_EXT_KEY = ""

RollupRank = Literal["bytes", "dual"]


@dataclass(frozen=True, slots=True)
class RollupOptions:
    """Bounds and ranking semantics for one rollup response."""

    depth: int
    top: int
    ext_top: int
    max_nodes: int
    ext_rank: RollupRank = "bytes"

    def __post_init__(self) -> None:
        if min(self.depth, self.top, self.ext_top, self.max_nodes) < 0:
            raise ValueError("rollup limits must be nonnegative")
        if self.ext_rank not in ("bytes", "dual"):
            raise ValueError(f"unknown extension ranking mode: {self.ext_rank!r}")


@dataclass(slots=True)
class _SubtreeAggregate:
    files_all: int = 0
    size_all: int = 0
    files_unignored: int = 0
    size_unignored: int = 0
    newest_mtime_ns: int = 0
    ext_files: Counter[str] = field(default_factory=Counter)
    ext_bytes: Counter[str] = field(default_factory=Counter)
    ext_files_unignored: Counter[str] = field(default_factory=Counter)
    ext_bytes_unignored: Counter[str] = field(default_factory=Counter)

    def absorb(self, other: _SubtreeAggregate) -> None:
        self.files_all += other.files_all
        self.size_all += other.size_all
        self.files_unignored += other.files_unignored
        self.size_unignored += other.size_unignored
        self.newest_mtime_ns = max(self.newest_mtime_ns, other.newest_mtime_ns)
        self.ext_files.update(other.ext_files)
        self.ext_bytes.update(other.ext_bytes)
        self.ext_files_unignored.update(other.ext_files_unignored)
        self.ext_bytes_unignored.update(other.ext_bytes_unignored)


def build_rollup(
    entries: Mapping[str, FsEntry],
    root_path: str,
    options: RollupOptions,
    ancestor_gitignored: bool,
) -> RollupResult | None:
    """Build a bounded node tree and exact extension tallies without filesystem I/O."""

    root_entry = entries.get(root_path)
    if root_entry is None or root_entry.type != "dir":
        return None

    children_by_parent = _group_children(entries)
    aggregates: dict[str, _SubtreeAggregate] = {}
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
    selected = _select_extension_keys(root_aggregate, options.ext_top, options.ext_rank)
    return {
        "node": cast(RollupDirNode, root_node),
        "ext_tallies": _serialize_extension_tallies(root_aggregate, selected),
    }


def _group_children(entries: Mapping[str, FsEntry]) -> dict[str, list[FsEntry]]:
    children_by_parent: dict[str, list[FsEntry]] = {}
    for entry in entries.values():
        if entry.path == entry.parent:
            continue
        children_by_parent.setdefault(entry.parent, []).append(entry)
    return children_by_parent


def _aggregate_subtree(
    directory_path: str,
    parent_ignored: bool,
    children_by_parent: Mapping[str, Sequence[FsEntry]],
    aggregates: dict[str, _SubtreeAggregate],
) -> _SubtreeAggregate:
    aggregate = _SubtreeAggregate()
    for child in children_by_parent.get(directory_path, ()):
        ignored = parent_ignored or child.gitignored
        if child.type == "dir":
            aggregate.absorb(
                _aggregate_subtree(child.path, ignored, children_by_parent, aggregates)
            )
            continue
        if child.type != "file":
            continue
        extension = child.ext or ROLLUP_NO_EXT_KEY
        aggregate.files_all += 1
        aggregate.size_all += child.size
        aggregate.newest_mtime_ns = max(aggregate.newest_mtime_ns, child.mtime_ns)
        aggregate.ext_files[extension] += 1
        aggregate.ext_bytes[extension] += child.size
        if not ignored:
            aggregate.files_unignored += 1
            aggregate.size_unignored += child.size
            aggregate.ext_files_unignored[extension] += 1
            aggregate.ext_bytes_unignored[extension] += child.size
    aggregates[directory_path] = aggregate
    return aggregate


def _file_node(entry: FsEntry, parent_ignored: bool) -> dict[str, Any]:
    return {
        "name": entry.name,
        "path": entry.path,
        "type": "file",
        "size": entry.size,
        "mtime": entry.mtime_ns / 1_000_000_000.0,
        "ext": entry.ext,
        "gitignored": parent_ignored or entry.gitignored,
    }


def _directory_node(
    entry: FsEntry,
    aggregate: _SubtreeAggregate,
    ignored: bool,
) -> dict[str, Any]:
    ranked_extensions = sorted(
        aggregate.ext_files,
        key=lambda key: (-aggregate.ext_bytes[key], -aggregate.ext_files[key], key),
    )
    return {
        "name": entry.name,
        "path": entry.path,
        "type": "dir",
        "state": "pending" if entry.total_files is None else "complete",
        "total_files": aggregate.files_all,
        "total_size": aggregate.size_all,
        "unignored_files": aggregate.files_unignored,
        "unignored_size": aggregate.size_unignored,
        "mtime": aggregate.newest_mtime_ns / 1_000_000_000.0,
        "gitignored": ignored,
        "dominant_ext": ranked_extensions[0] if ranked_extensions else "",
    }


def _all_weight(entry: FsEntry, aggregates: Mapping[str, _SubtreeAggregate]) -> int:
    return aggregates[entry.path].size_all if entry.type == "dir" else entry.size


def _unignored_weight(
    entry: FsEntry,
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
) -> int:
    if entry.type == "dir":
        return aggregates[entry.path].size_unignored
    return 0 if parent_ignored or entry.gitignored else entry.size


def _ordered_children(
    children: Sequence[FsEntry],
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
) -> list[FsEntry]:
    """Interleave all-file and visible-file rankings with stable path ties."""

    all_ranked = sorted(children, key=lambda child: (-_all_weight(child, aggregates), child.path))
    visible_ranked = sorted(
        children,
        key=lambda child: (-_unignored_weight(child, aggregates, parent_ignored), child.path),
    )
    ordered: list[FsEntry] = []
    seen: set[str] = set()
    for index in range(len(children)):
        for ranked in (all_ranked, visible_ranked):
            child = ranked[index]
            if child.path not in seen:
                ordered.append(child)
                seen.add(child.path)
    return ordered


def _emit_bounded_tree(
    root_entry: FsEntry,
    root_ignored: bool,
    children_by_parent: Mapping[str, Sequence[FsEntry]],
    aggregates: Mapping[str, _SubtreeAggregate],
    options: RollupOptions,
) -> dict[str, Any]:
    """Emit directory levels breadth-first under local and global budgets."""

    root_node = _directory_node(root_entry, aggregates[root_entry.path], root_ignored)
    remaining_nodes = max(0, options.max_nodes - 1)
    pending = deque([(root_entry, root_node, 0, root_ignored)])
    while pending:
        entry, node, level, ignored = pending.popleft()
        if level >= options.depth or remaining_nodes <= 0:
            node["children"] = None
            continue

        children = _ordered_children(
            children_by_parent.get(entry.path, ()),
            aggregates,
            ignored,
        )
        emitted: list[dict[str, Any]] = []
        omitted: list[FsEntry] = []
        for child in children:
            if len(emitted) >= options.top or remaining_nodes <= 0:
                omitted.append(child)
                continue
            child_ignored = ignored or child.gitignored
            if child.type == "dir":
                child_node = _directory_node(child, aggregates[child.path], child_ignored)
                emitted.append(child_node)
                pending.append((child, child_node, level + 1, child_ignored))
                remaining_nodes -= 1
            elif child.type == "file":
                emitted.append(_file_node(child, ignored))
                remaining_nodes -= 1
        node["children"] = emitted
        if omitted:
            node["rest"] = _rest_bucket(omitted, aggregates, ignored)
    return root_node


def _rest_bucket(
    children: Sequence[FsEntry],
    aggregates: Mapping[str, _SubtreeAggregate],
    parent_ignored: bool,
) -> dict[str, int]:
    rest = {
        "dirs": 0,
        "files": 0,
        "size": 0,
        "unignored_files": 0,
        "unignored_size": 0,
    }
    for child in children:
        if child.type == "dir":
            aggregate = aggregates[child.path]
            rest["dirs"] += 1
            rest["files"] += aggregate.files_all
            rest["size"] += aggregate.size_all
            rest["unignored_files"] += aggregate.files_unignored
            rest["unignored_size"] += aggregate.size_unignored
        elif child.type == "file":
            rest["files"] += 1
            rest["size"] += child.size
            if not (parent_ignored or child.gitignored):
                rest["unignored_files"] += 1
                rest["unignored_size"] += child.size
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


def _select_extension_keys(
    aggregate: _SubtreeAggregate,
    limit: int,
    rank_mode: RollupRank,
) -> list[str]:
    keys = set(aggregate.ext_files)
    keys.update(aggregate.ext_bytes)
    keys.update(aggregate.ext_files_unignored)
    keys.update(aggregate.ext_bytes_unignored)
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
    all_keys = set(aggregate.ext_files)
    all_keys.update(aggregate.ext_bytes)
    all_keys.update(aggregate.ext_files_unignored)
    all_keys.update(aggregate.ext_bytes_unignored)
    omitted = all_keys - selected
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


__all__ = [
    "ROLLUP_NO_EXT_KEY",
    "ROLLUP_REST_EXT_KEY",
    "RollupOptions",
    "RollupRank",
    "build_rollup",
]
