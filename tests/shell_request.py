"""The request a test hands ``server.index`` to render the shell without a server.

The index reads two things from its request: the cookies, and the application, whose
state holds what a lifespan opened (the mirror session, and the store a checkout keeps of
its origin). A double that models only the cookies fails wherever the index reads the
application, which it does for every repository checkout, the one these tests run in
included. So the doubles are this one request, and it carries the server's own
application: no lifespan has been entered on it, so it holds what a server holds before
any store is open.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from starlette.requests import Request

from metabrowser import server


def shell_request() -> Request:
    """A cookieless request for the shell, on the server's own application."""

    return cast(Request, SimpleNamespace(app=server.app, cookies={}))
