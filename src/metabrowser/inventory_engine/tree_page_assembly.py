"""Lossless, coherent assembly for bounded directory-style query pages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from metabrowser.inventory_engine.contract import (
    DirectoryProjection,
    DirectoryQuery,
    EngineVersion,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryEntry,
    ReadQuery,
    ReadRequest,
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
) -> TreePageAssembly:
    """Read every bounded page from one engine version and host boundary."""

    if any(query.query_id == page_query.query_id for query in companion_queries):
        raise ValueError("the page query_id must be unique among companion queries")
    if page_query.after is not None:
        raise ValueError("tree page assembly starts from the first page")
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
        previous_remaining: int | None = None
        filtered_totals: tuple[int, int, int] | None = None
        try:
            async with coordinator.read_session() as session:
                while True:
                    current_query = replace(page_query, after=after)
                    queries = (
                        (*companion_queries, current_query)
                        if first_read is None
                        else (current_query,)
                    )
                    read = await session.read(ReadRequest(queries=queries, at_version=pinned))
                    projection = read.result.projection(page_query.query_id)
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
                    if previous_remaining is not None and previous_remaining != (
                        len(projection.entries) + projection.remaining_rows
                    ):
                        raise InventoryConsistencyError(
                            "tree pages did not conserve the exact remaining row count"
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
                    next_page = projection.next_page
                    if next_page is None:
                        complete_projection = replace(
                            projection,
                            entries=tuple(page_entries),
                            next_page=None,
                            remaining_rows=0,
                        )
                        return TreePageAssembly(
                            first_read=first_read,
                            final_read=read,
                            projection=complete_projection,
                            decorated_entries=MappingProxyType(decorated),
                        )
                    previous_remaining = projection.remaining_rows
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


__all__ = ["TreePageAssembly", "TreePageProjection", "TreePageQuery", "assemble_tree_pages"]
