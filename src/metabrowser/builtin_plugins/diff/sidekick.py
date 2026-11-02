"""Data hooks for the built-in diff plugin.

``GET /api/plugin/diff/document?path=<rel>`` parses the patch file into
File Diff Format and returns the hydrated document — the same shape
``metab --diff`` emits and the conformance corpus validates, so the
browser model never sees a plugin-specific envelope. The file is parsed
whatever it is called, because the kind system, which a plugin may extend,
decides which files open in this view. A virtual path
``<patch>/<inner>`` (the container contract) returns the same document
narrowed to that one file change, inside a ``.patch`` or ``.diff`` file only.
On a pinned Git revision the patch
address is a ``GitPath`` ``g1-`` prefix; the inner path is the remainder.

``GET /api/plugin/diff/children?path=<rel>`` lists the change entries as
nav-tree child rows for the container affordance.

``GET /api/plugin/diff/comparison?revision=<rev>`` (or
``?left=&right=[&base_policy=merge_base]``) serves the same document for
a Git comparison at the active subject's ``GitLocation``, so the history
view renders diffs through this plugin's view instead of growing a diff
surface of its own. A pinned revision does not need a working tree. On a
store, a request naming full commit IDs is kept and validated;
``comparison_cache.py`` says what the answer depends on.

The patch handlers read through the content reader, which serves an attached
folder and a pinned revision alike and keeps the blocking part off the event
loop for both; the bounded parse runs in the thread pool. The comparison
handler is async because ``git`` is.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import re
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.diff.comparison_cache import (
    ComparisonCache,
    ResolvedManifest,
    encode_body,
)
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource, PatchHydration
from metabrowser.diff.adapters.patch_file import (
    MAX_NAMED_SECTIONS,
    MAX_PATCH_BYTES,
    parse_unified_patch,
)
from metabrowser.diff.format import (
    Availability,
    BasePolicy,
    ChangeSetDocument,
    ChangeSetManifest,
    FileChange,
    FilePatch,
    ResolvedComparison,
    Totals,
    dump_document,
)
from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget
from metabrowser.git.repo import repo_info
from metabrowser.git.routes import session_git_location
from metabrowser.http_caching import (
    BUILD_TAG,
    build_scoped_etag,
    etag_headers,
    immutable_headers,
    matches_if_none_match,
)
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.plugin_api import (
    ContentReadError,
    read_content_window,
    resolve_content,
    resolve_content_container,
)

if TYPE_CHECKING:
    from starlette.requests import Request

    from metabrowser.plugin_api import ContentRef

_PATCH_EXTS = (".patch", ".diff")

# Hunks hydrated per comparison request. A commit view shows its files
# in order and the rest stay `deferred` — a declared gap, not a silent
# truncation — so one oversized commit cannot stall the panel. Sized to
# cover ordinary commits whole; measured against this repository's own
# history, where the 95th-percentile commit touches far fewer files.
MAX_HYDRATED_FILES = 50

# A revision compares against its first parent; only two endpoints choose a base.
_TWO_ENDPOINT_POLICIES = frozenset({BasePolicy.direct.value, BasePolicy.merge_base.value})

# A commit ID in full: SHA-1 or SHA-256. Anything else names what it names now.
_FULL_COMMIT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")

_COMPARISONS = ComparisonCache()


def _error(kind: str, message: str, status: int, *, path: str) -> JSONResponse:
    return JSONResponse({"error": kind, "message": message, "path": path}, status_code=status)


def _parse_bytes(data: bytes) -> ChangeSetDocument:
    return parse_unified_patch(data[: MAX_PATCH_BYTES + 1])


async def _resolve_patch(subpath: str, *, any_name: bool) -> tuple[ContentRef, str] | None:
    """The content a request names, and the inner path when it names a virtual child.

    With ``any_name``, a file the request names itself is read whatever it is
    called. Which files are diffs is the kind system's decision, and a plugin may
    add match rules to the ``diff`` kind, so the name is not this hook's to check.
    That is what 0.11.0 did, and a file holding no diff answers an empty change
    set with a warning.

    ``<patch>/<inner>`` is the container contract, and stays scoped to this
    plugin's own extensions: the content reader performs the nearest-container
    walk and resolves a virtual child only inside a file this plugin claims. The
    reader compares the logical extension, so ``change.patch.gz`` is claimed too.
    """

    if any_name:
        direct = await resolve_content(subpath)
        if direct is not None:
            return direct, ""
    return await resolve_content_container(subpath, suffixes=_PATCH_EXTS)


async def _patch_document(
    subpath: str, *, error_kind: str, any_name: bool = False
) -> tuple[ChangeSetDocument, str] | JSONResponse:
    """Resolve a real or virtual patch identity and parse it.

    The content reader performs the resolution and the bounded read; the parse
    runs in the thread pool. One byte past the cap keeps the parser's own
    truncation reporting authoritative, and bounding the read keeps a multi-GB
    file from ever landing in memory on the request path.
    """

    try:
        found = await _resolve_patch(subpath, any_name=any_name)
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
    opened = await _patch_document(subpath, error_kind="diff_document", any_name=True)
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


def _kept_key(location: GitLocation, intent: dict[str, Any]) -> tuple[str, ...] | None:
    """The comparison's key in memory, or None for one whose answer can change.

    A store, and a request whose every endpoint is a full commit ID. A folder's answer
    depends on its working tree and its configuration, and a name's on where it points now.
    """
    if not isinstance(location.target, RepositoryStoreTarget):
        return None
    endpoints = [intent[name] for name in ("revision", "left", "right") if name in intent]
    if not all(_FULL_COMMIT_ID.fullmatch(endpoint) for endpoint in endpoints):
        return None
    policy = str(intent.get("base_policy", ""))
    return (str(location.target.git_dir), *endpoints, policy)


def _encoded_response(request: Request, encoded: bytes, headers: dict[str, str]) -> Response:
    """An answer kept compressed. It goes as it is, which the server's compression leaves be."""
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(
            encoded,
            media_type="application/json",
            headers={**headers, "Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )
    return Response(
        gzip.decompress(encoded),
        media_type="application/json",
        headers={**headers, "Vary": "Accept-Encoding"},
    )


async def comparison_handler(request: Request) -> Response:
    """A Git comparison at the active subject's location, as a ChangeSetDocument.

    ``?revision=<rev>`` compares a commit against its first parent — the
    same resolution ``metab --diff REV`` performs. ``?left=&right=``
    compares two endpoints, directly or, with ``&base_policy=merge_base``,
    from their merge base, as a pull request's Files changed does. Hunks are
    hydrated up to a bound; the rest stay ``deferred``, which the renderer
    states rather than eliding.
    ``&file=<path>`` narrows to one change and hydrates it regardless of
    the bound — the deferred sections' on-demand loader.
    On a pinned revision, ``HEAD`` is that object id.

    A request naming two commit IDs on a store sends an entity tag, answers a matching
    ``If-None-Match`` with 304, and is kept in memory. With ``&build=`` naming this build it
    is immutable as well, since the address then says everything its answer depends on.
    """
    revision = request.query_params.get("revision", "").strip()
    wanted_file = request.query_params.get("file", "").strip()
    left = request.query_params.get("left", "").strip()
    right = request.query_params.get("right", "").strip()
    base_policy = request.query_params.get("base_policy", "").strip()
    if base_policy and (revision or base_policy not in _TWO_ENDPOINT_POLICIES):
        return _error(
            "diff_comparison",
            "base_policy is direct or merge_base, and only for a left and right comparison.",
            400,
            path=revision or f"{left}..{right}",
        )
    if revision:
        intent: dict[str, Any] = {"revision": revision}
    elif left and right:
        intent = {"left": left, "right": right, "base_policy": base_policy or "direct"}
    else:
        return _error(
            "diff_comparison",
            "Name a revision, or both endpoints of a comparison.",
            400,
            path=revision or f"{left}..{right}",
        )

    location = session_git_location()
    kept_key = _kept_key(location, intent)
    headers: dict[str, str] = {}
    if kept_key is not None:
        answer_key = (*kept_key, wanted_file)
        identity = hashlib.sha256("\0".join(answer_key[1:]).encode()).hexdigest()[:32]
        etag = build_scoped_etag(f"comparison-{identity}")
        immutable = request.query_params.get("build", "") == BUILD_TAG
        headers = immutable_headers(etag) if immutable else etag_headers(etag)
        if matches_if_none_match(request, etag):
            return Response(status_code=304, headers=headers)
        encoded = _COMPARISONS.body(answer_key)
        if encoded is not None:
            return _encoded_response(request, encoded, headers)

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

    async def listed() -> ResolvedManifest:
        resolved = await source.resolve(intent)
        return ResolvedManifest(resolved, await source.manifest(resolved))

    try:
        comparison = (
            await listed() if kept_key is None else await _COMPARISONS.manifest(kept_key, listed)
        )
        resolved, manifest = comparison.resolved, comparison.manifest
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
        hydration = (
            await source.hydrate(resolved, hydrate_ids, manifest=manifest)
            if hydrate_ids
            else PatchHydration({})
        )
    except DiffSourceError as exc:
        # The source's own refusals carry user-facing messages: unknown
        # revision, no such file in the comparison.
        return _error("diff_comparison", str(exc), 404, path=revision)
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
    if hydration.left_out:
        projected, resolved = _say_left_out(projected, resolved, hydration.left_out)
    document = _document_from(resolved, manifest, tuple(projected), hydration.patches)
    # A large answer is seconds of serializing and compressing, so neither is done on the
    # event loop: 29 MB took 712 ms to serialize, measured in explorations/performance-loop.
    body = await asyncio.to_thread(_json_body, document)
    if kept_key is None:
        return Response(body, media_type="application/json")
    encoded = await asyncio.to_thread(encode_body, body)
    _COMPARISONS.remember_body((*kept_key, wanted_file), encoded)
    return _encoded_response(request, encoded, headers)


def _json_body(document: ChangeSetDocument) -> bytes:
    return bytes(JSONResponse(dump_document(document)).body)


def _say_left_out(
    files: list[FileChange], resolved: ResolvedComparison, left_out: tuple[str, ...]
) -> tuple[list[FileChange], ResolvedComparison]:
    """Mark the files the diff did not produce, and name them, keeping every other file."""
    gone = set(left_out)
    marked = [
        change.model_copy(update={"availability": Availability.failed})
        if change.id in gone
        else change
        for change in files
    ]
    named = [_change_display_path(change) for change in files if change.id in gone]
    said = ", ".join(named[:MAX_NAMED_SECTIONS])
    more = len(named) - MAX_NAMED_SECTIONS
    warning = f"{len(named)} file(s) could not be read from the produced diff: {said}"
    warnings = (*resolved.warnings, f"{warning}, and {more} more" if more > 0 else warning)
    return marked, resolved.model_copy(update={"warnings": warnings})


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
