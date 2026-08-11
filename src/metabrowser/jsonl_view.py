"""Server-side parser for the browser's JSONL log preview.

Reads a JSONL file in a single pass, sniffs the adapter from the first
non-empty lines, parses the rest with the matching parser, and returns
events + a summary block ready to ship as JSON.

The file is read once: the first 20 valid lines feed ``detect_adapter``,
then the parser consumes that buffered prefix and the remaining lines.
Raw event payloads stay structured in the response; the client formats
them lazily when a row is expanded, keeping the hot path and wire payload
bounded for large logs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from metabrowser.gz_io import ArtifactPath
from metabrowser.logutil.parsing import LogEvent, create_parser, detect_adapter

LOG = logging.getLogger(__name__)

# 256 KiB. Skip individual lines longer than this — Pi message_update
# events embed full file contents and would OOM the parser.
_MAX_LINE_LEN = 256 * 1024
# 2 MiB. Above this we cap the raw tab and truncate per-event raw to keep
# the response payload (and the client-side parse + DOM cost) bounded.
# Embedded per-event payloads begin to dominate above this threshold;
# larger logs remain navigable through the file's ``/raw`` URL.
_LARGE_FILE_BYTES = 2 * 1024 * 1024
# 5 MiB cap on the raw-tab payload for large files.
_LARGE_FILE_RAW_CAP = 5 * 1024 * 1024
# 8 KiB max per-event raw payload for large files. Enough to read most
# tool inputs/outputs in place; oversized payloads (e.g. Pi
# ``message_update`` events embedding a whole source file) get a
# ``... (truncated)`` marker and the full bytes remain available via
# ``/raw`` for download.
_LARGE_FILE_PER_EVENT_RAW = 8 * 1024
# Absolute decompressed-input ceiling for one JSONL parse. Raw-tab truncation
# controls response size separately; this bound protects the parser itself.
_JSONL_PARSE_MAX_BYTES = 64 * 1024 * 1024


class JsonlParseLimitError(ValueError):
    """A JSONL artifact exceeded the parser's decompressed-input ceiling."""


def _parse_jsonl_file(filepath: Path) -> dict[str, Any]:
    """Parse a JSONL log file and return structured events + summary.

    Transparently handles compressed JSONL via :class:`ArtifactPath`. The
    reader enforces the parser's decoded-byte ceiling before compressed trailer
    validation, so malformed metadata cannot obscure a limit violation.

    Single-pass: the first 20 valid lines are buffered to detect the
    adapter, then handed back into the parser before continuing through
    the rest of the file.
    """
    artifact = ArtifactPath(filepath)
    file_size = artifact.disk_size if artifact.is_compressed else artifact.logical_size
    if not artifact.is_compressed and file_size > _JSONL_PARSE_MAX_BYTES:
        raise JsonlParseLimitError(
            f"JSONL content exceeds {_JSONL_PARSE_MAX_BYTES} decompressed bytes"
        )
    large_file = not artifact.is_compressed and file_size > _LARGE_FILE_BYTES
    max_raw_total = _LARGE_FILE_RAW_CAP if artifact.is_compressed or large_file else None

    detection_buffer: list[str] = []
    parser = None
    adapter = "unknown"

    events: list[LogEvent] = []
    lines_total = 0
    lines_skipped = 0
    raw_parts: list[str] = []
    raw_bytes = 0
    raw_capped = False
    parse_errors = 0

    def _consume(stripped: str, line_number: int) -> None:
        """Run parser + collect raw_text for one already-stripped line."""
        nonlocal parse_errors, raw_bytes, raw_capped
        # _consume is only ever called after detection has assigned ``parser``;
        # the assert is for the type checker, not a runtime safety check.
        assert parser is not None
        try:
            events.extend(parser.parse_line(stripped))
        except Exception as exc:
            parse_errors += 1
            LOG.warning(
                "jsonl parse error in %s line %s: %s",
                filepath,
                line_number,
                exc,
                exc_info=True,
            )
            events.append(
                LogEvent(
                    kind="system",
                    summary=f"[parse_error] line {line_number}: {type(exc).__name__}: {exc}",
                    adapter=adapter,
                    is_error=True,
                    raw={
                        "line_number": line_number,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "line_preview": stripped[:1000],
                    },
                )
            )
        if raw_capped:
            return
        try:
            parsed = json.loads(stripped)
            part = json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, ValueError):
            part = stripped
        raw_bytes += len(part)
        if max_raw_total is not None and raw_bytes > max_raw_total:
            raw_capped = True
        else:
            raw_parts.append(part)

    logical_bytes_read = 0
    with artifact.open_text(errors="replace", max_output_bytes=_JSONL_PARSE_MAX_BYTES) as fh:
        for raw_line in fh:
            logical_bytes_read += len(raw_line.encode("utf-8", errors="replace"))
            if logical_bytes_read > _JSONL_PARSE_MAX_BYTES:
                raise JsonlParseLimitError(
                    f"JSONL content exceeds {_JSONL_PARSE_MAX_BYTES} decompressed bytes"
                )
            lines_total += 1
            stripped = raw_line.strip()
            if not stripped:
                continue
            if len(stripped) > _MAX_LINE_LEN:
                lines_skipped += 1
                continue

            if parser is None:
                detection_buffer.append(stripped)
                if len(detection_buffer) < 20:
                    continue
                # Adapter detection fires once we have 20 lines (or the
                # file ends, handled below). After detection we replay
                # the buffered lines through the parser.
                adapter = detect_adapter(detection_buffer)
                parser = create_parser(adapter)
                first_buffered_line = lines_total - len(detection_buffer) + 1
                for offset, buffered in enumerate(detection_buffer):
                    _consume(buffered, first_buffered_line + offset)
                detection_buffer = []
                continue

            _consume(stripped, lines_total)

        if parser is None:
            # File had fewer than 20 valid lines.
            adapter = detect_adapter(detection_buffer)
            parser = create_parser(adapter)
            first_buffered_line = lines_total - len(detection_buffer) + 1
            for offset, buffered in enumerate(detection_buffer):
                _consume(buffered, first_buffered_line + offset)

        events.extend(parser.flush())

    if artifact.is_compressed:
        file_size = logical_bytes_read
        large_file = file_size > _LARGE_FILE_BYTES
    max_per_event_raw = _LARGE_FILE_PER_EVENT_RAW if large_file else None

    tool_calls = sum(1 for e in events if e.kind == "tool_call")
    errors = sum(1 for e in events if e.is_error)
    result_event = next((e for e in events if e.kind == "result"), None)

    summary: dict[str, Any] = {
        "adapter": adapter,
        "total_events": len(events),
        "tool_calls": tool_calls,
        "errors": errors,
        "cost_usd": result_event.cost_usd if result_event else None,
        "duration_s": result_event.duration_s if result_event else None,
        "is_done": result_event.is_done if result_event else False,
        "is_error": result_event.is_error if result_event else False,
    }
    if lines_skipped:
        summary["lines_skipped"] = lines_skipped
        summary["lines_total"] = lines_total
    if parse_errors:
        summary["parse_errors"] = parse_errors
        summary["warning"] = (
            f"{parse_errors} log line(s) failed to parse; metabrowser kept "
            "rendering the rest of the file."
        )
    for e in events:
        if e.kind == "init":
            raw = e.raw if isinstance(e.raw, dict) else {}
            summary["model"] = raw.get("model")
            break

    serialized: list[dict[str, Any]] = _serialize_events(events, max_per_event_raw)

    raw_text = "\n".join(raw_parts)

    # Server emits raw byte counts; the client formats the truncation
    # banner via its single ``formatSize`` helper so every "X MB" in
    # the SPA renders identically.
    raw_truncation: dict[str, int] | None = None
    if raw_capped:
        raw_truncation = {
            "cap_bytes": max_raw_total or 0,
            "file_bytes": file_size,
            "lines_total": lines_total,
            "lines_skipped": lines_skipped,
        }

    # ``bytes_read`` is the byte cursor the SSE ``/api/stream`` endpoint
    # should resume from. We pass the file's pre-parse size — any bytes
    # appended while we were parsing arrive on the next stream cycle.
    return {
        "summary": summary,
        "events": serialized,
        "raw_text": raw_text,
        "raw_truncation": raw_truncation,
        "bytes_read": file_size,
    }


def _serialize_events(
    events: list[LogEvent],
    max_per_event_raw: int | None,
) -> list[dict[str, Any]]:
    """Convert dataclass events to JSON-serializable dicts.

    Drops the eager ``raw_json`` pretty-print step the client does
    lazily anyway (fall-through ``evt.raw_json || JSON.stringify(...)``).
    For large files we also truncate the raw payload per event so a
    1800-event log full of embedded file dumps doesn't balloon the
    response into the tens of megabytes.
    """
    serialized: list[dict[str, Any]] = []
    for e in events:
        d = asdict(e)
        raw = d["raw"]
        if isinstance(raw, str):
            if max_per_event_raw is not None and len(raw) > max_per_event_raw:
                raw = raw[:max_per_event_raw] + "\n... (truncated)"
            d["raw"] = {"_text": raw}
        elif isinstance(raw, dict) and max_per_event_raw is not None:
            # Cheap pre-flight: only re-serialize and truncate when the
            # payload would actually exceed the cap.
            preview = json.dumps(raw)
            if len(preview) > max_per_event_raw:
                d["raw"] = {"_truncated": True, "_text": preview[:max_per_event_raw] + "..."}
        serialized.append(d)
    return serialized
