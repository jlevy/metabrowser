"""Lossless, coherent assembly for bounded directory-style query pages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from metabrowser.inventory_engine.contract import (
    MAX_ASSEMBLED_PAGES,
    MAX_ASSEMBLED_ROWS,
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    FilteredTreeProjection,
    FilteredTreeQuery,
    GroupedTreeProjection,
    GroupedTreeQuery,
    InventoryEntry,
    ReadQuery,
    ReadRequest,
    TreeGroupProjection,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import (
    CoordinatedRead,
    DecoratedInventoryEntry,
    InventoryConsistencyError,
    InventoryCoordinator,
)

type TreePageQuery = DirectoryQuery | FilteredTreeQuery
type TreePageProjection = DirectoryProjection | FilteredTreeProjection

# Bound retries so a continuously moving provider cannot monopolize a request.
_MAX_ASSEMBLY_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class TreePageAssembly:
    """One complete tree projection plus its companion read boundary."""

    first_read: CoordinatedRead
    final_read: CoordinatedRead
    projection: TreePageProjection
    decorated_entries: Mapping[str, DecoratedInventoryEntry]


async def assemble_tree_pages(
    coordinator: InventoryCoordinator,
    *,
    page_query: TreePageQuery,
    companion_queries: tuple[ReadQuery, ...] = (),
    max_pages: int = MAX_ASSEMBLED_PAGES,
    max_assembled_rows: int = MAX_ASSEMBLED_ROWS,
) -> TreePageAssembly:
    """Read every bounded page from one engine version and host boundary."""

    if any(query.query_id == page_query.query_id for query in companion_queries):
        raise ValueError("the page query_id must be unique among companion queries")
    if page_query.after is not None:
        raise ValueError("tree page assembly starts from the first page")
    if max_pages <= 0 or max_assembled_rows <= 0:
        raise ValueError("tree page assembly bounds must be positive")
    expected_projection = (
        FilteredTreeProjection if isinstance(page_query, FilteredTreeQuery) else DirectoryProjection
    )
    last_version_error: VersionUnavailableError | None = None
    for _attempt in range(_MAX_ASSEMBLY_ATTEMPTS):
        after: str | None = None
        pinned: EngineVersion | None = None
        seen_cursors: set[str] = set()
        seen_paths: set[str] = set()
        page_entries: list[InventoryEntry] = []
        decorated: dict[str, DecoratedInventoryEntry] = {}
        first_read: CoordinatedRead | None = None
        filtered_totals: tuple[int, int, int] | None = None
        pages_read = 0
        try:
            async with coordinator.read_session() as session:
                while True:
                    if pages_read == max_pages:
                        raise InventoryConsistencyError(
                            "tree page assembly exceeded its page bound"
                        )
                    current_query = replace(page_query, after=after)
                    queries = (
                        (*companion_queries, current_query)
                        if first_read is None
                        else (current_query,)
                    )
                    read = await session.read(ReadRequest(queries=queries, at_version=pinned))
                    projection = read.result.completed_projection(page_query.query_id)
                    pages_read += 1
                    if not isinstance(projection, expected_projection):
                        raise TypeError("a tree page query returned the wrong projection")
                    if len(projection.entries) > current_query.max_rows:
                        raise InventoryConsistencyError("a tree page exceeded its row bound")
                    if isinstance(projection, FilteredTreeProjection):
                        current_totals = (
                            projection.matching_leaves,
                            projection.matching_files,
                            projection.matching_bytes,
                        )
                        if filtered_totals is None:
                            filtered_totals = current_totals
                        elif current_totals != filtered_totals:
                            raise InventoryConsistencyError(
                                "filtered tree totals changed within one version"
                            )
                    if first_read is None:
                        first_read = read
                        pinned = read.version.engine
                        decorated.update(read.entries)
                    elif read.version.engine != pinned:
                        raise InventoryConsistencyError(
                            "a version-pinned tree page changed engine version"
                        )
                    for entry in projection.entries:
                        if entry.path in seen_paths:
                            raise InventoryConsistencyError(
                                f"tree page assembly returned duplicate path {entry.path!r}"
                            )
                        decorated_entry = read.entries.get(entry.path)
                        if decorated_entry is None:
                            raise InventoryConsistencyError(
                                f"tree page omitted decoration join for {entry.path!r}"
                            )
                        seen_paths.add(entry.path)
                        page_entries.append(entry)
                        decorated.setdefault(entry.path, decorated_entry)
                    if len(page_entries) > max_assembled_rows:
                        raise InventoryConsistencyError("tree page assembly exceeded its row bound")
                    next_page = projection.next_page
                    if next_page is None:
                        complete_projection = replace(
                            projection,
                            entries=tuple(page_entries),
                            next_page=None,
                        )
                        return TreePageAssembly(
                            first_read=first_read,
                            final_read=read,
                            projection=complete_projection,
                            decorated_entries=MappingProxyType(decorated),
                        )
                    if next_page in seen_cursors:
                        raise InventoryConsistencyError("tree page cursor did not advance")
                    seen_cursors.add(next_page)
                    after = next_page
        except VersionUnavailableError as error:
            last_version_error = error
            continue
    if last_version_error is None:
        raise InventoryConsistencyError("tree page assembly exhausted without a version failure")
    raise VersionUnavailableError(
        f"inventory changed during {_MAX_ASSEMBLY_ATTEMPTS} bounded tree page assembly attempts"
    ) from last_version_error


@dataclass(frozen=True, slots=True)
class GroupedTreeAssembly:
    """Every group's complete filtered tree, read at one engine version."""

    first_read: CoordinatedRead
    final_read: CoordinatedRead
    groups: tuple[TreeGroupProjection, ...]


async def assemble_grouped_tree(
    coordinator: InventoryCoordinator,
    *,
    query: GroupedTreeQuery,
    companion_queries: tuple[ReadQuery, ...] = (),
    max_pages: int = MAX_ASSEMBLED_PAGES,
    max_assembled_rows: int = MAX_ASSEMBLED_ROWS,
) -> GroupedTreeAssembly:
    """Read a grouped tree and each group's continuation pages from one engine version.

    The first read answers every group from one pass with the companion queries beside
    it; a group whose rows outran the page bound continues as its own filtered tree,
    pinned to that read's version, so every group is cut from one index version.
    """

    if any(companion.query_id == query.query_id for companion in companion_queries):
        raise ValueError("the grouped query_id must be unique among companion queries")
    if max_pages <= 0 or max_assembled_rows <= 0:
        raise ValueError("grouped tree assembly bounds must be positive")
    last_version_error: VersionUnavailableError | None = None
    for _attempt in range(_MAX_ASSEMBLY_ATTEMPTS):
        try:
            async with coordinator.read_session() as session:
                first_read = await session.read(ReadRequest(queries=(*companion_queries, query)))
                projection = first_read.result.completed_projection(query.query_id)
                if not isinstance(projection, GroupedTreeProjection):
                    raise TypeError("a grouped tree query returned the wrong projection")
                if [group.key for group in projection.groups] != [
                    group.key for group in query.groups
                ]:
                    raise InventoryConsistencyError(
                        "a grouped tree answered other groups than it was asked for"
                    )
                pinned = first_read.version.engine
                final_read = first_read
                pages_read = 1
                assembled_rows = 0
                complete: list[TreeGroupProjection] = []
                for group, answer in zip(query.groups, projection.groups, strict=True):
                    if len(answer.entries) > query.max_rows:
                        raise InventoryConsistencyError("a tree page exceeded its row bound")
                    entries: list[InventoryEntry] = list(answer.entries)
                    seen_paths = {entry.path for entry in entries}
                    if len(seen_paths) != len(entries):
                        raise InventoryConsistencyError(
                            f"grouped tree group {group.key!r} returned a duplicate path"
                        )
                    # Counted on every page, as `assemble_tree_pages` counts, so a group
                    # whose cursors keep advancing stops at the bound, not past it.
                    assembled_rows += len(entries)
                    if assembled_rows > max_assembled_rows:
                        raise InventoryConsistencyError(
                            "grouped tree assembly exceeded its row bound"
                        )
                    seen_cursors: set[str] = set()
                    after = answer.next_page
                    while after is not None:
                        if pages_read == max_pages:
                            raise InventoryConsistencyError(
                                "grouped tree assembly exceeded its page bound"
                            )
                        if after in seen_cursors:
                            raise InventoryConsistencyError("tree page cursor did not advance")
                        seen_cursors.add(after)
                        page_query = query.group_query(group, after=after)
                        read = await session.read(
                            ReadRequest(queries=(page_query,), at_version=pinned)
                        )
                        pages_read += 1
                        page = read.result.completed_projection(page_query.query_id)
                        if not isinstance(page, FilteredTreeProjection):
                            raise TypeError("a tree page query returned the wrong projection")
                        if read.version.engine != pinned:
                            raise InventoryConsistencyError(
                                "a version-pinned tree page changed engine version"
                            )
                        if len(page.entries) > query.max_rows:
                            raise InventoryConsistencyError("a tree page exceeded its row bound")
                        if (
                            page.matching_leaves,
                            page.matching_files,
                            page.matching_bytes,
                        ) != (answer.matching_leaves, answer.matching_files, answer.matching_bytes):
                            raise InventoryConsistencyError(
                                "filtered tree totals changed within one version"
                            )
                        for entry in page.entries:
                            if entry.path in seen_paths:
                                raise InventoryConsistencyError(
                                    f"tree page assembly returned duplicate path {entry.path!r}"
                                )
                            seen_paths.add(entry.path)
                            entries.append(entry)
                        assembled_rows += len(page.entries)
                        if assembled_rows > max_assembled_rows:
                            raise InventoryConsistencyError(
                                "grouped tree assembly exceeded its row bound"
                            )
                        final_read = read
                        after = page.next_page
                    complete.append(replace(answer, entries=tuple(entries), next_page=None))
                return GroupedTreeAssembly(
                    first_read=first_read,
                    final_read=final_read,
                    groups=tuple(complete),
                )
        except VersionUnavailableError as error:
            last_version_error = error
            continue
    if last_version_error is None:
        raise InventoryConsistencyError("grouped tree assembly exhausted without a version failure")
    raise VersionUnavailableError(
        f"inventory changed during {_MAX_ASSEMBLY_ATTEMPTS} grouped tree assembly attempts"
    ) from last_version_error


__all__ = [
    "GroupedTreeAssembly",
    "TreePageAssembly",
    "TreePageProjection",
    "TreePageQuery",
    "assemble_grouped_tree",
    "assemble_tree_pages",
]
