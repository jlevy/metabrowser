"""Run Markdown projections in one long-lived child process, off the server's GIL.

A projection is pure Python. In a thread it holds the GIL, and every other request on
the server waits up to the interpreter's switch interval at each of its event-loop
wake-ups. With the 48,719-byte ``docs/reviewing-pull-requests.md`` pair projecting
continuously (Python 3.14, development Mac, load average 4, three alternating phases),
a request of eight wake-ups took 1.41-1.44 ms idle (p50), 32-35 ms beside a projection
thread and 1.41-1.42 ms (p95 at most 1.83 ms) beside the same projections in this
child, at the same 35-37 projections in 1.5 s. The repository budgets 50 ms for an
unrelated request's delay (``inventory_engine/providers/python_inventory.py``), and a
request with more wake-ups pays the switch interval at each.

The child costs memory while it runs: 56-66 MB resident once it is ready and 63-70 MB
after all 434 of this repository's real Markdown pairs (macOS ``ps`` RSS, two runs each
in two reviews of #349, under different loads). It starts only when a server projects a
second file, or a page asks ahead for its first screen, and it stops after ten idle
minutes.

The child is this module run with ``python -m``, so it never imports the server's main
module, and it speaks length-prefixed JSON over its standard input and output: plain
data each way, nothing executable. It starts at the second projection an event loop
asks for, or when :meth:`ProjectionWorker.start` is called (a page's ``prefetch=1``
request), and until it has imported the renderer each
projection runs in a thread, so the first screen of a Changes tab never waits for it.
A build without the GIL, or a platform where the child cannot start, keeps the thread.
A child that overruns or exits is stopped and started again on demand.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

from metabrowser.diff.format import FilePatch
from metabrowser.diff.markdown_projection import (
    LocalReference,
    MarkdownDiffProjection,
    PreparedMarkdownDiff,
    prepare_markdown_diff,
    unavailable_markdown_diff,
    warm_markdown_projection,
)

# A frame larger than this is a protocol fault: a request is at most 48 KiB of blobs
# and their patch, and an answer at most a few hundred KiB of HTML.
_MAX_FRAME = 16 * 1024 * 1024
# The child was ready 0.57 s after it started at load average 4 (review C of #349 saw
# about 2 s under heavier load); it is given far longer before it counts as failed.
_START_TIMEOUT_S = 30.0
# A projection answers within its budgets in well under a second (the slowest input
# measured inside every budget took 222-268 ms); a child that has not after this is
# stopped.
_PROJECTION_TIMEOUT_S = 10.0
# Starts that did not last before the worker settles on its thread for good.
_MAX_STARTS = 3
# A child no projection has used for this long is stopped; the next one starts it again,
# and runs in a thread while it does. A start took 0.23-0.24 s to ready (review E of
# #349), against 56-63 MB kept resident for as long as the server runs.
_IDLE_S = 600.0


def _gil_enabled() -> bool:
    probe = cast("Callable[[], bool] | None", getattr(sys, "_is_gil_enabled", None))
    return True if probe is None else probe()


def _frame(payload: object) -> bytes:
    data = json.dumps(payload, separators=(",", ":")).encode()
    return len(data).to_bytes(4, "big") + data


def _encode(
    old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
) -> dict[str, Any]:
    def blob(data: bytes | None) -> str | None:
        return None if data is None else base64.b64encode(data).decode()

    return {
        "old": blob(old),
        "new": blob(new),
        "patch": patch.model_dump(mode="json"),
        "namespace": namespace,
    }


def _decode(answer: dict[str, Any]) -> PreparedMarkdownDiff:
    projection = cast("MarkdownDiffProjection", answer["projection"])
    references = tuple(
        LocalReference(str(href), bool(image), str(template), str(fallback))
        for href, image, template, fallback in answer["references"]
    )
    return PreparedMarkdownDiff(projection, references)


def _answer(request: dict[str, Any]) -> dict[str, Any]:
    def blob(value: object) -> bytes | None:
        return None if value is None else base64.b64decode(str(value), validate=True)

    prepared = prepare_markdown_diff(
        old=blob(request["old"]),
        new=blob(request["new"]),
        patch=FilePatch.model_validate(request["patch"]),
        namespace=str(request["namespace"]),
    )
    return {
        "projection": prepared.projection,
        "references": [
            [reference.href, reference.image, reference.template, reference.fallback]
            for reference in prepared.references
        ],
    }


def serve(source: BinaryIO, sink: BinaryIO) -> None:
    """The child's loop: one answer for each request until its input closes."""

    warm_markdown_projection()
    sink.write(_frame({"ready": True}))
    sink.flush()
    while len(header := source.read(4)) == 4:
        size = int.from_bytes(header, "big")
        if size > _MAX_FRAME:
            return
        body = source.read(size)
        if len(body) != size:
            return
        sink.write(_frame(_answer(json.loads(body))))
        sink.flush()


async def _read(stream: asyncio.StreamReader) -> dict[str, Any]:
    size = int.from_bytes(await stream.readexactly(4), "big")
    if size > _MAX_FRAME:
        raise ConnectionError("oversized projection frame")
    return cast("dict[str, Any]", json.loads(await stream.readexactly(size)))


_CHILDREN: set[int] = set()


def _stop_children() -> None:
    for pid in list(_CHILDREN):
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
    _CHILDREN.clear()


# A child also exits when its input closes with this process; this ends one mid-import.
_register = cast(
    "Callable[[Callable[[], None]], None] | None", getattr(threading, "_register_atexit", None)
)
if _register is not None:
    _register(_stop_children)


class ProjectionWorker:
    """Prepare projections in the child once it is ready, and in a thread until then."""

    def __init__(self, *, processes: bool = True, command: Sequence[str] | None = None) -> None:
        self._processes = processes and _gil_enabled()
        # Isolated mode: no working directory or script directory on the module path, and
        # no PYTHON* variable or user site-packages, so the child runs only installed code
        # wherever the server was started (a checkout of the reviewed pull request
        # included). It starts in the package's own directory, as cache/probe.py's does.
        self._command = tuple(command or (sys.executable, "-I", "-m", __name__))
        self._process: asyncio.subprocess.Process | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock: asyncio.Lock | None = None
        self._starting: asyncio.Task[None] | None = None
        self._ready = False
        self._starts = 0
        self._requests = 0
        self._counted: asyncio.AbstractEventLoop | None = None
        self._used = 0.0
        self._idle_timer: asyncio.TimerHandle | None = None

    @property
    def ready(self) -> bool:
        """Whether projections now run in the child."""

        return self._ready and self._loop is _running_loop()

    async def started(self) -> bool:
        """Wait for a start in progress; whether projections now run in the child."""

        if self._starting is not None:
            await asyncio.shield(self._starting)
        return self.ready

    def start(self) -> None:
        """Start the child on this event loop if it is not running; it does not wait."""

        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            # A child's pipes belong to the loop that started it.
            self.stop()
        if not self._processes or self._starting is not None or self._starts >= _MAX_STARTS:
            return
        self._starts += 1
        self._loop, self._lock = loop, asyncio.Lock()
        self._starting = loop.create_task(self._launch())

    async def _launch(self) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=Path(__file__).resolve().parent,
            )
        except OSError:
            # The next projection may try again, up to the start limit.
            self._starting = None
            return
        self._process = process
        _CHILDREN.add(process.pid)
        assert process.stdout is not None
        try:
            ready = await asyncio.wait_for(_read(process.stdout), _START_TIMEOUT_S)
        except (TimeoutError, ConnectionError, asyncio.IncompleteReadError, ValueError):
            self._kill(process)
            return
        if ready.get("ready") is True and self._process is process:
            self._ready = True
            self._starts = 0
            # Counted from the start, not the first answer: a page's prefetch starts the
            # child, and its answers may all come from the thread or the route's cache.
            self._touch()

    def _touch(self) -> None:
        """Note a start or a projection, and stop the child once _IDLE_S passes without one."""

        loop = asyncio.get_running_loop()
        self._used = loop.time()
        if self._idle_timer is None:
            self._idle_timer = loop.call_later(_IDLE_S, self._idle)

    def _idle(self) -> None:
        self._idle_timer = None
        loop = self._loop
        if loop is None or self._process is None:
            return
        waited = loop.time() - self._used
        if waited < _IDLE_S or (self._lock is not None and self._lock.locked()):
            self._idle_timer = loop.call_later(max(_IDLE_S - waited, 0.0), self._idle)
            return
        self.stop()

    def _kill(self, process: asyncio.subprocess.Process) -> None:
        if self._process is process:
            self._process, self._ready, self._starting = None, False, None
        _CHILDREN.discard(process.pid)
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()

    def stop(self) -> None:
        """Stop the child; the next start begins a new one."""

        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        if self._process is not None:
            self._kill(self._process)
        if self._starting is not None:
            self._starting.cancel()
        self._process, self._ready, self._starting = None, False, None
        self._loop = self._lock = None

    async def prepare(
        self, *, old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
    ) -> PreparedMarkdownDiff:
        loop = asyncio.get_running_loop()
        if self._counted is not loop:
            # Each event loop counts its own: a command that runs one request per loop
            # in a process never starts a child.
            self._counted, self._requests = loop, 0
        self._requests += 1
        if self._requests >= 2:
            # A one-request command never pays for a child it would not use.
            self.start()
        process, lock = self._process, self._lock
        if not self.ready or process is None or lock is None:
            return await asyncio.to_thread(
                prepare_markdown_diff, old=old, new=new, patch=patch, namespace=namespace
            )
        assert process.stdin is not None and process.stdout is not None
        failure: Literal["unsupported", "too_large"] = "unsupported"
        async with lock:
            try:
                if process.returncode is not None:
                    raise ConnectionError("the child exited while idle")
                process.stdin.write(_frame(_encode(old, new, patch, namespace)))
                await process.stdin.drain()
            except ConnectionError:
                # Gone before this request reached it: not this input's doing, so the
                # request runs in a thread and the next one starts a child again.
                self._kill(process)
                return await asyncio.to_thread(
                    prepare_markdown_diff, old=old, new=new, patch=patch, namespace=namespace
                )
            except BaseException:
                # A request cut off part-way leaves the child's input out of step.
                self._kill(process)
                raise
            try:
                answer = _decode(
                    await asyncio.wait_for(_read(process.stdout), _PROJECTION_TIMEOUT_S)
                )
                self._touch()
                return answer
            except TimeoutError:
                failure = "too_large"
            except (ConnectionError, asyncio.IncompleteReadError, ValueError, KeyError):
                # The input may be what stopped it, so it is not retried in this process.
                pass
            except BaseException:
                # A cancelled exchange leaves an answer in the pipe for the next request.
                self._kill(process)
                raise
            self._kill(process)
        return unavailable_markdown_diff(failure)


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def main() -> None:
    # The protocol owns the original standard output; anything a library prints goes to
    # standard error instead of into a frame.
    sink = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    serve(sys.stdin.buffer, sink)


if __name__ == "__main__":
    main()
