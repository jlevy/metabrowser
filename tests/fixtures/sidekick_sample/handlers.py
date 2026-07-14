"""Test sidekick — echoes the query parameters back as JSON.

Exercises the data-hook handler contract: a callable that accepts a
Starlette Request and returns either a Response or a dict.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse


def echo_handler(request: Request) -> JSONResponse:
    """Echo handler — returns the `msg` and `path` query params."""
    return JSONResponse(
        {
            "echo": request.query_params.get("msg", ""),
            "path": request.query_params.get("path", ""),
        }
    )


def explode_handler(request: Request) -> JSONResponse:
    """Handler that raises so tests can assert graceful data-hook degradation."""
    raise RuntimeError("boom")


def explicit_500_handler(request: Request) -> JSONResponse:
    """Handler that returns an explicit 500 response."""
    return JSONResponse({"error": "explicit boom"}, status_code=500)
