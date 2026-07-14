"""Server-side data hooks for the built-in agent-log plugin."""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser.charts import extract_agent_charts
from metabrowser.gz_io import ArtifactPath


async def charts_handler(request: Request) -> JSONResponse:
    """Return tally and chart data for a supported coding-agent JSONL log."""
    from metabrowser.server import _safe_path  # noqa: PLC0415 -- avoids server import cycle

    subpath = request.query_params.get("path", "")
    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)
    if ArtifactPath(target).logical_ext != ".jsonl":
        return JSONResponse({"error": "Not a JSONL file"}, status_code=400)

    try:
        payload = await asyncio.to_thread(extract_agent_charts, target)
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(payload)
