"""What this server serves, how fresh it is, and switching what it serves.

``GET /api/source/status`` names the active subject and, for a pinned Git revision, the
commit it is pinned to and the ref that commit was resolved from, plus freshness: the
commit that ref names in the mirror now, the last fetch, and whether a refresh is
running. It is answered from memory, so polling it runs no Git and reads no store, and
it carries an ETag so an unchanged answer is a ``304``. The browser's revision label is
rendered from the same :func:`source_status`, so the label and
``metab --api /api/source/status`` cannot disagree.

``GET /api/source/refs`` lists the mirror's branches or tags for the ref selector,
filtered and bounded, with the default branch first and the served ref marked. It reads
the mirror alone, never the network.

``POST /api/source/refresh`` starts a background refresh of the served mirror, or joins
the one running, and returns at once. ``POST /api/source/pin`` switches the served pin
to a branch, tag, or commit in the mirror. Both change state or start work, so both are
POST routes with a JSON body behind the application's same-origin guard: content inside
an untrusted page cannot reach them with a link, an image, or a form.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Final, TypedDict, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from metabrowser.content_errors import ContentReadError
from metabrowser.git.tree_source import (
    GitPathError,
    GitRevisionSubject,
    ref_short_name,
    resolve_git_blob_entry,
    split_git_container_wire,
)
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
from metabrowser.source import (
    MAX_CONTAINER_INNER_DEPTH,
    SubjectNotOpenError,
    UnsupportedSourceCapabilityError,
    get_source_session,
    unsupported_source_payload,
)
from metabrowser.view_routes import (
    VIEW_ROUTE_PREFIX,
    decode_view_logical_path,
    format_view_href,
)

log = logging.getLogger(__name__)

# A pin request is one short ref name or commit ID, and the page's own address. Git
# bounds a ref name at the file system's name length; four KiB holds any real one with
# room for the JSON around it and an address a few levels deep.
MAX_SOURCE_REQUEST_BYTES: Final = 4 * 1024
# Refs one listing answers. The selector shows a page of plain rows and narrows by the
# filter box rather than scrolling far: a hundred rows is a few kilobytes of JSON, and
# the listing's cost is one ``for-each-ref`` of the namespace whatever the page size.
# A caller's limit is clamped to the range, as the ``/api/git/`` routes clamp theirs.
REFS_DEFAULT_LIMIT: Final = 100
REFS_MAX_LIMIT: Final = 1000
# The filter is a name fragment; a ref name longer than this is not one a reader types.
REFS_MAX_QUERY_CHARS: Final = 256
_REF_KINDS: Final = ("branch", "tag")


class SourceStatus(TypedDict):
    """The active subject, its pin when it is a Git revision, and its freshness.

    ``pin`` is the full commit ID every read uses. ``ref`` is the store ref the pin
    was resolved from, as recorded when it opened, and ``ref_name`` the name the
    origin knows it by; both are ``None`` when no ref is known. A filesystem subject
    has no pin, so all three are ``None``. The freshness fields are described by
    :class:`~metabrowser.mirror_refresh.FreshnessFields`; they are empty and
    ``refreshable`` is false unless the subject is a served mirror.
    """

    subject: str
    generation: int
    pin: str | None
    ref: str | None
    ref_name: str | None
    refreshable: bool
    latest: str | None
    ref_on_origin: bool | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    stale: bool
    pull_request: int | None
    selection_state: SelectionState | None
    selection_href: str | None


def source_status(mirror: MirrorSession | None = None) -> SourceStatus:
    """The envelope for the active session. Reads no store and runs no Git."""

    session = get_source_session()
    subject = session.subject
    if isinstance(subject, GitRevisionSubject):
        freshness: FreshnessFields = (
            mirror.freshness_fields(subject) if mirror is not None else UNSERVED_FRESHNESS
        )
        return SourceStatus(
            subject=subject.kind,
            generation=session.generation,
            pin=subject.commit_oid,
            ref=subject.ref,
            ref_name=ref_short_name(subject.ref),
            **freshness,
        )
    return SourceStatus(
        subject=subject.kind,
        generation=session.generation,
        pin=None,
        ref=None,
        ref_name=None,
        **UNSERVED_FRESHNESS,
    )


def _status_etag(status: SourceStatus) -> str:
    """A validator for exactly this envelope: any field that changes changes it."""

    body = json.dumps(status, sort_keys=True, separators=(",", ":")).encode()
    return build_scoped_etag(hashlib.sha256(body).hexdigest()[:32])


async def api_source_status(request: Request) -> Response:
    """``GET /api/source/status`` — the active subject, its pin, and its freshness."""

    status = source_status(mirror_session(request.app))
    etag = _status_etag(status)
    headers = etag_headers(etag)
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(status), headers=headers)


class SourceRef(TypedDict):
    """One row of ``/api/source/refs``: a :class:`MirrorRef` and whether it is served."""

    name: str
    ref: str
    commit: str
    default: bool
    current: bool


class SourceRefs(TypedDict):
    """The envelope of ``GET /api/source/refs``.

    ``refs`` are the matching refs in listing order, at most ``limit`` of them;
    ``total`` counts every match, and ``truncated`` says the page stops short of it.
    ``pin`` and ``ref`` are what the server serves now, so the selector marks the
    served ref even when the page was rendered for another.
    """

    kind: RefKind
    query: str
    limit: int
    pin: str
    ref: str | None
    total: int
    truncated: bool
    refs: list[SourceRef]


def source_refs(
    listed: tuple[MirrorRef, ...],
    subject: GitRevisionSubject,
    *,
    kind: RefKind,
    query: str,
    limit: int,
) -> SourceRefs:
    """The page of *listed* that matches *query*, a case-insensitive name fragment."""

    needle = query.casefold()
    matches = [entry for entry in listed if needle in entry.name.casefold()]
    return SourceRefs(
        kind=kind,
        query=query,
        limit=limit,
        pin=subject.commit_oid,
        ref=subject.ref,
        total=len(matches),
        truncated=len(matches) > limit,
        refs=[
            SourceRef(
                name=entry.name,
                ref=entry.ref,
                commit=entry.commit,
                default=entry.default,
                current=entry.ref == subject.ref,
            )
            for entry in matches[:limit]
        ],
    )


def _refs_limit(value: str | None) -> int:
    try:
        limit = int(value) if value is not None else REFS_DEFAULT_LIMIT
    except ValueError:
        limit = REFS_DEFAULT_LIMIT
    return max(1, min(limit, REFS_MAX_LIMIT))


async def api_source_refs(request: Request) -> JSONResponse:
    """``GET /api/source/refs?kind=branch|tag&q=&limit=`` — the mirror's branches or tags.

    Read from the mirror alone. A folder, or a pin with no mirror, answers
    ``unsupported_for_subject`` (409); an unknown ``kind`` or an overlong ``q``,
    ``invalid_request`` (400).
    """

    params = request.query_params
    kind = params.get("kind", "branch")
    query = params.get("q", "")
    if kind not in _REF_KINDS:
        return _error('"kind" is "branch" or "tag"', "invalid_request", 400)
    if len(query) > REFS_MAX_QUERY_CHARS:
        return _error("the filter is too long", "invalid_request", 400)
    try:
        mirror = _served_mirror(request, "refs")
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    subject = get_source_session().subject
    assert isinstance(subject, GitRevisionSubject)
    try:
        listed = await mirror.mirror.list_refs(kind)
    except ContentReadError as exc:
        # Git's text can name the store, so only the code leaves the server.
        log.warning("listing the mirror's refs failed: %s", exc)
        return _error("the mirror's refs could not be listed", exc.code, exc.http_status)
    page = source_refs(
        listed,
        subject,
        kind=kind,
        query=query,
        limit=_refs_limit(params.get("limit")),
    )
    return JSONResponse(dict(page))


def _served_mirror(request: Request, capability: str) -> MirrorSession:
    mirror = mirror_session(request.app)
    if mirror is None or not isinstance(get_source_session().subject, GitRevisionSubject):
        raise UnsupportedSourceCapabilityError(capability)
    return mirror


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


async def api_source_refresh(request: Request) -> JSONResponse:
    """``POST /api/source/refresh`` — start or join a refresh of the served mirror.

    Returns ``202`` as soon as the job is scheduled; the response never waits on the
    network. ``refresh`` says whether this request started the job or joined one that
    was running, and ``status`` is the envelope as of that moment.
    """

    try:
        await _json_object(request)
        mirror = _served_mirror(request, "refresh")
    except _BadRequestError as exc:
        return _error(str(exc), "invalid_request", exc.status_code)
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    started = mirror.request_refresh()
    return JSONResponse(
        {"refresh": started, "status": dict(source_status(mirror))}, status_code=202
    )


def _selection(body: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    unknown = sorted(set(body) - {"ref", "oid", "view"})
    if unknown:
        raise _BadRequestError('a pin request names only "ref" or "oid", and "view"')
    ref = body.get("ref")
    oid = body.get("oid")
    view = body.get("view")
    if (ref is None) == (oid is None):
        raise _BadRequestError('give exactly one of "ref" and "oid"')
    if not isinstance(ref if ref is not None else oid, str):
        raise _BadRequestError("the selection must be a string")
    return cast(str | None, ref), cast(str | None, oid), _view_identity(view)


def _view_identity(view: object) -> str | None:
    """The identity a page's ``/view/`` address names; ``""`` for the root.

    ``None`` when the request names no address. Decided before the pin switches, so a
    request that cannot be answered is refused with nothing changed. A page sends its
    ``location.pathname``, which is percent-encoded ASCII, so anything else is refused;
    a query or fragment is dropped, and an address that does not decode, as a stale or
    hand-written one may not, reads as the root.
    """

    if view is None:
        return None
    if not (isinstance(view, str) and view.isascii() and view.startswith(VIEW_ROUTE_PREFIX)):
        raise _BadRequestError('"view" is a /view/ address')
    raw = view.split("?", 1)[0].split("#", 1)[0]
    if len(raw) > len(VIEW_ROUTE_PREFIX):
        raw = raw.removesuffix("/")
    return decode_view_logical_path(raw.encode("ascii")) or ""


async def view_on_pin(subject: GitRevisionSubject, identity: str) -> str:
    """Where a page showing the ``/view/`` *identity* goes on *subject*.

    The same entry, in its canonical spelling, when the revision has it; otherwise the
    root, ``/view/``. An entry inside a container file keeps its address when the
    revision has that file and the inner path is within the container depth bound; the
    view then answers for the inner entry as it would for any link. A line anchor or
    query is not kept: the lines may differ on another revision.
    """

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


async def api_source_pin(request: Request) -> JSONResponse:
    """``POST /api/source/pin`` — serve another branch, tag, or commit of the mirror.

    The body is ``{"ref": "<branch or tag>"}`` or ``{"oid": "<commit ID>"}``, and
    optionally ``"view"``, the ``/view/`` address the page shows: the answer's
    ``view_href`` is then where that page goes on the new pin (:func:`view_on_pin`).
    The selection is resolved in the mirror alone: a branch, then a tag, then a commit ID.
    In a server, one the mirror lacks answers ``202`` with ``selection_pending`` and
    starts one background fetch; asking again after it ends answers the switch or
    ``404``.
    On success the old tree source is closed, the new one attached under a new session
    generation, and ``status`` is the new envelope; ``changed`` is false when the
    selection names what is already served.
    """

    try:
        ref, oid, view = _selection(await _json_object(request))
        mirror = _served_mirror(request, "pin")
    except _BadRequestError as exc:
        return _error(str(exc), "invalid_selection", exc.status_code)
    except UnsupportedSourceCapabilityError as exc:
        return JSONResponse(unsupported_source_payload(exc), status_code=409)
    try:
        changed, session = await mirror.switch_pin(ref=ref, oid=oid)
    except SelectionPendingError as exc:
        return JSONResponse(
            {
                "error": str(exc),
                "code": exc.code,
                "refresh": exc.refresh,
                "status": dict(source_status(mirror)),
            },
            status_code=exc.http_status,
        )
    except SelectionError as exc:
        return _error(str(exc), exc.code, exc.http_status)
    except ContentReadError as exc:
        # A Git failure while resolving or opening. Its text can name the store, so
        # only the code leaves the server.
        log.warning("switching the pin failed: %s", exc)
        return _error("the selection could not be opened", exc.code, exc.http_status)
    answer: dict[str, Any] = {"changed": changed, "status": dict(source_status(mirror))}
    if view is not None and isinstance(session.subject, GitRevisionSubject):
        answer["view_href"] = await view_on_pin(session.subject, view)
    return JSONResponse(answer)


# A page on a pin names the commit it was rendered for on every data request
# (static/source-pin-guard.js). A request that names another commit than the one served
# is from a page showing a pin the server no longer serves -- switched since, or served
# by an earlier run of the server -- and is refused rather than answered from the new
# pin, which would mix two revisions on one page. The commit, not the session
# generation, is the token: a generation counts from 1 again in every process.
PIN_HEADER: Final = "x-metabrowser-pin"
PIN_CHANGED_HEADER: Final = "x-metabrowser-pin-changed"
_PIN_EXEMPT_PREFIX: Final = "/api/source/"


class SourcePinGuard:
    """Refuse an ``/api`` request made for a commit the server does not serve.

    Only a request that names a commit is checked, so ``curl``, ``metab --api``, and a
    folder page, which send none, are unaffected. The ``/api/source/`` routes are
    exempt: a page learns what is served from the status route and switches through
    the pin route. The refusal is ``409 pin_changed`` with the served commit, or an
    empty value when a folder is served, in :data:`PIN_CHANGED_HEADER`, which the page
    reads without consuming the body.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and _guarded(scope):
            claimed = _header(scope, PIN_HEADER.encode())
            current = _served_pin() if claimed is not None else None
            if claimed is not None and current is not None and claimed != current:
                response = JSONResponse(
                    {
                        "error": "the server now serves another revision; reload the page",
                        "code": "pin_changed",
                        "pin": current or None,
                    },
                    status_code=409,
                    headers={PIN_CHANGED_HEADER: current, "cache-control": "no-store"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _guarded(scope: dict[str, Any]) -> bool:
    path = str(scope.get("path") or "")
    root_path = str(scope.get("root_path") or "")
    if root_path and path.startswith(root_path):
        path = path[len(root_path) :]
    return path.startswith("/api/") and not path.startswith(_PIN_EXEMPT_PREFIX)


def _header(scope: dict[str, Any], name: bytes) -> str | None:
    for key, value in scope.get("headers") or []:
        if key == name:
            return bytes(value).decode("latin-1").strip()
    return None


def _served_pin() -> str | None:
    """The served commit, ``""`` for a folder, or ``None`` when nothing is open yet."""

    try:
        subject = get_source_session().subject
    except SubjectNotOpenError:
        return None
    return subject.commit_oid if isinstance(subject, GitRevisionSubject) else ""


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
    "REFS_DEFAULT_LIMIT",
    "REFS_MAX_LIMIT",
    "REFS_MAX_QUERY_CHARS",
    "SOURCE_ROUTES",
    "SourcePinGuard",
    "SourceRef",
    "SourceRefs",
    "SourceStatus",
    "api_source_pin",
    "api_source_refresh",
    "api_source_refs",
    "api_source_status",
    "source_refs",
    "source_status",
    "view_on_pin",
]
