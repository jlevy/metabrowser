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
``comparison_cache.py`` says what the answer depends on. ``&types=`` narrows
the answer to the changed files of those types, the Files tab's File type
vocabulary (``tree_filter.parse_types``, matched by ``file_type_match``), and
``&group=type:<id>`` to those of one File type group, the Files tab's Group by
vocabulary (``tree_groups.parse_group``).

The patch handlers read through the content reader, which serves an attached
folder and a pinned revision alike and keeps the blocking part off the event
loop for both; the bounded parse runs in the thread pool. The comparison
handler is async because ``git`` is.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.diff.comparison_cache import (
    ComparisonCache,
    ResolvedManifest,
    encode_body,
)
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import (
    GitDiffSource,
    PatchHydration,
    mark_past_the_bounds,
    say_left_out,
)
from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, parse_unified_patch
from metabrowser.diff.format import (
    Availability,
    BasePolicy,
    ChangeSetDocument,
    ChangeSetManifest,
    EntryType,
    FileChange,
    FilePatch,
    ResolvedComparison,
    Totals,
    dump_document,
)
from metabrowser.diff.side_lines import MAX_LINES_ANSWER_BYTES, side_lines, side_lines_before
from metabrowser.file_type_match import (
    change_in_type_group,
    change_matches_types,
    change_sides,
    semantic_extension_tokens,
    type_tally,
)
from metabrowser.git.process import (
    GitError,
    GitLocation,
    GitTimeoutError,
    RepositoryStoreTarget,
    failure_detail,
)
from metabrowser.git.repo import repo_info
from metabrowser.git.routes import session_git_location
from metabrowser.http_caching import (
    BUILD_TAG,
    build_scoped_etag,
    etag_headers,
    immutable_headers,
    matches_if_none_match,
    store_tag,
)
from metabrowser.inventory_engine.contract import canonical_inventory_path
from metabrowser.plugin_api import (
    ContentReadError,
    read_content_window,
    resolve_content,
    resolve_content_container,
)
from metabrowser.settings import DIFF_GAP_LINES, TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.tree_filter import parse_types
from metabrowser.tree_groups import parse_group

if TYPE_CHECKING:
    from starlette.requests import Request

    from metabrowser.plugin_api import ContentRef

log = logging.getLogger(__name__)

_PATCH_EXTS = (".patch", ".diff")

# Hunks hydrated per comparison request. A commit view shows its files
# in order and the rest stay `deferred` — a declared gap, not a silent
# truncation — so one oversized commit cannot stall the panel. Sized to
# cover ordinary commits whole; measured against this repository's own
# history, where the 95th-percentile commit touches far fewer files.
MAX_HYDRATED_FILES = 50

# A revision compares against its first parent; only two endpoints choose a base.
_TWO_ENDPOINT_POLICIES = frozenset({BasePolicy.direct.value, BasePolicy.merge_base.value})

# What a comparison request may answer instead of its document: "" is the document,
# "types" the File type counts the diff view's menu reads, and "lines" a run of one file's
# lines, which the diff view draws where a hunk's gap opens (`_lines_answer`).
_COMPARISON_VIEWS = frozenset({"", "types", "lines"})

# The most one `view=lines` answer reads of a side: the bound a pinned file's text view
# reads one request within. Measured 2026-11-24 on a Mac at a load average near 230, an answer
# of 1,000 lines from the middle of a 16,763,876-byte side took 832-1,048 ms, nearly all of it
# Git's read (`phases=git`), beside 2.0-2.5 s for that file's comparison itself; cutting a
# 16 MiB side into lines, and the answer into JSON, run in `asyncio.to_thread`, off the event
# loop (`_lines_body`; `diff/side_lines.py` measures the cutting).
MAX_LINES_SIDE_BYTES = TEXT_PREVIEW_REQUEST_MAX_BYTES

# A commit ID in full: SHA-1 or SHA-256. Anything else names what it names now.
_FULL_COMMIT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")

_COMPARISONS = ComparisonCache()


async def shared_comparison_manifest(
    key: tuple[str, ...], load: Callable[[], Awaitable[ResolvedManifest]]
) -> ResolvedManifest:
    return await _COMPARISONS.manifest(key, load)


def _error(
    kind: str, message: str, status: int, *, path: str, detail: str = "", code: str = ""
) -> JSONResponse:
    """A refusal: *message* is the sentence the page shows (diff/index.js), *detail* and
    *code* what an agent reads beside it (docs/design-system-messages.md)."""
    body = {"error": kind, "message": message, "path": path}
    if detail:
        body["detail"] = detail
    if code:
        body["code"] = code
    return JSONResponse(body, status_code=status)


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


def comparison_cache_key(
    location: GitLocation, intent: dict[str, Any], store: str
) -> tuple[str, ...] | None:
    """The comparison's key in memory, or None for one whose answer can change.

    A store, named by its Git directory and its token *store*, and a request whose every
    endpoint is a full commit ID. The token is in the key because the store's
    ``info/attributes`` is in the token (review of #284, D2): an edit to it moves every
    address and tag, and has to move what this process holds as well, or a request at the
    new address is answered with the old body. A folder's answer depends on its working
    tree and its configuration, and a name's on where it points now.
    """
    if not isinstance(location.target, RepositoryStoreTarget):
        return None
    endpoints = [intent[name] for name in ("revision", "left", "right") if name in intent]
    if not all(_FULL_COMMIT_ID.fullmatch(endpoint) for endpoint in endpoints):
        return None
    policy = str(intent.get("base_policy", ""))
    return (str(location.target.git_dir), store, *endpoints, policy)


def middleware_sends_gzip(accept_encoding: str) -> bool:
    """The test Starlette's ``GZipMiddleware`` makes of ``Accept-Encoding``, which every
    response passes through on its way out: a plain substring, so ``gzip;q=0`` is taken for
    an acceptance. Read by its weights here instead, a kept body sent unpacked for such a
    client would be compressed again by the middleware, on the event loop, and arrive as
    gzip all the same. ``tests/test_diff_comparison_cache.py`` holds the two tests equal."""
    return "gzip" in accept_encoding


async def _encoded_response(request: Request, encoded: bytes, headers: dict[str, str]) -> Response:
    """An answer kept compressed. It goes as it is, which the server's compression leaves be,
    and is unpacked off the event loop for a client that does not take gzip."""
    if middleware_sends_gzip(request.headers.get("accept-encoding", "")):
        return Response(
            encoded,
            media_type="application/json",
            headers={**headers, "Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )
    return Response(
        await asyncio.to_thread(gzip.decompress, encoded),
        media_type="application/json",
        headers={**headers, "Vary": "Accept-Encoding"},
    )


def _reads_a_checkout() -> bool:
    """Whether the served subject is a revision a folder's server shows of its own checkout."""

    from metabrowser.checkout_revisions import checkout_revisions
    from metabrowser.source import as_git_revision_subject, get_source_session

    return (
        as_git_revision_subject(get_source_session().subject) is not None
        and checkout_revisions() is not None
    )


def _git_failure(exc: GitError, path: str) -> JSONResponse:
    """A Git failure with no command line in the body: its arguments spell every path asked
    for, hostile names included. The detail goes to the log."""
    log.warning("diff/comparison git failure: %s", failure_detail(exc))
    if isinstance(exc, GitTimeoutError):
        return _error(
            "diff_comparison",
            "Comparing these commits took too long. Try again.",
            504,
            path=path,
            detail="git diff timed out",
        )
    return _error(
        "diff_comparison",
        "These changes could not be read from Git.",
        502,
        path=path,
        detail="git diff failed",
    )


async def comparison_handler(request: Request) -> Response:
    """The active subject's Git comparison, through the shared comparison service."""

    return await comparison_at(
        request, session_git_location(), max_initial_files=MAX_HYDRATED_FILES
    )


async def comparison_at(
    request: Request,
    location: GitLocation,
    *,
    max_initial_files: int = MAX_HYDRATED_FILES,
    manifest_loader: Callable[
        [GitDiffSource, dict[str, Any], tuple[str, ...]], Awaitable[ResolvedManifest]
    ]
    | None = None,
    scope: tuple[str, ...] = (),
) -> Response:
    """A Git comparison at the supplied trusted location, as a ChangeSetDocument.

    ``?revision=<rev>`` compares a commit against its first parent — the
    same resolution ``metab --diff REV`` performs. ``?left=&right=``
    compares two endpoints, directly or, with ``&base_policy=merge_base``,
    from their merge base, as a pull request's Files changed does. Hunks are
    hydrated up to a bound; the rest stay ``deferred``, which the renderer
    states rather than eliding.
    ``&file=<path>`` narrows to one change and hydrates it regardless of
    the bound — the deferred sections' on-demand loader. It is the path exactly, since
    a name can begin or end with a space.
    ``&types=`` (repeated or comma-separated, as the Files tab sends it) keeps only
    the changes of those types, either side of a rename counting, before the bound
    is applied, so the hydrated files are the first matching ones. Totals are then the
    kept files'; ``truncated`` still says the listing stopped at its own bound, past
    which a matching file may exist.
    ``&group=type:<id>`` keeps only the changes in one File type group, the registry's
    display group either side classifies into (``file_type_match.change_in_type_group``),
    by the same rule and with the same totals: ``type:docs`` is a change set's documents,
    which a pull request's Docs tab shows. With ``types`` it keeps the changes both keep.
    A group that is no File type group is refused: a comparison's files have no ages.
    ``&view=types`` answers the comparison's File type counts instead of a document
    (``_type_tally_answer``), for the diff view's File type menu: the rows the Files
    tab's menu reads, over every listed change whatever ``types``, ``group`` and
    ``file`` say, so the menu does not shrink as the reader narrows.
    ``&view=lines&file=<path>&start=<n>&count=<m>`` answers lines *n* onward of that
    file's new side, and ``&end=<n>&count=<m>`` in place of ``start`` the lines before line
    *n* (``_lines_answer``): the unchanged lines between its hunks, which the diff view
    asks for when a reader opens a hunk's gap, downward from a hunk or upward to one. At
    most ``DIFF_GAP_LINES`` lines, and a short run where the side's lines are long, cut at
    the end far from the line asked from; ``line_count`` says where the side ends.
    On a pinned revision, ``HEAD`` is that object id.

    A request naming two commit IDs on a store sends an entity tag that names the build
    and the store, answers a matching ``If-None-Match`` with 304 once the store is known
    to answer, and is kept in memory. With ``&build=`` naming this build and ``&store=``
    naming this store it is immutable as well, since the address then says everything
    its answer depends on; a folder's address names no store, and its answer carries
    neither header.

    *scope* names a manifest that is not the two commits' whole comparison, as a native
    stack's is restricted to the files its layers change (``github/pull_stack.py``). It
    extends the key in memory, and so the entity tag and every kept answer, so such a
    manifest never shares an entry with the whole comparison of the same two commits; only a
    *manifest_loader* can answer for one.
    """
    if not 1 <= max_initial_files <= MAX_HYDRATED_FILES:
        raise ValueError(f"max_initial_files must be between 1 and {MAX_HYDRATED_FILES}")
    revision = request.query_params.get("revision", "").strip()
    wanted_file = request.query_params.get("file", "")
    left = request.query_params.get("left", "").strip()
    right = request.query_params.get("right", "").strip()
    base_policy = request.query_params.get("base_policy", "").strip()
    types = parse_types(request.query_params.getlist("types"))
    view = request.query_params.get("view", "")
    if view not in _COMPARISON_VIEWS:
        return _error(
            "diff_comparison",
            "view is types or lines, or absent for the comparison itself.",
            400,
            path=revision or f"{left}..{right}",
        )
    ask = _lines_ask(request) if view == "lines" else None
    if isinstance(ask, str):
        return _error("diff_lines", ask, 400, path=wanted_file)
    wanted_group = request.query_params.get("group", "")
    group = parse_group(wanted_group) if wanted_group else None
    if wanted_group and (group is None or group.by != "type"):
        return _error(
            "diff_comparison",
            "group is a File type group, type:<id>.",
            400,
            path=revision or f"{left}..{right}",
        )
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

    # The token names the store in the key, the tag and the address alike; one stat a request.
    store = (
        store_tag(location.target.git_dir)
        if isinstance(location.target, RepositoryStoreTarget)
        else ""
    )
    kept_key = comparison_cache_key(location, intent, store)
    if scope:
        if manifest_loader is None or kept_key is None:
            raise ValueError("a scoped comparison needs a store and its own manifest loader")
        kept_key = (*kept_key, *scope)
    body_generation = _COMPARISONS.body_generation()
    answer_key: tuple[str, ...] | None = None
    headers: dict[str, str] = {}
    # A validator this process did not issue is honored only once the store has answered
    # for the commits, so a store holding neither answers its plain refusal.
    revalidate = False
    if kept_key is not None:
        # A narrowed answer is kept apart from the whole one. With no types and no group the
        # key is the one it was, so a whole comparison's tag does not move. Each narrowing
        # is named, since a type token may hold `=` or `:` and so spell the other one. The counts depend
        # on the listing alone, so every request for them shares one key.
        answer_key = (
            (*kept_key, "", "view=types")
            if view == "types"
            else (*kept_key, wanted_file, "view=lines", *ask)
            if ask is not None
            else (
                *kept_key,
                wanted_file,
                str(max_initial_files),
                *((f"types={','.join(types)}",) if types else ()),
                *((f"group={group.key}",) if group is not None else ()),
            )
        )
        # The body identity includes the initial hydration count: callers share the
        # manifest, but a PR page and a generic comparison can draw different prefixes.
        identity = hashlib.sha256("\0".join(answer_key[2:]).encode()).hexdigest()[:32]
        etag = build_scoped_etag(f"comparison-{store}-{identity}")
        immutable = (
            request.query_params.get("build", "") == BUILD_TAG
            and request.query_params.get("store", "") == store
        )
        headers = immutable_headers(etag) if immutable else etag_headers(etag)
        if matches_if_none_match(request, etag):
            if _COMPARISONS.has_manifest(kept_key):
                return Response(status_code=304, headers=headers)
            revalidate = True
        else:
            encoded = _COMPARISONS.body(answer_key)
            if encoded is not None:
                return await _encoded_response(request, encoded, headers)

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

    # A comparison this request lists prints its patch in the same run when the two fit, and
    # the hydration below answers from it (H116). A caller's own loader lists without it.
    source = GitDiffSource(context.command_location(), patch_with_listing=manifest_loader is None)

    async def listed() -> ResolvedManifest:
        if manifest_loader is not None and kept_key is not None:
            return await manifest_loader(source, intent, kept_key)
        resolved = await source.resolve(intent)
        return ResolvedManifest(resolved, await source.manifest(resolved))

    try:
        if revalidate:
            await source.resolve(intent)
            return Response(status_code=304, headers=headers)
        comparison = (
            await listed()
            if kept_key is None
            else await shared_comparison_manifest(kept_key, listed)
        )
        resolved, manifest = comparison.resolved, comparison.manifest
        if view == "types":
            tally = await asyncio.to_thread(_type_tally_answer, resolved, manifest)
            return await _send_body(
                request, bytes(JSONResponse(tally).body), answer_key, headers, body_generation
            )
        if ask is not None:
            answer = await _lines_answer(source, resolved, manifest, wanted_file, ask)
            if isinstance(answer, JSONResponse):
                return answer
            return await _send_body(request, answer, answer_key, headers, body_generation)
        projected: list[FileChange] = []
        hydrate_ids: list[str] = []
        semantic = semantic_extension_tokens(types)
        for change in manifest.files:
            if wanted_file and _change_display_path(change) != wanted_file:
                continue
            if types and not change_matches_types(change, types, semantic=semantic):
                continue
            if group is not None and not change_in_type_group(change, group.id):
                continue
            if change.availability is not Availability.ready:
                projected.append(change)
                continue
            if not wanted_file and len(hydrate_ids) >= max_initial_files:
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
        # The source's own refusals: an unknown revision, no such file in the comparison.
        # The page shows the reader's sentence; the one naming the revision is detail.
        return _error(
            "diff_comparison",
            exc.reader_message,
            404,
            path=revision,
            detail=str(exc),
            code=exc.code,
        )
    except GitError as exc:
        if isinstance(location.target, RepositoryStoreTarget):
            from metabrowser.git.object_failures import observed_object_failures

            commits = (revision,) if revision else (left, right)
            observed = observed_object_failures.remember(location.target, commits, exc)
            if observed is not None:
                if observed.state == "object_corrupt" and kept_key is not None:
                    _COMPARISONS.invalidate(kept_key)
                if observed.state == "object_corrupt":
                    message = "Part of this comparison is damaged."
                    detail = "An object in this comparison does not match its ID."
                elif _reads_a_checkout():
                    # A revision of the served checkout, read in place: a partial clone
                    # names objects it does not hold, and nothing is fetched into it.
                    message = "Part of this comparison is not in this checkout."
                    detail = (
                        "An object in this comparison is not in the checkout, "
                        "and nothing is fetched into it."
                    )
                else:
                    message = "Part of this comparison is missing."
                    detail = (
                        "An object in this comparison is missing. "
                        "Repair the repository cache, then retry."
                    )
                return _error(observed.state, message, 409, path=revision, detail=detail)
        return _git_failure(exc, revision)

    if wanted_file:
        manifest = manifest.model_copy(
            update={"totals": listed_totals(projected), "truncated": False, "cursor": None}
        )
    elif types or group is not None:
        manifest = manifest.model_copy(update={"totals": listed_totals(projected)})
    if hydration.left_out:
        projected, resolved = say_left_out(projected, resolved, hydration.left_out)
    projected = mark_past_the_bounds(projected, hydration)
    document = _document_from(resolved, manifest, tuple(projected), hydration.patches)
    # A large answer is seconds of serializing and compressing, so neither is done on the
    # event loop: 29 MB took 712 ms to serialize, measured in explorations/performance-loop.
    body = await asyncio.to_thread(_json_body, document)
    return await _send_body(request, body, answer_key, headers, body_generation)


async def _send_body(
    request: Request,
    body: bytes,
    answer_key: tuple[str, ...] | None,
    headers: dict[str, str],
    generation: object,
) -> Response:
    """Send *body*, kept under *answer_key* when the comparison is one that is kept."""

    if answer_key is None:
        return Response(body, media_type="application/json")
    encoded = await asyncio.to_thread(encode_body, body)
    _COMPARISONS.remember_body(answer_key, encoded, generation=generation)
    return await _encoded_response(request, encoded, headers)


def _type_tally_answer(
    resolved: ResolvedComparison, manifest: ChangeSetManifest
) -> dict[str, object]:
    """A comparison's File type counts: every listed change, once under each type either
    of its sides has (``file_type_match.type_tally``). ``truncated`` says the listing
    stopped at its bound, so the counts are of the listed files."""

    return {
        "comparison_id": resolved.comparison_id,
        "files": len(manifest.files),
        "truncated": manifest.truncated,
        **type_tally(change_sides(change) for change in manifest.files),
    }


def _lines_ask(request: Request) -> tuple[str, str, str] | str:
    """A ``view=lines`` request's anchor (``start`` or ``end``), the line it names, and its
    count, the count at most ``DIFF_GAP_LINES``, or why the request is refused."""

    if not request.query_params.get("file", ""):
        return "view=lines names a file."
    whole = request.query_params.get("whole", "")
    if whole:
        if whole != "1" or any(
            request.query_params.get(key, "") for key in ("start", "end", "count")
        ):
            return "whole=1 asks for the complete new side without line parameters."
        return "whole", "1", str(DIFF_GAP_LINES)
    named = [key for key in ("start", "end") if request.query_params.get(key, "")]
    if len(named) != 1:
        return "view=lines names a start or an end, not both."
    (anchor,) = named
    line = _whole(request.query_params.get(anchor, ""))
    count = _whole(request.query_params.get("count", ""))
    if line is None or count is None:
        return f"{anchor} and count are whole numbers from 1."
    return anchor, str(line), str(min(count, DIFF_GAP_LINES))


def _whole(value: str) -> int | None:
    """*value* as a whole number from 1, in ASCII digits and short enough to be a line's
    number, or None."""

    if not (value.isascii() and value.isdigit() and len(value) <= 12) or int(value) < 1:
        return None
    return int(value)


async def _lines_answer(
    source: GitDiffSource,
    resolved: ResolvedComparison,
    manifest: ChangeSetManifest,
    path: str,
    ask: tuple[str, str, str],
) -> bytes | JSONResponse:
    """Lines of the new side of the change at *path* (``diff/side_lines.py``) as the
    answer's body, or why they cannot be read.

    A refusal is 409 with a ``code``: the change has no new side (``no_side``, a deleted
    file), it is not a file's text (``not_text``: a binary change, a symbolic link, a
    submodule), it is past :data:`MAX_LINES_SIDE_BYTES` (``blob_too_large``), or it is
    diffed through a textconv driver, whose hunks number the conversion's lines
    (``textconv``). The page shows the hunk's separator for it, as it does for a patch
    file, which has no side to read.
    """

    change = next((c for c in manifest.files if _change_display_path(c) == path), None)
    if change is None:
        return _error("diff_lines", "This comparison has no entry for that path.", 404, path=path)
    entry = change.new
    refused: tuple[str, str] | None = None
    if entry is None:
        refused = ("no_side", "this change has no new side")
    elif change.binary or entry.entry_type is not EntryType.file:
        refused = ("not_text", "the new side is not a file's text")
    elif await source.converts(entry.path):
        refused = ("textconv", "this file is diffed through a textconv driver")
    if refused is None and entry is not None:
        try:
            limit = MAX_LINES_ANSWER_BYTES if ask[0] == "whole" else MAX_LINES_SIDE_BYTES
            content = await source.side_bytes(entry, max_bytes=limit)
        except DiffSourceError as exc:
            refused = (exc.code or "no_content", str(exc))
        else:
            head = {"comparison_id": resolved.comparison_id, "file_id": change.id, "path": path}
            return await asyncio.to_thread(_lines_body, head, content, ask)
    code, detail = refused or ("no_content", "")
    return _error(
        "diff_lines", "These lines cannot be shown.", 409, path=path, detail=detail, code=code
    )


def _lines_body(head: dict[str, str], content: bytes, ask: tuple[str, str, str]) -> bytes:
    """The run *ask* names of a side's *content*, as a ``view=lines`` answer's JSON.

    A run is at most ``MAX_LINES_ANSWER_BYTES`` of text but keeps one longer line whole,
    up to the side's own bound, so this and its cutting run off the event loop.
    """

    anchor, line, count = ask
    cut = (side_lines_before if anchor == "end" else side_lines)(content, int(line), int(count))
    return bytes(
        JSONResponse(
            {
                **head,
                "start": cut.start,
                "lines": list(cut.lines),
                "line_count": cut.line_count,
                "ends_with_newline": cut.ends_with_newline,
            }
        ).body
    )


def listed_totals(changes: list[FileChange]) -> Totals:
    """The totals of a narrowed answer's own files, by the rule a listing follows.

    A binary change contributes zero lines exactly; an uncounted text change (unmerged,
    unsupported) makes the line counts unknown.
    """
    counted = [c for c in changes if c.additions is not None or c.binary]
    exact = len(counted) == len(changes)
    return Totals.model_construct(
        files=len(changes),
        additions=sum(c.additions or 0 for c in changes) if exact else None,
        deletions=sum(c.deletions or 0 for c in changes) if exact else None,
        exact=exact,
    )


def _json_body(document: ChangeSetDocument) -> bytes:
    return bytes(JSONResponse(dump_document(document)).body)


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
