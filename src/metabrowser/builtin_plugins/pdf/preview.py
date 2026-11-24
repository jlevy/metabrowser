"""First-page previews of PDFs: what one is keyed by, how it is rendered, and when it is not.

A preview is a PNG of a PDF's first page fitted inside :data:`PREVIEW_BOX`, rendered by
PDFium in a child process (:mod:`.render_child`) and kept in the cache
(:mod:`.preview_store`). The routes in :mod:`.sidekick` ask :func:`preview_for` for one.

- **Key.** A SHA-256 of the content's identity, the renderer's version, and the box
  (:func:`preview_key`). The content's identity is a pinned file's blob ID
  (``git-blob:<oid>``), which costs no read, or for a served folder's file the SHA-256 of
  its bytes (``sha256:<hex>``), remembered in this process by the file's identity, size,
  modification time, device, and inode, so the file is read again only when it may have
  changed. The renderer's version names the pypdfium2 release, the PDFium build, and the
  encoder's version (:func:`renderer_version`), so an upgrade gives every preview a new
  key. The same key is rendered once, and served from the cache after; a changed file
  has a new key. A folder's file and a pinned blob with the same bytes have different
  keys, so each is rendered once.
- **Isolation.** :func:`.preview_isolation.isolation_for` decides whether a render may
  run, and under which sandbox. An untrusted source without one is refused before its
  bytes are read or its key is computed, so the answer does not depend on what the cache
  happens to hold.
- **Bounds.** At most :data:`MAX_INPUT_BYTES` are read and piped to the child; the child
  limits its own CPU time (:data:`RENDER_CPU_SECONDS`) and, on Linux, its address space
  (:data:`ADDRESS_SPACE_BYTES`); the parent kills its process group at
  :data:`RENDER_DEADLINE_SECONDS`, and reads at most a header line and
  :data:`~.preview_store.ENTRY_MAX_BYTES` from it. At most :data:`CONCURRENT_RENDERS`
  run at once; the rest wait their turn, and concurrent requests for one key share one
  render, which finishes into the cache even when every requester has gone.
- **The child's output is not trusted.** :func:`png_facts` accepts only a PNG of the
  encoder's own form, with the dimensions the header line named, inside the box.
- **Failures are remembered** in this process by key (:class:`_Failures`): a refusal the
  bytes decide (not a PDF, encrypted, unreadable, no pages) for the process's life, and
  a deadline or a crash for :data:`FAILURE_RETRY_SECONDS`, so a page that asks again
  does not start another render that will fail the same way. Nothing about a failure is
  written to the cache, so a restart tries each once more.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import struct
import time
import zlib
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from metabrowser.builtin_plugins.pdf import preview_isolation, render_child
from metabrowser.builtin_plugins.pdf.preview_isolation import Isolation
from metabrowser.builtin_plugins.pdf.preview_store import ENTRY_MAX_BYTES, PreviewStore

LOG = logging.getLogger(__name__)

# The box a first page is fitted into, in pixels: twice the card's 240 by 320 CSS pixels,
# so a high-density display draws it sharp. Measured with `render_child.py` (2026-11-24,
# Apple silicon, load average 44 to 105), spawn to exit:
#
#   36 real PDFs (papers, slides, scanned books, plots; 77 KB to 9.6 MB, 1 to 264 pages):
#     every one rendered, in 0.115 to 0.414 s, as PNGs of 18 to 189 KB (median 71 KB),
#     with the child's peak resident memory at most 80 MB
#   generated: a vector page of 3,000 filled shapes and 1,000 curves, 0.17 s and 500 KB
#     (the largest PNG, its colors defeat zlib); 300 pages of text, 0.13 s and 56 KB;
#     one 2550 by 3300 RGB scanned page (7.8 MB), 0.28 s and 175 KB, 88 MB resident
#   under the macOS sandbox: the same PNGs, the same times within 15 ms
#
# A cold interpreter that loads PDFium is 0.08 to 0.10 s of each render; importing the
# `metabrowser` package as well would add 0.21 to 0.27 s, which is why the child runs as
# a file (`render_child.py`).
PREVIEW_BOX: Final = (480, 640)
# The most bytes of a PDF read and piped to the child. The largest real PDF measured,
# 9.6 MB, rendered in 0.29 s; reading it costs the server as much memory for the
# request, and two renders at once (`CONCURRENT_RENDERS`) hold twice that. A larger PDF
# gets no image, and its card still opens it.
MAX_INPUT_BYTES: Final = 64 * 1024 * 1024
# The parent kills the child's process group this long after starting it: 24 times the
# slowest measured render, at a load average of 105 on this machine.
RENDER_DEADLINE_SECONDS: Final = 10.0
# The child's own CPU limit, `RLIMIT_CPU`, which ends a render the deadline would, from
# inside, should the parent's kill be late.
RENDER_CPU_SECONDS: Final = 10
# The child's address space on Linux (`RLIMIT_AS`; macOS does not enforce it, and there
# the deadline and CPU limit bound a render). The largest measured child held 88 MB
# resident on macOS; its Linux address space was not measured here. One GiB is the SQLite
# readers' bound for a Python child (`READER_ADDRESS_SPACE_BYTES`), whose measurement it
# rests on.
ADDRESS_SPACE_BYTES: Final = 1024 * 1024 * 1024
# Renders running at once. Each holds a core for up to 0.4 s; two serve a page's cards
# without one diff's PDFs taking the machine.
CONCURRENT_RENDERS: Final = 2
# How long a render that ran out of time or crashed is not tried again for its key.
FAILURE_RETRY_SECONDS: Final = 60.0
# Keys whose failures are remembered, and folder files whose content hashes are; the
# oldest is forgotten first. Each is a few hundred bytes.
FAILURES_REMEMBERED: Final = 1024
CONTENT_HASHES_REMEMBERED: Final = 1024
# The child's header line: a JSON object of four small fields.
_ANSWER_LINE_MAX_BYTES: Final = 256
# The leading bytes of every PDF a preview is drawn for, as the pdf kind's magic rule
# claims them (manifest.toml).
PDF_MAGIC: Final = b"%PDF-"

type Reason = Literal[
    "not_a_pdf",
    "too_large",
    "no_sandbox",
    "encrypted",
    "unreadable",
    "empty",
    "page_size",
    "timed_out",
    "failed",
    "no_cache",
]

# What a card may say about a preview it has no image for, by reason.
REASON_MESSAGES: Final[dict[Reason, str]] = {
    "not_a_pdf": "This file does not begin as a PDF does.",
    "too_large": "This PDF is too large to preview.",
    "no_sandbox": (
        "Previews of this source's PDFs are drawn only in a sandbox, which this system lacks."
    ),
    "encrypted": "This PDF is password-protected.",
    "unreadable": "This PDF could not be read.",
    "empty": "This PDF has no pages.",
    "page_size": "This PDF's first page has no usable size.",
    "timed_out": "Drawing this PDF's first page took too long.",
    "failed": "This PDF's preview could not be drawn.",
    "no_cache": "Previews need Metabrowser's cache, which is unavailable.",
}
# Refusals the bytes decide, remembered for the process's life; the rest for
# `FAILURE_RETRY_SECONDS`.
_LASTING: Final = frozenset(
    {"not_a_pdf", "too_large", "encrypted", "unreadable", "empty", "page_size"}
)


class PreviewRefusedError(Exception):
    """A preview that will not be drawn, for *reason*."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason: Reason = reason


@dataclass(frozen=True, slots=True)
class PngFacts:
    width: int
    height: int
    pages: int


@dataclass(frozen=True, slots=True)
class Preview:
    """A preview in the cache under *key*. *rendered* says whether this request drew it."""

    key: str
    facts: PngFacts
    rendered: bool


@dataclass(frozen=True, slots=True)
class PreviewSource:
    """What a route resolved: whether it is trusted, its identity, and its bytes.

    *content_id* answers the content's identity for the key, and may read the bytes to
    hash them; *read* answers the bytes, at most :data:`MAX_INPUT_BYTES`, and raises
    :class:`PreviewRefusedError` for ``too_large``. Each is called at most once.
    """

    trusted: bool
    content_id: Callable[[], Awaitable[str]]
    read: Callable[[], Awaitable[bytes]]


def png_facts(data: bytes, *, box: tuple[int, int] = PREVIEW_BOX) -> PngFacts:
    """The size and page count of a PNG of :func:`.render_child.encode_png`'s own form.

    Raises ``ValueError`` for anything else: a PNG another encoder wrote, one whose size is
    outside *box*, a chunk whose checksum is wrong, or bytes after its end. The checks are
    on the container; the browser decodes the image data, in its own sandbox.
    """

    signature = render_child.PNG_SIGNATURE
    if not data.startswith(signature) or len(data) > ENTRY_MAX_BYTES:
        raise ValueError("not a preview PNG")
    offset = len(signature)
    kinds: list[bytes] = []
    size: tuple[int, int] | None = None
    pages: int | None = None
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("a PNG chunk is cut short")
        (length,) = struct.unpack_from(">I", data, offset)
        kind = data[offset + 4 : offset + 8]
        body = data[offset + 8 : offset + 8 + length]
        end = offset + 8 + length
        if len(body) != length or end + 4 > len(data):
            raise ValueError("a PNG chunk is cut short")
        (crc,) = struct.unpack_from(">I", data, end)
        if crc != zlib.crc32(kind + body):
            raise ValueError("a PNG chunk's checksum is wrong")
        kinds.append(kind)
        if kind == b"IHDR":
            if len(kinds) != 1 or length != 13:
                raise ValueError("the PNG header is not first")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise ValueError("the PNG is not 8-bit RGB")
            if not (1 <= width <= box[0] and 1 <= height <= box[1]):
                raise ValueError("the PNG is outside the preview box")
            size = (width, height)
        elif kind == b"tEXt":
            keyword, _, value = body.partition(b"\0")
            if keyword != render_child.PAGES_KEYWORD.encode() or pages is not None:
                raise ValueError("the PNG has text other than its page count")
            if not value.isdigit() or len(value) > 9:
                raise ValueError("the PNG's page count is not a count")
            pages = int(value)
        elif kind == b"IEND":
            if length != 0 or end + 4 != len(data):
                raise ValueError("the PNG continues past its end")
        elif kind != b"IDAT":
            raise ValueError("the PNG has a chunk the encoder does not write")
        offset = end + 4
    if size is None or pages is None or pages < 1 or b"IDAT" not in kinds or kinds[-1] != b"IEND":
        raise ValueError("the PNG is incomplete")
    return PngFacts(width=size[0], height=size[1], pages=pages)


_renderer: str | None = None


def renderer_version() -> str:
    """The renderer as a key names it: pypdfium2's release, PDFium's build, the encoder's.

    Read from the installed distributions' metadata and ``pypdfium2_raw/version.json``,
    so the server neither imports pypdfium2 nor loads PDFium to learn it.
    """

    global _renderer
    if _renderer is None:
        binding = importlib.metadata.version("pypdfium2")
        build = "unknown"
        spec = importlib.util.find_spec("pypdfium2_raw")
        if spec is not None and spec.submodule_search_locations:
            for location in spec.submodule_search_locations:
                with contextlib.suppress(OSError, ValueError):
                    info = json.loads((Path(location) / "version.json").read_text("utf-8"))
                    build = f"{info['major']}.{info['minor']}.{info['build']}.{info['patch']}"
                    break
        _renderer = f"pypdfium2 {binding}; pdfium {build}; png {render_child.ENCODER_VERSION}"
    return _renderer


def preview_key(content_id: str, renderer: str, box: tuple[int, int]) -> str:
    """The cache key of a preview: a SHA-256 over what it is computed from."""

    payload = json.dumps(
        {"box": list(box), "content": content_id, "renderer": renderer},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class _Failures:
    """Keys whose render failed, and until when they are not tried again."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._entries: OrderedDict[str, tuple[Reason, float | None]] = OrderedDict()

    def get(self, key: str) -> Reason | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        reason, until = entry
        if until is not None and time.monotonic() >= until:
            del self._entries[key]
            return None
        return reason

    def remember(self, key: str, reason: Reason) -> None:
        until = None if reason in _LASTING else time.monotonic() + FAILURE_RETRY_SECONDS
        self._entries[key] = (reason, until)
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


class ContentHashes:
    """Folder files' SHA-256s by fingerprint, so an unchanged file is not read to be keyed."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._entries: OrderedDict[tuple[object, ...], str] = OrderedDict()

    def get(self, fingerprint: tuple[object, ...]) -> str | None:
        found = self._entries.get(fingerprint)
        if found is not None:
            self._entries.move_to_end(fingerprint)
        return found

    def remember(self, fingerprint: tuple[object, ...], digest: str) -> None:
        self._entries[fingerprint] = digest
        self._entries.move_to_end(fingerprint)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


_failures = _Failures(FAILURES_REMEMBERED)
content_hashes = ContentHashes(CONTENT_HASHES_REMEMBERED)
_inflight: dict[str, asyncio.Task[Preview]] = {}
_renders: asyncio.Semaphore | None = None
_renders_loop: asyncio.AbstractEventLoop | None = None
_store: PreviewStore | None = None


def reset_for_tests() -> None:
    """Forget every remembered failure, content hash, and the opened store."""

    global _store
    _failures.clear()
    content_hashes.clear()
    _inflight.clear()
    _store = None


async def opened_store() -> PreviewStore | None:
    """The previews area, made owner-only the first time this process asks."""

    global _store
    if _store is None:
        _store = await asyncio.to_thread(PreviewStore.open)
    return _store


def _semaphore() -> asyncio.Semaphore:
    global _renders, _renders_loop
    loop = asyncio.get_running_loop()
    if _renders is None or _renders_loop is not loop:
        _renders = asyncio.Semaphore(CONCURRENT_RENDERS)
        _renders_loop = loop
    return _renders


async def preview_for(source: PreviewSource) -> Preview:
    """The preview of *source*, from the cache or rendered now.

    Raises :class:`PreviewRefusedError` when there is none to give. A content read that
    fails raises the read's own :class:`~metabrowser.content_errors.ContentReadError`.
    """

    decision = preview_isolation.isolation_for(
        trusted=source.trusted, sandbox=await preview_isolation.sandbox()
    )
    if decision == "no_sandbox":
        raise PreviewRefusedError("no_sandbox")
    content_id = await source.content_id()
    key = preview_key(content_id, renderer_version(), PREVIEW_BOX)
    store = await opened_store()
    if store is None:
        raise PreviewRefusedError("no_cache")
    cached = await asyncio.to_thread(store.read, key)
    if cached is not None:
        try:
            return Preview(key=key, facts=png_facts(cached), rendered=False)
        except ValueError:
            # An entry this encoder did not write: drawn again, and replaced.
            LOG.warning("pdf preview: a cached preview was not one this encoder writes")
    remembered = _failures.get(key)
    if remembered is not None:
        raise PreviewRefusedError(remembered)
    task = _inflight.get(key)
    if task is None:
        # The render is a task of its own, so a reader who leaves the page does not stop
        # it: it finishes into the cache, and the next request finds it there.
        task = asyncio.get_running_loop().create_task(
            _render_and_keep(source, key, decision, store)
        )
        _inflight[key] = task
        task.add_done_callback(lambda done: _settled(key, done))
    return await asyncio.shield(task)


def _settled(key: str, task: asyncio.Task[Preview]) -> None:
    if _inflight.get(key) is task:
        del _inflight[key]
    # Retrieved here, so a render whose every requester left logs no unretrieved error.
    if not task.cancelled():
        task.exception()


async def _render_and_keep(
    source: PreviewSource, key: str, isolation: Isolation, store: PreviewStore
) -> Preview:
    try:
        data = await source.read()
        if not data.startswith(PDF_MAGIC):
            raise PreviewRefusedError("not_a_pdf")
        async with _semaphore():
            facts, png = await render(data, isolation)
    except PreviewRefusedError as exc:
        _failures.remember(key, exc.reason)
        raise
    if not await asyncio.to_thread(store.write, key, png):
        raise PreviewRefusedError("no_cache")
    return Preview(key=key, facts=facts, rendered=True)


async def render(data: bytes, isolation: Isolation) -> tuple[PngFacts, bytes]:
    """Render *data*'s first page in a child under *isolation*: its facts and its PNG."""

    arguments = [
        str(PREVIEW_BOX[0]),
        str(PREVIEW_BOX[1]),
        str(RENDER_CPU_SECONDS),
        str(ADDRESS_SPACE_BYTES),
        str(MAX_INPUT_BYTES),
    ]
    command = preview_isolation.child_command(isolation, arguments)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd="/",
            env=preview_isolation.child_environment(),
            start_new_session=True,
        )
    except OSError as exc:
        LOG.warning("pdf preview: the render child did not start: %s", exc)
        raise PreviewRefusedError("failed") from exc
    try:
        async with asyncio.timeout(RENDER_DEADLINE_SECONDS):
            feeding = asyncio.create_task(_feed(process.stdin, data))
            out = await _read_capped(process.stdout, _ANSWER_LINE_MAX_BYTES + ENTRY_MAX_BYTES)
            await feeding
            code = await process.wait()
    except TimeoutError as exc:
        raise PreviewRefusedError("timed_out") from exc
    finally:
        if process.returncode is None:
            preview_isolation.kill_group(process.pid)
            await process.wait()
    if out is None or code != 0:
        LOG.warning(
            "pdf preview: the render child ended with %s", code if out else "too much output"
        )
        raise PreviewRefusedError("failed")
    return _parse_answer(out)


async def _feed(stdin: asyncio.StreamWriter | None, data: bytes) -> None:
    """Write *data* to the child and close its input. A child that stopped reading is fine."""

    if stdin is None:  # pragma: no cover - always piped
        return
    try:
        stdin.write(data)
        await stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        with contextlib.suppress(BrokenPipeError, ConnectionResetError, OSError):
            stdin.close()
            await stdin.wait_closed()


async def _read_capped(stdout: asyncio.StreamReader | None, limit: int) -> bytes | None:
    """The child's whole output, or None once it passes *limit*."""

    if stdout is None:  # pragma: no cover - always piped
        return None
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stdout.read(65536)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)


def _parse_answer(out: bytes) -> tuple[PngFacts, bytes]:
    line, newline, png = out.partition(b"\n")
    if not newline or len(line) > _ANSWER_LINE_MAX_BYTES:
        raise PreviewRefusedError("failed")
    try:
        answer = json.loads(line)
    except ValueError as exc:
        raise PreviewRefusedError("failed") from exc
    if not isinstance(answer, dict):
        raise PreviewRefusedError("failed")
    status = answer.get("status")
    if status == "failed":
        reason = answer.get("reason")
        if reason in render_child.FAILURE_REASONS:
            raise PreviewRefusedError(reason)
        raise PreviewRefusedError("failed")
    if status != "ready" or answer.get("png_bytes") != len(png):
        raise PreviewRefusedError("failed")
    try:
        facts = png_facts(png)
    except ValueError as exc:
        LOG.warning("pdf preview: the render child wrote a PNG this server refuses: %s", exc)
        raise PreviewRefusedError("failed") from exc
    expected = (answer.get("width"), answer.get("height"), answer.get("pages"))
    if expected != (facts.width, facts.height, facts.pages):
        raise PreviewRefusedError("failed")
    return facts, png


__all__ = [
    "ADDRESS_SPACE_BYTES",
    "CONCURRENT_RENDERS",
    "MAX_INPUT_BYTES",
    "PREVIEW_BOX",
    "REASON_MESSAGES",
    "RENDER_DEADLINE_SECONDS",
    "Preview",
    "PreviewRefusedError",
    "PreviewSource",
    "PngFacts",
    "Reason",
    "content_hashes",
    "opened_store",
    "png_facts",
    "preview_for",
    "preview_key",
    "render",
    "renderer_version",
    "reset_for_tests",
]
