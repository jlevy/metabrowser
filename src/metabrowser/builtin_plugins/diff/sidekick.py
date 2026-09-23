"""Data hooks for the built-in diff plugin.

``GET /api/plugin/diff/document?path=<rel>`` parses the patch file into
File Diff Format and returns the hydrated document — the same shape
``metab --diff`` emits and the conformance corpus validates, so the
browser model never sees a plugin-specific envelope. A virtual path
``<patch>/<inner>`` (the container contract) returns the same document
narrowed to that one file change. On a pinned Git revision the patch
address is a ``GitPath`` ``g1-`` prefix; the inner path is the remainder.

``GET /api/plugin/diff/children?path=<rel>`` lists the change entries as
nav-tree child rows for the container affordance.

``GET /api/plugin/diff/comparison?revision=<rev>`` (or ``?left=&right=``)
serves the same document for a Git comparison at the active subject's
``GitLocation``, so the history view renders diffs through this plugin's
view instead of growing a diff surface of its own. A pinned revision
does not need a working tree.

The patch handlers read through the content reader, which serves an attached
folder and a pinned revision alike and keeps the blocking part off the event
loop for both; the bounded parse runs in the thread pool. The comparison
handler is async because ``git`` is.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse

from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, parse_unified_patch
from metabrowser.diff.format import (
    Availability,
    ChangeSetDocument,
    ChangeSetManifest,
    FileChange,
    FilePatch,
    ResolvedComparison,
    Totals,
    dump_document,
)
from metabrowser.git.process import GitError
from metabrowser.git.repo import repo_info
from metabrowser.git.routes import session_git_location
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.plugin_api import (
    ContentReadError,
    ContentUnavailableError,
    read_content_window,
    resolve_content_container,
)

if TYPE_CHECKING:
    from starlette.requests import Request

_PATCH_EXTS = (".patch", ".diff")

# Hunks hydrated per comparison request. A commit view shows its files
# in order and the rest stay `deferred` — a declared gap, not a silent
# truncation — so one oversized commit cannot stall the panel. Sized to
# cover ordinary commits whole; measured against this repository's own
# history, where the 95th-percentile commit touches far fewer files.
MAX_HYDRATED_FILES = 50


def _error(kind: str, message: str, status: int, *, path: str) -> JSONResponse:
    return JSONResponse({"error": kind, "message": message, "path": path}, status_code=status)


def _parse_bytes(data: bytes) -> ChangeSetDocument:
    return parse_unified_patch(data[: MAX_PATCH_BYTES + 1])


async def _patch_document(
    subpath: str, *, error_kind: str
) -> tuple[ChangeSetDocument, str] | JSONResponse:
    """Resolve a real or virtual patch identity and parse it.

    The content reader performs the nearest-container walk, scoped to this
    plugin's own extensions so one plugin cannot open another's files, and the
    bounded read; the parse runs in the thread pool. One byte past the cap
    keeps the parser's own truncation reporting authoritative, and bounding the
    read keeps a multi-GB file from ever landing in memory on the request path.
    """

    try:
        found = await resolve_content_container(subpath, suffixes=_PATCH_EXTS)
        if found is None:
            return _error(error_kind, "This file is not available.", 404, path=subpath)
        ref, inner = found
        window = await read_content_window(ref, max_bytes=MAX_PATCH_BYTES + 1)
    except ContentReadError:
        # Every way a patch fails to arrive is the same thing to this view:
        # there is no change set to render at that address.
        return _error(error_kind, "This file is not available.", 404, path=subpath)
    return await asyncio.to_thread(_parse_bytes, window.data), inner


def _change_display_path(change: FileChange) -> str:
    side = change.new if change.new is not None else change.old
    return side.path if side is not None else ""


def _narrow_to_path(document: ChangeSetDocument, inner: str) -> ChangeSetDocument | None:
    """The same document, filtered to every change at path *inner*.

    Usually one change. A patch file records a type change as a delete
    plus an add at the same path — what git reports as one ``T`` entry —
    so a path can name more than one change, and the reader asking about
    that path wants both halves, not an arbitrary one.
    """
    matches = [c for c in document.manifest.files if _change_display_path(c) == inner]
    if not matches:
        return None
    patches = {c.id: document.patches[c.id] for c in matches if c.id in document.patches}
    # Binary changes contribute zero lines exactly, the same rule the
    # whole document follows; only an uncounted text change (deferred,
    # unsupported) makes the narrowed totals estimates.
    counted = [c for c in matches if c.additions is not None or c.binary]
    exact = len(counted) == len(matches)
    manifest = document.manifest.model_copy(
        update={
            "files": tuple(matches),
            "totals": Totals.model_construct(
                files=len(matches),
                additions=sum(c.additions or 0 for c in matches) if exact else None,
                deletions=sum(c.deletions or 0 for c in matches) if exact else None,
                exact=exact,
            ),
            "truncated": False,
            "cursor": None,
        }
    )
    return document.model_copy(update={"manifest": manifest, "patches": patches})


async def document_handler(request: Request) -> JSONResponse:
    """One patch file — or one change inside it — as a ChangeSetDocument."""
    subpath = request.query_params.get("path", "")
    opened = await _patch_document(subpath, error_kind="diff_document")
    if isinstance(opened, JSONResponse):
        return opened
    document, inner = opened
    if inner:
        narrowed = _narrow_to_path(document, inner)
        if narrowed is None:
            return _error(
                "diff_document",
                "This change set has no entry for that path.",
                404,
                path=subpath,
            )
        document = narrowed
    return JSONResponse(dump_document(document))


async def comparison_handler(request: Request) -> JSONResponse:
    """A Git comparison at the active subject's location, as a ChangeSetDocument.

    ``?revision=<rev>`` compares a commit against its first parent — the
    same resolution ``metab --diff REV`` performs. ``?left=&right=``
    compares two endpoints. Hunks are hydrated up to a bound; the rest
    stay ``deferred``, which the renderer states rather than eliding.
    ``&file=<path>`` narrows to one change and hydrates it regardless of
    the bound — the deferred sections' on-demand loader.
    On a pinned revision, ``HEAD`` is that object id.
    """
    revision = request.query_params.get("revision", "").strip()
    wanted_file = request.query_params.get("file", "").strip()
    left = request.query_params.get("left", "").strip()
    right = request.query_params.get("right", "").strip()
    if revision:
        intent: dict[str, Any] = {"revision": revision}
    elif left and right:
        intent = {"left": left, "right": right}
    else:
        return _error(
            "diff_comparison",
            "Name a revision, or both endpoints of a comparison.",
            400,
            path=revision or f"{left}..{right}",
        )

    location = session_git_location()
    context, _info = await repo_info(location)
    if context is None:
        if location.pinned_revision is not None:
            return _error(
                "diff_comparison",
                "This revision is not a readable Git repository.",
                404,
                path=revision,
            )
        return _error(
            "diff_comparison",
            "This folder is not the root of a Git repository.",
            404,
            path=revision,
        )

    source = GitDiffSource(context.command_location())
    try:
        resolved = await source.resolve(intent)
        manifest = await source.manifest(resolved)
        projected: list[FileChange] = []
        hydrate_ids: list[str] = []
        for change in manifest.files:
            if wanted_file and _change_display_path(change) != wanted_file:
                continue
            if change.availability is not Availability.ready:
                projected.append(change)
                continue
            if not wanted_file and len(hydrate_ids) >= MAX_HYDRATED_FILES:
                projected.append(change.model_copy(update={"availability": Availability.deferred}))
                continue
            projected.append(change)
            hydrate_ids.append(change.id)
        if wanted_file and not projected:
            return _error(
                "diff_comparison",
                "This comparison has no entry for that path.",
                404,
                path=wanted_file,
            )
        # One diff run and one parse for the whole set (review R3): a
        # commit click costs O(1) subprocesses, not O(files).
        patches: dict[str, FilePatch] = (
            await source.file_patches(resolved, hydrate_ids) if hydrate_ids else {}
        )
    except DiffSourceError as exc:
        # The source's own refusals carry user-facing messages: unknown
        # revision, no such file in the comparison.
        return _error("diff_comparison", str(exc), 404, path=revision)
    except ContentUnavailableError as exc:
        # A blob the pinned store lacks, found before any diff read it. Typed, so a
        # client can tell it from a failure; the message names only the object id.
        body: dict[str, str] = {"error": exc.code, "message": str(exc), "path": revision}
        oid = getattr(exc, "oid", None)
        if isinstance(oid, str):
            body["oid"] = oid
        return JSONResponse(body, status_code=404, headers={"cache-control": "no-store"})
    except GitError as exc:
        return _error("diff_comparison", str(exc), 502, path=revision)

    if wanted_file:
        counted = [c for c in projected if c.additions is not None or c.binary]
        manifest = manifest.model_copy(
            update={
                "totals": Totals.model_construct(
                    files=len(projected),
                    additions=sum(c.additions or 0 for c in projected)
                    if len(counted) == len(projected)
                    else None,
                    deletions=sum(c.deletions or 0 for c in projected)
                    if len(counted) == len(projected)
                    else None,
                    exact=len(counted) == len(projected),
                ),
                "truncated": False,
                "cursor": None,
            }
        )
    document = _document_from(resolved, manifest, tuple(projected), patches)
    return JSONResponse(dump_document(document))


def _document_from(
    resolved: ResolvedComparison,
    manifest: ChangeSetManifest,
    files: tuple[FileChange, ...],
    patches: dict[str, FilePatch],
) -> ChangeSetDocument:
    return ChangeSetDocument.model_construct(
        schema_="file-diff-v1",
        schema_version=1,
        resolved=resolved,
        manifest=manifest.model_copy(update={"files": files}),
        patches=patches,
    )


async def children_handler(request: Request) -> JSONResponse:
    """The change entries of one patch file, as nav-tree child rows."""
    subpath = request.query_params.get("path", "")
    opened = await _patch_document(subpath, error_kind="diff_children")
    if isinstance(opened, JSONResponse):
        return opened
    document, inner = opened
    if inner:
        # A child listing is asked of the container itself, never of one of
        # its virtual children.
        return _error("diff_children", "This file is not available.", 404, path=subpath)
    # One row per path, not per change: a patch file spells a type change
    # as delete-plus-add at the same path, and two rows sharing a virtual
    # path would be two rows that open the same thing.
    order: list[str] = []
    grouped: dict[str, list[FileChange]] = {}
    for change in document.manifest.files:
        display = _change_display_path(change)
        if not display:
            continue
        if display not in grouped:
            grouped[display] = []
            order.append(display)
        grouped[display].append(change)
    children: list[dict[str, Any]] = []
    for display in order:
        changes = grouped[display]
        entry: dict[str, Any] = {
            "name": display,
            "path": f"{subpath}/{canonical_inventory_path(display)}",
            "badge": "T" if len(changes) > 1 else changes[0].kind.value[:1].upper(),
        }
        if all(c.availability.value != "ready" for c in changes):
            entry["muted"] = True
        children.append(entry)
    return JSONResponse({"children": children, "truncated": document.manifest.truncated})
