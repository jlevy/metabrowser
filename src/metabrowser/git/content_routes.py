"""GitPath adapters for ``/api/tree``, ``/api/file``, ``/raw``, and KPress.

These honor a pinned ``GitRevisionSubject`` without a checkout, index, or
invented filesystem fact. ``/view/`` accepts a GitPath wire, optionally plus
a host container inner, and refuses a filesystem spelling. ``/api/tree`` keeps
Git-native ``entries`` and also projects a SPA ``tree`` array so navigation
can paint; Git trees lazy-load, gitlinks are files, and listings omit mtime,
size, and ignore. Patch-file container inners use a GitPath prefix plus a
host inner path. Blob kinds use extension, basename, sniffed adapter, and
JSON/YAML/frontmatter mappings parsed from blob bytes. ``path_glob`` stays
filesystem-only. Serving acquired Git from the CLI remains a later bead.
"""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Any, Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from metabrowser import kpress_adapter
from metabrowser.content_sniff import ContentClass, classify_prefix
from metabrowser.file_extensions import BROWSER_IMAGE_EXTS, BROWSER_TEXT_EXTS
from metabrowser.file_kinds import classify_by_ext
from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitObjectUnavailableError,
    GitPath,
    GitPathError,
    GitRevisionSubject,
    GitTreeEntry,
)
from metabrowser.plugin_api import MAX_CONTAINER_INNER_DEPTH
from metabrowser.settings import TEXT_PREVIEW_CHUNK_BYTES, TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.source import UnsupportedSourceCapabilityError
from metabrowser.tree_filter import TreeFilter
from metabrowser.view_routes import decode_view_logical_path

_NOT_FOUND = {"error": "Not found"}
_PATCH_EXTS = (".patch", ".diff")


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
    return {
        "path": entry.path.to_wire(),
        "display": entry.path.display(),
        "mode": entry.mode,
        "kind": entry.kind,
        "symlink": entry.is_symlink,
        "gitlink": entry.is_gitlink,
        "oid": entry.oid,
    }


def _nav_tree_type(entry: GitTreeEntry) -> Literal["dir", "file", "symlink"]:
    if entry.is_tree:
        return "dir"
    if entry.is_symlink:
        return "symlink"
    return "file"


def _nav_tree_node(entry: GitTreeEntry) -> dict[str, Any]:
    """SPA nav node. Omit inventory aggregates rather than invent zeros."""

    node: dict[str, Any] = {
        "name": _display_basename(entry.path),
        "path": entry.path.to_wire(),
        "type": _nav_tree_type(entry),
    }
    if entry.is_tree:
        node["children"] = None
        node["has_children"] = True
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
    return Path(_display_basename(path)).suffix.lower()


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


def _matches_types(path: GitPath, types: tuple[str, ...]) -> bool:
    name = _display_basename(path).lower()
    for token in types:
        if token.startswith("."):
            if name.endswith(token):
                return True
        elif name == token:
            return True
    return False


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


async def git_revision_tree(
    request: Request,
    subject: GitRevisionSubject,
    tree_filter: TreeFilter,
) -> JSONResponse:
    """List one Git tree. ``entries`` are Git facts; ``tree`` is the SPA nav."""

    if tree_filter.min_size:
        raise UnsupportedSourceCapabilityError("min_size")
    try:
        path = _git_path_from_query(request)
    except GitPathError:
        return _json(_NOT_FOUND, status_code=404)
    try:
        located = await subject.tree_source.resolve_path(path)
        if located is None or not located.is_tree:
            return _json(_NOT_FOUND, status_code=404)
        entries = await subject.tree_source.list_tree(path)
    except GitObjectUnavailableError as exc:
        return _json(_object_unavailable_payload(exc), status_code=404)
    if tree_filter.types:
        entries = tuple(entry for entry in entries if _matches_types(entry.path, tree_filter.types))
    return _json(
        {
            "subject": "git_revision",
            "path": path.to_wire(),
            "display": path.display(),
            "oid": located.oid,
            "kind": "tree",
            "entries": [_listing_entry(entry) for entry in entries],
            "tree": [_nav_tree_node(entry) for entry in entries],
        }
    )


def _tree_file_payload(entry: GitTreeEntry) -> dict[str, Any]:
    return {
        "subject": "git_revision",
        "type": "tree",
        "kind": "tree",
        "views": [],
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
    """File or tree envelope for one GitPath. No mtime or ignore state."""

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
            return _json(_tree_file_payload(entry))
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
            source_path=path.display(),
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
    "git_revision_file",
    "git_revision_kpress_render",
    "git_revision_raw",
    "git_revision_tree",
    "split_git_container_wire",
]
