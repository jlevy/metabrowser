"""On-demand Markdown redlines from one admitted immutable Git comparison."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections import OrderedDict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, cast

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, admitted_snapshot
from metabrowser.cache.loading import LoadingCache, LoadingCacheBusyError
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import (
    Availability,
    ChangeSetManifest,
    ContentRefKind,
    EntrySide,
    EntryType,
    FileChange,
    FilePatch,
)
from metabrowser.diff.markdown_projection import (
    MARKDOWN_DIFF_MAX_BYTES,
    MARKDOWN_DIFF_VERSION,
    bind_markdown_diff,
)
from metabrowser.diff.markdown_projection_worker import ProjectionWorker
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
_MARKDOWN = frozenset({".md", ".markdown", ".mdown", ".mkd"})
# Rendered blocks the route sends at most. The 434 real pairs of this repository's
# history answer with at most 45,677 bytes of HTML, and the most a pair inside every
# projection budget was found to make is 110,840 bytes: 255 links into the snapshot,
# each address about 400 bytes.
_MAX_HTML_BYTES = 256 * 1024
# The Markdown files one `git diff` hydrates when a reader reaches the first of them: the
# Source view's own run is a different request, so this route reads its patches itself.
# For this repository one file took 15.7 ± 1.9 ms and sixteen 20.0 ± 1.6 ms (hyperfine,
# 30 runs), so each later file of the batch answers without a subprocess.
_PATCH_BATCH = 16
_PATCH_ENTRIES = 64


def _fallback(status: Status = "unsupported") -> dict[str, Any]:
    return {
        "version": MARKDOWN_DIFF_VERSION,
        "status": status,
        "blocks": [],
        "source_only": False,
    }


def projection_worker(state: Any) -> ProjectionWorker:
    """The server's projection worker, which a test may replace before a request."""

    worker = getattr(state, "pull_rendered_diff_worker", None)
    if worker is None:
        worker = state.pull_rendered_diff_worker = ProjectionWorker()
    return cast("ProjectionWorker", worker)


def _path(side: EntrySide) -> GitPath:
    raw = (
        base64.b64decode(side.path_b64, validate=True)
        if side.path_b64 is not None
        else side.path.encode()
    )
    return GitPath(tuple(raw.split(b"/")))


def _projectable(change: FileChange) -> bool:
    if change.availability is not Availability.ready or change.binary:
        return False
    sides = [side for side in (change.old, change.new) if side is not None]
    return bool(sides) and all(
        side.entry_type is EntryType.file
        and side.content.kind is ContentRefKind.git_object
        and blob_logical_ext(_path(side)) in _MARKDOWN
        for side in sides
    )


class _Patches:
    """Patches of projectable Markdown files, hydrated a batch per `git diff`."""

    def __init__(self) -> None:
        self._kept: OrderedDict[tuple[str, ...], FilePatch] = OrderedDict()

    async def get(
        self,
        key: tuple[str, ...],
        source: GitDiffSource,
        comparison: Any,
        manifest: ChangeSetManifest,
        file_id: str,
    ) -> FilePatch | None:
        if (*key, file_id) in self._kept:
            self._kept.move_to_end((*key, file_id))
            return self._kept[(*key, file_id)]
        files = manifest.files
        at = next(index for index, change in enumerate(files) if change.id == file_id)
        # The files after this one in the manifest's order, as a reader scrolls to them.
        later = [
            change.id
            for change in files[at + 1 :]
            if _projectable(change) and (*key, change.id) not in self._kept
        ]
        batch = [file_id, *later[: _PATCH_BATCH - 1]]
        hydrated = await source.hydrate(comparison, batch, manifest=manifest)
        patches = dict(hydrated.patches)
        if file_id not in patches and len(batch) > 1:
            # Past one run's bound, a file that fits alone is asked for alone.
            alone = await source.hydrate(comparison, [file_id], manifest=manifest)
            patches.update(alone.patches)
        for each in batch:
            if each in patches:
                self._kept[(*key, each)] = patches[each]
        while len(self._kept) > _PATCH_ENTRIES:
            self._kept.popitem(last=False)
        return patches.get(file_id)


async def _project(
    published: PublishedSource, snapshot: Snapshot, file_id: str, namespace: str, state: Any
) -> dict[str, Any]:
    from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
    from metabrowser.kpress_adapter import document_stylesheets

    target = RepositoryStoreTarget(published.git_dir, published.object_format)
    source = GitDiffSource(GitLocation.revision(target, snapshot.head))
    comparison = await shared_pull_manifest(published, snapshot.base, snapshot.head)
    resolved, manifest = comparison.resolved, comparison.manifest
    if resolved.left.id != snapshot.base or resolved.right.id != snapshot.head:
        return _fallback()
    change = next((entry for entry in manifest.files if entry.id == file_id), None)
    if change is None or not _projectable(change):
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
    patches = getattr(state, "pull_rendered_diff_patches", None)
    if patches is None:
        patches = state.pull_rendered_diff_patches = _Patches()
    patch = await cast("_Patches", patches).get(
        (published.store_id, snapshot.base, snapshot.head), source, resolved, manifest, file_id
    )
    if patch is None or not patch.hunks:
        return _fallback()
    rewrite: Callable[[str, bool], str | None] | None = None
    if change.new is not None:
        path = _path(change.new)

        def head_reference(href: str, image: bool) -> str | None:
            return snapshot.reference(path, href, image)

        rewrite = head_reference

    prepared = await projection_worker(state).prepare(
        old=old, new=new, patch=patch, namespace=namespace
    )
    projection = bind_markdown_diff(prepared, rewrite)
    if sum(len(block["html"].encode()) for block in projection["blocks"]) > _MAX_HTML_BYTES:
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
        # One load at a time: under the GIL a second thread doubled every other
        # request's delay (35 to 74-84 ms for eight wake-ups) and projected no more per
        # second (37 in 1.5 s with one thread, 37-38 with two). The client asks for one
        # file at a time and retries a refused one.
        cache = state.pull_rendered_diff_cache = LoadingCache(max_values=32, max_loads=1)
    cache = cast("LoadingCache[tuple[str, ...], dict[str, Any]]", cache)
    key = (published.store_id, snapshot.store, str(number), base, head, file_id)
    namespace = "diff-" + hashlib.sha256("\0".join(key).encode()).hexdigest()[:20]
    try:
        answer = await cache.get(
            key, lambda: _project(published, snapshot, file_id, namespace, state)
        )
    except LoadingCacheBusyError:
        return JSONResponse({"code": "rendered_diff_busy"}, status_code=429, headers=_NO_STORE)
    except (DiffSourceError, GitError):
        return JSONResponse(
            {"code": "rendered_objects_unavailable"}, status_code=409, headers=_NO_STORE
        )
    except GitPathError:
        answer = _fallback()
    return JSONResponse(answer, headers=_NO_STORE)
