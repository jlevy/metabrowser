"""HTTP-readiness polling shared by local and tunneled browser launchers."""

from __future__ import annotations

import http.client
import time
from collections.abc import Callable
from urllib.parse import urlsplit


def _never_cancelled() -> bool:
    return False


def wait_for_http_ok_then(
    host: str,
    port: int,
    url: str,
    *,
    on_ready: Callable[[], None],
    on_error: Callable[[str], None],
    is_cancelled: Callable[[], bool] = _never_cancelled,
    timeout_s: float = 10.0,
) -> None:
    """Poll ``url`` until it serves HTTP OK, then invoke ``on_ready``.

    A client error is final, while server errors and connection failures are
    retried until the timeout. Cancellation returns quietly so a failed SSH
    process can report its own actionable error.
    """
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"

    deadline = time.monotonic() + timeout_s
    last_error: BaseException | None = None
    last_status: int | None = None
    while time.monotonic() < deadline:
        if is_cancelled():
            return
        conn: http.client.HTTPConnection | None = None
        try:
            conn = http.client.HTTPConnection(host, port, timeout=0.2)
            conn.request("GET", path, headers={"Connection": "close"})
            response = conn.getresponse()
            last_status = response.status
            response.read(256)
            if 200 <= response.status < 300:
                on_ready()
                return
            if 400 <= response.status < 500:
                on_error(f"Server returned HTTP {response.status} for {url}; not opening browser.")
                return
            time.sleep(0.05)
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
            time.sleep(0.05)
        finally:
            if conn is not None:
                conn.close()

    detail = f"last HTTP status {last_status}" if last_status is not None else "no HTTP response"
    if last_error is not None:
        detail = f"{detail}; {last_error}"
    on_error(
        f"Server did not serve HTTP OK at {url} within {timeout_s}s ({detail}); "
        "not opening browser automatically."
    )
