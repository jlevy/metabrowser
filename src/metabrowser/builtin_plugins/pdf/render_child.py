"""Render the first page of a PDF to a PNG, in a child process of the server.

PDFium is a native parser of bytes a content author wrote, so it never runs in the
server (threat model T7, ``docs/project/architecture/arch-threat-model.md``).
:mod:`metabrowser.builtin_plugins.pdf.preview` runs this file by its path,
``python -I -B <this file> <arguments>``, for each preview it renders: ``-I`` keeps the
working directory, the user's site-packages, and every ``PYTHON*`` variable out of the
interpreter, ``-B`` writes no bytecode (``-I`` ignores ``PYTHONDONTWRITEBYTECODE``), and
running the file rather than ``-m metabrowser...`` imports only the standard library and
``pypdfium2``, where importing the package would cost about 200 ms of every render
(measured beside :data:`metabrowser.builtin_plugins.pdf.preview.RENDER_DEADLINE_SECONDS`).
For an untrusted source the parent starts it under an operating-system sandbox as well.

Before it reads a byte of input the child limits itself: CPU seconds, its address space
where the platform enforces that (Linux; macOS does not), no file growth, no core file,
and no new processes.

The protocol, one render per process:

- **Arguments.** The box the page is fitted into, in pixels (width, height); the CPU
  seconds; the address-space bytes (0 for none); and the most input bytes it reads.
- **Input.** The PDF's bytes on stdin, to end of file.
- **Output.** One JSON line on stdout, then, for a render, the PNG. A render answers
  ``{"status": "ready", "width", "height", "pages", "png_bytes"}``; a PDF it cannot draw
  answers ``{"status": "failed", "reason"}``, with a reason in :data:`FAILURE_REASONS`.
  Both exit 0. Anything else (a crash, a signal, a limit) is the parent's to name.

The PNG is encoded here with the standard library (:func:`encode_png`), so no imaging
library is needed: 8-bit RGB, no interlace, every row filter 0, one ``tEXt`` chunk
naming the page count, so the cache entry describes itself.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import zlib
from collections.abc import Mapping
from typing import Final

# The encoder's own version, part of every preview's cache key with the renderer's, so a
# change to what this module writes gives every preview a new key.
ENCODER_VERSION: Final = 1

# zlib's default level. Re-encoding eight measured previews (five real PDFs and the three
# generated ones beside `PREVIEW_BOX` in preview.py), level 9 saved 0 to 13 percent and
# took 1.1 to 7 times as long, 452 ms against 64 ms on the scanned page; level 1 grew
# them by up to 66 percent (2026-11-24, load average 87 to 105).
_ZLIB_LEVEL: Final = 6

PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
# The one tEXt keyword the encoder writes, for the page count.
PAGES_KEYWORD: Final = "Pages"

# The argument that asks only whether the child starts and loads PDFium, and its answer:
# how the parent probes a sandbox (`preview_isolation.probe_sandbox`).
PROBE_ARGUMENT: Final = "--probe"
PROBE_ANSWER: Final = b"ok\n"

FAILURE_REASONS: Final = frozenset({"encrypted", "unreadable", "empty", "page_size", "too_large"})

# Exit status for arguments the parent never sends; a usage error is not a PDF's fault.
_USAGE_EXIT: Final = 64


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode_png(
    width: int,
    height: int,
    pixels: bytes | bytearray | memoryview,
    stride: int,
    *,
    text: Mapping[str, str] | None = None,
) -> bytes:
    """Encode 8-bit RGB *pixels*, *stride* bytes per row, as a PNG.

    Every row gets filter 0 (none): the previews are small and mostly flat, so zlib finds
    their runs without a predictor. *text* becomes one ``tEXt`` chunk per entry, before the
    image data; keys and values are Latin-1.
    """

    if width < 1 or height < 1:
        raise ValueError("a PNG has at least one pixel")
    row = width * 3
    if stride < row or len(pixels) < stride * (height - 1) + row:
        raise ValueError("the pixels do not cover the image")
    view = memoryview(pixels).cast("B")
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += view[y * stride : y * stride + row]
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunks = [_chunk(b"IHDR", header)]
    for key, value in (text or {}).items():
        chunks.append(_chunk(b"tEXt", key.encode("latin-1") + b"\0" + value.encode("latin-1")))
    chunks.append(_chunk(b"IDAT", zlib.compress(bytes(raw), _ZLIB_LEVEL)))
    chunks.append(_chunk(b"IEND", b""))
    return PNG_SIGNATURE + b"".join(chunks)


def limit_resources(cpu_seconds: int, address_space_bytes: int) -> None:
    """Bound this process before it parses anything.

    The CPU limit's soft value sends ``SIGXCPU`` and its hard value one second later
    ``SIGKILL``, so a render that ignores the first still ends. ``RLIMIT_FSIZE`` of zero
    makes any write to a file fail, ``RLIMIT_CORE`` of zero leaves no core file of the
    PDF's bytes, and ``RLIMIT_NPROC`` of zero makes a fork fail. A limit the platform
    refuses is skipped: the parent's deadline still holds.
    """

    import resource

    limits: list[tuple[int, int]] = [
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NPROC, 0),
    ]
    if address_space_bytes > 0 and sys.platform.startswith("linux"):
        limits.append((resource.RLIMIT_AS, address_space_bytes))
    for name, value in limits:
        hard = value + 1 if name == resource.RLIMIT_CPU else value
        try:
            resource.setrlimit(name, (value, hard))
        except (ValueError, OSError):
            continue


def _fit(width: float, height: float, box_width: int, box_height: int) -> float:
    """The scale that fits a page of *width* by *height* points inside the box.

    ``PdfPage.render`` rounds each side up, so the scale is pulled in by a hair to keep
    the rounded size inside the box.
    """

    return min(box_width / width, box_height / height) * (1 - 1e-9)


def render(data: bytes, box_width: int, box_height: int) -> tuple[dict[str, object], bytes]:
    """The answer line and PNG for *data*'s first page, fitted inside the box."""

    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        reason = "encrypted" if exc.err_code == pdfium_c.FPDF_ERR_PASSWORD else "unreadable"
        return {"status": "failed", "reason": reason}, b""
    try:
        pages = len(document)
        if pages < 1:
            return {"status": "failed", "reason": "empty"}, b""
        page = document[0]
        try:
            width, height = page.get_size()
            if not (math.isfinite(width) and math.isfinite(height)) or width <= 0 or height <= 0:
                return {"status": "failed", "reason": "page_size"}, b""
            bitmap = page.render(
                # A float, as pypdfium2 documents it; its default of 1 is what types it int.
                scale=_fit(width, height, box_width, box_height),  # pyright: ignore[reportArgumentType]
                may_draw_forms=False,
                rev_byteorder=True,
                force_bitmap_format=pdfium_c.FPDFBitmap_BGR,
            )
            try:
                if not (1 <= bitmap.width <= box_width and 1 <= bitmap.height <= box_height):
                    return {"status": "failed", "reason": "page_size"}, b""
                png = encode_png(
                    bitmap.width,
                    bitmap.height,
                    bytes(bitmap.buffer),
                    bitmap.stride,
                    text={PAGES_KEYWORD: str(pages)},
                )
                size = (bitmap.width, bitmap.height)
            finally:
                bitmap.close()
        except pdfium.PdfiumError:
            return {"status": "failed", "reason": "unreadable"}, b""
        finally:
            page.close()
    finally:
        document.close()
    answer: dict[str, object] = {
        "status": "ready",
        "width": size[0],
        "height": size[1],
        "pages": pages,
        "png_bytes": len(png),
    }
    return answer, png


def _read_input(max_bytes: int) -> bytes | None:
    data = sys.stdin.buffer.read(max_bytes + 1)
    return None if len(data) > max_bytes else data


def main(argv: list[str]) -> int:
    if argv == [PROBE_ARGUMENT]:
        import pypdfium2  # noqa: F401  # pyright: ignore[reportUnusedImport]

        sys.stdout.buffer.write(PROBE_ANSWER)
        sys.stdout.buffer.flush()
        return 0
    try:
        box_width, box_height, cpu_seconds, address_space, max_input = (int(a) for a in argv)
    except ValueError:
        return _USAGE_EXIT
    if min(box_width, box_height, cpu_seconds, max_input) < 1 or address_space < 0:
        return _USAGE_EXIT
    limit_resources(cpu_seconds, address_space)
    data = _read_input(max_input)
    if data is None:
        answer: dict[str, object] = {"status": "failed", "reason": "too_large"}
        png = b""
    else:
        answer, png = render(data, box_width, box_height)
    out = sys.stdout.buffer
    out.write(json.dumps(answer, separators=(",", ":")).encode() + b"\n")
    out.write(png)
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
