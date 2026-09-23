"""``GET /api/plugin/github/pull``: the served pull request's cached record.

:mod:`metabrowser.builtin_plugins.github.pull_route` builds the answer; this module is
the data hook the manifest names. The loader imports it at startup, so like the
``/api/cache/`` route table it imports nothing from the cache or the application home
itself: the handler imports the envelope builder, which reaches both, only when the
route is requested. Browsing a local directory therefore never loads the cache.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Final

from starlette.responses import JSONResponse

from metabrowser.source import get_source_session

if TYPE_CHECKING:
    from starlette.requests import Request

# The answer changes as the record ages and as a refresh replaces it.
_NO_STORE: Final = {"cache-control": "no-store"}


async def pull_handler(_request: Request) -> JSONResponse:
    """``GET /api/plugin/github/pull`` — see :mod:`.pull_route`."""

    from metabrowser.builtin_plugins.github.pull_route import served_pull_envelope

    envelope = await asyncio.to_thread(served_pull_envelope, get_source_session())
    return JSONResponse(dict(envelope), headers=_NO_STORE)


__all__ = ["pull_handler"]
