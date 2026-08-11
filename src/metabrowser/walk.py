"""Standalone inventory walk for debugging the tree walker.

The browser's left-nav tree is built by the inventory walker
(:func:`metabrowser.inventory.walk_tree`) plus the watcher's
incremental ``rewalk_subtree`` path. When the tree shows something
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
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from metabrowser.cancellable_thread import run_cancellable_thread
from metabrowser.events import FsEntry
from metabrowser.inventory import (
    DEFAULT_FIRST_RENDER_DEPTH,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES,
    get_instance,
    walk_tree,
)
from metabrowser.tree import _build_inventory_tree, inventory_status
from metabrowser.walker import build_gitignore_check_for

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
    first_render_depth: int = DEFAULT_FIRST_RENDER_DEPTH,
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
    latest: dict[str, FsEntry] = {}
    truncated = False
    async for entry in walk_tree(
        root,
        max_depth=max_depth,
        max_files=max_files,
        first_render_depth=first_render_depth,
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


# ── Machine-readable dumps (JSON / YAML) ──────────────────────────
#
# Everything the server's nav panel renders comes from two data
# surfaces, both reproducible here without an HTTP server or a browser:
#
#   * all-at-once — the exact ``/api/tree`` envelope (root + nested
#     ``tree`` + ``tally_cache_*``). This is what the SPA fetches to
#     paint the tree. Built by driving the real ``InventoryIndex`` and
#     calling the same ``_build_inventory_tree`` the route uses, so a
#     CLI dump and a live request return byte-identical structure.
#   * streaming — the sequence of ``FsEntry`` records the walker yields
#     (and the server pushes as ``fs.change`` upserts over SSE). One
#     record per line, in walk order.
#
# Both serialize to JSON or YAML, so the whole walk → analyze → build
# pipeline is testable from the CLI and pinnable in golden tests.


def _entry_to_dict(entry: FsEntry) -> dict[str, Any]:
    """An ``FsEntry`` as a plain dict — the streaming wire record."""
    return asdict(entry)


def _to_yaml(data: Any) -> str:

    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)


async def build_tree_envelope(
    root: Path,
    *,
    subpath: str = "",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Reproduce the exact ``/api/tree`` response envelope for *root*.

    Drives the process-wide :class:`InventoryIndex` to completion (the
    same object the server uses) and assembles the response with the
    same builder as the route, so this is a faithful stand-in for an
    HTTP ``GET /api/tree?path=<subpath>``.
    """

    inv = get_instance()
    # Fresh, deterministic state with the caller's caps.
    inv.clear()
    # The singleton's done-event may have been created under a previous
    # ``asyncio.run`` loop (e.g. a second dump in the same process).
    # Rebind it to the current loop so ``wait_until_done`` doesn't raise
    # "bound to a different event loop".
    inv._done_event = asyncio.Event()
    inv._max_depth = max_depth
    inv._max_files = max_files
    inv.start(root)
    await inv.wait_until_done(timeout=timeout)
    tree = _build_inventory_tree(parent_rel=subpath, max_depth=max_depth, root_abs=root)
    return {
        "root": str(root),
        "tree": tree,
        "tally_cache_status": inventory_status(),
        "tally_cache_max_files": inv.max_files(),
    }


def dump_tree(
    root: Path,
    *,
    fmt: Format = "json",
    subpath: str = "",
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> str:
    """All-at-once: the ``/api/tree`` envelope as JSON or YAML text."""

    if fmt not in ("json", "yaml"):
        raise ValueError(f"dump_tree expects json|yaml, got {fmt!r}")
    envelope = asyncio.run(
        build_tree_envelope(root, subpath=subpath, max_depth=max_depth, max_files=max_files)
    )
    if fmt == "json":
        return json.dumps(envelope, indent=2) + "\n"
    return _to_yaml(envelope)


async def stream_entries(
    root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    first_render_depth: int = DEFAULT_FIRST_RENDER_DEPTH,
) -> AsyncIterator[FsEntry]:
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
        first_render_depth=first_render_depth,
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
