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
Blob ``/api/file`` envelopes include that same ``ext`` so plugin-sdk
``langForPath`` and ``ctx.ext`` do not fall back to a GitPath wire; they omit
compressed identity because blobs are stored bytes with no gzip smudge.
Markdown blob envelopes include parsed YAML ``frontmatter`` and
``frontmatter_error`` the way filesystem ``/api/file`` does; KPress on a pin
uses that parse rather than an empty mapping.
Text blobs use the same first-window and highlight bound as filesystem
listings, and advertise ``bytes_read`` plus preview limits so Load more and
``fetchText`` can continue a truncated Git envelope.
A Git image blob is SPA ``image`` chrome (``ext`` from the compound tail,
preview view, no inline content); ``/raw`` serves the stored bytes so the
image plugin can paint. Alternative text uses the display name, not the
GitPath wire.
``/api/file``, ``/raw``, KPress, and plugin sidekicks follow in-tree relative
symlink blobs to the target object; the requested GitPath stays the route
identity. Kind checks (JSONL, structured, patch) use the leaf path.
Listings still show the symlink node. Absolute, dangling, and cyclic
targets 404.
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
decode GitPath wires to display names; C0 and invalid UTF-8 become U+FFFD.
Navigation identities stay wires. KPress ``source_path``
is the GitPath wire so Markdown rewrite cannot emit a filesystem spelling.
Patch-file container inners use a GitPath prefix plus a host inner path. Blob
kinds use extension, basename, sniffed adapter, and JSON/YAML/frontmatter
mappings parsed from blob bytes. ``path_glob`` stays filesystem-only. Serving
acquired Git over a listening port remains a later bead. The CLI can
``--show`` / ``--api`` a leased ``file://`` pin in-process.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import mimetypes
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from metabrowser import kpress_adapter
from metabrowser.capabilities import get_capabilities
from metabrowser.content_sniff import SNIFF_PREFIX_BYTES, ContentClass, classify_prefix
from metabrowser.file_extensions import (
    BROWSER_IMAGE_EXTS,
    BROWSER_TEXT_EXTS,
    syntax_language_for_path,
)
from metabrowser.file_kinds import classify_by_ext
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.folder_discovery import choose_readme_name
from metabrowser.fs_paths import derive_ext
from metabrowser.git.process import GitError, GitTimeoutError, failure_detail
from metabrowser.git.tree_source import (
    GitBlobIndex,
    GitBlobTallies,
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    GitTreeEntry,
    GitTreeSource,
    GitTreeTally,
    display_segment,
    follow_git_symlinks,
    resolve_git_blob_entry,
    split_git_container_wire,
)
from metabrowser.gz_io import ArtifactPath
from metabrowser.inventory_engine.contract import ascii_casefold
from metabrowser.inventory_rollup import RollupOptions, build_rollup, group_rollup_children
from metabrowser.settings import (
    FOLDER_DISCOVERY_MAX_ENTRIES,
    INVENTORY_MAX_FILES,
    SYNTAX_HIGHLIGHT_MAX_BYTES,
    TEXT_PREVIEW_CHUNK_BYTES,
    TEXT_PREVIEW_REQUEST_MAX_BYTES,
)
from metabrowser.source import MAX_CONTAINER_INNER_DEPTH, UnsupportedSourceCapabilityError
from metabrowser.tree import _tree_depth_from_query
from metabrowser.tree_filter import TreeFilter
from metabrowser.view_routes import decode_view_logical_path

log = logging.getLogger(__name__)

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


def _identity_fields(entry: GitTreeEntry, *, path: GitPath | None = None) -> dict[str, Any]:
    ident = entry.path if path is None else path
    return {
        "path": ident.to_wire(),
        "display": ident.display(),
        "mode": entry.mode,
        "git_kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }


def _display_basename(path: GitPath) -> str:
    if not path.segments:
        return ""
    return path.display().rsplit("/", 1)[-1]


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
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, str | None]:
    from metabrowser.plugin_loader.classify import (
        json_mapping_from_bytes,
        parse_frontmatter_bytes,
        yaml_mapping_from_bytes,
    )

    json_top = json_mapping_from_bytes(body) if ext == ".json" else None
    yaml_top = yaml_mapping_from_bytes(body) if ext in {".yaml", ".yml"} else None
    frontmatter = None
    frontmatter_error = None
    if ext == ".md":
        frontmatter, frontmatter_error = parse_frontmatter_bytes(body)
    return json_top, yaml_top, frontmatter, frontmatter_error


def _json_safe_git_frontmatter(value: dict[str, Any]) -> dict[str, Any]:
    from metabrowser.server import _json_safe_frontmatter

    safe = _json_safe_frontmatter(value)
    return safe if isinstance(safe, dict) else {}


def _git_frontmatter_envelope(
    *,
    mapping: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if mapping is not None:
        fields["frontmatter"] = _json_safe_git_frontmatter(mapping)
    if error is not None:
        fields["frontmatter_error"] = error
    return fields


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


def _git_filter_active(tree_filter: TreeFilter) -> bool:
    return bool(tree_filter.types or tree_filter.min_size)


def _blob_display_name(rel: bytes) -> str:
    return display_segment(rel.rsplit(b"/", 1)[-1])


def _git_blob_exts(index: GitBlobIndex) -> tuple[str, ...]:
    """Logical extension of every blob, aligned with ``index.blobs``.

    Derived once per tree: chrome tallies, index facts, and every filter read
    it instead of decoding each name again. Equal extensions share one string.
    """

    interned: dict[str, str] = {}
    exts: list[str] = []
    for rel, _oid in index.blobs:
        ext = derive_ext(_blob_display_name(rel))
        exts.append(interned.setdefault(ext, ext))
    return tuple(exts)


def _git_filter_tallies(
    index: GitBlobIndex,
    exts: tuple[str, ...],
    tree_filter: TreeFilter,
    semantic: frozenset[str],
) -> GitBlobTallies:
    """Running totals of the blobs *tree_filter* keeps. Same rules as ``_matches_types``."""

    folded_types = tuple(ascii_casefold(token) for token in tree_filter.types)
    ext_tokens = frozenset(token for token in folded_types if token.startswith("."))
    name_tokens = frozenset(token for token in folded_types if not token.startswith("."))
    suffix_tokens = tuple(token for token in ext_tokens if token in semantic)
    ext_verdicts: dict[str, bool] = {}
    floor = tree_filter.min_size
    matches = bytearray(len(index.blobs))
    for position, ((rel, oid), ext) in enumerate(zip(index.blobs, exts, strict=True)):
        keep = True
        if folded_types:
            verdict = ext_verdicts.get(ext)
            if verdict is None:
                verdict = bool(ext) and (
                    ext in ext_tokens or any(ext.endswith(token) for token in suffix_tokens)
                )
                ext_verdicts[ext] = verdict
            keep = verdict or (
                bool(name_tokens) and ascii_casefold(_blob_display_name(rel)) in name_tokens
            )
        if keep and floor:
            size = index.sizes.get(oid)
            keep = size is not None and size >= floor
        matches[position] = keep
    return GitBlobTallies(index.blobs, index.sizes, matches)


@dataclass(frozen=True, slots=True)
class _GitTallyView:
    """Subtree totals for one request: the whole index, or one filter's matches."""

    index: GitBlobIndex
    tallies: GitBlobTallies

    def tally(self, prefix: bytes = b"") -> GitTreeTally:
        return self.tallies.tally(self.index.prefix_spans(prefix))


async def _git_tally_view(
    source: GitTreeSource,
    index: GitBlobIndex | None,
    *,
    tree_oid: str,
    tree_filter: TreeFilter,
    semantic: frozenset[str],
) -> _GitTallyView | None:
    """Totals for the tree at *tree_oid*. A filter's matches are memoized per filter."""

    if index is None:
        return None
    if not _git_filter_active(tree_filter):
        return _GitTallyView(index, index.tallies)
    exts = await source.derived(("blob-exts", tree_oid), lambda: _git_blob_exts(index))
    tallies = await source.derived(
        ("filter-tallies", tree_oid, tree_filter.types, tree_filter.min_size),
        lambda: _git_filter_tallies(index, exts, tree_filter, semantic),
    )
    return _GitTallyView(index, tallies)


def _git_entry_visible(
    entry: GitTreeEntry,
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
    *,
    index_prefix: bytes = b"",
    semantic: frozenset[str] | None = None,
) -> bool:
    """Keep trees that have a matching descendant; drop empty filter dirs."""

    if not _git_filter_active(tree_filter):
        return True
    if entry.is_tree:
        if view is None:
            return True
        prefix = _join_git_prefix(index_prefix, entry.path.segments[-1])
        return view.tally(prefix).total_files > 0
    if tree_filter.types and not _matches_types(entry.path, tree_filter.types, semantic=semantic):
        return False
    if tree_filter.min_size:
        return _passes_min_size(entry, tree_filter.min_size)
    return True


def _git_visible_entries(
    entries: tuple[GitTreeEntry, ...],
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
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
            entry, tree_filter, view, index_prefix=index_prefix, semantic=semantic
        )
    )


# Nodes one ``/api/tree`` response may nest below the listed directory. ``depth``
# is accepted up to MAX_TREE_DEPTH, so without a bound one request could
# materialize a whole repository. Direct children are always listed; a
# directory whose children no longer fit is emitted as the same lazy sentinel
# the depth cap uses, and the SPA loads it on expansion.
#
# The filesystem tree has no cost-derived node bound to mirror: its page
# assembly stops only at the engine's MAX_ASSEMBLED_ROWS consistency guard and
# answers with an error. Measured on a synthetic 100,000-blob pin, on a heavily
# loaded machine: a warm build costs about 19 us per node (8,000 nodes in
# 149 ms), and a response at this bound took 0.4 to 0.6 s end to end for a
# 2.4 MiB body, against about 104,000 nodes unbounded. The default ``depth=2``
# listing of a 4,000-directory tree (8,000 nodes) stays whole.
GIT_NAV_TREE_MAX_NODES = 20_000


@dataclass(slots=True)
class _NavNodeBudget:
    remaining: int


async def _git_nav_tree(
    subject: GitRevisionSubject,
    entries: tuple[GitTreeEntry, ...],
    *,
    remaining_depth: int,
    tree_filter: TreeFilter,
    view: _GitTallyView | None,
    index_prefix: bytes,
    semantic: frozenset[str] | None,
    budget: _NavNodeBudget,
) -> list[dict[str, Any]]:
    """SPA ``tree`` nodes. Nest while depth and the node budget allow; else a lazy sentinel."""

    if remaining_depth <= 0:
        return []
    nodes: list[dict[str, Any]] = []
    nest = remaining_depth > 1
    # Directories first, matching the filesystem tree contract the SPA renders in
    # server order; ``sorted`` is stable, so names keep the source's byte order.
    for entry in sorted(entries, key=lambda item: not item.is_tree):
        prefix = _join_git_prefix(index_prefix, entry.path.segments[-1]) if entry.is_tree else b""
        tally = view.tally(prefix) if entry.is_tree and view is not None else None
        if entry.is_tree and nest and budget.remaining > 0:
            try:
                nested = await subject.tree_source.list_tree_entry(entry)
            except GitObjectUnavailableError:
                nodes.append(_nav_tree_node(entry, tally=tally))
                continue
            nested = _git_visible_entries(
                nested, tree_filter, view, index_prefix=prefix, semantic=semantic
            )
            if len(nested) <= budget.remaining:
                budget.remaining -= len(nested)
                children = await _git_nav_tree(
                    subject,
                    nested,
                    remaining_depth=remaining_depth - 1,
                    tree_filter=tree_filter,
                    view=view,
                    index_prefix=prefix,
                    semantic=semantic,
                    budget=budget,
                )
                nodes.append(_nav_tree_node(entry, tally=tally, children=children, loaded=True))
                continue
        nodes.append(_nav_tree_node(entry, tally=tally))
    return nodes


def _git_tree_filtered(
    view: _GitTallyView | None, tree_filter: TreeFilter
) -> dict[str, int] | None:
    """Subtree filter totals. Omit when sizes are incomplete."""

    if view is None or not _git_filter_active(tree_filter):
        return None
    tally = view.tally()
    if tally.total_size is None:
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


def _with_requested_path(
    payload: dict[str, Any], entry: GitTreeEntry, requested: GitPath
) -> dict[str, Any]:
    payload.update(_identity_fields(entry, path=requested))
    if payload.get("type") == "folder":
        payload["name"] = _display_basename(requested)
    return payload


def _git_text_window(request: Request, entry: GitTreeEntry, ext: str) -> tuple[int, int]:
    """The requested text window's offset and limit, under the filesystem's policy."""

    offset = max(0, _query_int(request, "offset", 0))
    default_limit = TEXT_PREVIEW_CHUNK_BYTES
    if (
        offset == 0
        and syntax_language_for_path(_display_basename(entry.path), ext)
        and SYNTAX_HIGHLIGHT_MAX_BYTES > 0
    ):
        default_limit = min(default_limit, SYNTAX_HIGHLIGHT_MAX_BYTES)
    limit = max(
        1,
        min(_query_int(request, "limit", default_limit), TEXT_PREVIEW_REQUEST_MAX_BYTES),
    )
    return offset, limit


def _git_text_preview_fields(
    request: Request, entry: GitTreeEntry, ext: str, body: bytes
) -> dict[str, Any]:
    """Bounded text window matching filesystem /api/file preview policy."""

    offset, limit = _git_text_window(request, entry, ext)
    return _git_text_fields(offset, limit, body[offset : offset + limit], len(body))


def _git_text_fields(offset: int, limit: int, window: bytes, size: int) -> dict[str, Any]:
    bytes_read = len(window)
    return {
        "content": window.decode("utf-8", "replace"),
        "content_offset": offset,
        "content_bytes": bytes_read,
        "bytes_read": bytes_read,
        "content_truncated": offset + bytes_read < size,
        "content_preview_limit": limit,
        "content_max_preview_limit": TEXT_PREVIEW_REQUEST_MAX_BYTES,
        "highlight_disabled": (
            SYNTAX_HIGHLIGHT_MAX_BYTES <= 0 or bytes_read > SYNTAX_HIGHLIGHT_MAX_BYTES
        ),
    }


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


def git_content_failure_response(exc: GitError) -> JSONResponse:
    """Typed envelope for a Git failure on a pin. No git text, so no local paths.

    Statuses match ``/api/git/*``: a timeout is 504 because a retry can
    plausibly fix it, and any other failure is 500. An object the store lacks
    and an oversized blob keep their own 404 and 413 envelopes.
    """

    if isinstance(exc, GitObjectUnavailableError):
        return _json(_object_unavailable_payload(exc), status_code=404)
    if isinstance(exc, GitBlobTooLargeError):
        return _json(_blob_too_large_payload(exc), status_code=413)
    if isinstance(exc, GitTimeoutError):
        return _json({"error": "git command timed out", "code": "git_timeout"}, status_code=504)
    return _json({"error": "git command failed", "code": "git_failed"}, status_code=500)


def _typed_git_failures[**P, R: Response](
    handler: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R | JSONResponse]]:
    """The one place a pin route turns an escaped ``GitError`` into a response.

    Handlers still answer the failures they give a route-specific shape, such
    as a plain 404 on ``/raw``. Everything else in the family lands here instead
    of becoming a bare 500.
    """

    @functools.wraps(handler)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> R | JSONResponse:
        try:
            return await handler(*args, **kwargs)
        except GitError as exc:
            log.warning("git pin %s failed: %s", handler.__name__, failure_detail(exc))
            return git_content_failure_response(exc)

    return guarded


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
                display = display_segment(segment)
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
                    name=display_segment(segment),
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


@_typed_git_failures
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
    # The body is capped by ``options.max_nodes``, so the memo holds a small
    # response, not the per-blob entries it was reduced from.
    status_code, payload = await subject.tree_source.derived(
        ("rollup", wire, options),
        lambda: _git_rollup_payload(index, path, children, options),
    )
    return _json(payload, status_code=status_code)


def _git_rollup_payload(
    index: GitBlobIndex,
    path: GitPath,
    children: tuple[GitTreeEntry, ...],
    options: RollupOptions,
) -> tuple[int, dict[str, Any]]:
    wire = path.to_wire()
    entries = _rollup_entries_from_index(index, path)
    if entries is None:
        missing_oid = _missing_blob_oid(index)
        return 404, {
            "error": f"object_unavailable: {missing_oid}",
            "code": "object_unavailable",
            "oid": missing_oid,
        }
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
        return 404, _NOT_FOUND
    node = built["node"]
    return 200, {
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


def _git_catalog_body(index: GitBlobIndex, exts: tuple[str, ...]) -> bytes:
    files: list[dict[str, str]] = []
    for (rel, _oid), ext in zip(index.blobs, exts, strict=True):
        path = _git_path_from_relative(rel)
        files.append({"p": path.to_wire(), "e": ext, "n": _blob_display_name(rel)})
    payload = {"complete": True, "truncated": False, "revision": 1, "files": files}
    return bytes(JSONResponse(payload).body)


@_typed_git_failures
async def git_revision_catalog(request: Request, subject: GitRevisionSubject) -> Response:
    """One-shot Quick File catalog from recursive blob names. No watcher."""

    del request
    source = subject.tree_source
    try:
        index = await source.blob_index()
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    if index is None:
        return _json({"complete": True, "truncated": True, "revision": 1, "files": []})
    exts = await _git_root_blob_exts(subject, index)
    # The rendered body is kept, not the row dicts: it is the smaller form, and
    # a repeat request skips serialization as well as the scan.
    body = await source.derived(
        ("catalog-body", subject.tree_oid), lambda: _git_catalog_body(index, exts)
    )
    return Response(
        content=body, media_type="application/json", headers={"cache-control": "no-store"}
    )


async def _git_root_blob_exts(subject: GitRevisionSubject, index: GitBlobIndex) -> tuple[str, ...]:
    return await subject.tree_source.derived(
        ("blob-exts", subject.tree_oid), lambda: _git_blob_exts(index)
    )


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


def _git_extension_counts(exts: tuple[str, ...]) -> Counter[str]:
    counts = Counter(exts)
    del counts[""]
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


def _git_tree_index_chrome(
    index: GitBlobIndex | None, exts: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Whole-tree filter tallies and summary. Ignore is absent, so ignored is 0.

    *exts* is ``_git_blob_exts(index)``. The caller memoizes the result per pin.
    """

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
    for (rel, _oid), ext in zip(index.blobs, exts, strict=True):
        name = ascii_casefold(_blob_display_name(rel))
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
    exts = await _git_root_blob_exts(subject, index)
    return await subject.tree_source.derived(
        ("index-facts", subject.tree_oid), lambda: _git_index_facts_from(index, exts)
    )


def _git_index_facts_from(index: GitBlobIndex, exts: tuple[str, ...]) -> _GitIndexFacts:
    dirs: set[bytes] = set()
    for rel, _oid in index.blobs:
        parts = rel.split(b"/")
        for depth in range(len(parts) - 1):
            dirs.add(b"/".join(parts[: depth + 1]))
    suffixes = tuple(
        sorted(_git_extension_counts(exts).items(), key=lambda item: (-item[1], item[0]))
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


@_typed_git_failures
async def git_revision_index_progress(subject: GitRevisionSubject) -> JSONResponse:
    """Terminal crawl footer for a pin. There is no walker."""

    try:
        facts = await _git_index_facts(subject)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    return _json({**_git_index_common(facts), "active": False})


@_typed_git_failures
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


@_typed_git_failures
async def git_revision_capabilities(subject: GitRevisionSubject) -> JSONResponse:
    """Observation surface for a pin: complete, no watcher, events off.

    The content-trust block is the same process-wide answer the filesystem
    route publishes. It is what the shell reads to decide whether a document
    gets its executing view, and a pinned blob is browsed the same way, so
    leaving it out would hide the profile exactly where it applies.
    """

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
            "capabilities": get_capabilities().as_wire(),
        }
    )


@_typed_git_failures
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
        source = subject.tree_source
        index = await source.blob_index(path)
        semantic = _semantic_extension_tokens(tree_filter.types)
        view = await _git_tally_view(
            source, index, tree_oid=located.oid, tree_filter=tree_filter, semantic=semantic
        )
        if remaining_depth <= 0:
            entries: tuple[GitTreeEntry, ...] = ()
            tree_nodes: list[dict[str, Any]] = []
        else:
            entries = await source.list_tree(path)
            entries = _git_visible_entries(
                entries, tree_filter, view, index_prefix=b"", semantic=semantic
            )
            tree_nodes = await _git_nav_tree(
                subject,
                entries,
                remaining_depth=remaining_depth,
                tree_filter=tree_filter,
                view=view,
                index_prefix=b"",
                semantic=semantic,
                budget=_NavNodeBudget(GIT_NAV_TREE_MAX_NODES - len(entries)),
            )
        root_index = index if not path.segments else await source.blob_index()
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    assert located is not None
    chrome = await _git_root_index_chrome(subject, root_index)
    filtered = _git_tree_filtered(view, tree_filter)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "path": path.to_wire(),
        "display": path.display(),
        "oid": located.oid,
        "kind": "tree",
        "entries": [_listing_entry(entry) for entry in entries],
        "tree": tree_nodes,
        **chrome,
    }
    if filtered is not None:
        payload["filtered"] = filtered
    return _json(payload)


async def _git_root_index_chrome(
    subject: GitRevisionSubject, root_index: GitBlobIndex | None
) -> dict[str, Any]:
    if root_index is None:
        return _git_tree_index_chrome(None)
    exts = await _git_root_blob_exts(subject, root_index)
    return await subject.tree_source.derived(
        ("index-chrome", subject.tree_oid), lambda: _git_tree_index_chrome(root_index, exts)
    )


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


async def _blob_file_payload(entry: GitTreeEntry, body: bytes, request: Request) -> dict[str, Any]:
    ext = _logical_ext(entry.path)
    payload: dict[str, Any] = {
        "subject": "git_revision",
        "size": len(body),
        **_identity_fields(entry),
    }
    if ext:
        payload["ext"] = ext
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

        # Off the loop, as the filesystem envelope does: a blob can be as large as
        # the preview bound, and parsing it is synchronous.
        parsed = await asyncio.to_thread(parse_jsonl_bytes, body)
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
    json_top, yaml_top, frontmatter, frontmatter_error = _git_blob_content_predicates(ext, body)
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
            **_git_text_preview_fields(request, entry, ext, body),
            **_git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error),
        }
    )
    return payload


# Every content predicate reads a bounded prefix: a JSON mapping is refused past 256 KiB,
# YAML reads 16 KiB, and frontmatter 256 KiB. One byte past the largest gives each the
# answer the whole blob would.
_PREDICATE_PREFIX_BYTES = 256 * 1024 + 1


async def _windowed_blob_file_response(
    request: Request,
    source: GitTreeSource,
    entry: GitTreeEntry,
    size: int,
    *,
    requested: GitPath,
    wire: str,
) -> JSONResponse:
    """``/api/file`` for a blob larger than the pin reads whole.

    The filesystem types a large file from its extension and a bounded sniff, then
    serves the requested text window. A pin does the same from a streamed window, so
    the blob is never held whole and nothing is refused for its size before it is
    classified. Like a compressed artifact, a blob streams from its start, so reaching
    an offset costs reading up to it: a text window is clipped to end within the pin's
    ceiling, and one that would start past it is 416, as a compressed file is past its
    decompression budget.
    """

    ext = _logical_ext(entry.path)
    payload: dict[str, Any] = {"subject": "git_revision", "size": size, **_identity_fields(entry)}
    if ext:
        payload["ext"] = ext
    if ext in BROWSER_IMAGE_EXTS:
        payload.update({"type": "image", "kind": "image", "views": _views_for_kind("image")})
        return _json(_with_requested_path(payload, entry, requested))
    offset, limit = _git_text_window(request, entry, ext)
    limit = min(limit, source.max_blob_bytes - offset)
    head, _size = await source.read_blob_window(
        entry.oid,
        offset=0,
        max_bytes=max(_PREDICATE_PREFIX_BYTES, offset + limit if limit > 0 else 0),
    )
    content_class = classify_prefix(head[:SNIFF_PREFIX_BYTES])
    if content_class is ContentClass.BINARY or (
        ext not in BROWSER_TEXT_EXTS and content_class is not ContentClass.TEXT
    ):
        payload.update({"type": "binary", "kind": "binary", "views": _views_for_kind("binary")})
        return _json(_with_requested_path(payload, entry, requested))
    if ext == ".jsonl":
        return await _windowed_jsonl_response(source, entry, size, payload, requested, wire)
    if limit <= 0:
        return _json(
            {
                "type": "error",
                "path": wire,
                "error": "Requested preview window exceeds the stream budget for this blob",
                "max_offset": source.max_blob_bytes,
            },
            status_code=416,
        )
    json_top, yaml_top, frontmatter, frontmatter_error = _git_blob_content_predicates(
        ext, head[:_PREDICATE_PREFIX_BYTES]
    )
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
            **_git_text_fields(offset, limit, head[offset : offset + limit], size),
            **_git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error),
        }
    )
    return _json(_with_requested_path(payload, entry, requested))


async def _windowed_jsonl_response(
    source: GitTreeSource,
    entry: GitTreeEntry,
    size: int,
    payload: dict[str, Any],
    requested: GitPath,
    wire: str,
) -> JSONResponse:
    """Parse a JSONL blob under the filesystem's parser ceiling, or say it is too large."""

    from metabrowser.jsonl_view import _JSONL_PARSE_MAX_BYTES, parse_jsonl_bytes

    if size > _JSONL_PARSE_MAX_BYTES:
        # The filesystem refuses an uncompressed file this size before reading it.
        return _json(
            {
                "type": "error",
                "kind": "error",
                "views": [],
                "path": wire,
                "error": f"JSONL content exceeds {_JSONL_PARSE_MAX_BYTES} decompressed bytes",
            }
        )
    body, _size = await source.read_blob_window(entry.oid, offset=0, max_bytes=size)
    parsed = await asyncio.to_thread(parse_jsonl_bytes, body)
    adapter = parsed.get("summary", {}).get("adapter")
    adapter_name = adapter if isinstance(adapter, str) else None
    kind = _plugin_kind_for_git_path(entry.path, adapter=adapter_name) or classify_by_ext(
        ".jsonl", adapter_name
    )
    payload.update({"type": "jsonl", "kind": kind, "views": _views_for_kind(kind), **parsed})
    return _json(_with_requested_path(payload, entry, requested))


def _patch_container_payload(
    entry: GitTreeEntry, *, wire: str, inner: str, path: GitPath
) -> dict[str, Any]:
    ext = _logical_ext(entry.path)
    return {
        "subject": "git_revision",
        "type": "text",
        "kind": "diff",
        "views": _views_for_kind("diff"),
        "path": wire,
        "display": path.display(),
        "container": path.to_wire(),
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


@_typed_git_failures
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
            entry = await resolve_git_blob_entry(subject.tree_source, path)
            if entry is None or _logical_ext(entry.path) not in _PATCH_EXTS:
                return _json(_NOT_FOUND, status_code=404)
        except GitObjectUnavailableError:
            return _json(_NOT_FOUND, status_code=404)
        return _json(_patch_container_payload(entry, wire=wire, inner=inner, path=path))
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None:
            return _json(_NOT_FOUND, status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None:
                return _json(_NOT_FOUND, status_code=404)
            entry = followed
        if entry.is_tree:
            children = await subject.tree_source.list_tree(entry.path)
            index = await subject.tree_source.blob_index(entry.path)
            payload = _tree_file_payload(
                entry, children, tally=None if index is None else index.tally()
            )
            return _json(_with_requested_path(payload, entry, path))
        if entry.is_gitlink:
            return _json(_with_requested_path(_gitlink_file_payload(entry), entry, path))
        if not entry.is_blob:
            return _json(_NOT_FOUND, status_code=404)
        source = subject.tree_source
        size = entry.size if entry.size is not None else (await source.object_info(entry.oid)).size
        if size > source.max_blob_bytes:
            return await _windowed_blob_file_response(
                request, source, entry, size, requested=path, wire=wire
            )
        body = await source.read_blob(entry.path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    payload = await _blob_file_payload(entry, body, request)
    return _json(_with_requested_path(payload, entry, path))


@_typed_git_failures
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
        if entry is None:
            return _json(_NOT_FOUND, status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None:
                return _json(_NOT_FOUND, status_code=404)
            entry = followed
        if not entry.is_blob or entry.is_symlink or entry.is_gitlink:
            return _json(_NOT_FOUND, status_code=404)
        body = (
            b"" if source_override is not None else await subject.tree_source.read_blob(entry.path)
        )
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
    frontmatter = None
    frontmatter_error = None
    if ext == ".md":
        parse_source = source_override.encode() if source_override is not None else body
        _, _, frontmatter, frontmatter_error = _git_blob_content_predicates(ext, parse_source)
    envelope = _git_frontmatter_envelope(mapping=frontmatter, error=frontmatter_error)
    try:
        rendered = await asyncio.to_thread(
            kpress_adapter.render_kpress_view,
            source_text=content,
            # Display text is not a route identity; wiki rewrite must stay on the wire.
            source_path=entry.path.to_wire(),
            kind=kind,
            view=view,
            ext=ext,
            mtime_hash=entry.oid,
            size=logical_size,
            frontmatter=envelope.get("frontmatter"),
            frontmatter_error=envelope.get("frontmatter_error"),
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


@_typed_git_failures
async def git_revision_raw(request: Request, subject: GitRevisionSubject) -> Response:
    """Blob bytes for one GitPath. In-tree relative symlink blobs are followed.

    Only the query form answers. The path form, `/raw/<path>`, is the address of a
    document whose relative references resolve beside it, and its one consumer is
    the HTML preview frame, which a pin never offers: acquired content always runs
    under the untrusted profile. A reference inside a raw pinned document therefore
    reaches `unsupported_for_subject` rather than a 404 that would misreport a
    present file as missing. Markdown images need no path form: the link enhancer
    resolves them to GitPath wires in the pinned tree and requests the query form.
    """

    if "path" in getattr(request, "path_params", {}):
        raise UnsupportedSourceCapabilityError("raw_document_path")
    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return PlainTextResponse("Not found", status_code=404)
    try:
        entry = await subject.tree_source.resolve_path(path)
        if entry is None or not entry.is_blob:
            return PlainTextResponse("Not found", status_code=404)
        if entry.is_symlink:
            followed = await follow_git_symlinks(subject.tree_source, entry)
            if followed is None or not followed.is_blob or followed.is_gitlink:
                return PlainTextResponse("Not found", status_code=404)
            entry = followed
        body = await subject.tree_source.read_blob(entry.path)
    except GitObjectUnavailableError:
        return PlainTextResponse("Not found", status_code=404)
    except GitBlobTooLargeError as exc:
        return _json(_blob_too_large_payload(exc), status_code=413)
    media_type, _ = mimetypes.guess_type(_display_basename(entry.path))
    return Response(
        content=body,
        media_type=media_type or "application/octet-stream",
        headers={"cache-control": "no-store"},
    )


__all__ = [
    "decode_git_view_path",
    "git_content_failure_response",
    "git_revision_capabilities",
    "git_revision_catalog",
    "git_revision_file",
    "git_revision_index_meta",
    "git_revision_index_progress",
    "git_revision_kpress_render",
    "git_revision_raw",
    "git_revision_rollup",
    "git_revision_tree",
    "resolve_git_blob_entry",
    "split_git_container_wire",
]
