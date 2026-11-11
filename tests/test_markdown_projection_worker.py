"""The projection worker: its protocol, its thread until the child is ready, and failures."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

from metabrowser.diff import markdown_projection_worker as worker_module
from metabrowser.diff.markdown_projection import bind_markdown_diff, prepare_markdown_diff
from metabrowser.diff.markdown_projection_worker import ProjectionWorker, serve
from tests.test_markdown_diff_projection import (
    _patch,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def processes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the child on every build.

    A build without the GIL keeps its projections in a thread by choice
    (`test_a_build_without_the_gil_keeps_its_thread`), not because a child cannot run
    there, so the child's own paths are tested on that build too.
    """

    monkeypatch.setattr(worker_module, "_gil_enabled", lambda: True)


_needs_child = pytest.mark.usefixtures("processes")

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


def test_a_build_without_the_gil_keeps_its_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without the GIL a projection thread does not stall the event loop, so a child
    # would cost its memory for nothing.
    monkeypatch.setattr(worker_module, "_gil_enabled", lambda: False)

    async def run() -> None:
        worker = ProjectionWorker()
        patch = _patch(OLD, NEW)
        for _ in range(3):
            answer = await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            assert answer.projection["status"] == "ready"
        worker.start()
        assert not await worker.started()
        assert worker._starting is None  # pyright: ignore[reportPrivateUsage]
        assert worker._process is None  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())


@_needs_child
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


@_needs_child
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


# A child that says it is ready and then never answers.
_SILENT = (
    "import sys, json, time\n"
    "body = json.dumps({'ready': True}).encode()\n"
    "sys.stdout.buffer.write(len(body).to_bytes(4, 'big') + body)\n"
    "sys.stdout.buffer.flush()\n"
    "time.sleep(600)\n"
)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@_needs_child
def test_the_child_runs_only_installed_code_wherever_the_server_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "imported"
    (tmp_path / "base64.py").write_text(
        f"open({str(marker)!r}, 'a').write('imported')\nfrom binascii import *\n",
        encoding="utf-8",
    )
    (tmp_path / "json.py").write_text(
        f"open({str(marker)!r}, 'a').write('imported')\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    async def run() -> None:
        worker = ProjectionWorker()
        worker.start()
        try:
            async with asyncio.timeout(60):
                assert await worker.started()
            answer = await worker.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
            assert answer.projection["status"] == "ready"
        finally:
            worker.stop()

    asyncio.run(run())
    assert not marker.exists(), "the child imported a module from the working directory"


@_needs_child
def test_a_child_that_died_while_idle_answers_from_a_thread_and_starts_again() -> None:
    async def run() -> None:
        worker = ProjectionWorker()
        patch = _patch(OLD, NEW)
        try:
            worker.start()
            async with asyncio.timeout(60):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None
            process.kill()
            await process.wait()
            answer = await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            assert answer.projection["status"] == "ready", "not this input's failure"
            assert worker._process is None  # pyright: ignore[reportPrivateUsage]
            await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            async with asyncio.timeout(60):
                assert await worker.started(), "the next projection starts a child again"
        finally:
            worker.stop()

    asyncio.run(run())


@_needs_child
def test_a_child_that_cannot_start_is_tried_again_up_to_the_limit(tmp_path: Path) -> None:
    async def run() -> None:
        worker = ProjectionWorker(command=(str(tmp_path / "absent-python"),))
        for _ in range(5):
            worker.start()
            assert not await worker.started()
        assert worker._starts == 3  # pyright: ignore[reportPrivateUsage]
        answer = await worker.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
        assert answer.projection["status"] == "ready", "the thread answers instead"

    asyncio.run(run())


@_needs_child
def test_an_overrunning_child_is_stopped_and_refuses_that_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_PROJECTION_TIMEOUT_S", 0.3)

    async def run() -> None:
        worker = ProjectionWorker(command=(sys.executable, "-c", _SILENT))
        try:
            worker.start()
            async with asyncio.timeout(30):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None
            answer = await worker.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
            assert answer.projection["status"] == "too_large"
            assert answer.projection["blocks"] == []
            assert await process.wait() is not None
            assert worker._process is None  # pyright: ignore[reportPrivateUsage]
        finally:
            worker.stop()

    asyncio.run(run())


@_needs_child
def test_a_cancelled_exchange_stops_the_child_so_no_answer_is_left_behind() -> None:
    async def run() -> None:
        worker = ProjectionWorker(command=(sys.executable, "-c", _SILENT))
        try:
            worker.start()
            async with asyncio.timeout(30):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None
            task = asyncio.create_task(
                worker.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
            )
            await asyncio.sleep(0.2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert await process.wait() is not None
            assert worker._process is None  # pyright: ignore[reportPrivateUsage]
        finally:
            worker.stop()

    asyncio.run(run())


@_needs_child
def test_a_new_event_loop_replaces_the_child_the_old_loop_started() -> None:
    worker = ProjectionWorker(command=(sys.executable, "-c", _SILENT))
    pids: list[int] = []

    async def first() -> None:
        worker.start()
        async with asyncio.timeout(30):
            assert await worker.started()
        process = worker._process  # pyright: ignore[reportPrivateUsage]
        assert process is not None
        pids.append(process.pid)

    async def second() -> None:
        assert not worker.ready, "a child belongs to the loop that started it"
        worker.start()
        try:
            async with asyncio.timeout(30):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None and process.pid != pids[0]
        finally:
            worker.stop()

    asyncio.run(first())
    asyncio.run(second())
    for _ in range(50):
        if not _alive(pids[0]):
            break
        time.sleep(0.05)
    assert not _alive(pids[0]), "the old loop's child was stopped"


@_needs_child
def test_an_idle_child_is_stopped_and_the_next_projection_starts_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_IDLE_S", 0.3)

    async def run() -> None:
        worker = ProjectionWorker()
        patch = _patch(OLD, NEW)
        try:
            worker.start()
            async with asyncio.timeout(60):
                assert await worker.started()
            process = worker._process  # pyright: ignore[reportPrivateUsage]
            assert process is not None
            await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            await asyncio.sleep(0.8)
            assert worker._process is None, "the idle child was stopped"  # pyright: ignore[reportPrivateUsage]
            assert await process.wait() is not None
            answer = await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            assert answer.projection["status"] == "ready", "from the thread meanwhile"
            await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n")
            async with asyncio.timeout(60):
                assert await worker.started()
        finally:
            worker.stop()

    asyncio.run(run())


@_needs_child
def test_a_child_no_projection_reaches_is_stopped_when_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A page's prefetch starts the child, and every answer may then come from the
    # thread or the route's cache, so the idle stop counts from the start.
    monkeypatch.setattr(worker_module, "_IDLE_S", 0.3)

    async def run() -> None:
        worker = ProjectionWorker()
        try:
            for _ in range(2):
                worker.start()
                async with asyncio.timeout(60):
                    assert await worker.started()
                process = worker._process  # pyright: ignore[reportPrivateUsage]
                assert process is not None
                await asyncio.sleep(0.8)
                assert worker._process is None, "a child nothing used was stopped"  # pyright: ignore[reportPrivateUsage]
                assert await process.wait() is not None
        finally:
            worker.stop()

    asyncio.run(run())
