"""What this server serves, how fresh it is, and switching what it serves.

``GET /api/source/status`` names the active subject and, for a pinned Git revision, the
commit it is pinned to and the ref that commit was resolved from, plus freshness: the
commit that ref names in the mirror now, the last fetch, and whether a refresh is
running. It is answered from memory, so polling it runs no Git and reads no store, and
it carries an ETag so an unchanged answer is a ``304``. The browser's revision label is
rendered from the same :func:`source_status`, so the label and
``metab --api /api/source/status`` cannot disagree.

``GET /api/source/refs`` lists every one of the mirror's branches or tags for the ref
selector, filtered by name, the default branch first and then newest first, with the
served ref marked. It reads the mirror alone, never the network. An answer the Git
routes' memo can keep is kept under the refs' state, so asking again while no ref moved
runs no Git; past about 9,000 branches, or past ``MAX_REF_ENTRIES`` loose refs, every
listing runs Git.

A folder that is a repository's root answers the same two routes for its own checkout
(:mod:`metabrowser.checkout_revisions`): the refs route lists its branches, tags, and
remote-tracking branches from its own Git directory, and the pin route serves one of them
as a pinned revision, or the working tree again, without writing the checkout.

``POST /api/source/refresh`` starts a background refresh of the served mirror, or joins
the one running, and returns at once. With ``{"for": "commit"}`` it is the fetch a
commit the mirror lacks waits for, which a page asks for by itself only when the mirror
is older than the freshness window. ``POST /api/source/pin`` switches the served pin
to a branch, tag, or commit in the mirror. Both change state or start work, so both are
POST routes with a JSON body behind the application's same-origin guard: content inside
an untrusted page cannot reach them with a link, an image, or a form.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Final, NamedTuple, TypedDict, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from metabrowser.checkout_revisions import (
    CheckoutGitUnsupportedError,
    CheckoutRevisions,
    checkout_ref_name,
    checkout_revisions,
)
from metabrowser.content_errors import ContentReadError
from metabrowser.git.process import GitLocation
from metabrowser.git.ref_state import ref_state
from metabrowser.git.repo import repo_info
from metabrowser.git.route_memo import keep_body, kept_answer
from metabrowser.http_caching import build_scoped_etag, etag_headers, matches_if_none_match
from metabrowser.mirror_refresh import (
    UNSERVED_FRESHNESS,
    FreshnessFields,
    LastOutcome,
    MirrorRef,
    MirrorSession,
    RefKind,
    SelectionError,
    SelectionPendingError,
    SelectionState,
    mirror_session,
)
from metabrowser.paths_safe import _safe_path  # pyright: ignore[reportPrivateUsage]
from metabrowser.source import (
    MAX_CONTAINER_INNER_DEPTH,
    SubjectNotOpenError,
    UnsupportedSourceCapabilityError,
    as_git_revision_subject,
    get_source_session,
    unsupported_source_payload,
)
from metabrowser.view_routes import (
    VIEW_ROUTE_PREFIX,
    decode_safe_view_path,
    decode_view_logical_path,
    format_view_href,
)

if TYPE_CHECKING:
    # Annotations only. The server registers this table for a folder too, so what a
    # function needs from the revision tree source it imports where a pin is served.
    from metabrowser.git.tree_source import GitRevisionSubject

log = logging.getLogger(__name__)

# A pin request is one short ref name or commit ID, and the page's own address. Git
# bounds a ref name at the file system's name length; four KiB holds any real one with
# room for the JSON around it and an address a few levels deep.
MAX_SOURCE_REQUEST_BYTES: Final = 4 * 1024
# A listing answers every matching ref; nothing pages or caps it. Its cost is one
# ``for-each-ref`` of the kind's whole namespace, which the earlier page of 100 rows never
# bounded, so a listing of every ref costs the server what a page did, plus encoding the
# rows. Measured 2026-11-19 in process on macOS, Git 2.50.1, at a load average of 13, on
# synthetic checkouts (``for-each-ref`` and parsing, then the rows encoded as JSON):
#
#   branches                1,301 loose  1,301 packed  10,001 loose  10,001 packed
#   for-each-ref, ms                 77            29           478            120
#   JSON, bytes, encode ms     291 KB, 1.7   291 KB, 1.7   2.2 MB, 12    2.2 MB, 12
#
# What bounds a listing is the store-read policy's output cap and deadline
# (``GIT_SUBPROCESS_MAX_BYTES``, ``GIT_SUBPROCESS_TIMEOUT_S``): about 105 bytes of Git's
# output a ref there, so the cap is reached past about 300,000 refs, and the deadline
# sooner in a repository of loose refs. Past either the listing is refused, as it was
# with a page, rather than cut short. The browser draws only the rows in view, so its
# cost does not grow with the rows (static/source-ref-selector.js, ``ROWS_OVERSCAN``).
# An answer is kept under the refs' state (:func:`_refs_answer_key`), so asking again
# while no ref moved runs no Git, but only an answer the memo can keep: one under its
# ``MAX_ENTRY_BYTES``, about 9,000 branches, from a repository with no more loose refs than
# ``MAX_REF_ENTRIES``. Neither 10,001-branch case above is kept, so each listing there
# costs what the table says.
# The filter is a name fragment; a ref name longer than this is not one a reader types.
REFS_MAX_QUERY_CHARS: Final = 256
# The lists a mirror has, and the ones a checkout has: its remote-tracking branches too.
_MIRROR_REF_KINDS: Final[tuple[RefKind, ...]] = ("branch", "tag")
_CHECKOUT_REF_KINDS: Final[tuple[RefKind, ...]] = ("branch", "tag", "remote")
# What a listing of a kind the subject has no list of is told, by whether a checkout answers.
_KIND_REFUSAL: Final = {
    False: '"kind" is "branch" or "tag"',
    True: '"kind" is "branch", "tag", or "remote"',
}


class SourceStatus(TypedDict):
    """The active subject, its pin when it is a Git revision, and its freshness.

    ``pin`` is the full commit ID every read uses. ``ref`` is the store ref the pin
    was resolved from, as recorded when it opened, and ``ref_name`` the name the
    origin knows it by; both are ``None`` when no ref is known. A filesystem subject
    has no pin, so all three are ``None``. The freshness fields are described by
    :class:`~metabrowser.mirror_refresh.FreshnessFields`; they are empty and
    ``refreshable`` is false unless the subject is a served mirror.

    ``name``, ``origin``, and ``location`` are what a served mirror's page shows where
    a folder's shows its name and path, from
    :class:`~metabrowser.mirror_refresh.MirrorDisplay`: the repository's name as a
    checkout would have it, the address it mirrors, and where the mirror is kept. All
    three are ``None`` for a folder and for a pin with no mirror. ``location`` is the
    one field of any route's answer that names a path in the cache, and ``origin`` is
    the source's address as given, which for a ``file://`` source is a path of the
    reader's. Both are display text, with the home directory as ``~`` when they are
    under it: no route takes either back as an input.

    ``borrows`` is the checkout a served mirror borrows objects from, beside ``location``
    under the same exception, and ``None`` for one that holds its own objects. ``shallow``
    is whether the mirror's history stops at a shallow boundary, as the checkout's does.

    A revision a folder's server shows of its own checkout is a pin with no origin:
    ``name`` is the folder's name, ``location`` the checkout's path, shown as a folder's
    is, ``origin`` is ``None``, and nothing is refreshable, since Metabrowser fetches
    nothing into a checkout. ``GET /api/identity`` says such a subject's ``kind`` is
    still ``folder``.
    """

    subject: str
    generation: int
    pin: str | None
    ref: str | None
    ref_name: str | None
    name: str | None
    origin: str | None
    location: str | None
    borrows: str | None
    shallow: bool
    refreshable: bool
    latest: str | None
    # False when the origin deleted the ref. None for a pin by commit ID, a ref not yet
    # observed, or one the store swept (``cache/lender.py``) until a fetch names it again.
    ref_on_origin: bool | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    stale: bool
    pull_request: int | None
    selection_state: SelectionState | None
    selection_href: str | None


def source_status(
    mirror: MirrorSession | None = None, checkout: CheckoutRevisions | None = None
) -> SourceStatus:
    """The envelope for the active session. Reads no store and runs no Git.

    *checkout* is the served checkout's revisions, which name a revision of it.
    """

    session = get_source_session()
    pin = as_git_revision_subject(session.subject)
    if pin is not None and checkout is not None and checkout.serves(pin):
        return SourceStatus(
            subject=pin.kind,
            generation=session.generation,
            pin=pin.commit_oid,
            ref=pin.ref,
            ref_name=checkout_ref_name(pin.ref),
            name=checkout.display.name,
            origin=None,
            location=checkout.display.location,
            borrows=None,
            shallow=checkout.shallow,
            **UNSERVED_FRESHNESS,
        )
    if pin is not None:
        from metabrowser.git.tree_source import ref_short_name

        freshness: FreshnessFields = (
            mirror.freshness_fields(pin) if mirror is not None else UNSERVED_FRESHNESS
        )
        display = mirror.mirror.display if mirror is not None else None
        return SourceStatus(
            subject=pin.kind,
            generation=session.generation,
            pin=pin.commit_oid,
            ref=pin.ref,
            ref_name=ref_short_name(pin.ref),
            name=display.name if display is not None else None,
            origin=display.origin if display is not None else None,
            location=display.location if display is not None else None,
            borrows=display.borrows if display is not None else None,
            shallow=mirror.shallow() if mirror is not None else False,
            **freshness,
        )
    return SourceStatus(
        subject=session.subject.kind,
        generation=session.generation,
        pin=None,
        ref=None,
        ref_name=None,
        name=None,
        origin=None,
        location=None,
        borrows=None,
        shallow=False,
        **UNSERVED_FRESHNESS,
    )


def _status_etag(status: SourceStatus) -> str:
    """A validator for exactly this envelope: any field that changes changes it."""

    body = json.dumps(status, sort_keys=True, separators=(",", ":")).encode()
    return build_scoped_etag(hashlib.sha256(body).hexdigest()[:32])


async def api_source_status(request: Request) -> Response:
    """``GET /api/source/status`` — the active subject, its pin, and its freshness."""

    status = source_status(mirror_session(request.app), checkout_revisions())
    etag = _status_etag(status)
    headers = etag_headers(etag)
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(status), headers=headers)


class SourceRef(TypedDict):
    """One row of ``/api/source/refs``: a :class:`MirrorRef` and whether it is served.

    ``default`` marks a mirror's default branch and ``checked_out`` the branch a
    checkout's ``HEAD`` is on; each lists first, and the other is false.
    ``committed_at`` is the commit's committer date in epoch seconds, from which a row
    shows its age; ``None`` when Git printed none. The page shows ``commit`` as every line
    names a commit (``shortCommit`` in static/formatters.js).
    """

    name: str
    ref: str
    commit: str
    committed_at: float | None
    default: bool
    checked_out: bool
    current: bool


class WorkingTree(TypedDict):
    """A checkout's working tree, the choice a ref list has beside its refs.

    ``current`` is whether the server serves it now. ``head`` is the full ref ``HEAD`` is
    on and ``head_name`` the branch's name, both ``None`` when ``HEAD`` is detached.
    ``name`` is the folder's name and ``location`` its path with the home directory as
    ``~``, as the page names the folder: display text, with any control or invisible
    character already replaced. The page keeps the name whole where the path ends with
    it, in the platform's separator; at the home directory the path is ``~`` alone.
    """

    current: bool
    head: str | None
    head_name: str | None
    name: str
    location: str


class SourceRefs(TypedDict):
    """The envelope of ``GET /api/source/refs``.

    ``refs`` are every matching ref, in listing order: the default or checked-out branch
    first, then newest first by the date each row shows (``_newest_first`` in
    ``cache/resolve.py``). ``pin`` and ``ref`` are what the server serves now, so the
    selector marks the served ref even when the page was rendered for another; both are
    ``None`` while a checkout's working tree is served. ``kinds`` are the lists the subject has: a
    checkout's remote-tracking branches are a third. ``working_tree`` is ``None`` for a
    mirror, which has none.
    """

    kind: RefKind
    query: str
    pin: str | None
    ref: str | None
    kinds: list[RefKind]
    working_tree: WorkingTree | None
    refs: list[SourceRef]


def source_refs(
    listed: tuple[MirrorRef, ...],
    subject: GitRevisionSubject | None,
    *,
    kind: RefKind,
    query: str,
    working_tree: WorkingTree | None = None,
) -> SourceRefs:
    """Every ref of *listed* that matches *query*, a case-insensitive name fragment.

    *subject* is the served revision, ``None`` on a checkout's working tree, and
    *working_tree* is given for a checkout, whose first-listed branch is the one checked
    out where a mirror's is its default.
    """

    needle = query.casefold()
    matches = [entry for entry in listed if needle in entry.name.casefold()]
    of_checkout = working_tree is not None
    served_ref = subject.ref if subject is not None else None
    return SourceRefs(
        kind=kind,
        query=query,
        pin=subject.commit_oid if subject is not None else None,
        ref=served_ref,
        kinds=list(_CHECKOUT_REF_KINDS if of_checkout else _MIRROR_REF_KINDS),
        working_tree=working_tree,
        refs=[
            SourceRef(
                name=entry.name,
                ref=entry.ref,
                commit=entry.commit,
                committed_at=entry.committed_at,
                default=entry.default and not of_checkout,
                checked_out=entry.default and of_checkout,
                current=served_ref is not None and entry.ref == served_ref,
            )
            for entry in matches
        ],
    )


async def _refs_answer_key(
    location: GitLocation,
    *,
    kind: RefKind,
    query: str,
    subject: GitRevisionSubject | None,
    first_ref: str | None,
) -> tuple[str, ...] | None:
    """What a listing is kept under in the Git routes' memo, or ``None`` to keep nothing.

    Everything the answer reads: the repository's refs, whose state
    :func:`~metabrowser.git.ref_state.ref_state` names; the list and the filter; what is
    served, which marks a row and says whether the working tree is; and *first_ref*, the
    branch listed first and marked. That is a mirror's default branch, which its store
    records outside its refs, or the branch a checkout's ``HEAD`` is on as
    :func:`~metabrowser.git.repo.repo_info` names it, which ``working_tree`` reports too.
    ``repo_info`` keeps ``HEAD`` for ``GIT_REPO_INFO_TTL_S``, so the state alone, which
    reads ``HEAD`` afresh, could key a listing made from the ``HEAD`` it kept before a
    switch, and serve it until a ref moved; ``/api/git/refs`` keys its answer on
    ``HEAD``'s ref for the same reason. The served root's name and path cannot change
    while it is served, and a new root empties the memo. ``None`` when the state cannot
    be named, as for a repository with more loose refs than one state may stat
    (``MAX_REF_ENTRIES``).
    """

    state = await ref_state(location)
    if state is None:
        return None
    return (
        "source-refs",
        location.identity,
        kind,
        query,
        subject.commit_oid if subject is not None else "",
        (subject.ref or "") if subject is not None else "",
        first_ref or "",
        state,
    )


def _encoded_refs(
    listed: tuple[MirrorRef, ...],
    subject: GitRevisionSubject | None,
    *,
    kind: RefKind,
    query: str,
    working_tree: WorkingTree | None,
) -> bytes:
    """The listing's body, as :func:`keep_body` keeps it, filtered and encoded.

    Run off the event loop: its cost grows with every ref the namespace holds, which only
    Git's output cap bounds. Measured 2026-11-19 at a load average of about 20, filtering
    10,001 refs took 7 ms and encoding them 13 ms.
    """

    page = source_refs(listed, subject, kind=kind, query=query, working_tree=working_tree)
    return bytes(JSONResponse(dict(page)).body)


async def api_source_refs(request: Request) -> Response:
    """``GET /api/source/refs?kind=branch|tag|remote&q=`` — the refs to choose among.

    A mirror's branches or tags, read from the mirror alone. A checkout's branches, tags,
    or remote-tracking branches (``kind=remote``), read from its own Git directory, with
    ``working_tree`` saying whether its working tree is served. A plain folder, a
    subdirectory of a checkout, or a pin with no mirror answers
    ``unsupported_for_subject`` (409); a ``kind`` the subject has no list of, or an
    overlong ``q``, ``invalid_request`` (400).

    The answer is kept in the Git routes' memo (:mod:`metabrowser.git.route_memo`) under
    :func:`_refs_answer_key`, and carries that memo's entity tag, so the same listing
    asked again while no ref moved runs no Git. Measured 2026-11-19 at a load average of
    13: naming the state took 20 ms over 1,301 loose branches and 0.4 ms packed, against
    the 77 and 29 ms a listing takes. The memo keeps only what it can: a body over its
    ``MAX_ENTRY_BYTES``, past about 9,000 branches, is served and not kept, and a
    repository with more loose refs than ``MAX_REF_ENTRIES`` has no state to key on, so
    every listing of either runs Git. Both 10,001-branch checkouts measured beside
    ``REFS_MAX_QUERY_CHARS`` are such, the packed one by its body and the loose one by
    its 20,001 loose refs.
    """

    params = request.query_params
    kind = params.get("kind", "branch")
    query = params.get("q", "")
    if len(query) > REFS_MAX_QUERY_CHARS:
        return _error("the filter is too long", "invalid_request", 400)
    try:
        source = _switchable(request, "refs")
    except UnsupportedSourceCapabilityError as exc:
        # A kind no subject has is refused as before, whatever is served.
        if kind not in _CHECKOUT_REF_KINDS:
            return _error(_KIND_REFUSAL[False], "invalid_request", 400)
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    of_checkout = isinstance(source, CheckoutRevisions)
    if kind not in (_CHECKOUT_REF_KINDS if of_checkout else _MIRROR_REF_KINDS):
        return _error(_KIND_REFUSAL[of_checkout], "invalid_request", 400)
    kind = cast(RefKind, kind)
    subject = as_git_revision_subject(get_source_session().subject)
    working_tree: WorkingTree | None = None
    try:
        if isinstance(source, CheckoutRevisions):
            # HEAD as the listing will read it (`_repository`), and the key names it.
            context, _info = await repo_info(source.root)
            head_ref = context.head["ref"] if context is not None else None
            key = await _refs_answer_key(
                GitLocation.filesystem(source.root),
                kind=kind,
                query=query,
                subject=subject,
                first_ref=head_ref,
            )
            kept = kept_answer(request, key)
            if kept is not None:
                return kept
            # One reading of the repository answers both: its HEAD and its refs.
            head, listed = await source.list_refs(kind)
            if head != head_ref:
                # HEAD was read again between the key and the listing: keep nothing.
                key = None
            working_tree = WorkingTree(
                current=subject is None,
                head=head,
                head_name=checkout_ref_name(head),
                name=source.display.name,
                location=source.display.location,
            )
        else:
            # A mirror is the source only while it serves a pin (`_switchable`).
            pin = cast("GitRevisionSubject", subject)
            default_ref = await source.mirror.default_ref() if kind == "branch" else None
            key = await _refs_answer_key(
                GitLocation.revision(pin.command_target, pin.commit_oid),
                kind=kind,
                query=query,
                subject=pin,
                first_ref=default_ref,
            )
            kept = kept_answer(request, key)
            if kept is not None:
                return kept
            listed = await source.mirror.list_refs(kind, default_ref=default_ref)
    except UnsupportedSourceCapabilityError as exc:
        # Git does not take the served root for a repository's root.
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    except CheckoutGitUnsupportedError as exc:
        # Its own words: the Git needed, and no path.
        return _error(str(exc), exc.code, exc.http_status)
    except ContentReadError as exc:
        # Git's text can name the store, so only the code leaves the server.
        log.warning("listing the refs failed: %s", exc)
        where = "checkout" if isinstance(source, CheckoutRevisions) else "mirror"
        return _error(f"the {where}'s refs could not be listed", exc.code, exc.http_status)
    body = await asyncio.to_thread(
        _encoded_refs, listed, subject, kind=kind, query=query, working_tree=working_tree
    )
    return keep_body(request, key, body)


def _served_mirror(request: Request, capability: str) -> MirrorSession:
    mirror = mirror_session(request.app)
    if mirror is None or as_git_revision_subject(get_source_session().subject) is None:
        raise UnsupportedSourceCapabilityError(capability)
    return mirror


def _switchable(request: Request, capability: str) -> MirrorSession | CheckoutRevisions:
    """What lists refs and switches the pin here: the served mirror, or the served checkout.

    A checkout answers on its working tree and on each of its revisions. Anything else,
    a plain folder or a pin with no mirror, raises
    :class:`UnsupportedSourceCapabilityError`.
    """

    mirror = mirror_session(request.app)
    if mirror is not None and as_git_revision_subject(get_source_session().subject) is not None:
        return mirror
    checkout = checkout_revisions()
    if checkout is None:
        raise UnsupportedSourceCapabilityError(capability)
    return checkout


class _BadRequestError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _json_object(request: Request) -> dict[str, Any]:
    """The request's JSON object body, read to at most :data:`MAX_SOURCE_REQUEST_BYTES`."""

    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_SOURCE_REQUEST_BYTES:
        raise _BadRequestError("the request body is too large", status_code=413)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_SOURCE_REQUEST_BYTES:
            raise _BadRequestError("the request body is too large", status_code=413)
        chunks.append(chunk)
    try:
        decoded = json.loads(b"".join(chunks) or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _BadRequestError("the request body is not JSON") from exc
    if not isinstance(decoded, dict):
        raise _BadRequestError("the request body must be a JSON object")
    return cast(dict[str, Any], decoded)


def _error(message: str, code: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message, "code": code}, status_code=status_code)


def _refresh_request(body: dict[str, Any]) -> tuple[bool, bool]:
    """Whether a refresh request is for a missing commit, and whether it is a retry."""

    unknown = sorted(set(body) - {"for", "retry"})
    if unknown:
        raise _BadRequestError('a refresh request names only "for" and "retry"')
    purpose = body.get("for")
    retry = body.get("retry", False)
    if purpose is not None and purpose != "commit":
        raise _BadRequestError('"for" may only be "commit"')
    if not isinstance(retry, bool) or (retry and purpose is None):
        raise _BadRequestError('"retry" is true or false, and goes with "for"')
    return purpose == "commit", retry


async def api_source_refresh(request: Request) -> JSONResponse:
    """``POST /api/source/refresh`` — start or join a refresh of the served mirror.

    Returns ``202`` as soon as the job is scheduled; the response never waits on the
    network. ``refresh`` says whether this request started the job or joined one that
    was running, and ``status`` is the envelope as of that moment. When only the attended
    pull request is stale and the queue of pull requests has no room for its job, nothing
    starts and the answer is ``429`` with ``too_many``, as the pull-request route says.

    ``{"for": "commit"}`` asks for the fetch a commit the mirror lacks waits for
    (:meth:`~metabrowser.mirror_refresh.MirrorSession.request_commit_fetch`): the
    mirror's branches and tags, and the data served beside it. A page sends it by
    itself for a commit's address, so it fetches the mirror only when the last fetch is
    older than the freshness window; inside the window ``refresh`` is ``"fresh"`` and
    no mirror fetch starts, and the answer is ``200`` unless a refresh of the data
    beside the mirror is running. ``"retry": true`` is a reader's own click and always
    fetches. That answer also carries ``pull_refresh``: how the attended pull request's
    refresh was answered (``started``, ``joined``, or ``too_many`` when the queue had no
    room for it), or null when none was asked for, so a page can tell a fetch that ran
    from one a full queue refused.
    """

    try:
        for_commit, retry = _refresh_request(await _json_object(request))
        mirror = _served_mirror(request, "refresh")
    except _BadRequestError as exc:
        return _error(str(exc), "invalid_request", exc.status_code)
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    pulled: dict[str, Any] = {}
    if for_commit:
        fetch = mirror.request_commit_fetch(retry=retry)
        started: str = fetch.refresh
        pulled["pull_refresh"] = fetch.pull_refresh
    else:
        started = mirror.request_refresh()
    status = source_status(mirror)
    if started == "too_many":
        # Only the attended pull request was stale, and the queue of pull requests is full.
        return JSONResponse(
            {
                "refresh": started,
                "status": dict(status),
                "error": "too many pull requests are being fetched; try again when one has finished",
                "code": "too_many",
            },
            status_code=429,
        )
    # Nothing scheduled and nothing running is an answer, not accepted work.
    accepted = started != "fresh" or status["refreshing"]
    return JSONResponse(
        {"refresh": started, **pulled, "status": dict(status)},
        status_code=202 if accepted else 200,
    )


class _Selection(NamedTuple):
    ref: str | None
    oid: str | None
    under: str | None
    view: str | None
    working_tree: bool


def _selection(body: dict[str, Any], *, checkout: bool = False) -> _Selection:
    """What a pin request selects. *checkout* is whether a checkout answers it.

    Only a checkout has a working tree to return to, and its own refs for ``under``.
    ``view`` is the page's ``/view/`` address as sent, less its query and fragment.
    """

    unknown = sorted(set(body) - {"ref", "oid", "under", "view", "working_tree"})
    if unknown:
        raise _BadRequestError(
            'a pin request names only "ref", "oid", or "working_tree", with "under" and "view"'
            if checkout
            else 'a pin request names only "ref" or "oid", "under", and "view"'
        )
    ref = body.get("ref")
    oid = body.get("oid")
    under = body.get("under")
    view = _view_address(body.get("view"))
    working_tree = body.get("working_tree")
    if working_tree is not None:
        if not checkout:
            raise _BadRequestError('"working_tree" is for a checkout; a mirror has none')
        if working_tree is not True or ref is not None or oid is not None or under is not None:
            raise _BadRequestError('"working_tree" is true, alone or with "view"')
        return _Selection(None, None, None, view, True)
    if (ref is None) == (oid is None):
        raise _BadRequestError('give exactly one of "ref" and "oid"')
    if not isinstance(ref if ref is not None else oid, str):
        raise _BadRequestError("the selection must be a string")
    if under is not None:
        if oid is None or not isinstance(under, str):
            raise _BadRequestError('"under" names the ref a commit given by "oid" is served under')
        # Only a request that names one reads the mirror's ref rules, which a folder's
        # server, registering this table too, never loads (tests/test_plugin_public_api.py).
        from metabrowser.cache.resolve import CHECKOUT_REFS, MIRROR_REFS, is_pinnable_ref

        if not is_pinnable_ref(under, CHECKOUT_REFS if checkout else MIRROR_REFS):
            raise _BadRequestError(
                '"under" is a branch, a tag, or a remote-tracking branch of the checkout'
                if checkout
                else '"under" is an origin branch, a tag, or a pull request\'s refs/pull/<n>/head'
            )
    return _Selection(cast(str | None, ref), cast(str | None, oid), under, view, False)


def _view_address(view: object) -> str | None:
    """The ``/view/`` address a request names, without its query or fragment, or ``None``.

    A page sends its ``location.pathname``, which is percent-encoded ASCII, so anything
    else is refused before the pin switches, with nothing changed.
    """

    if view is None:
        return None
    if not (isinstance(view, str) and view.isascii() and view.startswith(VIEW_ROUTE_PREFIX)):
        raise _BadRequestError('"view" is a /view/ address')
    raw = view.split("?", 1)[0].split("#", 1)[0]
    if len(raw) > len(VIEW_ROUTE_PREFIX):
        raw = raw.removesuffix("/")
    return raw


def _view_identity(address: str | None, *, on_folder: bool = False) -> str | None:
    """The identity a page's ``/view/`` *address* names on the subject it was drawn for.

    ``None`` when the request names no address, and ``""`` for the root. On a pin the
    identity is a ``GitPath`` wire, optionally with a container's inner path. On a
    folder (*on_folder*) it is a path under the served root, contained as the view route
    contains it, and returned as the wire of the same names, which is what a revision
    calls that entry. An address that does not decode, as a stale or hand-written one
    may not, reads as the root.
    """

    if address is None:
        return None
    raw = address.encode("ascii")
    if not on_folder:
        return decode_view_logical_path(raw) or ""
    native = decode_safe_view_path(raw)
    if not native:
        return ""
    from metabrowser.git.tree_source import GitPath, GitPathError

    try:
        return GitPath.from_segments(*(os.fsencode(part) for part in native.split("/"))).to_wire()
    except (GitPathError, ValueError):
        return ""


def _folder_view(identity: str) -> str:
    """Where the entry a revision calls *identity* is in the served folder. Blocking.

    The same names as a path under the root, when the folder has that entry; the root
    otherwise. An entry inside a container file keeps its address when the folder has
    the container. Containment is the folder's own (``paths_safe``), so a name that
    would leave the root, or that this platform cannot spell, is the root.
    """

    from metabrowser.git.tree_source import GitPathError, split_git_container_wire

    try:
        git_path, inner = split_git_container_wire(identity)
        native = "/".join(os.fsdecode(segment) for segment in git_path.segments)
    except (GitPathError, ValueError):
        return VIEW_ROUTE_PREFIX
    if not native or any(part in {".", ".."} for part in native.split("/")):
        return VIEW_ROUTE_PREFIX
    target = _safe_path(native)
    try:
        if target is None or not target.exists():
            return VIEW_ROUTE_PREFIX
        if inner:
            if inner.count("/") + 1 > MAX_CONTAINER_INNER_DEPTH or not target.is_file():
                return VIEW_ROUTE_PREFIX
            return format_view_href(f"{native}/{inner}")
        return format_view_href(native) + ("/" if target.is_dir() else "")
    except (OSError, ValueError):
        return VIEW_ROUTE_PREFIX


async def view_on_pin(subject: GitRevisionSubject, identity: str) -> str:
    """Where a page showing the ``/view/`` *identity* goes on *subject*.

    The same entry, in its canonical spelling, when the revision has it; otherwise the
    root, ``/view/``. An entry inside a container file keeps its address when the
    revision has that file and the inner path is within the container depth bound; the
    view then answers for the inner entry as it would for any link. A line anchor or
    query is not kept: the lines may differ on another revision.
    """

    from metabrowser.git.tree_source import (
        GitPathError,
        resolve_git_blob_entry,
        split_git_container_wire,
    )

    if not identity:
        return VIEW_ROUTE_PREFIX
    try:
        git_path, inner = split_git_container_wire(identity)
        if not git_path.segments:
            return VIEW_ROUTE_PREFIX
        if inner:
            if inner.count("/") + 1 > MAX_CONTAINER_INNER_DEPTH:
                return VIEW_ROUTE_PREFIX
            container = await resolve_git_blob_entry(subject.tree_source, git_path)
            return VIEW_ROUTE_PREFIX if container is None else format_view_href(identity)
        entry = await subject.tree_source.resolve_path(git_path)
    except (GitPathError, ContentReadError, ValueError) as exc:
        log.debug("the page's address is not in the new pin: %s", exc)
        return VIEW_ROUTE_PREFIX
    if entry is None:
        return VIEW_ROUTE_PREFIX
    return VIEW_ROUTE_PREFIX + git_path.to_wire() + ("/" if entry.is_tree else "")


# The first characters of a ``GitPath`` wire segment, which a revision's address begins with.
_WIRE_SEGMENT: Final = "g1-"


async def crossed_view_href(raw_path: bytes) -> str | None:
    """Where a ``/view/`` address written for the other side of a checkout goes, or ``None``.

    A checkout's server shows its working tree or one of its revisions, and the two name
    an entry differently: a folder by its path, a revision by a ``GitPath`` wire. An
    address of one, kept by a tab, a history entry, or a bookmark, can arrive while the
    other is served. This answers the address to send it to instead, by the translation
    a switch's ``view_href`` uses:

    - on a revision, a folder's path goes to the same names in the revision when it has
      them, and to the root otherwise, where it would be refused as no address at all;
    - on the working tree, a revision's wire goes to the same names in the folder when
      it has them, and to the root otherwise. The caller asks only for an address the
      folder has no entry by, and one that merely begins as a wire does is the folder's
      own missing path.

    ``None`` for any other server, and for an address that needs no translation.
    """

    checkout = checkout_revisions()
    if checkout is None:
        return None
    try:
        address = _view_address(raw_path.decode("ascii"))
    except (UnicodeDecodeError, _BadRequestError):
        return None
    if address is None:
        return None
    pin = as_git_revision_subject(get_source_session().subject)
    if pin is not None:
        identity = _view_identity(address, on_folder=True)
        return await view_on_pin(pin, identity) if identity else VIEW_ROUTE_PREFIX
    identity = decode_view_logical_path(address.encode("ascii")) or ""
    if not identity.startswith(_WIRE_SEGMENT):
        return None
    from metabrowser.git.tree_source import GitPathError, split_git_container_wire

    try:
        split_git_container_wire(identity)
    except (GitPathError, ValueError):
        # Not a wire, only a name that begins as one: the folder's own missing path.
        return None
    return await asyncio.to_thread(_folder_view, identity)


async def api_source_pin(request: Request) -> JSONResponse:
    """``POST /api/source/pin`` — serve another branch, tag, or commit of the mirror.

    The body is ``{"ref": "<branch or tag>"}`` or ``{"oid": "<commit ID>"}``, and
    optionally ``"view"``, the ``/view/`` address the page shows: the answer's
    ``view_href`` is then where that page goes on the new pin (:func:`view_on_pin`).
    With ``"oid"``, ``"under"`` names the full ref the commit is served under, as View on
    branch names ``refs/pull/<n>/head``; when the mirror's ref is not at the commit, as
    for a page drawn before the pull request moved on, nothing is switched and the answer
    is ``409`` with ``ref_moved``.
    The selection is resolved in the mirror alone: a branch, then a tag, then a commit ID.
    In a server, one the mirror lacks answers ``202`` with ``selection_pending`` and
    starts one background fetch; asking again after it ends answers the switch or
    ``404``.
    On success the old tree source is closed, the new one attached under a new session
    generation, and ``status`` is the new envelope; ``changed`` is false when the
    selection names what is already served.

    A folder that is a repository's root answers for its own checkout. The selection is
    resolved in the checkout's refs alone, a branch, then a tag, then a remote-tracking
    branch, then a commit ID, and nothing is fetched for one it lacks, which is ``404``.
    The revision is served in the folder's place, read from the checkout's Git objects
    and under the untrusted profile, and the checkout is not written.
    ``{"working_tree": true}`` serves the folder again. ``view_href`` crosses between the
    folder's addresses and the revision's: the same names on the other side when the
    entry is there, else the root.
    """

    try:
        body = await _json_object(request)
        source = _switchable(request, "pin")
        selection = _selection(body, checkout=isinstance(source, CheckoutRevisions))
        # Where the page is, read on the subject it was drawn for, before any switch.
        identity = _view_identity(
            selection.view,
            on_folder=as_git_revision_subject(get_source_session().subject) is None,
        )
    except _BadRequestError as exc:
        return _error(str(exc), "invalid_selection", exc.status_code)
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    mirror = source if isinstance(source, MirrorSession) else None
    checkout = source if isinstance(source, CheckoutRevisions) else None

    def status() -> dict[str, Any]:
        return dict(source_status(mirror, checkout))

    try:
        if selection.working_tree:
            assert checkout is not None
            changed, session = await checkout.serve_working_tree()
        else:
            changed, session = await source.switch_pin(
                ref=selection.ref, oid=selection.oid, under=selection.under
            )
    except SelectionPendingError as exc:
        return JSONResponse(
            {"error": str(exc), "code": exc.code, "refresh": exc.refresh, "status": status()},
            status_code=exc.http_status,
        )
    except SelectionError as exc:
        return _error(str(exc), exc.code, exc.http_status)
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    except CheckoutGitUnsupportedError as exc:
        return _error(str(exc), exc.code, exc.http_status)
    except ContentReadError as exc:
        # A Git failure while resolving or opening. Its text can name the store, so
        # only the code leaves the server.
        log.warning("switching the pin failed: %s", exc)
        return _error("the selection could not be opened", exc.code, exc.http_status)
    answer: dict[str, Any] = {"changed": changed, "status": status()}
    switched = as_git_revision_subject(session.subject)
    if identity is not None:
        if switched is not None:
            answer["view_href"] = await view_on_pin(switched, identity)
        elif checkout is not None:
            answer["view_href"] = await asyncio.to_thread(_folder_view, identity)
    return JSONResponse(answer)


# A page on a pin names the commit it was rendered for on every data request
# (static/source-pin-guard.js). A request that names another commit than the one served
# is from a page showing a pin the server no longer serves -- switched since, or served
# by an earlier run of the server -- and is refused rather than answered from the new
# pin, which would mix two revisions on one page. The commit, not the session
# generation, is the token: a generation counts from 1 again in every process.
PIN_HEADER: Final = "x-metabrowser-pin"
PIN_CHANGED_HEADER: Final = "x-metabrowser-pin-changed"
# What the page of a checkout's working tree names where a pin's page names its commit.
# Such a folder's server can come to serve a revision, so its page says what it shows
# too, and is refused rather than answered from the revision. Not a commit ID, which is
# hexadecimal, so it can never name a served pin.
WORKING_TREE_PIN: Final = "working-tree"
_PIN_EXEMPT_PREFIX: Final = "/api/source/"
# The event log's routes (event_log_route.py) answer about the server, whichever revision
# it serves. A page left on an old pin still sends its reports there, the last of them as
# it is left, and its Details read the log, so neither is refused (A4, review A of #629).
_PIN_EXEMPT_EVENT_LOG: Final = "/api/event-log"
# A checkout's Commits tab and a commit's view: answered whichever revision a page names,
# since they read the checkout's history and its Git directory whichever revision Files
# shows (`history_git_location` in git/routes.py). The chooser that switches the served
# revision is in the Files toolbar, which the Commits tab hides, so a refusal there would
# stop the tab at a reload offer its reader cannot see.
_CHECKOUT_HISTORY_PREFIX: Final = "/api/git/"


def pin_changed_response(claimed: str | None) -> JSONResponse | None:
    """Return the standard refusal when a caller names a different served pin."""
    if claimed is None:
        return None
    current = _served_pin()
    if current is None or claimed.strip() == (current or WORKING_TREE_PIN):
        return None
    return JSONResponse(
        {
            "error": "the server now serves another revision; reload the page",
            "code": "pin_changed",
            "pin": current or None,
        },
        status_code=409,
        headers={PIN_CHANGED_HEADER: current, "cache-control": "no-store"},
    )


class SourcePinGuard:
    """Refuse an ``/api`` request made for a commit the server does not serve.

    Only a request that names a commit is checked, so ``curl``, ``metab --api``, and a
    plain folder's page, which send none, are unaffected. The page of a checkout's
    working tree names :data:`WORKING_TREE_PIN`, since its server can serve a revision
    of the checkout instead, and is refused while one is served. The ``/api/source/``
    routes are exempt: a page learns what is served from the status route and switches
    through the pin route. So are the event log's, which are about the server. So are a checkout's ``/api/git/`` routes, which answer the same
    whichever of its revisions is served. A mirror's stay guarded: its freshness row, at
    the foot of the pane, offers the reload on every tab. The refusal is
    ``409 pin_changed`` with the served commit, or
    an empty value when a folder is served, in :data:`PIN_CHANGED_HEADER`, which the page
    reads without consuming the body.

    One request that names nothing is refused too, on a server that can show a working
    tree. A working-tree page takes its guard with the selector's bundle, after its first
    requests, so for a moment it names nothing, and a revision served from another tab in
    that moment would answer it. While a checkout's revision is served, a page's own
    ``fetch`` that names no commit cannot be that revision's page, which names its commit
    from before its first script: it is a page of something else, and is refused as the
    working tree's is. A browser says which requests those are (``Sec-Fetch-Site:
    same-origin`` with ``Sec-Fetch-Dest: empty``); ``curl`` and ``metab --api`` send
    neither and are answered. A mirror has no working tree and no such page, so a
    mirror's server is left as it was: a worker's or a frame's request there, which
    cannot carry the commit, is answered.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and _guarded(scope):
            claimed = _header(scope, PIN_HEADER.encode())
            if (
                claimed is None
                and _own_page_fetch(scope)
                and _served_pin()
                and checkout_revisions() is not None
            ):
                # A page that is not the served revision's, on a server that has a
                # working tree to show: what a working-tree page names. A mirror has no
                # such page, and its requests are checked only by what they name.
                claimed = WORKING_TREE_PIN
            response = pin_changed_response(claimed)
            if response is not None and not _checkout_history(scope):
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _route_path(scope: dict[str, Any]) -> str:
    path = str(scope.get("path") or "")
    root_path = str(scope.get("root_path") or "")
    if root_path and path.startswith(root_path):
        path = path[len(root_path) :]
    return path


def _guarded(scope: dict[str, Any]) -> bool:
    path = _route_path(scope)
    return (
        path.startswith("/api/")
        and not path.startswith(_PIN_EXEMPT_PREFIX)
        and path != _PIN_EXEMPT_EVENT_LOG
        and not path.startswith(f"{_PIN_EXEMPT_EVENT_LOG}/")
    )


def _checkout_history(scope: dict[str, Any]) -> bool:
    """Whether this is a checkout's ``/api/git/`` request, which no switch makes stale.

    Asked only of a request about to be refused, so a page whose pin is served pays
    nothing for it.
    """

    return (
        _route_path(scope).startswith(_CHECKOUT_HISTORY_PREFIX) and checkout_revisions() is not None
    )


def _own_page_fetch(scope: dict[str, Any]) -> bool:
    """Whether a browser says this is a ``fetch`` made by one of this server's own pages.

    The fetch metadata the origin check reads: a script's request to its own origin, as
    ``fetch`` and an event stream are, and not a navigation, an image, or a frame. A
    client that is no browser sends neither header.
    """

    return (
        _header(scope, b"sec-fetch-site") == "same-origin"
        and _header(scope, b"sec-fetch-dest") == "empty"
    )


def _header(scope: dict[str, Any], name: bytes) -> str | None:
    for key, value in scope.get("headers") or []:
        if key == name:
            return bytes(value).decode("latin-1")
    return None


def _served_pin() -> str | None:
    """The served commit, ``""`` for a folder, or ``None`` when nothing is open yet."""

    try:
        subject = get_source_session().subject
    except SubjectNotOpenError:
        return None
    pin = as_git_revision_subject(subject)
    return pin.commit_oid if pin is not None else ""


SOURCE_ROUTES = [
    Route("/api/source/status", api_source_status),
    Route("/api/source/refs", api_source_refs),
    Route("/api/source/refresh", api_source_refresh, methods=["POST"]),
    Route("/api/source/pin", api_source_pin, methods=["POST"]),
]


__all__ = [
    "MAX_SOURCE_REQUEST_BYTES",
    "PIN_CHANGED_HEADER",
    "PIN_HEADER",
    "REFS_MAX_QUERY_CHARS",
    "SOURCE_ROUTES",
    "WORKING_TREE_PIN",
    "SourcePinGuard",
    "SourceRef",
    "SourceRefs",
    "SourceStatus",
    "WorkingTree",
    "api_source_pin",
    "api_source_refresh",
    "api_source_refs",
    "api_source_status",
    "crossed_view_href",
    "source_refs",
    "source_status",
    "view_on_pin",
]
