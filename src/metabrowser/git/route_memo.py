"""Encoded answers of the Git routes that depend only on a repository's refs.

``/api/git/refs`` and ``/api/git/summary`` answer from the refs and the commits they reach,
so two requests made while :func:`~metabrowser.git.ref_state.ref_state` names the same
state get the same body. This keeps that body, serialized, under a key that names the
route, the location, the state, and every request input the answer reads, and serves it
with an entity tag made from the same key. A request whose ``If-None-Match`` names the tag
of a body this process keeps is answered 304.

The tag is honored only for a body this process made, kept or just computed, never from
the key alone: a body this process made is known to be the answer, while a tag another
process issued could name a state whose answer is now a failure, such as a ref to an
object that is gone.

The bound is on both entries and bytes. Measured 2026-11-11 on this repository: the refs
body is 17.9 KB and the summary 67 bytes. A repository with tens of thousands of refs
makes a refs body of a few megabytes, which is kept unless it is over
:data:`MAX_ENTRY_BYTES`.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse, Response

from metabrowser.http_caching import build_scoped_etag, etag_headers, matches_if_none_match
from metabrowser.paths_safe import register_root_callback

if TYPE_CHECKING:
    from starlette.requests import Request

# Two routes, a handful of scopes and locations, and states that only move forward: a
# state that moved is never asked for again, so most entries are reclaimed by count.
MAX_ENTRIES = 64
MAX_BYTES = 8 * 1024 * 1024
# A body larger than this is served and not kept: one must not push out every other.
MAX_ENTRY_BYTES = MAX_BYTES // 4


class GitAnswerMemo:
    """A bounded least-recently-used map from an answer's key to its encoded body."""

    def __init__(
        self,
        *,
        max_entries: int = MAX_ENTRIES,
        max_bytes: int = MAX_BYTES,
        max_entry_bytes: int = MAX_ENTRY_BYTES,
    ) -> None:
        if min(max_entries, max_bytes, max_entry_bytes) < 1:
            raise ValueError("memo bounds must be positive")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.max_entry_bytes = max_entry_bytes
        self._bodies: OrderedDict[tuple[str, ...], bytes] = OrderedDict()
        self._bytes = 0

    @property
    def total_bytes(self) -> int:
        return self._bytes

    def __len__(self) -> int:
        return len(self._bodies)

    def get(self, key: tuple[str, ...]) -> bytes | None:
        body = self._bodies.get(key)
        if body is not None:
            self._bodies.move_to_end(key)
        return body

    def put(self, key: tuple[str, ...], body: bytes) -> None:
        previous = self._bodies.pop(key, None)
        if previous is not None:
            self._bytes -= len(previous)
        if len(body) > self.max_entry_bytes:
            return
        self._bodies[key] = body
        self._bytes += len(body)
        while len(self._bodies) > self.max_entries or self._bytes > self.max_bytes:
            _evicted_key, evicted = self._bodies.popitem(last=False)
            self._bytes -= len(evicted)

    def clear(self) -> None:
        self._bodies.clear()
        self._bytes = 0


GIT_ANSWERS = GitAnswerMemo()


def answer_tag(key: tuple[str, ...]) -> str:
    """The entity tag of the body kept under *key*, scoped to this build."""

    return build_scoped_etag("git-answer\0" + "\0".join(key))


def kept_answer(request: Request, key: tuple[str, ...] | None) -> Response | None:
    """The kept answer for *key*, as a 304 when the client holds it, or None."""

    if key is None:
        return None
    body = GIT_ANSWERS.get(key)
    if body is None:
        return None
    headers = etag_headers(answer_tag(key))
    if matches_if_none_match(request, headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def keep_answer(request: Request, key: tuple[str, ...] | None, payload: dict[str, Any]) -> Response:
    """Serialize *payload*, keep it under *key* when there is one, and answer with it.

    A client that already holds the tag is answered 304 here too: the body was just
    computed, so the tag is known to name it.
    """

    if key is None:
        return JSONResponse(payload)
    headers = etag_headers(answer_tag(key))
    response = JSONResponse(payload, headers=headers)
    GIT_ANSWERS.put(key, bytes(response.body))
    if matches_if_none_match(request, headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return response


# Another root is another repository; nothing kept for the previous one applies.
register_root_callback(GIT_ANSWERS.clear)


__all__ = [
    "GIT_ANSWERS",
    "GitAnswerMemo",
    "MAX_BYTES",
    "MAX_ENTRIES",
    "MAX_ENTRY_BYTES",
    "answer_tag",
    "keep_answer",
    "kept_answer",
]
