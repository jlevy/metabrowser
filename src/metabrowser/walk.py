"""Standalone inventory walk for debugging the tree walker.

The browser's left-nav tree is built by the Python provider's
:func:`metabrowser.walker.walk_tree` plus its verified incremental refresh path.
When the tree shows something
surprising — a phantom subtree, a directory that appears to contain a
copy of itself, a symlink that got followed when it shouldn't have —
the fastest way to see what the walker actually produces is to run it
once, outside the server, and print every entry.

:func:`walk_report` does exactly that: it drives the *same*
``walk_tree`` the server uses, keeps the finalized form of each entry,
annotates symlinks (which the walker records as leaf entries because it
scans with ``follow_symlinks=False``), and renders a deterministic,
diff-friendly text report. The ``--walk`` CLI mode is a thin
wrapper; a golden test pins the report shape against a fixture tree
that includes files, nested dirs, gitignored content, and several
kinds of symlink (in-tree, escaping, ancestor).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from metabrowser.cancellable_thread import run_cancellable_thread
from metabrowser.inventory_engine.contract import (
    DiagnosticsQuery,
    DirectoryQuery,
    EntryProjection,
    EntryQuery,
    FilteredTreeProjection,
    FilteredTreeQuery,
    InventoryEntry,
    InventoryFilter,
    LifecyclePhase,
    ReadQuery,
    ReadRequest,
)
from metabrowser.inventory_engine.runtime import (
    InventoryRuntime,
    default_inventory_config,
)
from metabrowser.inventory_engine.tree_page_assembly import (
    TreePageQuery,
    assemble_tree_pages,
)
from metabrowser.tree import build_inventory_tree_from_entries
from metabrowser.tree_filter import TreeFilter
from metabrowser.walker import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES,
    build_gitignore_check_for,
    walk_tree,
)

# Detail levels, coarse → fine.
Detail = str  # one of: "summary", "dirs", "all"
DETAIL_LEVELS: tuple[str, ...] = ("summary", "dirs", "all")

# Output formats for the machine-readable dump surface.
Format = str  # one of: "text", "json", "yaml"
FORMATS: tuple[str, ...] = ("text", "json", "yaml")


@dataclass(frozen=True)
class WalkRow:
    """One rendered entry plus the symlink's raw target for diagnostics."""

    path: str
    type: str  # "file" | "dir" | "symlink"
    is_symlink: bool
    symlink_target: str  # raw readlink value, "" when not a symlink
    gitignored: bool
    size: int
    total_files: int | None  # dirs only
    total_size: int | None  # dirs only


@dataclass(frozen=True)
class WalkResult:
    root: str
    status: str
    rows: tuple[WalkRow, ...]

    @property
    def file_count(self) -> int:
        return sum(1 for r in self.rows if r.type == "file" and not r.is_symlink)

    @property
    def dir_count(self) -> int:
        return sum(1 for r in self.rows if r.type == "dir")

    @property
    def symlink_count(self) -> int:
        return sum(1 for r in self.rows if r.is_symlink)


async def walk_collect(
    root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> WalkResult:
    """Run the inventory walker once over *root* and collect the
    finalized entry for every path, annotated with symlink info.

    Drives the production :func:`walk_tree` so the report reflects the
    real walker — including its ``follow_symlinks=False`` behavior, the
    reason a symlinked directory shows up as a leaf rather than an
    expanded subtree.
    """

    gi_check = await run_cancellable_thread(
        lambda cancel_event: build_gitignore_check_for(
            root,
            cancel_event=cancel_event,
        )
    )
    # ``walk_tree`` yields dirs twice (placeholder then finalized); keep
    # the last write per path so dir rows carry real aggregates.
    latest: dict[str, InventoryEntry] = {}
    truncated = False
    async for entry in walk_tree(
        root,
        max_depth=max_depth,
        max_files=max_files,
        gitignore_check=gi_check,
    ):
        latest[entry.path] = entry

    rows: list[WalkRow] = []
    for path, entry in latest.items():
        abs_path = root if path == "" else root / path
        try:
            is_symlink = abs_path.is_symlink()
        except OSError:
            is_symlink = False
        target = ""
        if is_symlink:
            try:
                target = os.readlink(abs_path)
            except OSError:
                target = "<unreadable>"
        rows.append(
            WalkRow(
                path=path,
                type=entry.type,
                is_symlink=is_symlink,
                symlink_target=target,
                gitignored=entry.gitignored,
                size=entry.size,
                total_files=entry.total_files,
                total_size=entry.total_size,
            )
        )

    # Deterministic order: by path, with the root ("") first.
    rows.sort(key=lambda r: (r.path != "", r.path))
    if max_files and sum(1 for r in rows if r.type == "file" and not r.is_symlink) >= max_files:
        truncated = True
    return WalkResult(
        root=root.name or str(root),
        status="truncated" if truncated else "done",
        rows=tuple(rows),
    )


def render_report(result: WalkResult, *, detail: Detail = "all") -> str:
    """Render a :class:`WalkResult` as deterministic text.

    ``summary`` — header + counts only.
    ``dirs``    — header + one line per directory (with aggregates).
    ``all``     — header + every entry; symlinks flagged and never
                  shown with descendants (the bug this guards against).
    """

    if detail not in DETAIL_LEVELS:
        raise ValueError(f"unknown detail {detail!r}; expected one of {DETAIL_LEVELS}")

    lines: list[str] = []
    lines.append(f"walk: {result.root}")
    lines.append(f"status: {result.status}")
    lines.append(
        f"counts: files={result.file_count} dirs={result.dir_count} symlinks={result.symlink_count}"
    )
    root_row = next((r for r in result.rows if r.path == ""), None)
    if root_row is not None:
        lines.append(f"totals: total_files={root_row.total_files} total_size={root_row.total_size}")
    if detail == "summary":
        return "\n".join(lines) + "\n"

    lines.append("")
    lines.append("entries:")
    for row in result.rows:
        if detail == "dirs" and row.type != "dir":
            continue
        label = row.path or "."
        lines.append("  " + _render_row(label, row, detail))
    return "\n".join(lines) + "\n"


def _render_row(label: str, row: WalkRow, detail: Detail) -> str:
    if row.is_symlink:
        # A symlink is always a leaf in the walker's output. Showing the
        # target makes "did this get followed?" obvious at a glance.
        tail = f" -> {row.symlink_target}" if detail == "all" else ""
        flags = " [gitignored]" if row.gitignored else ""
        return f"{label} [symlink]{flags}{tail}"
    if row.type == "dir":
        flags = " [gitignored]" if row.gitignored else ""
        return f"{label} [dir] files={row.total_files} size={row.total_size}{flags}"
    flags = " [gitignored]" if row.gitignored else ""
    return f"{label} [file] size={row.size}{flags}"


def walk_report(
    root: Path,
    *,
    detail: Detail = "all",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> str:
    """Synchronous convenience: walk *root* and return the report text."""

    result = asyncio.run(walk_collect(root, max_depth=max_depth, max_files=max_files))
    return render_report(result, detail=detail)


def describe_filter(tree_filter: TreeFilter) -> str:
    """One-line rendering of a filter selection, for the report header."""

    parts: list[str] = []
    if tree_filter.types:
        parts.append(f"types={','.join(tree_filter.types)}")
    if tree_filter.recency_seconds:
        parts.append(f"age<={tree_filter.recency_seconds}s")
    if tree_filter.min_size:
        parts.append(f"size>={tree_filter.min_size}")
    if not tree_filter.include_ignored:
        parts.append("ignored=excluded")
    return " ".join(parts) if parts else "none"


def _render_filtered_rows(nodes: list[dict[str, Any]], detail: Detail) -> list[str]:
    """Flatten a filtered tree into the report's one-line-per-entry shape.

    Flat paths rather than indentation, matching the unfiltered report and
    keeping a golden diff readable when one folder's contents change.
    """

    lines: list[str] = []
    for node in nodes:
        flags = " [gitignored]" if node.get("gitignored") else ""
        if node["type"] == "dir":
            lines.append(
                f"  {node['path']} [dir] "
                f"files={node['total_files']} size={node['total_size']}{flags}"
            )
            children = node.get("children")
            if children:
                lines.extend(_render_filtered_rows(children, detail))
        elif detail != "dirs":
            kind = "symlink" if node["type"] == "symlink" else "file"
            lines.append(f"  {node['path']} [{kind}] size={node.get('size', 0)}{flags}")
    return lines


def filtered_walk_report(
    root: Path,
    *,
    tree_filter: TreeFilter,
    detail: Detail = "all",
    subpath: str = "",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    now_sec: float | None = None,
) -> str:
    """Text report of what a filter selects, from the route's own projection.

    This is the CLI answer to the two questions the nav panel raises and a
    screenshot cannot settle: which folders a filter leaves standing, and what
    each of them rolls up to. Both come from
    :func:`metabrowser.tree.build_filtered_inventory_tree`, the same call the
    ``/api/tree`` route makes, so what this prints is what the panel paints.
    """

    if detail not in DETAIL_LEVELS:
        raise ValueError(f"unknown detail {detail!r}; expected one of {DETAIL_LEVELS}")
    envelope = asyncio.run(
        build_tree_envelope(
            root,
            subpath=subpath,
            max_depth=max_depth,
            max_files=max_files,
            tree_filter=tree_filter,
            now_sec=now_sec,
        )
    )
    matched = envelope["filtered"] or {"files": 0, "size": 0, "entries": 0}
    lines = [
        f"walk: {root.name or root}",
        f"status: {envelope['tally_cache_status']}",
        f"filter: {describe_filter(tree_filter)}",
        f"matched: files={matched['files']} size={matched['size']}",
    ]
    if detail == "summary":
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("entries:")
    lines.extend(_render_filtered_rows(envelope["tree"], detail))
    return "\n".join(lines) + "\n"


# ── Machine-readable dumps (JSON / YAML) ──────────────────────────
#
# Everything the server's nav panel renders comes from two data
# surfaces, both reproducible here without an HTTP server or a browser:
#
#   * all-at-once — the exact ``/api/tree`` envelope (root + nested
#     ``tree`` + ``tally_cache_*``). This is what the SPA fetches to
#     paint the tree. Built through the Python provider and the same
#     provider-neutral tree builder the route uses, so a CLI dump and a live
#     request return byte-identical structure.
#   * streaming — the sequence of semantic inventory records the walker yields
#     (and the server pushes as ``fs.change`` upserts over SSE). One
#     record per line, in walk order.
#
# Both serialize to JSON or YAML, so the whole walk → analyze → build
# pipeline is testable from the CLI and pinnable in golden tests.


def _entry_to_dict(entry: InventoryEntry) -> dict[str, Any]:
    """Project one semantic observation into the established CLI record."""

    entry_type = entry.type.value
    return {
        "path": entry.path,
        "parent": entry.parent,
        "name": entry.name,
        "type": entry_type,
        "ext": entry.ext,
        "kind": entry_type if entry_type != "file" else "file",
        "size": entry.size,
        "mtime_ns": entry.mtime_ns,
        "mtime_hash": "",
        "active": False,
        "views": (),
        "labels": (),
        "total_files": entry.total_files,
        "total_size": entry.total_size,
        "unignored_files": entry.unignored_files,
        "unignored_size": entry.unignored_size,
        "newest_mtime_ns": entry.newest_mtime_ns,
        "gitignored": entry.gitignored,
        "write_token": None,
    }


def _to_yaml(data: Any) -> str:

    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)


async def build_tree_envelope(
    root: Path,
    *,
    subpath: str = "",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    timeout: float = 60.0,
    tree_filter: TreeFilter | None = None,
    now_sec: float | None = None,
) -> dict[str, Any]:
    """Reproduce the exact ``/api/tree`` response envelope for *root*.

    Opens and closes a local inventory runtime with the caller's caps, then
    assembles the response from the same typed projections and pure builder as
    the route. No process-global state or event-loop-bound object survives the
    call.

    An active *tree_filter* takes the route's filtered path, so the pruning
    and the rolled-up folder totals a reader sees in the nav panel are the
    ones this dump shows.
    """

    config = replace(
        default_inventory_config(),
        max_files=max_files,
        max_depth=max_depth,
        watch_mode="off",
    )
    runtime = InventoryRuntime(config=config)
    await runtime.open(root)
    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            diagnostic = await runtime.coordinator.read(
                ReadRequest(queries=(DiagnosticsQuery(query_id="walk-status"),))
            )
            if diagnostic.result.state.phase in {
                LifecyclePhase.READY,
                LifecyclePhase.WATCHING,
                LifecyclePhase.FAILED,
                LifecyclePhase.STOPPED,
            }:
                break
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("inventory walk did not settle before the timeout")
            await asyncio.sleep(min(0.01, remaining))

        active_filter = tree_filter is not None and tree_filter.active
        projection_id = "walk-filtered" if active_filter else "walk-directory"
        companion_queries: tuple[ReadQuery, ...] = (
            EntryQuery(query_id="walk-parent", path=subpath),
        )
        page_query: TreePageQuery | None = None
        as_of_ns = time.time_ns() if now_sec is None else int(now_sec * 1_000_000_000)
        if active_filter:
            assert tree_filter is not None
            extensions = tuple(value for value in tree_filter.types if value.startswith("."))
            filenames = tuple(value for value in tree_filter.types if not value.startswith("."))
            page_query = FilteredTreeQuery(
                query_id=projection_id,
                path=subpath,
                max_depth=max(1, max_depth),
                max_rows=max_files,
                filter=InventoryFilter(
                    extensions=extensions,
                    filenames=filenames,
                    recency_seconds=(
                        float(tree_filter.recency_seconds) if tree_filter.recency_seconds else None
                    ),
                    minimum_size=tree_filter.min_size or None,
                    include_ignored=tree_filter.include_ignored,
                    as_of_ns=as_of_ns if tree_filter.recency_seconds else None,
                ),
            )
        elif max_depth > 0:
            page_query = DirectoryQuery(
                query_id=projection_id,
                path=subpath,
                max_depth=max_depth,
                max_rows=max_files,
            )

        assembly = (
            await assemble_tree_pages(
                runtime.coordinator,
                page_query=page_query,
                companion_queries=companion_queries,
            )
            if page_query is not None
            else None
        )
        read = (
            assembly.first_read
            if assembly is not None
            else await runtime.coordinator.read(ReadRequest(queries=companion_queries))
        )
        parent = read.result.projection("walk-parent")
        if not isinstance(parent, EntryProjection):
            raise TypeError("the walk parent query returned the wrong projection")
        entries = ()
        filtered_projection: FilteredTreeProjection | None = None
        if assembly is not None:
            projection = assembly.projection
            if isinstance(projection, FilteredTreeProjection):
                filtered_projection = projection
            entries = projection.entries
        tree = build_inventory_tree_from_entries(
            entries=entries,
            parent_rel=subpath,
            max_depth=max_depth,
            root_abs=root,
            parent_ignored=bool(parent.entry.gitignored) if parent.entry is not None else False,
        )
        state = assembly.final_read.result.state if assembly is not None else read.result.state
        budget = any(issue.code.value == "resource_budget" for issue in state.issues)
        if budget:
            status = "truncated"
        elif state.phase is LifecyclePhase.FAILED:
            status = "failed"
        elif state.phase is LifecyclePhase.STOPPED:
            status = "idle"
        elif state.coverage.complete:
            status = "done"
        else:
            status = "scanning"
        return {
            "root": str(root),
            "tree": tree,
            "filtered": (
                {
                    "files": filtered_projection.matching_files,
                    "size": filtered_projection.matching_bytes,
                    "entries": filtered_projection.matching_leaves,
                }
                if filtered_projection is not None
                else None
            ),
            "tally_cache_status": status,
            "tally_cache_max_files": config.max_files,
        }
    finally:
        await runtime.close()


def dump_tree(
    root: Path,
    *,
    fmt: Format = "json",
    subpath: str = "",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    tree_filter: TreeFilter | None = None,
    now_sec: float | None = None,
) -> str:
    """All-at-once: the ``/api/tree`` envelope as JSON or YAML text."""

    if fmt not in ("json", "yaml"):
        raise ValueError(f"dump_tree expects json|yaml, got {fmt!r}")
    envelope = asyncio.run(
        build_tree_envelope(
            root,
            subpath=subpath,
            max_depth=max_depth,
            max_files=max_files,
            tree_filter=tree_filter,
            now_sec=now_sec,
        )
    )
    if fmt == "json":
        return json.dumps(envelope, indent=2) + "\n"
    return _to_yaml(envelope)


async def stream_entries(
    root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> AsyncIterator[InventoryEntry]:
    """Yield each walker record in walk order — the streaming surface
    (mirrors the server's ``fs.change`` upserts)."""

    gi_check = await run_cancellable_thread(
        lambda cancel_event: build_gitignore_check_for(
            root,
            cancel_event=cancel_event,
        )
    )
    async for entry in walk_tree(
        root,
        max_depth=max_depth,
        max_files=max_files,
        gitignore_check=gi_check,
    ):
        yield entry


async def stream_dump_lines(
    root: Path,
    *,
    fmt: Format = "json",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> AsyncIterator[str]:
    """Streaming serialization: one record per yielded chunk.

    ``json`` → JSONL (one compact object per line).
    ``yaml`` → a YAML document stream (``---``-delimited).
    """

    if fmt not in ("json", "yaml"):
        raise ValueError(f"stream_dump_lines expects json|yaml, got {fmt!r}")
    async for entry in stream_entries(root, max_depth=max_depth, max_files=max_files):
        record = _entry_to_dict(entry)
        if fmt == "json":
            yield json.dumps(record, separators=(",", ":"))
        else:
            yield "---\n" + _to_yaml(record).rstrip("\n")


def collect_stream(
    root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> list[dict[str, Any]]:
    """All walker records as dicts, in walk order (for tests)."""

    async def _run() -> list[dict[str, Any]]:
        return [
            _entry_to_dict(e)
            async for e in stream_entries(root, max_depth=max_depth, max_files=max_files)
        ]

    return asyncio.run(_run())
