"""On-demand Markdown redlines from one admitted immutable Git comparison."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, cast

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, admitted_snapshot
from metabrowser.cache.loading import LoadingCache, LoadingCacheBusyError
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import Availability, ContentRefKind, EntrySide, EntryType
from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget
from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitPath,
    GitPathError,
    blob_logical_ext,
    read_store_blob,
)
from metabrowser.git.wire import is_full_revision

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

type Status = Literal["unsupported", "too_large"]
_NO_STORE = {"cache-control": "no-store"}


def _fallback(status: Status = "unsupported") -> dict[str, Any]:
    return {
        "version": "markdown-diff-v1",
        "status": status,
        "blocks": [],
        "source_only": False,
    }


def _path(side: EntrySide) -> GitPath:
    raw = (
        base64.b64decode(side.path_b64, validate=True)
        if side.path_b64 is not None
        else side.path.encode()
    )
    return GitPath(tuple(raw.split(b"/")))


async def _project(
    published: PublishedSource, snapshot: Snapshot, file_id: str, namespace: str
) -> dict[str, Any]:
    from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
    from metabrowser.diff.markdown_projection import MARKDOWN_DIFF_MAX_BYTES, project_markdown_diff
    from metabrowser.kpress_adapter import document_stylesheets

    target = RepositoryStoreTarget(published.git_dir, published.object_format)
    source = GitDiffSource(GitLocation.revision(target, snapshot.head))
    comparison = await shared_pull_manifest(published, snapshot.base, snapshot.head)
    resolved, manifest = comparison.resolved, comparison.manifest
    if resolved.left.id != snapshot.base or resolved.right.id != snapshot.head:
        return _fallback()
    change = next((entry for entry in manifest.files if entry.id == file_id), None)
    if change is None or change.availability is not Availability.ready or change.binary:
        return _fallback()
    sides = [side for side in (change.old, change.new) if side is not None]
    for side in sides:
        if (
            side.entry_type is not EntryType.file
            or side.content.kind is not ContentRefKind.git_object
            or blob_logical_ext(_path(side)) not in {".md", ".markdown", ".mdown", ".mkd"}
        ):
            return _fallback()

    async def blob(side: EntrySide | None, budget: int) -> bytes | None:
        if side is None:
            return None
        oid = side.content.oid
        assert oid is not None
        return await read_store_blob(target, oid, max_blob_bytes=budget)

    try:
        old = await blob(change.old, MARKDOWN_DIFF_MAX_BYTES)
        new = await blob(change.new, MARKDOWN_DIFF_MAX_BYTES - len(old or b""))
    except GitBlobTooLargeError:
        return _fallback("too_large")
    patch = (await source.hydrate(resolved, [file_id], manifest=manifest)).patches.get(file_id)
    if patch is None or not patch.hunks:
        return _fallback()
    rewrite: Callable[[str, bool], str | None] | None = None
    if change.new is not None:
        path = _path(change.new)

        def head_reference(href: str, image: bool) -> str | None:
            return snapshot.reference(path, href, image)

        rewrite = head_reference

    projection = await asyncio.to_thread(
        project_markdown_diff,
        old=old,
        new=new,
        patch=patch,
        namespace=namespace,
        rewrite_local=rewrite,
    )
    if sum(len(block["html"].encode()) for block in projection["blocks"]) > 256 * 1024:
        return _fallback("too_large")
    return {
        **projection,
        **(
            {"assets": await asyncio.to_thread(document_stylesheets)}
            if projection["status"] == "ready"
            else {}
        ),
    }


async def pull_rendered_diff_handler(request: Request) -> JSONResponse:
    params = request.query_params
    try:
        number = requested_number(params)
    except PullRequestError:
        number = None
    base, head = params.get("left", ""), params.get("right", "")
    file_id = params.get("rendered_file", "")
    if (
        number is None
        or not is_full_revision(base)
        or not is_full_revision(head)
        or not file_id
        or len(file_id) > 128
    ):
        return JSONResponse({"code": "invalid_rendered_diff"}, status_code=400, headers=_NO_STORE)
    snapshot = Snapshot(number, base, head, params.get("store", ""), "head")
    published = await admitted_snapshot(request, snapshot)
    if published is None:
        return JSONResponse({"code": "snapshot_expired"}, status_code=410, headers=_NO_STORE)

    state = request.app.state
    cache = getattr(state, "pull_rendered_diff_cache", None)
    if cache is None:
        # A projection is capped by the module's byte/node budgets. At most two
        # distinct loads per server can contend with the source diff.
        cache = state.pull_rendered_diff_cache = LoadingCache(max_values=32, max_loads=2)
    cache = cast("LoadingCache[tuple[str, ...], dict[str, Any]]", cache)
    key = (published.store_id, snapshot.store, str(number), base, head, file_id)
    namespace = "diff-" + hashlib.sha256("\0".join(key).encode()).hexdigest()[:20]
    try:
        answer = await cache.get(key, lambda: _project(published, snapshot, file_id, namespace))
    except LoadingCacheBusyError:
        return JSONResponse({"code": "rendered_diff_busy"}, status_code=429, headers=_NO_STORE)
    except GitError:
        return JSONResponse(
            {"code": "rendered_objects_unavailable"}, status_code=409, headers=_NO_STORE
        )
    except (DiffSourceError, GitPathError):
        answer = _fallback()
    return JSONResponse(answer, headers=_NO_STORE)
