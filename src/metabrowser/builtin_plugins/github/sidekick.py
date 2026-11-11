"""The pull routes: one pull request's, ``pull`` and ``pull-refresh``, the lists', ``pulls``
and ``pulls-refresh``, and a pull request's changed files, ``pull-files`` and
``pull-files-refresh``, all under ``/api/plugin/github/``.

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
import json
import re
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, Response

from metabrowser.http_caching import matches_if_none_match
from metabrowser.source import get_source_session
from metabrowser.source_routes import PIN_HEADER, pin_changed_response

if TYPE_CHECKING:
    from starlette.requests import Request

    from metabrowser.builtin_plugins.github.pull_route import PullView
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
    ``fetched_at``. A matching ``wait_full_after`` revision may hold the cache read
    briefly until its already-running selected refresh settles or revokes the preview.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        PullEnvelope,
        PullRequestError,
        envelope_etag,
        note_full_record,
        pull_envelope,
        pull_host,
        pull_view,
        record_stamp,
        requested_number,
    )

    try:
        number = requested_number(request.query_params)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    wait_after = request.query_params.get("wait_full_after")
    if wait_after is not None and re.fullmatch(r"[0-9a-f]{64}", wait_after) is None:
        return _invalid_request('"wait_full_after" is a core preview revision')
    claimed_pin = request.headers.get(PIN_HEADER) if wait_after is not None else None
    pinned_subject = None
    if claimed_pin is not None:
        if (refusal := pin_changed_response(claimed_pin)) is not None:
            return refusal
        # Snapshot pin metadata stays tied to the claim even if the pin changes back.
        pinned_subject = get_source_session().subject
    await _resolve(request)

    async def snapshot() -> tuple[PullView, tuple[int, int, int] | None, PullEnvelope]:
        subject = pinned_subject if pinned_subject is not None else get_source_session().subject
        view = pull_view(pull_host(request.app), subject, number)
        stamp = await asyncio.to_thread(record_stamp, view)
        envelope = await asyncio.to_thread(pull_envelope, view)
        return view, stamp, envelope

    view, stamp, envelope = await snapshot()
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
            view, stamp, envelope = await snapshot()
    if not await _preview_current(view, envelope["core_preview"]):
        envelope["core_preview"] = None
    if envelope["record"] is not None:
        note_full_record(view)
    if view.kept is not None:
        view.kept.saw_record(envelope["fetched_at"], without_store=_without_store(envelope))
    comparison = (envelope.get("record") or {}).get("comparison")
    if view.host is not None and isinstance(comparison, dict):
        served = await view.host.pulls.companion(number)
        served.note_comparison((comparison["base"], comparison["head"]))
    if claimed_pin is not None and (refusal := pin_changed_response(claimed_pin)) is not None:
        return refusal
    etag = envelope_etag(envelope, stamp)
    headers = {**_NO_STORE, "etag": etag}
    if matches_if_none_match(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(envelope), headers=headers)


async def pull_markdown_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/github/pull-markdown?number=<n>&part=<part>`` — see :mod:`.pull_markdown`."""

    from metabrowser.builtin_plugins.github.pull_markdown import render_part
    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
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
    status_code, body = await asyncio.to_thread(
        render_part, view, request.query_params.get("part", "")
    )
    return JSONResponse(body, status_code=status_code, headers=_NO_STORE)


async def pull_snapshot_handler(request: Request) -> Response:
    from metabrowser.builtin_plugins.github.pull_snapshot import (
        pull_snapshot_handler as read_snapshot,
    )

    return await read_snapshot(request)


async def pull_comparison_handler(request: Request) -> Response:
    """Read a checkout's pinned PR comparison from its store; never acquire on GET."""

    if "rendered_file" in request.query_params:
        from metabrowser.builtin_plugins.github.pull_rendered_diff import pull_rendered_diff_handler

        return await pull_rendered_diff_handler(request)

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
        manifest_loader=partial(load_pull_manifest, published),
    )

    if response.status_code == 409 and any(
        failure.state == "object_corrupt"
        for failure in observed_object_failures.pending(target, (left, right))
    ):
        try:
            await asyncio.to_thread(invalidate_pull_manifest, published, (left, right))
        except (OSError, PrivateStorageError):
            return JSONResponse(
                {
                    "error": "object_corrupt",
                    "message": "An object does not match its ID, and its cached comparison could not be discarded. Clear the affected repository cache before retrying.",
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

    The body names ``number``, and may name ``retry``, a reader's own click. ``refresh``
    says whether this request ``started`` the job or ``joined`` one that was running,
    answered ``202``, or why an automatic request started nothing: the record is not due
    (``not_due``), or there is none (``not_cached``), answered ``200``. Past the bound on
    jobs it is refused, ``too_many``, answered ``429``, and nothing starts. ``pull`` is the
    envelope as of that moment: with a job running, ``refreshing`` is true, and it is
    ``pending`` while no record is cached yet.
    With ``prepare_comparison``, a checkout may prepare the named cached record revision
    at idle priority. Its envelope adds ``preparing_comparison`` while it remains optional.
    """

    from metabrowser.builtin_plugins.github.pull_route import (
        PullRequestError,
        note_full_record,
        pull_envelope,
        pull_host,
        pull_view,
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
    try:
        started = await start_refresh(host, ask)
    except PullRequestError as exc:
        return _invalid_request(str(exc))
    if ask.wait_core and started in {"started", "joined"}:
        served = host.pulls.held(ask.number)
        if served is not None:
            await served.wait_for_core()
    # Read after the start, on the loop: a job is running, whatever it does next.
    view = pull_view(host, get_source_session().subject, ask.number)
    envelope = await asyncio.to_thread(pull_envelope, view)
    if not await _preview_current(view, envelope["core_preview"]):
        envelope["core_preview"] = None
    if envelope["record"] is not None:
        note_full_record(view)
    if view.kept is not None:
        view.kept.saw_record(envelope["fetched_at"], without_store=_without_store(envelope))
    # ``status_route`` is where a one-shot ``--api`` reads how the refresh ended.
    answer = {"refresh": started, "pull": dict(envelope), "status_route": status_route(ask.number)}
    if started == "too_many":
        answer.update(_TOO_MANY)
    return JSONResponse(answer, status_code=_REFRESH_STATUS[started], headers=_NO_STORE)


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

        async def disconnected() -> None:
            while (await request.receive())["type"] != "http.disconnect":
                pass

        async with asyncio.TaskGroup() as group:
            reading = group.create_task(read_timeline(host.pulls, ask, gate))
            disconnect = group.create_task(disconnected())
            finished, _ = await asyncio.wait(
                (reading, disconnect), return_when=asyncio.FIRST_COMPLETED
            )
            if disconnect in finished:
                reading.cancel()
            else:
                answer = reading.result()
            disconnect.cancel()
    if (refusal := pin_changed_response(request.headers.get(PIN_HEADER))) is not None:
        return refusal
    return JSONResponse(answer.model_dump(mode="json"), headers=_NO_STORE)


async def pull_cores_prepare_handler(request: Request) -> JSONResponse:
    """Schedule or release a source-owned visible core window."""
    from metabrowser.builtin_plugins.github.pull_cores import (
        cached_batch,
        core_request,
        request_preparation,
    )
    from metabrowser.builtin_plugins.github.pull_route import pull_host, status_route

    body = await _json_body(request)
    if isinstance(body, tuple):
        return _invalid_request(*body)
    try:
        ask = core_request(body)
    except ValueError as exc:
        return _invalid_request(str(exc))
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
        failure = host.pulls.core_failure
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
    Retry and reconnect honor rate-limit holds.
    """

    from metabrowser.builtin_plugins.github.pull_list_route import (
        ListRequestError,
        ListWindow,
        list_view,
        pull_list_envelope,
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
    started = start_refresh(view, ask, wanted=wanted)
    # Read after the start, on the loop: the job is running, whatever it does next.
    after = list_view(request.app, ask.name)
    envelope = await asyncio.to_thread(pull_list_envelope, after, ListWindow(ask.name, limit=0))
    answer = {"refresh": started, "pulls": dict(envelope), "status_route": status_route(ask.name)}
    return JSONResponse(answer, status_code=200 if started == "not_due" else 202, headers=_NO_STORE)


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
    started = start_refresh(view, retry=retry, wanted=wanted)
    envelope = await asyncio.to_thread(stack_envelope, stack_view(request.app))
    return JSONResponse(
        {"refresh": started, "stacks": dict(envelope), "status_route": STACKS_ROUTE},
        status_code=200 if started == "not_due" else 202,
        headers=_NO_STORE,
    )


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


async def pull_files_refresh_handler(request: Request) -> JSONResponse:
    """``POST /api/plugin/github/pull-files-refresh`` — start or join one file list's refresh.

    The body names ``number``, and may name ``retry``, a reader's own click. ``refresh``
    says whether this request ``started`` the job or ``joined`` one that was running,
    answered ``202``; that it is ``not_due``, answered ``200``: the list is whole and
    current, it was tried within the window, or GitHub's limit holds; or, past the bound on
    jobs, ``too_many``, answered ``429``, starting nothing. ``files`` is the envelope as of
    that moment without its rows.
    """

    from metabrowser.builtin_plugins.github.pull_files_route import (
        FilesRequestError,
        FilesWindow,
        files_refresh_request,
        files_refresh_wanted,
        files_view,
        pull_files_envelope,
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
    started = start_files_refresh(view, ask, wanted=wanted, local=local)
    # Read after the start, on the loop: the job is running, whatever it does next.
    after = files_view(request.app, ask.number)
    envelope = await asyncio.to_thread(pull_files_envelope, after, FilesWindow(ask.number, limit=0))
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
    "pull_files_handler",
    "pull_files_refresh_handler",
    "pull_handler",
    "pull_markdown_handler",
    "pull_refresh_handler",
    "pull_comparison_handler",
    "pulls_handler",
    "stacks_handler",
    "stacks_refresh_handler",
    "pulls_refresh_handler",
]
