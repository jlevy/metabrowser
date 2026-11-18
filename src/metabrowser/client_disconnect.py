"""Stop a request's work when its client has gone.

The server does not cancel a handler whose client disconnects, so work a reader no longer
waits for runs to its end: a page that navigates away, a transclusion past its own
deadline, or a panel that scrolled past a batch. A handler whose work is worth stopping
waits for it through :func:`unless_disconnected`, which cancels it at the disconnect. The
Markdown child's renders are the case that matters most: an abandoned one would hold the
child, which renders one document at a time, for its whole deadline
(:mod:`metabrowser.diff.markdown_projection_worker`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from starlette.requests import Request

# What a request whose client disconnected answers, which no client reads: nginx's
# "client closed request", so the slow-request log tells abandoned work from answered work.
CLIENT_CLOSED: Final = 499


async def unless_disconnected[ResultT](
    request: Request, work: Coroutine[Any, Any, ResultT]
) -> ResultT | None:
    """*work*'s result, or ``None`` when the client disconnected first and *work* was cancelled.

    Read the body before calling this: it waits on the request's next message, which
    after the body is the disconnect. Cancellation lands at *work*'s next ``await``, so a
    blocking call already in a worker thread runs to its end, and nothing after it does.
    """

    async def disconnected() -> None:
        while (await request.receive())["type"] != "http.disconnect":
            pass

    doing = asyncio.ensure_future(work)
    disconnect = asyncio.ensure_future(disconnected())
    try:
        await asyncio.wait((doing, disconnect), return_when=asyncio.FIRST_COMPLETED)
    finally:
        disconnect.cancel()
        if not doing.done():
            doing.cancel()
        # Let both unwind before the response: cancelled work ends its own processes.
        await asyncio.wait((doing, disconnect))
    if doing.cancelled():
        return None
    return doing.result()
