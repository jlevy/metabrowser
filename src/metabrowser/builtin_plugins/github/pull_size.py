"""``GET github/pull-size``: the size a pull request's comparison pushes, and its patch's.

The page names the comparison it shows, as the rendered diff does: ``number``, ``left``
and ``right`` (its base and head), and ``store``, the store's token. The pair is admitted
as that route admits it (:func:`.pull_snapshot.admitted_snapshot`), so nothing but a
comparison this reader may read is measured, and no fetch starts.

The size is that of the head against the pair's merge base, the commits Files changed
compares: :func:`metabrowser.git.change_size.pull_change_size`. It is measured once and
kept beside the store, so a page opened again, here or on a fresh server, answers from
the bank. The prefetch measures most pull requests' sizes before a page asks
(:mod:`.pull_files_refresh`).

Outcomes, each JSON with a stable ``code`` on a refusal:

- ``200``: ``{"number": n, "size": GitChangeSize}``, ``unknown`` with its reason where the
  size cannot be known;
- ``400 invalid_pull_size``: the request is malformed;
- ``410 snapshot_expired``: the pair is not admitted;
- ``409 snapshot_unavailable``: admission could not be decided now;
- ``409 size_objects_unavailable``: Git failed reading the pair's objects.
"""

from __future__ import annotations

from typing import Final

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.github.pull_route import PullRequestError, requested_number
from metabrowser.builtin_plugins.github.pull_snapshot import Snapshot, admitted_snapshot
from metabrowser.git.wire import is_full_revision

# An admitted pair names immutable commits, so its size never changes; but admission does
# (a pair can stop being admitted), so the browser asks again rather than reuse an answer.
_NO_STORE: Final = {"Cache-Control": "no-store"}


async def pull_size_handler(request: Request) -> Response:
    from metabrowser.git.change_size import pull_change_size
    from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget

    params = request.query_params
    try:
        number = requested_number(params)
    except PullRequestError:
        number = None
    base, head = params.get("left", ""), params.get("right", "")
    if number is None or not is_full_revision(base) or not is_full_revision(head):
        return JSONResponse({"code": "invalid_pull_size"}, status_code=400, headers=_NO_STORE)
    snapshot = Snapshot(number, base, head, params.get("store", ""))
    published, admission = await admitted_snapshot(request, snapshot)
    if admission == "unknown":
        return JSONResponse({"code": "snapshot_unavailable"}, status_code=409, headers=_NO_STORE)
    if published is None:
        return JSONResponse({"code": "snapshot_expired"}, status_code=410, headers=_NO_STORE)
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), head
    )
    try:
        size = await pull_change_size(location, base, head)
    except GitError:
        return JSONResponse(
            {"code": "size_objects_unavailable"}, status_code=409, headers=_NO_STORE
        )
    return JSONResponse({"number": number, "size": dict(size)}, headers=_NO_STORE)


__all__ = ["pull_size_handler"]
