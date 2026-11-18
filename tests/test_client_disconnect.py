"""Only a client that left stops a request's work (``metabrowser/client_disconnect.py``).

Review E of #527 (E4): a ``receive`` that raised was taken for a disconnect, so the work
was cancelled and the route answered ``499`` to a caller it could not watch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from metabrowser.client_disconnect import unless_disconnected


class _Request:
    """A request whose next message is *message*, or which raises *error*."""

    def __init__(self, message: dict[str, Any] | None = None, error: Exception | None = None):
        self.message, self.error = message, error

    async def receive(self) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        if self.message is None:
            await asyncio.Event().wait()
        assert self.message is not None
        return self.message


async def _work(seconds: float) -> str:
    await asyncio.sleep(seconds)
    return "done"


def test_a_receive_that_fails_is_logged_and_the_work_runs_to_its_end(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = _Request(error=RuntimeError("no receive here"))
    with caplog.at_level(logging.WARNING, logger="metabrowser.client_disconnect"):
        answer = asyncio.run(unless_disconnected(request, _work(0.2)))  # pyright: ignore[reportArgumentType]
    assert answer == "done"
    assert any("no receive here" in record.getMessage() for record in caplog.records)


def test_a_client_that_left_cancels_the_work() -> None:
    request = _Request(message={"type": "http.disconnect"})
    assert asyncio.run(unless_disconnected(request, _work(5.0))) is None  # pyright: ignore[reportArgumentType]


def test_work_that_finishes_first_is_answered() -> None:
    request = _Request()
    assert asyncio.run(unless_disconnected(request, _work(0.0))) == "done"  # pyright: ignore[reportArgumentType]
