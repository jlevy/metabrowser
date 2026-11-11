"""``GET github/pull-rendered-diff``: one changed Markdown file of an admitted comparison.

The envelope's ``rendered_route`` names the comparison; a page appends ``file``, the
manifest ID of the file. The pair passes the same admission check as
``GET github/pull-snapshot``, and the answer is ``markdown-diff-v1``
(:mod:`metabrowser.diff.markdown_projection`) or a refusal with its own code. A page's
request sent before the reader asks names ``prefetch=1``, which also starts the projection
process, so the first screen of Changes is computed while the reader is still on
Conversation.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, cast

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, admitted_snapshot
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
from metabrowser.loading_cache import LoadingCache

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
# A later file joins the batch only when the manifest counts its changed lines and they
# are few enough for a pair the projection could answer: the 434 real pairs of at most
# 48 KiB change p50 14, p90 75 and at most 722 lines. Without this, fifteen 216 KB
# rewrites the route would refuse anyway were hydrated beside a 4-line file, which took
# 1.3 s instead of 18-55 ms and kept 102 MB (review E of #349).
_BATCH_FILE_LINES = 1_000
_BATCH_LINES = 2_000
# What the route keeps of hydrated patches, in patch lines: at most a few dozen pairs.
_KEPT_LINES = 20_000
# Loads that wait for the projection slot before more are refused (see _Slot).
_MAX_WAITING = 4


def _fallback(status: Status = "unsupported") -> dict[str, Any]:
    return {
        "version": MARKDOWN_DIFF_VERSION,
        "status": status,
        "blocks": [],
        "source_only": False,
    }


class _Busy(Exception):
    """More loads wait for the projection slot than the route keeps waiting."""


class _Slot:
    """One load at a time per server; a few more wait their turn, and the rest are refused.

    Under the GIL a second projection thread doubled every other request's delay (35 to
    74-84 ms for eight wake-ups) and projected no more per second (37 in 1.5 s with one
    thread, 37-38 with two); the child process runs one projection at a time anyway. A
    page asks for one file at a time and keeps its request when the file scrolls away, so
    each open Changes tab holds at most one place; past four waiting, a load would wait
    four projections, and the page's own retry serves the reader better.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._waiting = 0

    async def run[T](self, load: Callable[[], Awaitable[T]]) -> T:
        if self._waiting >= _MAX_WAITING:
            raise _Busy
        self._waiting += 1
        try:
            await self._lock.acquire()
        finally:
            self._waiting -= 1
        try:
            return await load()
        finally:
            self._lock.release()


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


def _lines_of(patch: FilePatch) -> int:
    return sum(len(hunk.lines) for hunk in patch.hunks)


class _Patches:
    """Patches of projectable Markdown files, hydrated a few small ones per `git diff`."""

    def __init__(self) -> None:
        self._kept: OrderedDict[tuple[str, ...], FilePatch] = OrderedDict()
        self._lines = 0

    def _keep(self, key: tuple[str, ...], patch: FilePatch) -> None:
        if key in self._kept:
            return
        self._kept[key] = patch
        self._lines += _lines_of(patch)
        while self._lines > _KEPT_LINES and len(self._kept) > 1:
            _, dropped = self._kept.popitem(last=False)
            self._lines -= _lines_of(dropped)

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
        # The small projectable files after this one in the manifest's order, as a reader
        # scrolls to them.
        batch, budget = [file_id], _BATCH_LINES
        for change in files[at + 1 :]:
            if len(batch) == _PATCH_BATCH:
                break
            changed = (
                None
                if change.additions is None or change.deletions is None
                else change.additions + change.deletions
            )
            if (
                changed is not None
                and changed <= min(_BATCH_FILE_LINES, budget)
                and _projectable(change)
                and (*key, change.id) not in self._kept
            ):
                batch.append(change.id)
                budget -= changed
        hydrated = await source.hydrate(comparison, batch, manifest=manifest)
        patches = dict(hydrated.patches)
        if file_id not in patches and len(batch) > 1:
            # Past one run's bound, a file that fits alone is asked for alone.
            alone = await source.hydrate(comparison, [file_id], manifest=manifest)
            patches.update(alone.patches)
        for each in batch:
            if each in patches:
                self._keep((*key, each), patches[each])
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
    file_id = params.get("file", "")
    if (
        number is None
        or not is_full_revision(base)
        or not is_full_revision(head)
        or not file_id
        or len(file_id) > 128
    ):
        return JSONResponse({"code": "invalid_rendered_diff"}, status_code=400, headers=_NO_STORE)
    snapshot = Snapshot(number, base, head, params.get("store", ""), "head")
    published, admission = await admitted_snapshot(request, snapshot)
    if admission == "unknown":
        return JSONResponse({"code": "snapshot_unavailable"}, status_code=409, headers=_NO_STORE)
    if published is None:
        return JSONResponse({"code": "snapshot_expired"}, status_code=410, headers=_NO_STORE)

    state = request.app.state
    if params.get("prefetch") == "1":
        projection_worker(state).start()
    cache = getattr(state, "pull_rendered_diff_cache", None)
    if cache is None:
        cache = state.pull_rendered_diff_cache = LoadingCache(max_values=32)
    cache = cast("LoadingCache[tuple[str, ...], dict[str, Any]]", cache)
    slot = getattr(state, "pull_rendered_diff_slot", None)
    if slot is None:
        slot = state.pull_rendered_diff_slot = _Slot()
    slot = cast("_Slot", slot)
    key = (published.store_id, snapshot.store, str(number), base, head, file_id)
    namespace = "diff-" + hashlib.sha256("\0".join(key).encode()).hexdigest()[:20]
    try:
        answer = await cache.get(
            key, lambda: slot.run(lambda: _project(published, snapshot, file_id, namespace, state))
        )
    except _Busy:
        return JSONResponse({"code": "rendered_diff_busy"}, status_code=429, headers=_NO_STORE)
    except (DiffSourceError, GitError):
        return JSONResponse(
            {"code": "rendered_objects_unavailable"}, status_code=409, headers=_NO_STORE
        )
    except GitPathError:
        answer = _fallback()
    return JSONResponse(answer, headers=_NO_STORE)
