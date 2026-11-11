"""The projection worker: its protocol, its thread until the child is ready, and failures."""

from __future__ import annotations

import asyncio
import io
import json
import sys

import pytest

from metabrowser.diff import markdown_projection_worker as worker_module
from metabrowser.diff.markdown_projection import bind_markdown_diff, prepare_markdown_diff
from metabrowser.diff.markdown_projection_worker import ProjectionWorker, serve
from tests.test_markdown_diff_projection import (
    _patch,  # pyright: ignore[reportPrivateUsage]
)

OLD = b"# Guide\n\nSee [the old page](old.md) today.\n"
NEW = b"# Guide\n\nSee [the new page](new.md) now.\n"


def _frames(data: bytes) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    while data:
        size = int.from_bytes(data[:4], "big")
        frames.append(json.loads(data[4 : 4 + size]))
        data = data[4 + size :]
    return frames


def test_the_child_protocol_answers_what_the_server_would_compute() -> None:
    request = worker_module._encode(OLD, NEW, _patch(OLD, NEW), "n")  # pyright: ignore[reportPrivateUsage]
    sink = io.BytesIO()
    serve(io.BytesIO(worker_module._frame(request)), sink)  # pyright: ignore[reportPrivateUsage]
    ready, answer = _frames(sink.getvalue())
    assert ready == {"ready": True}
    decoded = worker_module._decode(answer)  # pyright: ignore[reportPrivateUsage]
    assert decoded == prepare_markdown_diff(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
    bound = bind_markdown_diff(decoded, lambda href, _image: f"/snapshot/{href}")
    assert 'href="/snapshot/new.md"' in bound["blocks"][-1]["html"]


def test_a_thread_worker_and_a_single_request_never_start_a_child() -> None:
    async def run() -> None:
        threaded = ProjectionWorker(processes=False)
        for _ in range(3):
            await threaded.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
        assert threaded._starting is None  # pyright: ignore[reportPrivateUsage]
        once = ProjectionWorker()
        answer = await once.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
        assert answer.projection["status"] == "ready"
        assert once._starting is None  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


@pytest.mark.skipif(
    not worker_module._gil_enabled(), reason="a build without the GIL keeps threads"
)  # pyright: ignore[reportPrivateUsage]
def test_projections_move_to_the_child_once_it_is_ready() -> None:
    async def run() -> None:
        worker = ProjectionWorker()
        patch = _patch(OLD, NEW)
        expected = prepare_markdown_diff(old=OLD, new=NEW, patch=patch, namespace="n")
        try:
            for _ in range(2):
                assert (
                    await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n") == expected
                )
            assert not worker.ready, "the first projections run while the child starts"
            async with asyncio.timeout(60):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None
            assert await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n") == expected
            assert worker._process is process  # pyright: ignore[reportPrivateUsage]
        finally:
            worker.stop()

    asyncio.run(run())


@pytest.mark.skipif(
    not worker_module._gil_enabled(), reason="a build without the GIL keeps threads"
)  # pyright: ignore[reportPrivateUsage]
def test_a_child_that_exits_mid_projection_is_stopped_and_refuses_that_input() -> None:
    # Says it is ready, then exits at the first request without answering.
    script = (
        "import sys, json\n"
        "body = json.dumps({'ready': True}).encode()\n"
        "sys.stdout.buffer.write(len(body).to_bytes(4, 'big') + body)\n"
        "sys.stdout.buffer.flush()\n"
        "sys.stdin.buffer.read(4)\n"
    )

    async def run() -> None:
        worker = ProjectionWorker(command=(sys.executable, "-c", script))
        patch = _patch(OLD, NEW)
        try:
            await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            async with asyncio.timeout(30):
                assert await worker.started()
            refused = await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            assert refused.projection["status"] == "unsupported"
            assert refused.projection["blocks"] == []
            assert not worker.ready
            assert worker._process is None  # pyright: ignore[reportPrivateUsage]
        finally:
            worker.stop()

    asyncio.run(run())
