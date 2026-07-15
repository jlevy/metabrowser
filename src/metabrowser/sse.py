"""Server-Sent Events endpoint for live JSONL log + chart updates.

The browser polls ``/api/activity`` every 5 s for tree decoration. That
remains the right shape for "is anything alive across the whole tree".
But for a tab the user is *looking at* — an open log, an open chart —
poll-then-refetch turns "live" into a sluggish flicker. SSE pushes
incremental events to the focused tab instead, eliminating polling for
the active view while leaving the activity poll alone.

Wire format
-----------

The endpoint emits standard ``text/event-stream`` frames:

* ``event: append`` — one JSON object containing a batch of newly
  appended events (parsed with the same single-pass parser as
  ``_parse_jsonl_file``) plus the new byte cursor. The client appends
  to the rendered log and extends in-memory chart series. The same
  complete-line cursor is the SSE event ID, so automatic reconnects
  continue from the last acknowledged record through ``Last-Event-ID``.
* ``event: heartbeat`` — empty frames every ~10 s to keep proxies
  happy and detect dead clients.
* ``event: closed`` — final frame when the writer rotates the file
  or the file disappears. Client surfaces a "Run ended" badge.

Only files with the ``.jsonl`` extension and below
``_LARGE_FILE_BYTES`` are streamable; oversized logs return 413 and
the client falls back to the polled ``/api/file`` path. The polled
path still refuses oversized payloads via the same threshold.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from starlette.responses import PlainTextResponse, Response, StreamingResponse

from metabrowser.gz_io import ArtifactPath
from metabrowser.jsonl_view import _LARGE_FILE_BYTES, _MAX_LINE_LEN
from metabrowser.logutil.parsing import LogEvent, create_parser, detect_adapter
from metabrowser.paths_safe import _safe_path

if TYPE_CHECKING:
    from starlette.requests import Request

# How long a single ``stat``+``read`` cycle waits before re-checking.
# Faster than the 5 s activity poll because the client is actively
# watching this file; slower than zero so we don't busy-spin.
_TAIL_POLL_INTERVAL_S = 0.5
# Heartbeat cadence — proxies and load balancers commonly drop idle
# connections after 30–60 s, and a reverse-proxy SSE stream needs to
# emit *something* periodically to stay alive.
_HEARTBEAT_INTERVAL_S = 10.0
# Per-batch cap on bytes parsed in one cycle. A burst-write from a
# producer shouldn't allow a single SSE frame to balloon to MB.
_MAX_BATCH_BYTES = 256 * 1024
# Adapter detection normally waits for enough lines to classify reliably, but
# short-lived producers can pause forever below that threshold. After a short
# no-growth grace period, use the lines we have so the live log does not stall.
_ADAPTER_DETECTION_GRACE_S = 1.0


def _sse_frame(event: str, payload: dict[str, Any], *, event_id: int | None = None) -> bytes:
    """Format an SSE frame with a named event and JSON-encoded data."""
    body = json.dumps(payload, separators=(",", ":"))
    id_line = f"id: {event_id}\n" if event_id is not None else ""
    return f"event: {event}\ndata: {body}\n{id_line}\n".encode()


def _sse_comment(text: str) -> bytes:
    """SSE comment line — ignored by the EventSource API but keeps the
    socket warm. Used for heartbeats."""
    return f": {text}\n\n".encode()


def _serialize_events(events: list[LogEvent]) -> list[dict[str, Any]]:
    """Match the polled ``_parse_jsonl_file`` event shape so the client
    can use the same renderer for both the polled and SSE paths."""
    out: list[dict[str, Any]] = []
    for e in events:
        d = asdict(e)
        raw = d["raw"]
        if isinstance(raw, str):
            d["raw"] = {"_text": raw}
        out.append(d)
    return out


def _bound_pending_line(
    pending: bytes,
    dropping_oversized_line: bool,
    *,
    max_line_bytes: int | None = None,
) -> tuple[bytes, bool]:
    """Keep an unterminated JSONL record within the per-line byte cap."""
    limit = _MAX_LINE_LEN if max_line_bytes is None else max_line_bytes
    if dropping_oversized_line or len(pending) > limit:
        return b"", True
    return pending, False


def _detect_parser_and_replay(lines: list[str]) -> tuple[str, Any, list[LogEvent]]:
    """Detect an adapter from buffered lines and replay them into a parser."""
    adapter = detect_adapter(lines[:20])
    parser = create_parser(adapter)
    events: list[LogEvent] = []
    for line in lines:
        events.extend(parser.parse_line(line))
    return adapter, parser, events


async def _tail_jsonl(
    filepath: Path,
    start_cursor: int,
) -> AsyncIterator[bytes]:
    """Async generator yielding SSE frames for a JSONL file's tail.

    Keeps a single parser instance alive across reads so adapter state
    (e.g. claude assistant aggregation) carries through batch
    boundaries. Tracks a partial-line buffer for the case where a read
    lands mid-line; the leftover stays in memory until the next cycle.
    """
    adapter = "unknown"
    parser = None
    detection_buffer: list[str] = []
    read_cursor = max(0, start_cursor)
    acknowledged_cursor = read_cursor
    byte_buffer = b""
    dropping_oversized_line = False
    last_heartbeat = time.monotonic()
    detection_last_growth: float | None = None

    try:
        initial_st = filepath.stat()
    except OSError:
        yield _sse_frame("closed", {"reason": "missing"})
        return
    inode = initial_st.st_ino
    read_cursor = min(read_cursor, initial_st.st_size)
    if read_cursor > 0:
        read_cursor = await asyncio.to_thread(_complete_line_cursor, filepath, read_cursor)
    acknowledged_cursor = read_cursor
    if read_cursor > 0:
        adapter, parser = await asyncio.to_thread(_prime_parser_to_cursor, filepath, read_cursor)

    while True:
        try:
            st = filepath.stat()
        except OSError:
            yield _sse_frame("closed", {"reason": "missing"})
            return

        # Rotation detection: a new inode means the writer recreated
        # the file (log rotation), and a shrunken size means it was
        # truncated. Either way, the cursor we're holding is stale —
        # tell the client and stop.
        if st.st_ino != inode or st.st_size < read_cursor:
            yield _sse_frame("closed", {"reason": "rotated"})
            return
        if st.st_size > _LARGE_FILE_BYTES:
            yield _sse_frame("closed", {"reason": "too_large"})
            return

        if st.st_size > read_cursor:
            # Read up to _MAX_BATCH_BYTES of new bytes. Bigger writes
            # arrive over multiple cycles, which is fine — the next
            # tick picks up the rest.
            chunk_end = min(st.st_size, read_cursor + _MAX_BATCH_BYTES)
            raw_chunk = await asyncio.to_thread(_read_slice, filepath, read_cursor, chunk_end)
            read_cursor = chunk_end

            byte_buffer += raw_chunk
            lines: list[str] = []
            if dropping_oversized_line:
                first_newline = byte_buffer.find(b"\n")
                if first_newline < 0:
                    byte_buffer = b""
                else:
                    byte_buffer = byte_buffer[first_newline + 1 :]
                    dropping_oversized_line = False
                    acknowledged_cursor = read_cursor - len(byte_buffer)
            last_newline = byte_buffer.rfind(b"\n")
            if last_newline >= 0:
                complete, byte_buffer = (
                    byte_buffer[: last_newline + 1],
                    byte_buffer[last_newline + 1 :],
                )
                acknowledged_cursor = read_cursor - len(byte_buffer)
                for raw_line in complete.split(b"\n")[:-1]:
                    stripped = raw_line.decode(errors="replace").strip()
                    if stripped and len(raw_line) <= _MAX_LINE_LEN:
                        lines.append(stripped)
            byte_buffer, dropping_oversized_line = _bound_pending_line(
                byte_buffer, dropping_oversized_line
            )

            if lines:
                # First batch: detect adapter from whatever we've got.
                if parser is None:
                    detection_buffer.extend(lines)
                    detection_last_growth = time.monotonic()
                    if len(detection_buffer) >= 20:
                        adapter, parser, new_events = _detect_parser_and_replay(detection_buffer)
                        detection_buffer = []
                        detection_last_growth = None
                    else:
                        new_events = []
                else:
                    new_events = []
                    for line in lines:
                        new_events.extend(parser.parse_line(line))

                if new_events:
                    payload = {
                        "adapter": adapter,
                        "cursor": acknowledged_cursor,
                        "events": _serialize_events(new_events),
                    }
                    yield _sse_frame("append", payload, event_id=acknowledged_cursor)
                    last_heartbeat = time.monotonic()

        if (
            parser is None
            and detection_buffer
            and detection_last_growth is not None
            and time.monotonic() - detection_last_growth >= _ADAPTER_DETECTION_GRACE_S
        ):
            adapter, parser, new_events = _detect_parser_and_replay(detection_buffer)
            detection_buffer = []
            detection_last_growth = None
            if new_events:
                payload = {
                    "adapter": adapter,
                    "cursor": acknowledged_cursor,
                    "events": _serialize_events(new_events),
                }
                yield _sse_frame("append", payload, event_id=acknowledged_cursor)
                last_heartbeat = time.monotonic()

        if time.monotonic() - last_heartbeat > _HEARTBEAT_INTERVAL_S:
            yield _sse_comment("heartbeat")
            last_heartbeat = time.monotonic()

        await asyncio.sleep(_TAIL_POLL_INTERVAL_S)


def _prime_parser_to_cursor(filepath: Path, cursor: int) -> tuple[str, Any]:
    """Detect the adapter and warm parser state up to ``cursor``.

    Browser SSE normally starts at the byte count returned by ``/api/file``.
    Without priming, the stream would wait for 20 *new* lines before it
    can detect an adapter. Files eligible for SSE are capped at 2 MiB, so
    replaying the prefix is bounded and preserves parser behavior.
    """
    prefix_lines: list[str] = []
    with filepath.open("rb") as fh:
        while fh.tell() < cursor:
            raw_line = fh.readline()
            if not raw_line:
                break
            stripped = raw_line.decode(errors="replace").strip()
            if stripped and len(stripped) <= _MAX_LINE_LEN:
                prefix_lines.append(stripped)

    adapter, parser, _events = _detect_parser_and_replay(prefix_lines)
    parser.flush()
    return adapter, parser


def _read_slice(filepath: Path, start: int, end: int) -> bytes:
    """Read the exact byte range used by the live-tail cursor."""
    with filepath.open("rb") as fh:
        fh.seek(start)
        return fh.read(end - start)


def _complete_line_cursor(filepath: Path, requested_cursor: int) -> int:
    """Rewind a requested cursor to the last complete JSONL record.

    Initial `/api/file` reads can race a writer and report an EOF cursor in the
    middle of a line. Streamable files are capped at 2 MiB, so inspecting the
    bounded prefix avoids dropping that partial record when it later completes.
    """
    if requested_cursor <= 0:
        return 0
    with filepath.open("rb") as source:
        prefix = source.read(requested_cursor)
    newline = prefix.rfind(b"\n")
    return newline + 1 if newline >= 0 else 0


async def api_stream(request: Request) -> Response:
    """SSE endpoint. Query params: ``path`` (required, JSONL file
    relative to served root), ``cursor`` (optional starting byte
    offset; default 0)."""
    subpath = request.query_params.get("path", "")
    target = _safe_path(subpath)
    if target is None or not target.is_file():
        return PlainTextResponse("Not found", status_code=404)
    # Reject compressed artifacts: sealed logs make no sense to live-tail. Clients
    # hitting an archived log should fall back to /api/file (single-shot
    # parse) or /raw (download). This check runs before the .jsonl check
    # because a compressed JSONL path would otherwise sneak through as
    # "non-JSONL" with the wrong error.
    if ArtifactPath(target).is_compressed:
        return PlainTextResponse("file is sealed; load via /api/file instead", status_code=400)
    if target.suffix.lower() != ".jsonl":
        return PlainTextResponse("Stream endpoint is JSONL-only", status_code=400)
    try:
        size = target.stat().st_size
    except OSError:
        return PlainTextResponse("Not found", status_code=404)
    if size > _LARGE_FILE_BYTES:
        return PlainTextResponse(
            "File too large for streaming view; use /api/file or /raw",
            status_code=413,
        )

    requested_cursor = request.headers.get("last-event-id", "") or request.query_params.get(
        "cursor", "0"
    )
    try:
        cursor = max(0, int(requested_cursor))
    except ValueError:
        cursor = 0

    headers = {
        "cache-control": "no-cache",
        # Disable proxy buffering. Without this, an upstream nginx (or
        # similar) can hold our SSE frames until its buffer fills,
        # turning a stream into a polled-with-extra-steps experience.
        "x-accel-buffering": "no",
    }
    return StreamingResponse(
        _tail_jsonl(target, cursor),
        media_type="text/event-stream",
        headers=headers,
    )
