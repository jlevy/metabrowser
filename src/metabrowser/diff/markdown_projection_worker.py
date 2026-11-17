"""Run Markdown off the server's interpreter, in one long-lived child process.

The child does two jobs. It projects Markdown diffs, and it renders every Markdown
document an untrusted author wrote: a pinned mirror's files, a folder served with
``--untrusted``, and a pull request's texts (:meth:`ProjectionWorker.render_inert`).

**Projections.** A projection is pure Python. In a thread it holds the GIL, and every
other request on the server waits up to the interpreter's switch interval at each of its
event-loop wake-ups. With the 48,719-byte ``docs/reviewing-pull-requests.md`` pair
projecting continuously (Python 3.14, development Mac, load average 4, three alternating
phases), a request of eight wake-ups took 1.41-1.44 ms idle (p50), 32-35 ms beside a
projection thread and 1.41-1.42 ms (p95 at most 1.83 ms) beside the same projections in
this child, at the same 35-37 projections in 1.5 s. The repository budgets 50 ms for an
unrelated request's delay (``inventory_engine/providers/python_inventory.py``), and a
request with more wake-ups pays the switch interval at each. A projection starts the
child at the second one an event loop asks for, or when :meth:`ProjectionWorker.start`
is called (a page's ``prefetch=1`` request), and until it has imported the renderer each
projection runs in a thread, so the first screen of a Changes tab never waits for it. A
build without the GIL, or a platform where the child cannot start, keeps the thread.

**Inert renders.** KPress's cost depends on what a document contains, not only on its
size, and a document's author can choose it: the review of mb-273l timed 23.1 s for
1,000 unpaired ``[`` before 239 KB of ``%``, 2.5 s for one 512 KiB line of ``a--b``, and
11.6 s for a highlighted 1,622-byte ``console`` fence. A thread cannot be stopped, so a
render of such a document held the interpreter until it finished, and each reload
started another. Here a render that runs past :data:`_RENDER_DEADLINE_S` is stopped with
its child and refused, and the refusal is kept by the document's identity, its blob ID
or a hash of its text, so a reload is refused at once. An inert render never runs in a
thread: until the child is ready it waits for it, at most :data:`_START_WAIT_S`, and is
refused when it is not. It renders fenced code plain (``plain_code`` in
:mod:`metabrowser.kpress_adapter`), since the inert page drops every class the
highlighting would add, and reduces the HTML to the inert allowlist
(:mod:`metabrowser.inert_html`) in the child too. A served pin starts the child as it
attaches (``cli/git_pin_cli.py``), and a pull request's page at its first read of the pull
route, so a first document or text does not wait for the start.

The child costs memory while it runs: 56-66 MB resident once it is ready and 63-70 MB
after all 434 of this repository's real Markdown pairs (macOS ``ps`` RSS, two runs each
in two reviews of #349, under different loads). It stops after ten idle minutes, and
the next render or projection starts it again.

The child is this module run with ``python -m``, so it never imports the server's main
module, and it speaks length-prefixed JSON over its standard input and output: plain
data each way, nothing executable. One request runs at a time. A child that overruns or
exits is stopped and started again on demand.

This module is imported by the server, so the projection module, which imports KPress
and Pygments, is imported where a projection runs rather than here: the server's start
does not pay for a renderer, as :mod:`metabrowser.kpress_adapter` explains.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import signal
import sys
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Final, Literal, cast

from metabrowser import kpress_adapter
from metabrowser.diff.format import FilePatch

if TYPE_CHECKING:
    from metabrowser.diff.markdown_projection import MarkdownDiffProjection, PreparedMarkdownDiff

# A request frame larger than this is a protocol fault. A projection is at most 48 KiB
# of blobs and their patch; a render is the route's text, at most
# ``settings.TEXT_PREVIEW_REQUEST_MAX_BYTES`` (16 MiB) of UTF-8, base64-encoded to a
# third more, beside its front matter, which is parsed from the same text.
_MAX_REQUEST_FRAME: Final = 64 * 1024 * 1024
# An answer frame larger than this is a protocol fault. A projection answers at most a
# few hundred KiB of HTML. A render's answer is bounded by what the child writes before
# the deadline, and is mostly KPress's record of the raw HTML it removed
# (``sanitizer_diagnostics``): measured 2026-11-17 (load average 10 to 21), 256 KiB of
# an unknown tag answered 10.8 MB in 1.2 s, 41 times its source, and the largest of this
# repository's Markdown files 2.1 MB. The bound is several deadlines of that.
_MAX_ANSWER_FRAME: Final = 256 * 1024 * 1024
# The child was ready 0.57 s after it started at load average 4 (review C of #349 saw
# about 2 s under heavier load); it is given far longer before it counts as failed.
_START_TIMEOUT_S = 30.0
# A projection answers within its budgets in well under a second (the slowest input
# measured inside every budget took 222-268 ms); a child that has not after this is
# stopped.
_PROJECTION_TIMEOUT_S = 10.0
# The longest one untrusted document's render may run in the child before the child is
# stopped and the document refused. Measured 2026-11-17 on an Apple M1 Pro
# (MacBookPro18,1), macOS 26.5.2, Python 3.14.7, KPress 0.3.8, at a load average of 9.9
# to 12.6, three renders of each with plain code and the inert hardening, as the child
# runs them: of the 30 largest Markdown files tracked in this repository, the slowest,
# `explorations/performance-loop/report.md` (325 KB), took 1.07 to 1.19 s to render and
# 0.19 s to harden, and the next, `docs/design-system.md` (340 KB), 0.22 to 0.23 s and
# 0.02 to 0.03 s; the other 28 took 0.04 to 0.23 s in all. Through the child, frames
# included, report.md answered in 1.26 to 1.75 s over five renders at a load average of
# 16 to 17. Five seconds is about three times that, room for a heavier load; a document
# over it is shown as source. METABROWSER_INERT_RENDER_DEADLINE_MS replaces it, as the
# other budgets in docs/command-line.md are replaced.
INERT_RENDER_DEADLINE_MS: Final = 5_000
_RENDER_DEADLINE_S = (
    int(os.environ.get("METABROWSER_INERT_RENDER_DEADLINE_MS", str(INERT_RENDER_DEADLINE_MS)))
    / 1000
)
# How long an inert render waits for the child to start: as long as a render may run,
# whatever the environment sets the deadline to. A start, both jobs warmed, took 1.36 s
# at load average 16 (2026-11-17; the projection alone 0.23 to 0.57 s at load average 4
# in #349); past this the render is refused as unavailable, and that refusal is not kept.
_START_WAIT_S = INERT_RENDER_DEADLINE_MS / 1000
# Starts in a row that did not become ready before the worker stops trying: projections
# stay in their thread, and inert renders are refused as unavailable, until a stop (a new
# event loop, or a server's end) counts again.
_MAX_STARTS = 3
# A child no projection or render has used for this long is stopped; the next one starts
# it again. A start took 0.23-0.24 s to ready (review E of #349), against 56-63 MB kept
# resident for as long as the server runs.
_IDLE_S = 600.0
# Refusals kept, by document. Each one cost a deadline of the child's time, so a server
# reaches this only after hours of refused renders; it bounds what a flood of distinct
# documents can make the server keep, at about 100 bytes a key.
_MAX_VERDICTS: Final = 1024

type RefusalCode = Literal["render_deadline", "renderer_exited", "renderer_unavailable"]

_REFUSALS: Final[dict[RefusalCode, tuple[int, str]]] = {
    "render_deadline": (422, "Rendering took longer than {deadline}, so it was stopped"),
    "renderer_exited": (422, "The renderer stopped while rendering this document"),
    "renderer_unavailable": (503, "The document renderer could not start"),
}


class InertRenderRefused(Exception):
    """An untrusted document's render was refused, and *code* says why."""

    def __init__(self, code: RefusalCode) -> None:
        super().__init__(code)
        self.code: RefusalCode = code

    @property
    def http_status(self) -> int:
        """The status a route answers the refusal with."""

        return _REFUSALS[self.code][0]

    @property
    def remembered(self) -> bool:
        """Whether the document is refused again at once: everything but an unavailable child."""

        return self.code != "renderer_unavailable"

    def payload(self) -> dict[str, Any]:
        """What a route answers: the code, a sentence for ``--api``, and the deadline."""

        seconds = _RENDER_DEADLINE_S
        deadline = f"{seconds:g} second" + ("" if seconds == 1 else "s")
        return {
            "code": self.code,
            "error": _REFUSALS[self.code][1].format(deadline=deadline),
            "deadline_ms": round(seconds * 1000),
        }


def kpress_refusal_payload(refused: InertRenderRefused, path: str) -> dict[str, Any]:
    """The ``/api/kpress/render`` answer to a refused render, on a folder and a pin alike."""

    return {"type": "kpress_render_refused", **refused.payload(), "path": path}


@dataclass(frozen=True, slots=True)
class InertRender:
    """One untrusted document to render in the child.

    *identity* names the document's bytes: ``blob:<oid>`` for a Git blob, or
    :func:`text_identity` of the text. A refusal is kept by it with the kind, extension,
    and mode, so another request for the same bytes is refused without rendering.
    *link_base*, when given, makes the answer a pull request's text: only its HTML,
    reduced by :func:`metabrowser.inert_html.harden` with every reference made absolute
    against that page. Without it the answer is :func:`kpress_adapter.inert_render`'s.
    """

    source_text: str
    source_path: str
    identity: str
    kind: str
    view: str
    ext: str
    mtime_hash: str
    size: int
    frontmatter: dict[str, Any] | None = None
    frontmatter_error: str | None = None
    profile: str | None = None
    include_toc: Literal["auto", "on", "off"] = "auto"
    link_base: str | None = None

    @property
    def verdict_key(self) -> tuple[str, ...]:
        return (self.identity, self.kind, self.ext, "text" if self.link_base else "document")

    @property
    def flight_key(self) -> tuple[object, ...]:
        """Everything that makes one render differ from another of the same bytes."""

        return (
            *self.verdict_key,
            self.source_path,
            self.view,
            self.mtime_hash,
            self.profile,
            self.include_toc,
            self.link_base,
            self.frontmatter_error,
            json.dumps(self.frontmatter, sort_keys=True, default=str),
        )


def text_identity(text: str) -> str:
    """The identity of a document with no blob: a hash of its text. Blocking for a large text."""

    return "sha256:" + hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


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
        "op": "project",
        "old": blob(old),
        "new": blob(new),
        "patch": patch.model_dump(mode="json"),
        "namespace": namespace,
    }


def _encode_render(request: InertRender, asset_url_prefix: str) -> dict[str, Any]:
    return {
        "op": "render",
        "source": base64.b64encode(request.source_text.encode("utf-8", "surrogatepass")).decode(),
        "source_path": request.source_path,
        "kind": request.kind,
        "view": request.view,
        "ext": request.ext,
        "mtime_hash": request.mtime_hash,
        "size": request.size,
        "frontmatter": request.frontmatter,
        "frontmatter_error": request.frontmatter_error,
        "profile": request.profile,
        "include_toc": request.include_toc,
        "asset_url_prefix": asset_url_prefix,
        "link_base": request.link_base,
    }


def _decode(answer: dict[str, Any]) -> PreparedMarkdownDiff:
    from metabrowser.diff.markdown_projection import LocalReference, PreparedMarkdownDiff

    projection = cast("MarkdownDiffProjection", answer["projection"])
    references = tuple(
        LocalReference(str(href), bool(image), str(template), str(fallback))
        for href, image, template, fallback in answer["references"]
    )
    return PreparedMarkdownDiff(projection, references)


def _project(request: dict[str, Any]) -> dict[str, Any]:
    from metabrowser.diff.markdown_projection import prepare_markdown_diff

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


def _render(request: dict[str, Any]) -> dict[str, Any]:
    """One inert render, as the child answers it: the render, or which KPress error."""

    from metabrowser.inert_html import harden

    source = base64.b64decode(str(request["source"]), validate=True)
    try:
        rendered = kpress_adapter.render_kpress_view(
            source_text=source.decode("utf-8", "surrogatepass"),
            source_path=str(request["source_path"]),
            kind=str(request["kind"]),
            view=str(request["view"]),
            ext=str(request["ext"]),
            mtime_hash=str(request["mtime_hash"]),
            size=int(request["size"]),
            frontmatter=cast("dict[str, Any] | None", request["frontmatter"]),
            frontmatter_error=cast("str | None", request["frontmatter_error"]),
            profile=cast("str | None", request["profile"]),
            include_toc=cast("Literal['auto', 'on', 'off']", request["include_toc"]),
            plain_code=True,
            asset_url_prefix=str(request["asset_url_prefix"]),
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return {"error": "invalid", "message": str(exc)}
    except kpress_adapter.KPressRenderError as exc:
        return {"error": "render", "message": str(exc)}
    link_base = request["link_base"]
    if isinstance(link_base, str):
        return {"rendered": {"html": harden(str(rendered["html"]), link_base)}}
    return {"rendered": kpress_adapter.inert_render(rendered)}


def _answer(request: dict[str, Any]) -> dict[str, Any]:
    return _render(request) if request.get("op") == "render" else _project(request)


def _warm() -> None:
    """Import and exercise both jobs once, as the child's first work."""

    from metabrowser.diff.markdown_projection import warm_markdown_projection

    warm_markdown_projection()
    _render(
        _encode_render(
            InertRender(
                source_text="# Warm\n\nA [link](a.md), `code`, and\n\n```console\n$ x\n```\n",
                source_path="warm.md",
                identity="warm",
                kind="markdown",
                view="document",
                ext=".md",
                mtime_hash="warm",
                size=0,
            ),
            "/kpress-static/",
        )
    )


def serve(source: BinaryIO, sink: BinaryIO) -> None:
    """The child's loop: one answer for each request until its input closes."""

    _warm()
    sink.write(_frame({"ready": True}))
    sink.flush()
    while len(header := source.read(4)) == 4:
        size = int.from_bytes(header, "big")
        if size > _MAX_REQUEST_FRAME:
            return
        body = source.read(size)
        if len(body) != size:
            return
        sink.write(_frame(_answer(json.loads(body))))
        sink.flush()


async def _read_body(stream: asyncio.StreamReader, limit: int) -> bytes:
    size = int.from_bytes(await stream.readexactly(4), "big")
    if size > limit:
        raise ConnectionError("oversized frame from the Markdown child")
    return await stream.readexactly(size)


async def _read(stream: asyncio.StreamReader) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(await _read_body(stream, _MAX_ANSWER_FRAME)))


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
    """Prepare projections in the child once it is ready, and in a thread until then;
    render untrusted documents in the child only."""

    def __init__(self, *, processes: bool = True, command: Sequence[str] | None = None) -> None:
        # Whether projections may move to the child. Inert renders always use it.
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
        self._verdicts: OrderedDict[tuple[str, ...], RefusalCode] = OrderedDict()
        self._flights: dict[tuple[object, ...], asyncio.Task[dict[str, Any]]] = {}

    @property
    def ready(self) -> bool:
        """Whether the child is ready on this event loop."""

        return self._ready and self._loop is _running_loop()

    async def started(self) -> bool:
        """Wait for a start in progress; whether the child is now ready."""

        if self._starting is not None:
            await asyncio.shield(self._starting)
        return self.ready

    def start(self, *, renders: bool = False) -> None:
        """Start the child on this event loop if it is not running; it does not wait.

        Projections start it only where they would use it; *renders* starts it on any
        build, since an inert render runs nowhere else.
        """

        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            # A child's pipes belong to the loop that started it.
            self.stop()
        if (
            (not self._processes and not renders)
            or self._starting is not None
            or self._starts >= _MAX_STARTS
        ):
            return
        self._starts += 1
        if self._loop is not loop or self._lock is None:
            self._loop, self._lock = loop, asyncio.Lock()
            self._flights = {}
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
        """Note a start or a request, and stop the child once _IDLE_S passes without one."""

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
        """Stop the child; the next start begins a new one, with its starts counted anew.

        A start this cuts off did not fail, and a server's lifespan, or a command's, ends
        with one: so the next loop may start the child again, up to the start limit.
        """

        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        if self._process is not None:
            self._kill(self._process)
        if self._starting is not None:
            self._starting.cancel()
        self._process, self._ready, self._starting = None, False, None
        self._loop = self._lock = None
        self._flights = {}
        self._starts = 0

    async def prepare(
        self, *, old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
    ) -> PreparedMarkdownDiff:
        from metabrowser.diff.markdown_projection import (
            prepare_markdown_diff,
            unavailable_markdown_diff,
        )

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
        if not self._processes or not self.ready or process is None or lock is None:
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

    def refusal(self, request: InertRender) -> InertRenderRefused | None:
        """The kept refusal of *request*'s document, if an earlier render was refused."""

        code = self._verdicts.get(request.verdict_key)
        if code is None:
            return None
        self._verdicts.move_to_end(request.verdict_key)
        return InertRenderRefused(code)

    async def render_inert(self, request: InertRender) -> dict[str, Any]:
        """*request* rendered and hardened in the child, within the deadline.

        Raises :class:`InertRenderRefused` when the render ran past the deadline, the
        child stopped while rendering it, or the child could not start, and
        :class:`kpress_adapter.KPressInvalidRequestError` or
        :class:`kpress_adapter.KPressRenderError` as an in-process render would. A
        request identical to one in flight waits for that render rather than queueing
        another, so reloads of a slow document do not stack.
        """

        refused = self.refusal(request)
        if refused is not None:
            raise refused
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self.start(renders=True)
        key = request.flight_key
        flight = self._flights.get(key)
        if flight is None:
            flight = loop.create_task(self._render_once(request))
            flights = self._flights
            flights[key] = flight

            def landed(task: asyncio.Task[dict[str, Any]]) -> None:
                if flights.get(key) is task:
                    del flights[key]
                if not task.cancelled():
                    # Retrieved here, so a render no request waits for any more is quiet.
                    task.exception()

            flight.add_done_callback(landed)
        return await asyncio.shield(flight)

    async def _ready_child(self) -> asyncio.subprocess.Process | None:
        """The ready child on this loop, started and waited for when there is none."""

        process = self._process
        if self.ready and process is not None and process.returncode is None:
            return process
        if process is not None and process.returncode is not None:
            # Gone while idle; one still starting is waited for, not replaced.
            self._kill(process)
        self.start(renders=True)
        try:
            async with asyncio.timeout(_START_WAIT_S):
                ready = await self.started()
        except TimeoutError:
            ready = False
        return self._process if ready else None

    async def _render_once(self, request: InertRender) -> dict[str, Any]:
        # The server's asset prefix, so the child names the assets this server serves.
        frame = await asyncio.to_thread(
            lambda: _frame(_encode_render(request, kpress_adapter.kpress_asset_url_prefix()))
        )
        lock = self._lock
        if lock is None:
            # Stopped since the flight began, with its loop: start on this one again.
            self.start(renders=True)
            lock = self._lock
        if lock is None:
            raise InertRenderRefused("renderer_unavailable")
        async with lock:
            # Another request may have refused the same document while this one waited.
            refused = self.refusal(request)
            if refused is not None:
                raise refused
            process = await self._ready_child()
            if process is None:
                raise InertRenderRefused("renderer_unavailable")
            assert process.stdin is not None and process.stdout is not None
            try:
                async with asyncio.timeout(_RENDER_DEADLINE_S):
                    process.stdin.write(frame)
                    await process.stdin.drain()
                    body = await _read_body(process.stdout, _MAX_ANSWER_FRAME)
            except TimeoutError:
                self._kill(process)
                self._remember(request, "render_deadline")
                raise InertRenderRefused("render_deadline") from None
            except (ConnectionError, asyncio.IncompleteReadError) as exc:
                if self._process is not process:
                    # Stopped from here, by a new loop or the server's end: not the
                    # document's doing, so nothing is kept.
                    raise InertRenderRefused("renderer_unavailable") from exc
                # The input may be what stopped it, so it is not rendered again.
                self._kill(process)
                self._remember(request, "renderer_exited")
                raise InertRenderRefused("renderer_exited") from exc
            except BaseException:
                # An exchange cut off part-way leaves the child's pipes out of step.
                self._kill(process)
                raise
            self._touch()
        answer = cast("dict[str, Any]", await asyncio.to_thread(json.loads, body))
        error = answer.get("error")
        if error == "invalid":
            raise kpress_adapter.KPressInvalidRequestError(str(answer.get("message")))
        if error is not None:
            raise kpress_adapter.KPressRenderError(str(answer.get("message")))
        return cast("dict[str, Any]", answer["rendered"])

    def _remember(self, request: InertRender, code: RefusalCode) -> None:
        self._verdicts[request.verdict_key] = code
        self._verdicts.move_to_end(request.verdict_key)
        while len(self._verdicts) > _MAX_VERDICTS:
            self._verdicts.popitem(last=False)


@cache
def shared_worker() -> ProjectionWorker:
    """This process's Markdown child, which every route that renders untrusted text shares."""

    return ProjectionWorker()


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
