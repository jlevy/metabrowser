"""The ``/api/git/`` route table.

A separate collection from the tree, recent, and file endpoints: it has
its own wire model, its own failure modes, and its own resource bounds,
and keeping it out of :mod:`metabrowser.server` means none of that leaks
into the endpoints that serve files.

Every route is read-only. Four shared rules hold across all of them:

* **``/api/git/repo`` is the gate.** When it reports ``is_repo: false``
  the browser never renders the Git tab, and every other route returns
  the same negative envelope with HTTP 200. "Not a repository" and "git
  is not installed" are ordinary states of the world, not errors, and a
  4xx would put them in the browser's error path.
* **Revisions are validated before they reach an argument vector.**
  :func:`~metabrowser.git.wire.is_full_revision` accepts only full SHA-1
  or SHA-256 object ids, so a caller-supplied value can never be read as
  an option or a revision expression.
* **Numeric parameters are clamped, not rejected.** An out-of-range
  ``limit`` is a client bug that should still render a panel.
* **Git failures become 5xx with a generic body.** Git's error text
  contains absolute local paths, so it is logged and dropped.
"""

from __future__ import annotations

import logging
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser.git.detail import read_commit_detail
from metabrowser.git.history import (
    HISTORY_SESSIONS,
    ExpiredHistorySessionError,
    HistoryStorageError,
    InvalidHistoryCursorError,
    StaleHistorySessionError,
)
from metabrowser.git.log import read_refs
from metabrowser.git.process import GitError, GitTimeoutError, failure_detail
from metabrowser.git.repo import RepoContext, repo_info
from metabrowser.git.wire import GitRepoInfo, is_full_revision
from metabrowser.paths_safe import _resolved_root_dir
from metabrowser.settings import GIT_LOG_DEFAULT_LIMIT, GIT_LOG_MAX_LIMIT

log = logging.getLogger(__name__)


def _negative_payload(info: GitRepoInfo) -> dict[str, object]:
    """The body every route returns when there is no readable repository."""
    return {"is_repo": False, "reason": info.get("reason", "not_a_repo")}


async def _resolve(served_root: Path) -> tuple[RepoContext | None, GitRepoInfo]:
    """Resolve the repository, translating discovery failures to a negative.

    Discovery already converts the ordinary failures into a negative
    envelope; this catches the residual ones (a timeout mid-discovery) so
    no route has to repeat the handling.
    """
    try:
        return await repo_info(served_root)
    except GitError as exc:
        log.warning("git repository resolution failed: %s", failure_detail(exc))
        return None, GitRepoInfo(is_repo=False, root=None, head=None, reason="git_failed")


def _git_failure_response(exc: GitError) -> JSONResponse:
    """Convert a git failure to a response with no local paths in it.

    A timeout is 504 rather than 500 because it is the one failure a
    retry can plausibly fix — a very large repository under load — and
    the browser can present it as such.
    """
    if isinstance(exc, GitTimeoutError):
        return JSONResponse({"error": "git command timed out"}, status_code=504)
    return JSONResponse({"error": "git command failed"}, status_code=500)


async def api_git_repo(_request: Request) -> JSONResponse:
    """``GET /api/git/repo`` — repository presence, root, and HEAD.

    The cheapest endpoint and the one the browser calls first: its
    ``is_repo`` decides whether the Git tab exists at all. TTL-cached in
    :mod:`metabrowser.git.repo`, so polling it is inexpensive.
    """
    _context, info = await _resolve(_resolved_root_dir())
    return JSONResponse(dict(info))


async def api_git_refs(_request: Request) -> JSONResponse:
    """``GET /api/git/refs`` — every branch, remote branch, and tag."""
    served_root = _resolved_root_dir()
    context, info = await _resolve(served_root)
    if context is None:
        return JSONResponse(_negative_payload(info))

    try:
        refs = await read_refs(served_root, head_ref=context.head["ref"])
    except GitError as exc:
        log.warning("git refs failed: %s", failure_detail(exc))
        return _git_failure_response(exc)

    return JSONResponse({"is_repo": True, "refs": refs})


async def api_git_log(request: Request) -> JSONResponse:
    """``GET /api/git/log`` — one page of history.

    Query parameters:

    ``limit``
        Commits to return, clamped to ``GIT_LOG_MAX_LIMIT``. A
        non-numeric value falls back to the default rather than failing:
        the panel should render.
    ``cursor``
        Opaque, from a previous page. A malformed cursor is rejected;
        restarting from the first page would make the append-only client
        duplicate rows and corrupt lane continuity.
    ``scope``
        ``all`` walks every ref. The default walks HEAD, its upstream,
        and whichever trunk refs exist, because ``--all`` in a
        many-ref repository shows whichever branch commits most often
        and buries the rest.
    """
    served_root = _resolved_root_dir()
    context, info = await _resolve(served_root)
    if context is None:
        return JSONResponse(_negative_payload(info))

    limit = _clamped_limit(request.query_params.get("limit", ""))
    cursor = request.query_params.get("cursor") or None

    # An unborn HEAD is a repository with no commits. `git log` exits
    # non-zero there, which would read as a failure; short-circuit to the
    # empty page that actually describes the state.
    if context.head.get("unborn"):
        return JSONResponse({"is_repo": True, "commits": [], "cursor": None, "has_more": False})

    raw_scope = request.query_params.get("scope")
    wants_all = raw_scope == "all" if raw_scope is not None else None
    try:
        page = await HISTORY_SESSIONS.read_page(
            served_root,
            wants_all=wants_all,
            limit=limit,
            cursor=cursor,
        )
    except InvalidHistoryCursorError:
        return JSONResponse(
            {"error": "invalid cursor", "code": "history_cursor_invalid"},
            status_code=400,
        )
    except StaleHistorySessionError:
        return JSONResponse(
            {
                "error": "git history changed; refresh required",
                "code": "history_stale",
            },
            status_code=409,
        )
    except ExpiredHistorySessionError:
        return JSONResponse(
            {
                "error": "git history session expired; refresh required",
                "code": "history_expired",
            },
            status_code=410,
        )
    except HistoryStorageError:
        return JSONResponse(
            {
                "error": "git history session storage exhausted",
                "code": "history_storage_exhausted",
            },
            status_code=507,
        )
    except GitError as exc:
        log.warning("git log failed: %s", failure_detail(exc))
        return _git_failure_response(exc)

    return JSONResponse(dict(page))


async def api_git_commit(request: Request) -> JSONResponse:
    """``GET /api/git/commit/{revision}`` — one commit's message and files.

    Backs both the hover card and the detail view, so it is called far
    more often than the other routes; the browser caches its responses.
    """
    revision = request.path_params.get("revision", "")
    if not isinstance(revision, str) or not is_full_revision(revision):
        # Deliberately not echoed back into the message: the value is
        # caller-controlled and this response is rendered in the browser.
        return JSONResponse(
            {"error": "revision must be a full 40- or 64-character object id"},
            status_code=400,
        )

    served_root = _resolved_root_dir()
    context, info = await _resolve(served_root)
    if context is None:
        return JSONResponse(_negative_payload(info))

    try:
        detail = await read_commit_detail(context, revision)
    except GitError as exc:
        log.warning("git commit detail failed for %s: %s", revision, failure_detail(exc))
        return _git_failure_response(exc)

    if detail is None:
        return JSONResponse({"error": "unknown revision"}, status_code=404)

    return JSONResponse(dict(detail))


def _clamped_limit(raw: str) -> int:
    """Parse and clamp a ``limit`` query parameter."""
    try:
        limit = int(raw)
    except ValueError:
        return GIT_LOG_DEFAULT_LIMIT
    return max(1, min(limit, GIT_LOG_MAX_LIMIT))


# Composed into ``metabrowser.server.ROUTES``. Kept as a list here so the
# collection stays legible as a unit and can be mounted or omitted
# wholesale.
GIT_ROUTES: list[Route] = [
    Route("/api/git/repo", api_git_repo),
    Route("/api/git/refs", api_git_refs),
    Route("/api/git/log", api_git_log),
    Route("/api/git/commit/{revision}", api_git_commit),
]


__all__ = [
    "GIT_ROUTES",
    "api_git_commit",
    "api_git_log",
    "api_git_refs",
    "api_git_repo",
]
