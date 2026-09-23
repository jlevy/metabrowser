"""``GET /api/source/status``: what this server is serving.

One envelope names the active subject and, for a pinned Git revision, the commit
it is pinned to and the ref that commit was resolved from. The browser's revision
label is rendered from the same :func:`source_status` the route returns, so the
label and ``metab --api /api/source/status`` cannot disagree.

The pin is immutable for the life of a session. Freshness, refresh, and pin
switching extend this envelope in a later step of the thin-mirror plan.
"""

from __future__ import annotations

from typing import TypedDict

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser.git.tree_source import GitRevisionSubject, ref_short_name
from metabrowser.source import get_source_session


class SourceStatus(TypedDict):
    """The active subject, and its pin when it is a Git revision.

    ``pin`` is the full commit ID every read uses. ``ref`` is the store ref the pin
    was resolved from, as recorded when it opened, and ``ref_name`` the name the
    origin knows it by; both are ``None`` when no ref is known. A filesystem subject
    has no pin, so all three are ``None``.
    """

    subject: str
    generation: int
    pin: str | None
    ref: str | None
    ref_name: str | None


def source_status() -> SourceStatus:
    """The envelope for the active session. Reads no store and runs no Git."""

    session = get_source_session()
    subject = session.subject
    if isinstance(subject, GitRevisionSubject):
        return SourceStatus(
            subject=subject.kind,
            generation=session.generation,
            pin=subject.commit_oid,
            ref=subject.ref,
            ref_name=ref_short_name(subject.ref),
        )
    return SourceStatus(
        subject=subject.kind,
        generation=session.generation,
        pin=None,
        ref=None,
        ref_name=None,
    )


async def api_source_status(_request: Request) -> JSONResponse:
    """``GET /api/source/status`` — the active subject and its pin."""

    return JSONResponse(dict(source_status()), headers={"cache-control": "no-store"})


SOURCE_ROUTES = [Route("/api/source/status", api_source_status)]


__all__ = ["SOURCE_ROUTES", "SourceStatus", "api_source_status", "source_status"]
