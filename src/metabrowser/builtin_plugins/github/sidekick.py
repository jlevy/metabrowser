"""The plugin's data routes, every one the manifest names, all under ``/api/plugin/github/``:
one pull request's (``pull``, ``pull-refresh``, and the routes of its guide, texts, timeline,
comparison, rendered diffs, and their images), the catalog's (``pulls``, ``pulls-refresh``,
``pull-cores-prepare``), every open pull request's status (``pull-statuses``), changed
files (``pull-files``, ``pull-files-refresh``), stacks
(``stacks``, ``stacks-refresh``, ``stack-change``, and a stack's page, ``stack`` and
``stack-comparison``), background prefetch (``pulls-prefetch``),
``cache-clear``, which discards all of a repository's, and ``status``, the GitHub status
check, and ``gh-requests``, the report of what the event log says the servers asked of
GitHub, which any served root answers. The table in
``docs/project/architecture/arch-github-pull-requests.md``, checked against the manifest
by ``tests/test_github_route_table.py``, names each one.

:mod:`metabrowser.builtin_plugins.github.pull_route`,
:mod:`metabrowser.builtin_plugins.github.pull_list_route`, and
:mod:`metabrowser.builtin_plugins.github.pull_files_route` build the answers; this module is
the data hooks the manifest names. The loader imports it at startup, so like the
``/api/cache/`` route table it imports nothing from the cache or the application home
itself: each handler imports the envelope builder, which reaches both, only when it is
requested. Browsing a local directory therefore never loads the cache.

A refresh route starts or joins a refresh job in the refresh coordinator and returns
``202`` at once, never waiting on the network, or says why it started none. It starts work, so it is a ``POST`` with a
JSON object body: the application's same-origin guard and its JSON content-type rule keep
content inside an untrusted page from reaching it with a link, an image, or a form, and a
page for a pin the server no longer serves is refused
``pin_changed`` by the pin guard. Plugin data routes are one path segment, so the
refresh is ``pull-refresh`` beside ``pull``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, Response

from metabrowser.client_disconnect import CLIENT_CLOSED, unless_disconnected
from metabrowser.diff.markdown_projection_worker import start_for_pages
from metabrowser.http_caching import matches_if_none_match
from metabrowser.source import get_source_session
from metabrowser.source_routes import PIN_HEADER, pin_changed_response

if TYPE_CHECKING:
    from starlette.requests import Request

    from metabrowser.builtin_plugins.github.pull_cores import CoreRequest
    from metabrowser.builtin_plugins.github.pull_freshness import RecordFreshness
    from metabrowser.builtin_plugins.github.pull_route import PullEnvelope, PullView
    from metabrowser.builtin_plugins.github.served_pull import PullCorePreview

# The answer changes as the record ages and as a refresh replaces it.
_NO_STORE: Final = {"cache-control": "no-store"}
# A refresh request carries a few short parameters; a JSON object of any size worth reading fits.
MAX_REFRESH_REQUEST_BYTES: Final = 1024
# Eight ready files covered the visible viewport in three paired browser runs on
# public Ruff PRs of 1,031 and 1,627 files (2026-11-03, Chrome 152, 1400x900). One
# left visible reserved space at 1,031. Hydrating fifty cost 112–181 ms in the
# route; eight cost 21 ms. Later files use the existing on-approach loader.
INITIAL_PULL_FILES: Final = 8
# A job started or joined is on its way. A request that started none has its answer now,
# which past the bound on jobs is a refusal.
_REFRESH_STATUS: Final = {
    "started": 202,
    "joined": 202,
    "not_due": 200,
    "not_cached": 200,
    "too_many": 429,
}
_TOO_MANY: Final = {
    "error": "too many pull requests are being fetched; try again when one has finished",
    "code": "too_many",
}


async def _resolve(request: Request) -> None:
    """On a folder, find the served checkout's repository off the loop, once per root.

    A route reads it from memory after this, as it reads a mirror's. Nothing before a
    route is asked for resolves it, so a folder whose Pulls tab is never opened reads none
    of its checkout for this.
    """

    from metabrowser.builtin_plugins.github.checkout import ensure_resolved

    await ensure_resolved(request.app)


def _without_store(envelope: Any) -> bool:
    """Whether the record an envelope carries was written with no store."""

    record = envelope.get("record")
    unavailable = record.get("unavailable") if isinstance(record, dict) else None
    return isinstance(unavailable, dict) and unavailable.get("comparison") == "no_store"


def _drop_core_preview(envelope: PullEnvelope) -> None:
    """Drop a revoked core preview, and the label entries, fast poll, and verdict it alone
    asked for: with no pull request shown there is no head to judge."""

    envelope["core_preview"] = None
    if envelope["record"] is None:
        envelope["repository_labels"] = []
        envelope["labels_pending"] = False
        envelope["readiness"] = None


async def _preview_current(view: PullView, preview: PullCorePreview | None) -> bool:
    """Finish revocation checks on the loop after bounded disk validation."""
    from metabrowser.builtin_plugins.github.pull_route import (
        cached_core_preview_current,
        core_preview_current,
    )

    if preview is None:
        return True
    host = view.host
    if host is None:
        return False
    reader = host.pulls.observed_reader
    identity = host.pulls.core_catalog_identity
    if preview is not view.core_preview and not await asyncio.to_thread(
        cached_core_preview_current, view, preview
    ):
        return False
    # Nothing can revoke the accepted mutable observation between this check and
    # the caller's response construction: no await occurs in this final section.
    return (
        host.pulls.observed_reader == reader
        and host.pulls.core_catalog_identity == identity
        and core_preview_current(view, preview)
    )


async def pull_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull?number=<n>`` — see :mod:`.pull_route`.

    The answer carries an entity tag, and a request whose ``If-None-Match`` names it is
    answered ``304`` without the record, so a page can poll it as cheaply as the status
    route. The tag covers everything but the record, which changes only with
    ``fetched_at``, and the verdict's time, which a ``304`` carries in
    ``x-metabrowser-verified``. A matching ``wait_full_after`` revision may hold the cache read
    briefly until its already-running selected refresh settles or revokes the preview.
    ``warm=1`` marks a read the Pulls tab sends to warm a comparison ahead of a click, which
    is not a view: it is answered the same, and is left out of the numbers a prefetch's
    ``changed`` adds (``pull_prefetch.note_viewed``).
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        envelope_etag,
        follow_adopted_head,
        note_full_record,
        pull_answer,
        pull_host,
        pull_view,
        record_stamp,
        requested_number,
        verified_header,
    )

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    wait_after = request.query_params.get("wait_full_after")
    if wait_after is not None and re.fullmatch(r"[0-9a-f]{64}", wait_after) is None:
        return _invalid_request('"wait_full_after" is a core preview revision')
    warm = request.query_params.get("warm")
    if warm not in (None, "1"):
        return _invalid_request('"warm" is 1')
    claimed_pin = request.headers.get(PIN_HEADER) if wait_after is not None else None
    pinned_subject = None
    if claimed_pin is not None:
        if (refusal := pin_changed_response(claimed_pin)) is not None:
            return refusal
        # Snapshot pin metadata stays tied to the claim even if the pin changes back.
        pinned_subject = get_source_session().subject
    await _resolve(request)

    async def snapshot() -> tuple[
        PullView, tuple[int, int, int] | None, PullEnvelope, RecordFreshness | None
    ]:
        subject = pinned_subject if pinned_subject is not None else get_source_session().subject
        view = pull_view(pull_host(request.app), subject, number)
        stamp = await asyncio.to_thread(record_stamp, view)
        envelope, freshness = await asyncio.to_thread(pull_answer, view)
        return view, stamp, envelope, freshness

    view, stamp, envelope, freshness = await snapshot()
    if view.host is not None:
        # The page asks for its texts' Markdown next, which renders in the Markdown child
        # alone (pull_markdown.py), and a first paint over a core preview waits for the
        # description's: start the child at the page's first read, which is often a core
        # preview, so that wait is not spent on the child's start. A warm read is a page
        # about to open. Measured in tests/test_type_scale_chrome.py's page, 2026-11-17: a
        # cold child put the full record's paint 170 to 200 ms after its read, the hold's
        # whole bound, where an in-thread render had met it. Only a served page follows a
        # read: a one-shot `--api` read of this route starts nothing.
        start_for_pages()
    preview = envelope["core_preview"]
    # Prepared and adopted observations carry catalog admission. A captured live preview
    # may already have settled while the worker was building its first envelope.
    if (
        wait_after is not None
        and preview is not None
        and preview["revision"] == wait_after
        and envelope["record"] is None
        and view.kept is not None
        and view.core_window is None
        and view.core_admission is None
    ):
        kept = view.kept
        waited = await kept.wait_for_full(preview)
        if waited or kept.core_preview is not preview:
            view, stamp, envelope, freshness = await snapshot()
    if not await _preview_current(view, envelope["core_preview"]):
        _drop_core_preview(envelope)
    if envelope["record"] is not None:
        note_full_record(view)
        follow_adopted_head(view, envelope)
    if view.kept is not None:
        view.kept.saw_record(
            envelope["fetched_at"], without_store=_without_store(envelope), freshness=freshness
        )
    if view.host is not None and warm is None:
        from metabrowser.builtin_plugins.github.pull_prefetch import note_viewed

        # What a prefetch's ``changed`` adds: the numbers this server answered last, for a
        # reader. A warm reads a record the reader has not opened.
        note_viewed(view.host.pulls, number)
    comparison = (envelope.get("record") or {}).get("comparison")
    if view.host is not None and isinstance(comparison, dict):
        served = await view.host.pulls.companion(number)
        served.note_comparison((comparison["base"], comparison["head"]))
    if claimed_pin is not None and (refusal := pin_changed_response(claimed_pin)) is not None:
        return refusal
    etag = envelope_etag(envelope, stamp)
    headers = {
        **_NO_STORE,
        "etag": etag,
        **verified_header(envelope, scanning=view.catalog_scanning),
    }
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_markdown_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull-markdown?number=<n>&part=<part>`` — see :mod:`.pull_markdown`."""

    from metabrowser.builtin_plugins.github.pull_markdown import render_part
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        pull_answer,
        pull_host,
        pull_view,
        requested_number,
    )

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = pull_view(pull_host(request.app), get_source_session().subject, number)

    async def current_core() -> PullCorePreview | None:
        # The preview the pull route would answer now, revoked ones dropped as it drops them,
        # so the description renders only what a page may show.
        envelope, _freshness = await asyncio.to_thread(pull_answer, view)
        preview = envelope["core_preview"]
        if envelope["record"] is not None or preview is None:
            return None
        return preview if await _preview_current(view, preview) else None

    # A page that goes away, or scrolls past a text, leaves the render to no one, and an
    # abandoned render must not hold the Markdown child.
    answer = await unless_disconnected(
        request,
        render_part(view, request.query_params.get("part", ""), current_core=current_core),
    )
    if answer is None:
        return Response(status_code=CLIENT_CLOSED, headers=_NO_STORE)
    status_code, body = answer
    return JSONResponse(body, status_code=status_code, headers=_NO_STORE)


async def guided_review_handler(request: Request) -> Response:
    """Read one step of an author-provided guide and its pinned diff excerpts: a pull
    request's, ``number=<n>``, or a native stack's, ``stack=<n>``, whose guide is a
    member's `stack-review` block read against the stack's combined comparison."""
    from metabrowser.builtin_plugins.github.guided_review import (
        guided_review,
        stack_guided_review,
    )
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        pull_host,
        requested_number,
    )
    from metabrowser.git.routes import session_git_location
    from metabrowser.git.wire import is_full_revision
    from metabrowser.view_routes import parse_pull_number

    params = request.query_params
    step = parse_pull_number(params.get("step", "1"))
    if "stack" in params:
        if "number" in params:
            return _invalid_request('name a pull request by "number" or a stack by "stack"')
        stack = parse_pull_number(params["stack"])
        if stack is None:
            return _invalid_request('"stack" is a native stack number')
        if step is None:
            return _invalid_request("step must be a positive integer")
        # The comparison the page draws, named as `stack-comparison` names it, or none for
        # the stack's current one.
        drawn = tuple(params.get(name, "") for name in ("left", "right", "key"))
        if any(drawn) and (
            not is_full_revision(drawn[0])
            or not is_full_revision(drawn[1])
            or re.fullmatch(r"[0-9a-f]{32}", drawn[2]) is None
        ):
            return _invalid_request("a stack's comparison names its two commits and its key")
        repository, published, reader = await _stack_sources(request)
        if repository is None:
            return JSONResponse({"state": "not_github"}, status_code=409, headers=_NO_STORE)
        # A `{commit}`'s row links its page only where that page reads Git, as below.
        answer = await unless_disconnected(
            request,
            stack_guided_review(
                repository,
                published,
                reader,
                stack,
                step,
                links=session_git_location(),
                drawn=(drawn[0], drawn[1], drawn[2]) if any(drawn) else None,
            ),
        )
        if answer is None:
            return Response(status_code=CLIENT_CLOSED, headers=_NO_STORE)
        return JSONResponse(answer, headers=_NO_STORE)
    try:
        number = requested_number(params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    if step is None:
        return _invalid_request("step must be a positive integer")
    await _resolve(request)
    host = pull_host(request.app)
    if host is None:
        return JSONResponse({"state": "not_github"}, status_code=409, headers=_NO_STORE)
    # A `{commit}`'s row links its page only where that page reads Git: a served checkout's.
    answer = await unless_disconnected(
        request,
        guided_review(
            host, number, step, served_repository(request.app), links=session_git_location()
        ),
    )
    if answer is None:
        return Response(status_code=CLIENT_CLOSED, headers=_NO_STORE)
    return JSONResponse(answer, headers=_NO_STORE)


async def pull_image_handler(request: Request) -> Response:
    """An image at the head of an admitted comparison, for its rendered Markdown."""
    from metabrowser.builtin_plugins.github.pull_snapshot import (
        pull_image_handler as read_image,
    )

    return await read_image(request)


async def pull_rendered_diff_handler(request: Request) -> Response:
    """One changed Markdown file of an admitted comparison, rendered as a redline."""

    from metabrowser.builtin_plugins.github.pull_rendered_diff import (
        pull_rendered_diff_handler as rendered,
    )

    return await rendered(request)


async def pull_size_handler(request: Request) -> Response:
    """The size an admitted comparison of a pull request pushes; see :mod:`.pull_size`."""

    from metabrowser.builtin_plugins.github.pull_size import pull_size_handler as sized

    return await sized(request)


async def pull_comparison_handler(request: Request) -> Response:
    """Read a checkout's pinned PR comparison from its store; never acquire on GET."""

    from metabrowser.builtin_plugins.diff.sidekick import comparison_at
    from metabrowser.builtin_plugins.github.pull_manifest import (
        invalidate_pull_manifest,
        load_pull_manifest,
    )
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        cached_pull_record,
        pull_host,
        requested_number,
    )
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.git.object_failures import observed_object_failures
    from metabrowser.git.process import GitLocation, repository_store_target
    from metabrowser.git.wire import is_full_revision
    from metabrowser.home import PrivateStorageError

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    left = request.query_params.get("left", "")
    right = request.query_params.get("right", "")
    if (
        request.query_params.get("base_policy") != "merge_base"
        or not is_full_revision(left)
        or not is_full_revision(right)
        or "revision" in request.query_params
    ):
        return _invalid_request("a pull comparison requires two full commit IDs")
    await _resolve(request)
    host = pull_host(request.app)
    if host is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
            headers=_NO_STORE,
        )
    if host.pulls.git_dir is None:
        return JSONResponse(
            {"error": "this comparison has no available repository store", "code": "no_store"},
            status_code=409,
            headers=_NO_STORE,
        )
    published = host.pulls.published
    if not isinstance(published, PublishedSource):
        raise AssertionError("a store-backed pull host has no published source")
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

    record, _dumped, _revision = await asyncio.to_thread(
        cached_pull_record, published.home, published.slug, number
    )
    if not isinstance(record, PullRecord):
        return JSONResponse(
            {"error": "this pull request has not been fetched", "code": "not_cached"},
            status_code=404,
            headers=_NO_STORE,
        )
    served = await host.pulls.companion(number)
    if record.comparison is not None:
        served.note_comparison((record.comparison.base, record.comparison.head))
    # Read-only full-endpoint links remain usable after a restart. Only an already
    # issued PR pair can gain protected display ownership for POST network repair.
    if served.issued_comparison((left, right)):
        served.note_comparison((left, right), displayed=True)
    target = repository_store_target(git_dir=published.git_dir)
    response = await comparison_at(
        request,
        GitLocation.revision(target, right),
        max_initial_files=INITIAL_PULL_FILES,
        manifest_loader=partial(load_pull_manifest, published, number),
    )

    if response.status_code == 409 and any(
        failure.state == "object_corrupt"
        for failure in observed_object_failures.pending(target, (left, right))
    ):
        try:
            await asyncio.to_thread(invalidate_pull_manifest, published, number, (left, right))
        except (OSError, PrivateStorageError):
            # The diff shows `message` (diff/index.js); what happened and what fixes it stay
            # in `detail`, for `metab --api` and agents.
            return JSONResponse(
                {
                    "error": "object_corrupt",
                    "message": "This repository’s saved copy is damaged, so these changes cannot be shown.",
                    "detail": "An object does not match its ID, and its cached comparison could "
                    "not be discarded. Clear the affected repository cache before retrying.",
                },
                status_code=409,
                headers=_NO_STORE,
            )
    return response


async def _json_body(request: Request) -> dict[str, Any] | tuple[str, int]:
    """The body, a JSON object of at most :data:`MAX_REFRESH_REQUEST_BYTES`.

    Otherwise the message and status ``POST /api/source/refresh`` answers the same body
    with.
    """

    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_REFRESH_REQUEST_BYTES:
        return "the request body is too large", 413
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REFRESH_REQUEST_BYTES:
            return "the request body is too large", 413
        chunks.append(chunk)
    try:
        decoded = json.loads(b"".join(chunks) or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "the request body is not JSON", 400
    if not isinstance(decoded, dict):
        return "the request body must be a JSON object", 400
    return decoded


async def pull_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pull-refresh`` — start or join one pull request's refresh.

    The body names ``number``, and may name ``retry``: a reader's own click, or the one
    comparison request a page on Changes sends by itself for a record without a store.
    ``refresh`` says whether this request ``started`` the job or ``joined`` one that was
    running, answered ``202``, or why an automatic request started nothing: the record is
    not due (``not_due``), or there is none (``not_cached``), answered ``200``. Past the bound on
    jobs it is refused, ``too_many``, answered ``429``, and nothing starts. ``pull`` is the
    envelope as of that moment: with a job running, ``refreshing`` is true, and it is
    ``pending`` while no record is cached yet. With ``held``, the ``record_revision`` of
    the record the asker has, a ``pull`` whose record is that one names ``record_held``
    in place of ``record`` (:func:`.pull_route.refresh_answer_pull`), as a visible page's
    recurring ask does.
    With ``prepare_comparison``, a checkout whose store is attached may prepare the named
    cached record revision as optional work: only while no other pull job of the
    checkout runs, with no network slot, and ended by any reader's refresh. Its envelope
    adds ``preparing_comparison`` while it remains optional.
    """

    from metabrowser.builtin_plugins.github.pull_list_route import (
        DEFAULT_LIST,
        attend_list,
        list_view,
    )
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        follow_adopted_head,
        note_full_record,
        pull_answer,
        pull_host,
        pull_view,
        refresh_answer_pull,
        refresh_request,
        start_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = refresh_request(body)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    host = pull_host(request.app)
    if host is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    # A visible page's automatic ask also keeps its repository's list probed, beside its
    # own record's probe and for no longer (:func:`.pull_list_route.attend_list`). The
    # answer waits for it, at most ``PROBE_WAIT_S`` and a thread's read: a one-shot
    # ``metab --api`` drains the coordinator's jobs running when the answer comes and then
    # shuts the application down, which cancels every other task, and neither the ask's
    # read of the catalog nor the scan a probe's change starts is such a job until it has
    # begun. Without the wait, whether a one-shot ask probes the list and scans for what
    # it finds would depend on timing (review A7 of #737). The two probes run side by
    # side, so the wait is the list's time past the record's.
    attending = None if ask.retry else attend_list(list_view(request.app, DEFAULT_LIST))
    try:
        with _whose(ask.retry):
            started = await start_refresh(host, ask)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    finally:
        if attending is not None:
            await asyncio.shield(attending)
    if ask.wait_core and started in {"started", "joined"}:
        served = host.pulls.held(ask.number)
        if served is not None:
            await served.wait_for_core()
    # Read after the start, on the loop: a job is running, whatever it does next.
    view = pull_view(host, get_source_session().subject, ask.number)
    envelope, freshness = await asyncio.to_thread(pull_answer, view)
    if not await _preview_current(view, envelope["core_preview"]):
        _drop_core_preview(envelope)
    if envelope["record"] is not None:
        note_full_record(view)
        follow_adopted_head(view, envelope)
    if view.kept is not None:
        view.kept.saw_record(
            envelope["fetched_at"], without_store=_without_store(envelope), freshness=freshness
        )
    # ``status_route`` is where a one-shot ``--api`` reads how the refresh ended.
    answer = {
        "refresh": started,
        "pull": refresh_answer_pull(envelope, ask.held),
        "status_route": status_route(ask.number),
    }
    if started == "too_many":
        answer.update(_TOO_MANY)
    return JSONResponse(answer, status_code=_REFRESH_STATUS[started], headers=_NO_STORE)


def _whose(retry: bool, *, speculative: bool = False) -> contextlib.AbstractContextManager[None]:
    """The context a refresh starts in: a reader's own for a *retry*, which no ceiling counts.

    The job's task copies it, so what a reader's click spends is not counted against the
    process's automatic work (:func:`.gh_budget.readers_own`). An automatic ask for
    *speculative* work starts in that context instead (:func:`.gh_budget.speculative`).
    """

    from metabrowser.builtin_plugins.github import gh_budget

    if retry:
        return gh_budget.readers_own()
    return gh_budget.speculative() if speculative else contextlib.nullcontext()


def _invalid_request(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": message, "code": "invalid_request"}, status_code=status_code)


async def pull_timeline_handler(request: Request) -> JSONResponse:
    """Read the selected PR's independently cached Conversation projection."""

    from pydantic import ValidationError

    from metabrowser.builtin_plugins.github.pull_route import pull_host
    from metabrowser.builtin_plugins.github.pull_timeline import (
        TimelineRequest,
        read_timeline,
        unavailable,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = TimelineRequest.model_validate(body)
    except ValidationError:
        return _invalid_request('a timeline request requires "number" and "record_revision"')
    await _resolve(request)
    host = pull_host(request.app)
    answer = unavailable(ask)
    if host is not None:
        # Pages run serially, with at most one optional gh process per app.
        # Foreground refresh keeps its own network slots.
        gate = getattr(request.app.state, "github_pull_timeline_gate", None)
        if gate is None:
            gate = request.app.state.github_pull_timeline_gate = asyncio.Lock()
        read = await unless_disconnected(request, read_timeline(host.pulls, ask, gate))
        if read is not None:
            answer = read
    if (refusal := pin_changed_response(request.headers.get(PIN_HEADER))) is not None:
        return refusal
    return JSONResponse(answer.model_dump(mode="json"), headers=_NO_STORE)


async def pull_cores_prepare_handler(request: Request) -> Response:
    """Schedule or release a source-owned visible core window.

    A batch stops at its next thread hop once its client has gone: the panel abandons a
    batch a reader scrolled past, and one that has waited past its timeout. It starts no
    provider read for it then. A release always runs to its end, so ownership is never
    left behind.
    """
    from metabrowser.builtin_plugins.github.pull_cores import core_request

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = core_request(body)
    except ValueError as exc:
        return _invalid_request(str(exc))
    if not ask.numbers:
        return await _core_window_answer(request, ask)
    answer = await unless_disconnected(request, _core_window_answer(request, ask))
    if answer is None:
        # Nobody reads it; the status names an abandoned batch in the slow-request log.
        return Response(status_code=CLIENT_CLOSED, headers=_NO_STORE)
    return answer


async def _core_window_answer(request: Request, ask: CoreRequest) -> JSONResponse:
    from metabrowser.builtin_plugins.github.pull_cores import (
        cached_batch,
        failure_held,
        request_preparation,
    )
    from metabrowser.builtin_plugins.github.pull_route import pull_host, status_route

    await _resolve(request)
    host = pull_host(request.app)
    if host is None or host.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
            headers=_NO_STORE,
        )
    preparation = await request_preparation(host.pulls, host.coordinator, ask, host.running)
    answer: dict[str, Any] = {"preparation": preparation}
    if preparation in {"ready", "partial"}:
        coverage = await asyncio.to_thread(cached_batch, host.pulls, ask)
        if coverage is None or (
            preparation == "ready"
            and (
                len(coverage[0]) + len(coverage[1]) != len(ask.numbers)
                or {*coverage[0], *coverage[1]} != set(ask.numbers)
            )
        ):
            answer["preparation"] = "not_owner"
        else:
            answer["ready_numbers"], answer["skipped_numbers"] = map(list, coverage)
            if preparation == "partial":
                from datetime import timedelta

                from metabrowser.builtin_plugins.github import pulls
                from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
                from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

                covered = {*coverage[0], *coverage[1]}
                retry = [number for number in ask.numbers if number not in covered]
                if not retry:
                    # A selected read or another worker can settle the last member
                    # during this cache recheck.
                    answer["preparation"] = "ready"
                else:
                    answer["retry_numbers"] = retry
                # This is the existing per-member attempt lease, not a coverage
                # cutoff: later cohorts proceed and this subset remains unfinished.
                if retry:
                    answer["retry_at"] = utc_stamp(
                        pulls.utc_now() + timedelta(seconds=FRESHNESS_WINDOW_S)
                    )
    elif preparation in {"failed", "held"}:
        # A batch held for another reason, the share or the catalog's backfill, names the
        # last failure only while it still holds the walk: a rate limit whose reset has
        # passed told the panel to wait for that reset, so it asked again every second
        # (review B1 of #761).
        failure = (
            host.pulls.core_failure if preparation == "failed" or failure_held(host.pulls) else None
        )
        answer["failure"] = (
            {"outcome": failure.outcome, "message": failure.message, "reset_at": failure.reset_at}
            if failure is not None
            else None
        )
    if preparation in {"started", "joined"}:
        answer["status_route"] = status_route(ask.numbers[0])
    return JSONResponse(
        answer, status_code=202 if preparation in {"started", "joined"} else 200, headers=_NO_STORE
    )


async def pulls_handler(request: Request) -> Response:
    """Catalog window or lightweight search projection — see :mod:`.pull_list_route`.

    Both read from the cache alone. A window carries an entity tag so the tab can
    poll cheaply. Search returns only its lightweight results and catalog status.
    """

    from metabrowser.builtin_plugins.github.pull_catalog import catalog_search
    from metabrowser.builtin_plugins.github.pull_list_route import (
        ListRequestError,
        envelope_etag,
        list_view,
        list_window,
        pull_list_envelope,
        search_query,
    )

    if (raw_query := request.query_params.get("q")) is not None:
        try:
            query = search_query(raw_query)
        except ListRequestError as exc:
            return _invalid_request(str(exc))
        await _resolve(request)
        view = list_view(request.app, "all")
        matches = await asyncio.to_thread(catalog_search, view.repository, query)
        return JSONResponse({**matches, "refreshing": view.refreshing}, headers=_NO_STORE)

    try:
        window = list_window(request.query_params)
    except ListRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = list_view(request.app, window.name)
    envelope = await asyncio.to_thread(pull_list_envelope, view, window)
    etag = envelope_etag(envelope, window)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pulls_refresh_handler(request: Request) -> JSONResponse:
    """Start/join automatic catalog backfill; state/target prioritize a display window.

    The default state is open and target is 500. The background worker continues to
    all metadata after that prefix. A background or reconnect ask joins without
    reprioritizing. Reconnect can retry one recent network failure early.
    Retry and reconnect honor rate-limit holds. An automatic ask that finds nothing else
    due probes the list and waits for it at most ``PROBE_WAIT_S``: a change starts the
    job with its delta scan first, and anything else answers ``not_due`` with
    ``checked_at`` as the probe left it. ``pulls`` is the envelope without its
    rows, with ``refreshing`` as of the start. When a job runs after the start, ``pulls``
    was read before it, so a job this request started has not changed it; when none runs,
    it is read after ``refreshing``, as ``GET`` reads it.

    Once the list's answer is read, the ask starts the scan of every open pull request's
    status when it is due (:func:`.pull_status_scan.ask_status_scan`), and ``status_scan``
    says whether it ``started``, ``joined``, or was ``not_due``; ``status_scan_at`` is when
    the last scan ended, ``None`` before any (:func:`.pull_status_scan.scan_ended_at`), so a
    page learns of a scan that ended since its last ask whoever started it. The scan is a
    job of its own, so it never holds the list's refresh, and ``GET pull-statuses`` answers
    it. The ask reads only the scan's stamp for it, never Git: a look at the mirror's base
    branches, when only a moved one could start a scan, runs as a job of its own after the
    answer, and starts the scan itself.
    """

    from metabrowser.builtin_plugins.github.pull_list_route import (
        ListRequestError,
        ListWindow,
        list_envelope,
        list_view,
        probe_list,
        read_catalog_window,
        refresh_request,
        refresh_wanted,
        start_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = refresh_request(body)
    except ListRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = list_view(request.app, ask.name)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted = await asyncio.to_thread(refresh_wanted, view, ask)
    if wanted == "probe":
        # A visible page asks every LIST_PROBE_S; most asks end here, in a free conditional
        # read that finds nothing new (:mod:`.pull_list_probe`).
        wanted = await probe_list(view)
    # Read before the start, as the file list's refresh does: a job with no gh to run
    # writes its stamp at once, and an answer read after the start would race that write.
    window = ListWindow(ask.name, limit=0)
    found = await asyncio.to_thread(read_catalog_window, view, window)
    with _whose(ask.retry):
        started = start_refresh(view, ask, wanted=wanted)
    # Nothing is awaited from the start to here, so a job this request started has done
    # nothing yet. One it joined may have, and the answer says it is still refreshing.
    after = list_view(request.app, ask.name)
    if not after.refreshing:
        # No job runs, but one may have ended during that read: read again, after
        # refreshing, so an answer that says nothing is refreshing shows how it ended.
        found = await asyncio.to_thread(read_catalog_window, after, window)
    envelope = list_envelope(after, found, window)
    from metabrowser.builtin_plugins.github.pull_route import pull_host
    from metabrowser.builtin_plugins.github.pull_status_scan import ask_status_scan, scan_ended_at

    host = pull_host(request.app)
    # The catalog as this ask read it before the list's start: a first read the job just
    # started is not yet one the scan may follow.
    listed = found.listed if found is not None else None
    scan = await ask_status_scan(
        view.repository,
        view.coordinator,
        reader=listed.reader if listed is not None else None,
        git_dir=host.pulls.git_dir if host is not None else None,
        retry=ask.retry,
        changed=wanted == "changed",
    )
    answer = {
        "refresh": started,
        "pulls": dict(envelope),
        "status_route": status_route(ask.name),
        "status_scan": scan,
        "status_scan_at": await scan_ended_at(view.repository, view.coordinator),
    }
    return JSONResponse(answer, status_code=200 if started == "not_due" else 202, headers=_NO_STORE)


async def pulls_prefetch_handler(request: Request) -> JSONResponse:
    """``GET`` or ``POST /api/plugin/github/pulls-prefetch`` — see :mod:`.pull_prefetch`.

    The ``POST`` body names ``records`` and ``files``, each at most 16 pull-request numbers
    in a visible page's order of priority, and ``changed``. It replaces the repository's
    background queue and answers ``202`` with ``prefetch`` ``started`` or ``joined`` and
    the ``GET`` as its ``status_route``, or ``200`` with ``not_due`` or ``deferred`` and a
    ``reason``. A ``202`` with a ``reason`` says the governor refused the rest and the lane
    lists only what the store gives. The ``GET`` reports the lane from memory.
    """

    from metabrowser.builtin_plugins.github.pull_prefetch import (
        PREFETCH_ROUTE,
        PrefetchRequestError,
        prefetch_envelope,
        prefetch_request,
        request_prefetch,
    )
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    ask = None
    if request.method == "POST":
        body = await _json_body(request)
        if isinstance(body, tuple):
            return _invalid_request(*body)
        try:
            ask = prefetch_request(body)
        except PrefetchRequestError as exc:
            return _invalid_request(str(exc))
    elif request.query_params:
        return _invalid_request("a prefetch report has no query parameters")
    await _resolve(request)
    host = pull_host(request.app)
    if host is None or host.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
            headers=_NO_STORE,
        )
    if ask is None:
        envelope = await prefetch_envelope(host)
        return JSONResponse(dict(envelope), headers=_NO_STORE)
    started, reason, queued = await request_prefetch(request.app, host, ask)
    answer: dict[str, Any] = {"prefetch": started, "queued": queued}
    if reason is not None:
        answer["reason"] = reason
    if started in {"started", "joined"}:
        answer["status_route"] = PREFETCH_ROUTE
    return JSONResponse(
        answer, status_code=202 if started in {"started", "joined"} else 200, headers=_NO_STORE
    )


async def stacks_handler(request: Request) -> Response:
    """Read optional native stack membership from the cache alone."""
    from metabrowser.builtin_plugins.github.pull_stacks_route import (
        envelope_etag,
        stack_envelope,
        stack_view,
    )

    if request.query_params:
        return _invalid_request("a stack snapshot has no query parameters")
    await _resolve(request)
    envelope = await asyncio.to_thread(stack_envelope, stack_view(request.app))
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def stack_change_handler(request: Request) -> Response:
    """``GET /api/plugin/github/stack-change?number=<stack>`` — a stack's combined change.

    Its members' own changed files accumulated, each file once and their lines summed, from
    the cache alone (:mod:`.pull_stack_change`): no GitHub call, no fetch, and no Git.
    """
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
    from metabrowser.builtin_plugins.github.pull_stack_change import envelope_etag, stack_change

    if set(request.query_params) != {"number"}:
        return _invalid_request('a stack change names its stack by "number" alone')
    try:
        number = requested_number(request.query_params)
    except PullRequestError:
        return _invalid_request('"number" is a native stack number')
    await _resolve(request)
    envelope = await stack_change(served_repository(request.app), number)
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def _stack_sources(request: Request) -> tuple[Any, Any, str | None]:
    """The served repository, its published store or ``None``, and the observed reader."""

    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_route import pull_host
    from metabrowser.cache.acquire import PublishedSource

    await _resolve(request)
    host = pull_host(request.app)
    published = host.pulls.published if host is not None else None
    store = (
        published
        if isinstance(published, PublishedSource) and host is not None and host.pulls.git_dir
        else None
    )
    reader = host.pulls.observed_reader if host is not None else None
    repository = served_repository(request.app) if host is not None else None
    return repository, store, reader


async def stack_handler(request: Request) -> Response:
    """``GET /api/plugin/github/stack?number=<stack>[&since=<key>]`` — a native stack's page.

    Its members, its combined comparison and that comparison's routes, the members the top
    lacks, the members still pending and which of them a refresh is fetching now, the
    totals, and each file's layers (:mod:`.pull_stack`). ``since``, the key of a comparison
    this route answered before, the one the asking page draws, keeps it admitted and adds
    how each member's head moved from it (``moved``). No GitHub call and no fetch; the
    first read after a member moves lists the comparison in the store.
    """
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        pull_host,
        requested_number,
    )
    from metabrowser.builtin_plugins.github.pull_stack import envelope_etag, stack_envelope

    if not {"number"} <= set(request.query_params) <= {"number", "since"}:
        return _invalid_request('a stack names itself by "number", and "since" alone besides')
    try:
        number = requested_number(request.query_params)
    except PullRequestError:
        return _invalid_request('"number" is a native stack number')
    since = request.query_params.get("since")
    if since is not None and re.fullmatch(r"[0-9a-f]{32}", since) is None:
        return _invalid_request('"since" is a stack comparison\'s key')
    repository, published, reader = await _stack_sources(request)
    host = pull_host(request.app)
    answer = await unless_disconnected(
        request,
        stack_envelope(
            repository,
            published,
            number,
            reader,
            host.running if host is not None else lambda _number: False,
            since,
        ),
    )
    if answer is None:
        return Response(status_code=CLIENT_CLOSED, headers=_NO_STORE)
    etag = envelope_etag(answer)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(answer), headers=headers)


async def stack_comparison_handler(request: Request) -> Response:
    """``GET /api/plugin/github/stack-comparison`` — a stack's combined comparison.

    The address the ``stack`` route answers names the stack, both commits, and the digest
    of its members; the stack's current comparison is answered, or one the ``stack`` route
    answered before and keeps (:mod:`.pull_stack_retained`), through the diff plugin's
    ``comparison_at`` with the stack's restricted manifest, so ``group=``, ``types=``,
    ``file=``, and ``view=types`` work as on a pull request. An address neither names
    answers ``410 stack_moved``, and one whose retained pairs cannot be read now ``409
    snapshot_unavailable``.
    """

    from metabrowser.builtin_plugins.diff.sidekick import comparison_at
    from metabrowser.builtin_plugins.github.pull_manifest import invalidate_stack_manifest
    from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
    from metabrowser.builtin_plugins.github.pull_stack import (
        combined,
        forget,
        read_stack,
        stack_key,
        stack_scope,
    )
    from metabrowser.builtin_plugins.github.pull_stack_retained import retained_stack_pair
    from metabrowser.git.object_failures import observed_object_failures
    from metabrowser.git.process import GitLocation, repository_store_target
    from metabrowser.git.wire import is_full_revision
    from metabrowser.home import PrivateStorageError

    params = request.query_params
    try:
        number = requested_number(params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    left, right, key = params.get("left", ""), params.get("right", ""), params.get("key", "")
    if (
        params.get("base_policy") != "direct"
        or not is_full_revision(left)
        or not is_full_revision(right)
        or re.fullmatch(r"[0-9a-f]{32}", key) is None
        or "revision" in params
    ):
        return _invalid_request("a stack comparison names its two commits and its key")
    repository, published, reader = await _stack_sources(request)
    if repository is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
            headers=_NO_STORE,
        )
    if published is None:
        return JSONResponse(
            {"error": "this comparison has no available repository store", "code": "no_store"},
            status_code=409,
            headers=_NO_STORE,
        )
    read = await read_stack(repository, published, number, reader)
    current = read.pair
    pair = (
        current
        if current is not None
        and (current.base, current.head, current.digest) == (left, right, key)
        else await asyncio.to_thread(
            retained_stack_pair, published, number, reader, left, right, key
        )
    )
    if pair == "unknown":
        return JSONResponse({"code": "snapshot_unavailable"}, status_code=409, headers=_NO_STORE)
    if pair is None:
        return JSONResponse(
            {
                "error": "this stack has moved; read its page again for its comparison",
                "code": "stack_moved",
            },
            status_code=410,
            headers=_NO_STORE,
        )

    async def manifest(*_args: object) -> Any:
        return (await combined(published, pair)).manifest

    target = repository_store_target(git_dir=published.git_dir)
    response = await comparison_at(
        request,
        GitLocation.revision(target, right),
        max_initial_files=INITIAL_PULL_FILES,
        manifest_loader=manifest,
        scope=stack_scope(pair),
    )
    if response.status_code == 409 and any(
        failure.state == "object_corrupt"
        for failure in observed_object_failures.pending(target, (left, right))
    ):
        forget(published, pair)
        try:
            await asyncio.to_thread(
                invalidate_stack_manifest, published, number, stack_key(published, pair)
            )
        except (OSError, PrivateStorageError):
            # As `pull_comparison_handler` answers: the diff shows `message`, and what
            # happened and what fixes it stay in `detail`, for `metab --api` and agents.
            return JSONResponse(
                {
                    "error": "object_corrupt",
                    "message": "This repository’s saved copy is damaged, so these changes cannot be shown.",
                    "detail": "An object does not match its ID, and its cached comparison could "
                    "not be discarded. Clear the affected repository cache before retrying.",
                },
                status_code=409,
                headers=_NO_STORE,
            )
    return response


async def stacks_refresh_handler(request: Request) -> Response:
    """Start or join optional stack work; core PR/catalog outcomes stay independent."""
    from metabrowser.builtin_plugins.github.pull_stacks import refresh_wanted
    from metabrowser.builtin_plugins.github.pull_stacks_route import (
        STACKS_ROUTE,
        stack_envelope,
        stack_view,
        start_refresh,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    retry = body.get("retry", False)
    if set(body) - {"retry"} or not isinstance(retry, bool):
        return _invalid_request('a stack refresh accepts only optional boolean "retry"')
    await _resolve(request)
    view = stack_view(request.app)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted = await asyncio.to_thread(refresh_wanted, view.repository, retry=retry)
    with _whose(retry):
        started = start_refresh(view, retry=retry, wanted=wanted)
    envelope = await asyncio.to_thread(stack_envelope, stack_view(request.app))
    return JSONResponse(
        {"refresh": started, "stacks": dict(envelope), "status_route": STACKS_ROUTE},
        status_code=200 if started == "not_due" else 202,
        headers=_NO_STORE,
    )


async def labels_handler(request: Request) -> Response:
    """``GET /api/plugin/github/labels`` — the repository's cached label set, cache only."""

    from metabrowser.builtin_plugins.github.pull_labels_route import (
        envelope_etag,
        label_envelope,
        label_view,
    )

    if request.query_params:
        return _invalid_request("a label set has no query parameters")
    await _resolve(request)
    envelope = await asyncio.to_thread(label_envelope, label_view(request.app))
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def labels_refresh_handler(request: Request) -> Response:
    """``POST /api/plugin/github/labels-refresh`` — start or join the label set's refresh.

    The body may name only a boolean ``retry``, a reader's own ask past the set's age.
    ``202`` started or joined the job, ``200`` says it was ``not_due``.
    """

    from metabrowser.builtin_plugins.github.pull_labels import refresh_wanted
    from metabrowser.builtin_plugins.github.pull_labels_route import (
        LABELS_ROUTE,
        label_envelope,
        label_view,
        start_refresh,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    retry = body.get("retry", False)
    if set(body) - {"retry"} or not isinstance(retry, bool):
        return _invalid_request('a label refresh accepts only optional boolean "retry"')
    await _resolve(request)
    view = label_view(request.app)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted = await asyncio.to_thread(refresh_wanted, view.repository, retry=retry)
    # The set's periodic read colors chips nobody is waiting on: speculative work.
    with _whose(retry, speculative=True):
        started = start_refresh(view, retry=retry, wanted=wanted)
    envelope = await asyncio.to_thread(label_envelope, label_view(request.app))
    return JSONResponse(
        {"refresh": started, "labels": dict(envelope), "status_route": LABELS_ROUTE},
        status_code=200 if started == "not_due" else 202,
        headers=_NO_STORE,
    )


async def cache_clear_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/cache-clear`` — discard the served repository's GitHub cache.

    The body is an empty JSON object. Everything this plugin keeps for the repository
    goes, under the lock its writers take (:func:`.pull_record.clear_pulls`), and is
    fetched again when it is next wanted: ``cleared`` counts the files removed. The
    repository's source and Git store stay. A cache that refuses answers ``409`` with
    ``cache_unwritable`` and why. The failures that name this route say what to paste.
    """

    from metabrowser.builtin_plugins.github.gh_lists import cache_failure_reason
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_record import clear_pulls
    from metabrowser.cache.locks import run_lock_section
    from metabrowser.home import PrivateStorageError

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    if body:
        return _invalid_request("a cache clear names no fields")
    await _resolve(request)
    repository = served_repository(request.app)
    if repository is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    try:
        cleared = await run_lock_section(partial(clear_pulls, repository.home, repository.slug))
    except (PrivateStorageError, OSError) as exc:
        name = repository.source.removeprefix("https://github.com/")
        return JSONResponse(
            {
                "error": f"the GitHub cache of {name} could not be cleared",
                "detail": cache_failure_reason(exc),
                "code": "cache_unwritable",
            },
            status_code=409,
            headers=_NO_STORE,
        )
    return JSONResponse({"cleared": cleared, "source": repository.source}, headers=_NO_STORE)


async def status_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/status`` — the GitHub status check (:mod:`.gh_status`).

    ``gh``'s path and version, the active github.com account, its token's scopes, and one
    state with the step that fixes it: the ``github`` section ``metab --doctor --json``
    prints. It runs ``gh``, which asks GitHub, so it is a ``POST`` with a JSON object
    body, as every route that starts work is. The body is empty, or names ``fresh: true``
    to run gh again rather than reuse an answer from the last
    :data:`~.gh_status.GH_STATUS_TTL_S`, as a retry after signing in does. Every state
    answers ``200``.
    """

    from metabrowser.builtin_plugins.github.gh_status import (
        forget_github_status,
        github_status,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    fresh = body.get("fresh", False)
    if set(body) - {"fresh"} or not isinstance(fresh, bool):
        return _invalid_request("a status request names only fresh, true or false")
    if fresh:
        forget_github_status()
    status = await github_status()
    return JSONResponse(status.to_json(), headers=_NO_STORE)


async def gh_requests_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/github/gh-requests?since=&until=&pid=&buckets=`` — see :mod:`.gh_requests`.

    What the servers that share this event log asked of GitHub in a window: the calls, what
    they cost, how fast they were answered, how many ran at once, and how long their jobs
    queued. From the event log alone, with no gh and no Git, so any served root answers it,
    as ``status`` does.
    """

    from datetime import UTC, datetime

    from metabrowser import event_log
    from metabrowser.builtin_plugins.github.gh_requests import parse_query, report
    from metabrowser.event_log_route import QueryError

    try:
        query = parse_query(dict(request.query_params), now=datetime.now(UTC))
    except QueryError as exc:
        return JSONResponse({"error": str(exc), "code": "invalid_query"}, status_code=400)
    try:
        state, directory = event_log.log_directory()
    except ValueError as exc:
        return JSONResponse({"error": str(exc), "code": "event_log_unconfigured"}, status_code=409)
    answer = await asyncio.to_thread(report, query, state=state, directory=directory)
    return JSONResponse(answer, headers=_NO_STORE)


async def pull_files_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull-files?number=<n>&offset=&limit=`` — see :mod:`.pull_files_route`.

    From the cache alone, with an entity tag, so a tree that polls a list while it fills is
    answered ``304`` until the next page is published.
    """

    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRequestError,
        envelope_etag,
        files_file_stamp,
        files_view,
        files_window,
        pull_files_envelope,
    )

    try:
        window = files_window(request.query_params)
    except FilesRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = files_view(request.app, window.number)
    stamp = await asyncio.to_thread(files_file_stamp, view)
    envelope = await asyncio.to_thread(pull_files_envelope, view, window)
    etag = envelope_etag(envelope, stamp)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_files_summary_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull-files-summary?numbers=<n>,<n>`` — see :mod:`.pull_files_summary`.

    What each named pull request's cached changed-files list sums to, for its Pulls row's
    brief change line: from the cache alone, with no gh and no Git.
    """

    from metabrowser.builtin_plugins.github.pull_files_summary import (
        SummaryRequestError,
        envelope_etag,
        files_summary,
        listing_numbers,
        summary_numbers,
    )
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository

    # A repeated parameter would be read as its last value alone: refused, as any other shape.
    if len(request.query_params.getlist("numbers")) > 1:
        return _invalid_request('"numbers" is named once')
    try:
        numbers = summary_numbers(request.query_params)
    except SummaryRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    listing = listing_numbers(request.app, numbers)
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    host = pull_host(request.app)
    store = host.pulls.git_dir if host is not None else None
    envelope = await files_summary(served_repository(request.app), listing, numbers, store)
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_statuses_handler(request: Request) -> Response:
    """``GET /api/plugin/github/pull-statuses?numbers=<n>,<n>`` — see :mod:`.pull_statuses_route`.

    Each named pull request's operational status and the verdict on it, for its Pulls row:
    from the cache alone, with no gh and no Git.
    """

    from metabrowser.builtin_plugins.github.pull_files_summary import SummaryRequestError
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_status_scan import scanning
    from metabrowser.builtin_plugins.github.pull_statuses_route import (
        envelope_etag,
        pull_statuses,
        status_numbers,
    )
    from metabrowser.mirror_refresh import refresh_coordinator

    # A repeated parameter would be read as its last value alone: refused, as any other shape.
    if len(request.query_params.getlist("numbers")) > 1:
        return _invalid_request('"numbers" is named once')
    try:
        numbers = status_numbers(request.query_params)
    except SummaryRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    repository = served_repository(request.app)
    running = repository is not None and scanning(
        refresh_coordinator(request.app), repository.source
    )
    envelope = await asyncio.to_thread(pull_statuses, repository, numbers, scanning=running)
    etag = envelope_etag(envelope)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_files_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pull-files-refresh`` — start or join one file list's refresh.

    The body names ``number``, and may name ``retry``, a reader's own click. ``refresh``
    says whether this request ``started`` the job or ``joined`` one that was running,
    answered ``202``; that it is ``not_due``, answered ``200``: the list is whole and
    current, it was tried within the window, or GitHub's limit holds; or, past the bound on
    jobs, ``too_many``, answered ``429``, starting nothing. ``files`` is the envelope
    without its rows, with ``refreshing`` as of the start. When a job runs after the start,
    ``files`` was read before it, so a job this request started has not changed it; when
    none runs, it is read after ``refreshing``, as ``GET`` reads it.
    """

    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRequestError,
        FilesWindow,
        files_envelope,
        files_refresh_request,
        files_refresh_wanted,
        files_view,
        read_files,
        start_files_refresh,
        status_route,
    )

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = files_refresh_request(body)
    except FilesRequestError as exc:
        return _invalid_request(str(exc))
    await _resolve(request)
    view = files_view(request.app, ask.number)
    if view.repository is None or view.coordinator is None:
        return JSONResponse(
            {"error": "this server serves no GitHub repository", "code": "not_github"},
            status_code=409,
        )
    wanted, local = await asyncio.to_thread(files_refresh_wanted, view, ask)
    # Read before the start: a job this request starts may write at once, as one with no gh
    # to run writes its stamp, and an answer read after the start would race that write.
    found = await asyncio.to_thread(read_files, view)
    with _whose(ask.retry):
        started = start_files_refresh(view, ask, wanted=wanted, local=local)
    # Nothing is awaited from the start to here, so a job this request started has done
    # nothing yet. One it joined may have, and the answer says it is still refreshing.
    after = files_view(request.app, ask.number)
    if not after.refreshing:
        # No job runs, but one may have ended during that read: read again, after
        # refreshing, so an answer that says nothing is refreshing shows how it ended.
        found = await asyncio.to_thread(read_files, after)
    envelope = files_envelope(after, found, FilesWindow(ask.number, limit=0))
    answer: dict[str, Any] = {
        "refresh": started,
        "files": dict(envelope),
        "status_route": status_route(ask.number),
    }
    if started == "too_many":
        answer.update(_TOO_MANY)
    return JSONResponse(answer, status_code=_REFRESH_STATUS[started], headers=_NO_STORE)


__all__ = [
    "MAX_REFRESH_REQUEST_BYTES",
    "guided_review_handler",
    "pull_files_handler",
    "pull_files_summary_handler",
    "pull_files_refresh_handler",
    "pull_handler",
    "pull_markdown_handler",
    "pull_refresh_handler",
    "pull_comparison_handler",
    "pull_rendered_diff_handler",
    "pull_size_handler",
    "pull_statuses_handler",
    "pulls_handler",
    "pulls_prefetch_handler",
    "stack_change_handler",
    "stack_comparison_handler",
    "stack_handler",
    "stacks_handler",
    "stacks_refresh_handler",
    "labels_handler",
    "labels_refresh_handler",
    "pulls_refresh_handler",
]
