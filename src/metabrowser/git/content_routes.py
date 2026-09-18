"""GitPath adapters for ``/api/tree``, ``/api/file``, ``/raw``, KPress, rollup, catalog, and index status.

These honor a pinned ``GitRevisionSubject`` without a checkout, index, or
invented filesystem fact. ``/view/`` accepts a GitPath wire, optionally plus
a host container inner, and refuses a filesystem spelling. ``/api/tree`` keeps
Git-native ``entries`` and also projects a SPA ``tree`` array so navigation
can paint; ``depth`` nests SPA children the way filesystem listings do (default 2)
and emits a lazy sentinel past the cap. Gitlinks are files, and listings omit mtime
and ignore. Blob and symlink entries carry ``cat-file`` sizes; trees and
gitlinks stay unsized, so ``min_size`` can filter without ``ls-tree -l``.
Directory ``total_files`` / ``total_size`` come from recursive ``ls-tree -r``
plus ``cat-file`` info; a truncated listing or missing blob omits the
incomplete dimension. ``/api/tree`` also carries whole-tree ``extensions``,
``canonical_extensions``, ``type_families``, and ``type_presets`` rows plus
``tally_cache_status`` from that index so the type filter and truncation
banner do not wait on a filesystem walker. A complete blob-size tally also
fills the whole-tree ``summary`` (``files``, ``size``, ignored 0/0) so the
nav header has honest counts; incomplete sizes omit ``summary`` rather than
inventing 0. ``types`` and ``min_size`` keep ancestor trees of matching blobs
and emit subtree ``filtered`` totals; empty filter dirs are omitted. File nav
nodes include ``ext`` from the same bounded compound-tail helper as
filesystem inventory, so type filters match ``bundle.min.js`` as ``.min.js``
and do not treat a basename ending in ``md`` as ``.md``.
``logical_ext`` is only the inner extension of a compressed name.
``include_ignored=0`` is a no-op because ignore is absent.
The SPA hides Modified within because recency still has no honest mtime.
A Git tree ``/api/file`` envelope is SPA ``folder`` chrome (``git_kind`` stays
``tree``) with no invented mtime or ignore. Omitted mtime leaves
SPA age chrome empty rather than pending. A direct-child README blob sets
``readme_path`` to its GitPath wire and mounts the Overview view. A complete
blob-size tally also mounts treemap and File Overview; ``/api/rollup`` answers
from the same index and omits mtime. A missing blob size 404s rollup rather
than emitting a partial sum. ``/api/catalog`` lists those blob names as
Quick File rows (``p`` GitPath wire, ``e`` display suffix, ``n`` display
basename) and is complete at once; a truncated index is an empty truncated
snapshot rather than a partial list. ``/api/index/progress``, ``/api/index/meta``,
and ``/api/capabilities`` report that same complete-at-once index without a
watcher or invented mtime. SPA path chrome and copy-path
decode GitPath wires to display names; navigation identities stay wires. KPress ``source_path``
is the GitPath wire so Markdown rewrite cannot emit a filesystem spelling.
Patch-file container inners use a GitPath prefix plus a host inner path. Blob
kinds use extension, basename, sniffed adapter, and JSON/YAML/frontmatter
mappings parsed from blob bytes. ``path_glob`` stays filesystem-only. Serving
acquired Git from the CLI remains a later bead.
"""

from __future__ import annotations

import asyncio
import mimetypes
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from metabrowser import kpress_adapter
from metabrowser.content_sniff import ContentClass, classify_prefix
from metabrowser.file_extensions import BROWSER_IMAGE_EXTS, BROWSER_TEXT_EXTS
from metabrowser.file_kinds import classify_by_ext
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.folder_discovery import choose_readme_name
from metabrowser.fs_paths import derive_ext
from metabrowser.git.tree_source import (
    GitBlobIndex,
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    GitTreeEntry,
    GitTreeTally,
)
from metabrowser.gz_io import ArtifactPath
from metabrowser.inventory_engine.contract import ascii_casefold
from metabrowser.inventory_rollup import RollupOptions, build_rollup, group_rollup_children
from metabrowser.plugin_api import MAX_CONTAINER_INNER_DEPTH
from metabrowser.settings import (
    FOLDER_DISCOVERY_MAX_ENTRIES,
    INVENTORY_MAX_FILES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)
from metabrowser.tree import _tree_depth_from_query
from metabrowser.tree_filter import TreeFilter
from metabrowser.view_routes import decode_view_logical_path

_NOT_FOUND = {"error": "Not found"}
_PATCH_EXTS = (".patch", ".diff")
# Same cap as ``PythonInventoryStore.navigation_tallies``.
_GIT_FILTER_TALLY_LIMIT = 200


def _git_path_from_query(request: Request) -> GitPath:
    return GitPath.from_wire(request.query_params.get("path", ""))


def decode_git_view_path(raw_path: bytes) -> str | None:
    """Decode ``/view/`` as a GitPath wire, optionally plus a container inner.

    Filesystem spellings are not GitPath identities. Missing Git objects stay
    valid shell destinations, matching missing files under a served root.
    """

    logical = decode_view_logical_path(raw_path)
    if logical is None:
        return None
    try:
        split_git_container_wire(logical)
    except GitPathError:
        return None
    return logical


def split_git_container_wire(wire: str) -> tuple[GitPath, str]:
    """Split a request identity into a GitPath prefix and a container inner path.

    ``g1-`` tokens are the Git tree address. Anything after the last
    contiguous ``g1-`` prefix is a virtual inner path owned by a container
    blob, not another tree segment.
    """

    if wire == "":
        return GitPath.root(), ""
    parts = wire.split("/")
    cut = 0
    while cut < len(parts) and parts[cut].startswith("g1-"):
        cut += 1
    if cut == 0:
        raise GitPathError("GitPath wire tokens must use the g1- role prefix")
    return GitPath.from_wire("/".join(parts[:cut])), "/".join(parts[cut:])


def _listing_entry(entry: GitTreeEntry) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": entry.path.to_wire(),
        "display": entry.path.display(),
        "mode": entry.mode,
        "kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }
    if entry.size is not None:
        payload["size"] = entry.size
    return payload


def _nav_tree_type(entry: GitTreeEntry) -> Literal["dir", "file", "symlink"]:
    if entry.is_tree:
        return "dir"
    if entry.is_symlink:
        return "symlink"
    return "file"


def _join_git_prefix(prefix: bytes, name: bytes) -> bytes:
    return name if not prefix else prefix + b"/" + name


def _nav_tree_node(
    entry: GitTreeEntry,
    *,
    tally: GitTreeTally | None = None,
    children: list[dict[str, Any]] | None = None,
    loaded: bool = False,
) -> dict[str, Any]:
    """SPA nav node. Omit inventory aggregates rather than invent zeros."""

    node: dict[str, Any] = {
        "name": _display_basename(entry.path),
        "path": entry.path.to_wire(),
        "type": _nav_tree_type(entry),
    }
    if entry.is_tree:
        if loaded:
            nested = children if children is not None else []
            node["children"] = nested
            node["has_children"] = bool(nested)
        else:
            node["children"] = None
            node["has_children"] = True
        if tally is not None:
            node["total_files"] = tally.total_files
            if tally.total_size is not None:
                node["total_size"] = tally.total_size
    else:
        if not entry.is_symlink and not entry.is_gitlink:
            name = _display_basename(entry.path)
            ext = derive_ext(name)
            if ext:
                node["ext"] = ext
            artifact = ArtifactPath(Path(name))
            if artifact.is_compressed:
                inner = artifact.logical_ext
                if inner:
                    node["logical_ext"] = inner
                node["compressed"] = True
                compression = artifact.compression
                if compression is not None:
                    node["compression"] = compression
    if entry.size is not None:
        node["size"] = entry.size
    return node


def _identity_fields(entry: GitTreeEntry) -> dict[str, Any]:
    return {
        "path": entry.path.to_wire(),
        "display": entry.path.display(),
        "mode": entry.mode,
        "git_kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }


def _display_basename(path: GitPath) -> str:
    if not path.segments:
        return ""
    return path.segments[-1].decode("utf-8", "replace")


def _logical_ext(path: GitPath) -> str:
    return derive_ext(_display_basename(path))


def _semantic_extension_tokens(types: tuple[str, ...]) -> frozenset[str]:
    registry = load_file_type_registry()
    return frozenset(
        token
        for token in types
        if token.startswith(".") and registry.classify("", token).family_id is not None
    )


def _plugin_kind_for_git_path(
    path: GitPath,
    *,
    adapter: str | None = None,
    json_top_level: dict[str, Any] | None = None,
    yaml_top_level: dict[str, Any] | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> str | None:
    from metabrowser.plugin_loader.classify import classify_identity
    from metabrowser.server import _PLUGIN_KIND_RULES

    return classify_identity(
        _PLUGIN_KIND_RULES,
        ext=_logical_ext(path),
        basename=_display_basename(path),
        adapter=adapter,
        json_top_level=json_top_level,
        yaml_top_level=yaml_top_level,
        frontmatter=frontmatter,
    )


def _git_blob_content_predicates(
    ext: str, body: bytes
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    from metabrowser.plugin_loader.classify import (
        frontmatter_from_bytes,
        json_mapping_from_bytes,
        yaml_mapping_from_bytes,
    )

    json_top = json_mapping_from_bytes(body) if ext == ".json" else None
    yaml_top = yaml_mapping_from_bytes(body) if ext in {".yaml", ".yml"} else None
    frontmatter = frontmatter_from_bytes(body) if ext == ".md" else None
    return json_top, yaml_top, frontmatter


def _views_for_kind(kind: str) -> list[dict[str, Any]]:
    # Plugin kinds such as diff live in manifests, not VIEW_REGISTRY.
    from metabrowser.server import _views_for_kind as merged_views_for_kind

    return merged_views_for_kind(kind)


def _passes_min_size(entry: GitTreeEntry, floor: int) -> bool:
    """Unsized blobs and gitlinks drop. Trees are decided by descendants."""

    if entry.is_tree:
        return True
    return entry.size is not None and entry.size >= floor


def _matches_types(
    path: GitPath,
    types: tuple[str, ...],
    *,
    semantic: frozenset[str] | None = None,
) -> bool:
    """Match like the SPA type filter: dotted tokens are logical extensions."""

    name = ascii_casefold(_display_basename(path))
    ext = _logical_ext(path)
    semantic_tokens = semantic if semantic is not None else _semantic_extension_tokens(types)
    for token in types:
        folded = ascii_casefold(token)
        if folded.startswith("."):
            if ext and (ext == folded or (folded in semantic_tokens and ext.endswith(folded))):
                return True
        elif name == folded:
            return True
    return False


def _blob_matches_tree_filter(
    path: GitPath,
    oid: str,
    *,
    tree_filter: TreeFilter,
    sizes: Mapping[str, int],
    semantic: frozenset[str] | None = None,
) -> bool:
    if tree_filter.types and not _matches_types(path, tree_filter.types, semantic=semantic):
        return False
    if tree_filter.min_size:
        size = sizes.get(oid)
        if size is None or size < tree_filter.min_size:
            return False
    return True


def _git_filter_active(tree_filter: TreeFilter) -> bool:
    return bool(tree_filter.types or tree_filter.min_size)


def _git_filtered_tally(
    index: GitBlobIndex | None,
    tree_filter: TreeFilter,
    *,
    prefix: bytes = b"",
    semantic: frozenset[str] | None = None,
) -> GitTreeTally | None:
    """Matching descendant blobs under ``prefix``. None when the index is absent."""

    if index is None:
        return None
    files = 0
    size = 0
    size_known = True
    needle = prefix + b"/" if prefix else b""
    semantic_tokens = (
        semantic if semantic is not None else _semantic_extension_tokens(tree_filter.types)
    )
    for name, oid in index.blobs:
        if prefix and name != prefix and not name.startswith(needle):
            continue
        if not _blob_matches_tree_filter(
            _git_path_from_relative(name),
            oid,
            tree_filter=tree_filter,
            sizes=index.sizes,
            semantic=semantic_tokens,
        ):
            continue
        files += 1
        blob_size = index.sizes.get(oid)
        if blob_size is None:
            size_known = False
        else:
            size += blob_size
    return GitTreeTally(files, size if size_known else None)


def _git_entry_visible(
    entry: GitTreeEntry,
    tree_filter: TreeFilter,
    index: GitBlobIndex | None,
    *,
    index_prefix: bytes = b"",
    semantic: frozenset[str] | None = None,
) -> bool:
    """Keep trees that have a matching descendant; drop empty filter dirs."""

    if not _git_filter_active(tree_filter):
        return True
    if entry.is_tree:
        tally = _git_filtered_tally(
            index,
            tree_filter,
            prefix=_join_git_prefix(index_prefix, entry.path.segments[-1]),
            semantic=semantic,
        )
        if tally is None:
            return True
        return tally.total_files > 0
    if tree_filter.types and not _matches_types(entry.path, tree_filter.types, semantic=semantic):
        return False
    if tree_filter.min_size:
        return _passes_min_size(entry, tree_filter.min_size)
    return True


def _git_dir_tally(
    index: GitBlobIndex | None,
    tree_filter: TreeFilter,
    *,
    prefix: bytes,
    semantic: frozenset[str] | None = None,
) -> GitTreeTally | None:
    if index is None:
        return None
    if _git_filter_active(tree_filter):
        return _git_filtered_tally(index, tree_filter, prefix=prefix, semantic=semantic)
    return index.tally(prefix)


def _git_visible_entries(
    entries: tuple[GitTreeEntry, ...],
    tree_filter: TreeFilter,
    index: GitBlobIndex | None,
    *,
    index_prefix: bytes,
    semantic: frozenset[str] | None,
) -> tuple[GitTreeEntry, ...]:
    if not _git_filter_active(tree_filter):
        return entries
    return tuple(
        entry
        for entry in entries
        if _git_entry_visible(
            entry, tree_filter, index, index_prefix=index_prefix, semantic=semantic
        )
    )


async def _git_nav_tree(
    subject: GitRevisionSubject,
    entries: tuple[GitTreeEntry, ...],
    *,
    remaining_depth: int,
    tree_filter: TreeFilter,
    index: GitBlobIndex | None,
    index_prefix: bytes,
    semantic: frozenset[str] | None,
) -> list[dict[str, Any]]:
    """SPA ``tree`` nodes. Nest while ``remaining_depth`` allows; else a lazy sentinel."""

    if remaining_depth <= 0:
        return []
    nodes: list[dict[str, Any]] = []
    nest = remaining_depth > 1
    for entry in entries:
        prefix = _join_git_prefix(index_prefix, entry.path.segments[-1]) if entry.is_tree else b""
        tally = (
            _git_dir_tally(index, tree_filter, prefix=prefix, semantic=semantic)
            if entry.is_tree
            else None
        )
        if entry.is_tree and nest:
            try:
                nested = await subject.tree_source.list_tree(entry.path)
            except GitObjectUnavailableError:
                nodes.append(_nav_tree_node(entry, tally=tally))
                continue
            nested = _git_visible_entries(
                nested, tree_filter, index, index_prefix=prefix, semantic=semantic
            )
            children = await _git_nav_tree(
                subject,
                nested,
                remaining_depth=remaining_depth - 1,
                tree_filter=tree_filter,
                index=index,
                index_prefix=prefix,
                semantic=semantic,
            )
            nodes.append(_nav_tree_node(entry, tally=tally, children=children, loaded=True))
            continue
        nodes.append(_nav_tree_node(entry, tally=tally))
    return nodes


def _git_tree_filtered(
    index: GitBlobIndex | None,
    tree_filter: TreeFilter,
    *,
    semantic: frozenset[str] | None = None,
) -> dict[str, int] | None:
    """Subtree filter totals. Omit when sizes are incomplete."""

    if not _git_filter_active(tree_filter):
        return None
    tally = _git_filtered_tally(index, tree_filter, semantic=semantic)
    if tally is None or tally.total_size is None:
        return None
    return {
        "files": tally.total_files,
        "size": tally.total_size,
        "entries": tally.total_files,
    }


def _query_int(request: Request, name: str, default: int) -> int:
    raw = request.query_params.get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _blob_too_large_payload(exc: GitBlobTooLargeError) -> dict[str, Any]:
    return {
        "error": str(exc),
        "code": exc.code,
        "oid": exc.oid,
        "size": exc.size,
        "max_bytes": exc.max_bytes,
    }


def _object_unavailable_payload(exc: GitObjectUnavailableError) -> dict[str, Any]:
    return {"error": str(exc), "code": exc.code, "oid": exc.oid}


def _json(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers={"cache-control": "no-store"})


@dataclass(frozen=True, slots=True)
class _GitRollupEntry:
    path: str
    parent: str
    name: str
    type: str
    ext: str
    size: int
    mtime_ns: int
    gitignored: bool
    total_files: int | None


def _dir_rollup_entry(path: GitPath, parent: GitPath, *, total_files: int) -> _GitRollupEntry:
    wire = path.to_wire()
    return _GitRollupEntry(
        path=wire,
        parent=parent.to_wire() if path.segments else wire,
        name=_display_basename(path),
        type="dir",
        ext="",
        size=0,
        mtime_ns=0,
        gitignored=False,
        total_files=total_files,
    )


def _rollup_entries_from_index(
    index: GitBlobIndex, tree_path: GitPath
) -> dict[str, _GitRollupEntry] | None:
    """Map one blob index to rollup entries. ``None`` when any blob size is missing."""

    root_tally = index.tally()
    if root_tally.total_size is None:
        return None
    root_wire = tree_path.to_wire()
    entries: dict[str, _GitRollupEntry] = {
        root_wire: _GitRollupEntry(
            path=root_wire,
            parent=root_wire,
            name=_display_basename(tree_path),
            type="dir",
            ext="",
            size=0,
            mtime_ns=0,
            gitignored=False,
            total_files=root_tally.total_files,
        )
    }
    for rel, oid in index.blobs:
        size = index.sizes.get(oid)
        if size is None:
            return None
        parts = rel.split(b"/")
        cursor = tree_path
        parent_wire = root_wire
        for index_part, segment in enumerate(parts):
            cursor = cursor.child(segment)
            wire = cursor.to_wire()
            last = index_part == len(parts) - 1
            if last:
                display = segment.decode("utf-8", "replace")
                entries[wire] = _GitRollupEntry(
                    path=wire,
                    parent=parent_wire,
                    name=display,
                    type="file",
                    ext=derive_ext(display),
                    size=size,
                    mtime_ns=0,
                    gitignored=False,
                    total_files=None,
                )
            elif wire not in entries:
                rel_prefix = b"/".join(parts[: index_part + 1])
                entries[wire] = _GitRollupEntry(
                    path=wire,
                    parent=parent_wire,
                    name=segment.decode("utf-8", "replace"),
                    type="dir",
                    ext="",
                    size=0,
                    mtime_ns=0,
                    gitignored=False,
                    total_files=index.tally(rel_prefix).total_files,
                )
            parent_wire = wire
    return entries


def _missing_blob_oid(index: GitBlobIndex) -> str:
    for _name, oid in index.blobs:
        if oid not in index.sizes:
            return oid
    raise RuntimeError("blob index reported incomplete sizes without a missing oid")


async def git_revision_rollup(
    request: Request,
    subject: GitRevisionSubject,
    options: RollupOptions,
) -> JSONResponse:
    """Bounded directory rollup from recursive blob names and sizes. No mtime."""

    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        located = await subject.tree_source.resolve_path(path)
        if located is None or not located.is_tree:
            return _json(_NOT_FOUND, status_code=404)
        index = await subject.tree_source.blob_index(path)
        children = await subject.tree_source.list_tree(path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    wire = path.to_wire()
    if index is None:
        return _json(
            {
                "subject": "git_revision",
                "root": "",
                "path": wire,
                "node": None,
                "ext_tallies": [],
                "file_type_breakdown": None,
                "index_status": "truncated",
                "indexed_files": 0,
                "max_files": INVENTORY_MAX_FILES,
                "truncated": True,
            }
        )
    entries = _rollup_entries_from_index(index, path)
    if entries is None:
        missing_oid = _missing_blob_oid(index)
        return _json(
            {
                "error": f"object_unavailable: {missing_oid}",
                "code": "object_unavailable",
                "oid": missing_oid,
            },
            status_code=404,
        )
    for child in children:
        if not child.is_tree:
            continue
        child_wire = child.path.to_wire()
        if child_wire in entries:
            continue
        child_tally = index.tally(child.path.segments[-1])
        entries[child_wire] = _dir_rollup_entry(
            child.path, path, total_files=child_tally.total_files
        )
    built = build_rollup(
        entries,
        group_rollup_children(entries),
        wire,
        options,
        False,
    )
    if built is None:
        return _json(_NOT_FOUND, status_code=404)
    node = built["node"]
    return _json(
        {
            "subject": "git_revision",
            "root": "",
            "path": wire,
            "node": node,
            "ext_tallies": built["ext_tallies"],
            "file_type_breakdown": built["file_type_breakdown"],
            "index_status": "complete",
            "indexed_files": node["total_files"],
            "max_files": INVENTORY_MAX_FILES,
            "truncated": False,
        }
    )


async def git_revision_catalog(request: Request, subject: GitRevisionSubject) -> JSONResponse:
    """One-shot Quick File catalog from recursive blob names. No watcher."""

    del request
    try:
        index = await subject.tree_source.blob_index()
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    if index is None:
        return _json({"complete": True, "truncated": True, "revision": 1, "files": []})
    files: list[dict[str, str]] = []
    for rel, _oid in index.blobs:
        path = _git_path_from_relative(rel)
        files.append({"p": path.to_wire(), "e": _logical_ext(path), "n": _display_basename(path)})
    return _json({"complete": True, "truncated": False, "revision": 1, "files": files})


def _git_path_from_relative(name: bytes) -> GitPath:
    return GitPath.from_segments(*name.split(b"/"))


_GIT_INDEX_PROVIDER = "git"
_GIT_INDEX_CONTRACT = "git-revision"


@dataclass(frozen=True, slots=True)
class _GitIndexFacts:
    truncated: bool
    indexed_files: int
    indexed_dirs: int
    suffixes: tuple[tuple[str, int], ...]


def _git_extension_counts(index: GitBlobIndex) -> Counter[str]:
    counts: Counter[str] = Counter()
    for rel, _oid in index.blobs:
        ext = _logical_ext(_git_path_from_relative(rel))
        if ext:
            counts[ext] += 1
    return counts


def _ranked_tally_rows(counts: Mapping[str, int]) -> list[list[object]]:
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [[key, count, 0] for key, count in ranked[:_GIT_FILTER_TALLY_LIMIT]]


def _git_tree_summary(index: GitBlobIndex | None) -> dict[str, int] | None:
    """Whole-tree tracked/ignored split. Omit when sizes are incomplete."""

    if index is None:
        return None
    tally = index.tally()
    if tally.total_size is None:
        return None
    return {
        "files": tally.total_files,
        "size": tally.total_size,
        "ignored_files": 0,
        "ignored_size": 0,
    }


def _git_tree_index_chrome(index: GitBlobIndex | None) -> dict[str, Any]:
    """Whole-tree filter tallies and summary. Ignore is absent, so ignored is 0."""

    truncated = index is None
    preset_rows = [[preset["id"], 0, 0] for preset in FILTER_TYPE_PRESETS]
    payload: dict[str, Any] = {
        "tally_cache_status": "truncated" if truncated else "done",
        "tally_cache_max_files": INVENTORY_MAX_FILES,
    }
    summary = _git_tree_summary(index)
    if summary is not None:
        payload["summary"] = summary
    payload["extensions"] = []
    payload["canonical_extensions"] = []
    payload["type_families"] = []
    payload["type_presets"] = preset_rows
    if index is None:
        return payload
    registry = load_file_type_registry()
    extension_counts: Counter[str] = Counter()
    canonical_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    preset_counts: Counter[str] = Counter({preset["id"]: 0 for preset in FILTER_TYPE_PRESETS})
    normalized_presets: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for preset in FILTER_TYPE_PRESETS:
        extensions: set[str] = set()
        names: set[str] = set()
        for value in preset["values"]:
            normalized = ascii_casefold(value)
            (extensions if normalized.startswith(".") else names).add(normalized)
        normalized_presets.append((preset["id"], frozenset(extensions), frozenset(names)))
    for rel, _oid in index.blobs:
        path = _git_path_from_relative(rel)
        ext = _logical_ext(path)
        name = ascii_casefold(_display_basename(path))
        classification = registry.classify(name, ext)
        if ext:
            extension_counts[ext] += 1
            canonical_counts[classification.canonical_extension or ext] += 1
            if classification.family_id is not None:
                family_counts[classification.family_id] += 1
        semantic_category = classification.group_id
        for preset_id, preset_extensions, preset_names in normalized_presets:
            if preset_id == semantic_category or ext in preset_extensions or name in preset_names:
                preset_counts[preset_id] += 1
    payload["extensions"] = _ranked_tally_rows(extension_counts)
    payload["canonical_extensions"] = _ranked_tally_rows(canonical_counts)
    payload["type_families"] = [
        [family_id, count, 0]
        for family_id, count in sorted(
            family_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    payload["type_presets"] = [
        [preset["id"], preset_counts[preset["id"]], 0] for preset in FILTER_TYPE_PRESETS
    ]
    return payload


async def _git_index_facts(subject: GitRevisionSubject) -> _GitIndexFacts:
    index = await subject.tree_source.blob_index()
    if index is None:
        return _GitIndexFacts(True, 0, 0, ())
    dirs: set[bytes] = set()
    for rel, _oid in index.blobs:
        parts = rel.split(b"/")
        for depth in range(len(parts) - 1):
            dirs.add(b"/".join(parts[: depth + 1]))
    suffixes = tuple(
        sorted(_git_extension_counts(index).items(), key=lambda item: (-item[1], item[0]))
    )
    return _GitIndexFacts(False, len(index.blobs), len(dirs), suffixes)


def _git_index_common(facts: _GitIndexFacts) -> dict[str, Any]:
    return {
        "status": "truncated" if facts.truncated else "done",
        "indexed_files": facts.indexed_files,
        "max_files": INVENTORY_MAX_FILES,
        "truncated": facts.truncated,
        "complete": True,
        "provider": _GIT_INDEX_PROVIDER,
        "contract": _GIT_INDEX_CONTRACT,
    }


async def git_revision_index_progress(subject: GitRevisionSubject) -> JSONResponse:
    """Terminal crawl footer for a pin. There is no walker."""

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json({**_git_index_common(facts), "active": False})


async def git_revision_index_meta(subject: GitRevisionSubject) -> JSONResponse:
    """Index summary from blob names. No mtime or watcher facts."""

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json(
        {
            **_git_index_common(facts),
            "indexed_dirs": facts.indexed_dirs,
            "suffixes": [{"ext": ext, "count": count} for ext, count in facts.suffixes],
        }
    )


async def git_revision_capabilities(subject: GitRevisionSubject) -> JSONResponse:
    """Observation surface for a pin: complete, no watcher, events off."""

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json(
        {
            "backends": [
                {
                    "prefix": ".",
                    "mode": "none",
                    "reason": "git-revision-immutable",
                    "state": "idle",
                }
            ],
            "index": {
                "complete": True,
                "indexed_files": facts.indexed_files,
                "max_files": INVENTORY_MAX_FILES,
                "truncated": facts.truncated,
                "provider": _GIT_INDEX_PROVIDER,
                "contract": _GIT_INDEX_CONTRACT,
            },
            "events": {"stream": "off", "reason": "git-revision-no-watcher"},
        }
    )


async def git_revision_tree(
    request: Request,
    subject: GitRevisionSubject,
    tree_filter: TreeFilter,
) -> JSONResponse:
    """List one Git tree. ``entries`` are Git facts; ``tree`` is the SPA nav."""

    remaining_depth = _tree_depth_from_query(request.query_params.get("depth", ""))
    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        located = await subject.tree_source.resolve_path(path)
        if located is None or not located.is_tree:
            return _json(_NOT_FOUND, status_code=404)
        index = await subject.tree_source.blob_index(path)
        semantic = _semantic_extension_tokens(tree_filter.types)
        if remaining_depth <= 0:
            entries: tuple[GitTreeEntry, ...] = ()
            tree_nodes: list[dict[str, Any]] = []
        else:
            entries = await subject.tree_source.list_tree(path)
            entries = _git_visible_entries(
                entries, tree_filter, index, index_prefix=b"", semantic=semantic
            )
            tree_nodes = await _git_nav_tree(
                subject,
                entries,
                remaining_depth=remaining_depth,
                tree_filter=tree_filter,
                index=index,
                index_prefix=b"",
                semantic=semantic,
            )
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    assert located is not None
    root_index = index if not path.segments else await subject.tree_source.blob_index()
    filtered = _git_tree_filtered(index, tree_filter, semantic=semantic)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "path": path.to_wire(),
        "display": path.display(),
        "oid": located.oid,
        "kind": "tree",
        "entries": [_listing_entry(entry) for entry in entries],
        "tree": tree_nodes,
        **_git_tree_index_chrome(root_index),
    }
    if filtered is not None:
        payload["filtered"] = filtered
    return _json(payload)


def _git_readme_child(
    children: tuple[GitTreeEntry, ...],
) -> tuple[GitTreeEntry | None, bool]:
    """Pick a direct-child README blob. Symlinks and gitlinks are not READMEs."""

    truncated = len(children) > FOLDER_DISCOVERY_MAX_ENTRIES
    scanned = children[:FOLDER_DISCOVERY_MAX_ENTRIES]
    by_name: dict[str, GitTreeEntry] = {}
    for child in scanned:
        if child.is_symlink or child.is_gitlink or not child.is_blob:
            continue
        name = _display_basename(child.path)
        if name.casefold() != "readme.md":
            continue
        by_name[name] = child
    chosen = choose_readme_name(list(by_name))
    return by_name.get(chosen), truncated


def _folder_views(*, readme: bool, tally: GitTreeTally | None) -> list[dict[str, Any]]:
    """Overview when a README or complete tally exists; treemap needs sizes."""

    complete = tally is not None and tally.total_size is not None
    wanted: set[str] = set()
    if readme or complete:
        wanted.add("overview")
    if complete:
        wanted.add("treemap")
    return [view for view in _views_for_kind("folder") if view.get("id") in wanted]


def _dir_tally_payload(tally: GitTreeTally | None) -> dict[str, Any]:
    if tally is None:
        return {}
    payload: dict[str, Any] = {"total_files": tally.total_files}
    if tally.total_size is not None:
        payload["total_size"] = tally.total_size
    return {"dir": payload}


def _tree_file_payload(
    entry: GitTreeEntry,
    children: tuple[GitTreeEntry, ...],
    *,
    tally: GitTreeTally | None,
) -> dict[str, Any]:
    """SPA folder chrome. Keep Git ``tree`` identity; omit mtime and ignore."""

    readme, truncated = _git_readme_child(children)
    return {
        "subject": "git_revision",
        "type": "folder",
        "kind": "folder",
        "name": _display_basename(entry.path),
        "views": _folder_views(readme=readme is not None, tally=tally),
        "readme_path": readme.path.to_wire() if readme else "",
        "readme_search_truncated": truncated,
        **_dir_tally_payload(tally),
        **_identity_fields(entry),
    }


def _gitlink_file_payload(entry: GitTreeEntry) -> dict[str, Any]:
    return {
        "subject": "git_revision",
        "type": "gitlink",
        "kind": "commit",
        "views": [],
        **_identity_fields(entry),
    }


def _blob_file_payload(entry: GitTreeEntry, body: bytes, request: Request) -> dict[str, Any]:
    ext = _logical_ext(entry.path)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "size": len(body),
        **_identity_fields(entry),
    }
    if entry.is_symlink:
        payload.update(
            {
                "type": "symlink",
                "kind": "symlink",
                "views": [],
                "content": body.decode("utf-8", "replace"),
                "content_offset": 0,
                "content_bytes": len(body),
                "content_truncated": False,
            }
        )
        return payload
    content_class = classify_prefix(body)
    if ext in BROWSER_IMAGE_EXTS:
        payload.update(
            {
                "type": "image",
                "kind": "image",
                "views": _views_for_kind("image"),
            }
        )
        return payload
    if content_class is ContentClass.BINARY or (
        ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT
    ):
        payload.update(
            {
                "type": "binary",
                "kind": "binary",
                "views": _views_for_kind("binary"),
            }
        )
        return payload
    if ext == ".jsonl":
        from metabrowser.jsonl_view import parse_jsonl_bytes

        parsed = parse_jsonl_bytes(body)
        adapter = parsed.get("summary", {}).get("adapter")
        adapter_name = adapter if isinstance(adapter, str) else None
        kind = _plugin_kind_for_git_path(entry.path, adapter=adapter_name) or classify_by_ext(
            ext, adapter_name
        )
        payload.update(
            {
                "type": "jsonl",
                "kind": kind,
                "views": _views_for_kind(kind),
                **parsed,
            }
        )
        return payload
    offset = max(0, _query_int(request, "offset", 0))
    limit = max(
        1,
        min(_query_int(request, "limit", TEXT_PREVIEW_CHUNK_BYTES), TEXT_PREVIEW_REQUEST_MAX_BYTES),
    )
    window = body[offset : offset + limit]
    json_top, yaml_top, frontmatter = _git_blob_content_predicates(ext, body)
    kind = _plugin_kind_for_git_path(
        entry.path,
        json_top_level=json_top,
        yaml_top_level=yaml_top,
        frontmatter=frontmatter,
    ) or (classify_by_ext(ext) if ext else "text")
    payload.update(
        {
            "type": "text",
            "kind": kind,
            "views": _views_for_kind(kind),
            "content": window.decode("utf-8", "replace"),
            "content_offset": offset,
            "content_bytes": len(window),
            "content_truncated": offset + len(window) < len(body),
        }
    )
    return payload


def _patch_container_payload(entry: GitTreeEntry, *, wire: str, inner: str) -> dict[str, Any]:
    ext = _logical_ext(entry.path)
    return {
        "subject": "git_revision",
        "type": "text",
        "kind": "diff",
        "views": _views_for_kind("diff"),
        "path": wire,
        "display": entry.path.display(),
        "container": entry.path.to_wire(),
        "container_inner": inner,
        "ext": ext,
        "size": 0,
        "mode": entry.mode,
        "git_kind": entry.kind,
        "symlink": False,
        "gitlink": False,
        "oid": entry.oid,
        "content": "",
        "content_offset": 0,
        "content_bytes": 0,
        "bytes_read": 0,
        "content_truncated": False,
    }


async def git_revision_file(request: Request, subject: GitRevisionSubject) -> JSONResponse:
    """File or folder envelope for one GitPath. No mtime or ignore state."""

    wire = request.query_params.get("path", "")
    try:
        path, inner = split_git_container_wire(wire)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    if inner:
        if inner.count("/") + 1 > MAX_CONTAINER_INNER_DEPTH:
            return _json(_NOT_FOUND, status_code=404)
        try:
            entry = await subject.tree_source.resolve_path(path)
            if (
                entry is None
                or not entry.is_blob
                or entry.is_symlink
                or entry.is_gitlink
                or _logical_ext(entry.path) not in _PATCH_EXTS
            ):
                return _json(_NOT_FOUND, status_code=404)
        except GitObjectUnavailableError:
            return _json(_NOT_FOUND, status_code=404)
        return _json(_patch_container_payload(entry, wire=wire, inner=inner))
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None:
            return _json(_NOT_FOUND, status_code=404)
        if entry.is_tree:
            children = await subject.tree_source.list_tree(path)
            index = await subject.tree_source.blob_index(path)
            return _json(
                _tree_file_payload(entry, children, tally=None if index is None else index.tally())
            )
        if entry.is_gitlink:
            return _json(_gitlink_file_payload(entry))
        if not entry.is_blob:
            return _json(_NOT_FOUND, status_code=404)
        body = await subject.tree_source.read_blob(path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    return _json(_blob_file_payload(entry, body, request))


async def git_revision_kpress_render(
    subject: GitRevisionSubject,
    *,
    subpath: str,
    view: str,
    profile: str | None,
    source_override: str | None,
    include_toc: Literal["auto", "on", "off"],
    max_bytes: int,
) -> JSONResponse:
    """Render one Git blob through KPress. No mtime; the cache key is the OID."""

    try:
        path = GitPath.from_wire(subpath)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None or not entry.is_blob or entry.is_symlink or entry.is_gitlink:
            return _json(_NOT_FOUND, status_code=404)
        body = b"" if source_override is not None else await subject.tree_source.read_blob(path)
    except GitObjectUnavailableError:
        return _json(_NOT_FOUND, status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)

    ext = _logical_ext(entry.path)
    if source_override is not None:
        content = source_override
        logical_size = len(source_override.encode())
    else:
        if len(body) > max_bytes:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": "File is too large for full document rendering",
                    "path": path.to_wire(),
                    "size": len(body),
                    "max_size": max_bytes,
                },
                status_code=413,
            )
        content_class = classify_prefix(body)
        if ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT:
            return JSONResponse(
                {
                    "type": "kpress_render_error",
                    "error": "KPress render supports text-like files only",
                    "path": path.to_wire(),
                    "ext": ext,
                    "size": len(body),
                },
                status_code=415,
            )
        content = body.decode("utf-8", "replace")
        logical_size = len(body)

    kind = classify_by_ext(ext) if ext else "text"
    try:
        rendered = await asyncio.to_thread(
            kpress_adapter.render_kpress_view,
            source_text=content,
            # Display text is not a route identity; wiki rewrite must stay on the wire.
            source_path=path.to_wire(),
            kind=kind,
            view=view,
            ext=ext,
            mtime_hash=entry.oid,
            size=logical_size,
            frontmatter=None,
            frontmatter_error=None,
            profile=profile,
            include_toc=include_toc,
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "Invalid KPress render request",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=400,
        )
    except kpress_adapter.KPressRenderError as exc:
        return JSONResponse(
            {
                "type": "kpress_render_error",
                "error": "KPress render failed",
                "detail": str(exc),
                "diagnostics": [str(exc)],
            },
            status_code=502,
        )
    return JSONResponse(rendered, headers={"cache-control": "no-cache"})


async def git_revision_raw(request: Request, subject: GitRevisionSubject) -> Response:
    """Blob bytes for one GitPath. Symlink targets are not followed."""

    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return PlainTextResponse("Not found", status_code=404)
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None or not entry.is_blob:
            return PlainTextResponse("Not found", status_code=404)
        body = await subject.tree_source.read_blob(path)
    except GitObjectUnavailableError:
        return PlainTextResponse("Not found", status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    media_type, _ = mimetypes.guess_type(_display_basename(path))
    return Response(
        content=body,
        media_type=media_type or "application/octet-stream",
        headers={"cache-control": "no-store"},
    )


__all__ = [
    "decode_git_view_path",
    "git_revision_capabilities",
    "git_revision_catalog",
    "git_revision_file",
    "git_revision_index_meta",
    "git_revision_index_progress",
    "git_revision_kpress_render",
    "git_revision_raw",
    "git_revision_rollup",
    "git_revision_tree",
    "split_git_container_wire",
]
