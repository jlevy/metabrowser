"""Serve a page of immediate children from the shared structured-data model."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal

from starlette.datastructures import QueryParams
from starlette.responses import JSONResponse

from metabrowser.builtin_plugins.structured.offer import offers_table
from metabrowser.builtin_plugins.structured.parser import STRUCTURED_PARSE_MAX_BYTES
from metabrowser.frontmatter_yaml import FRONTMATTER_MAX_BYTES
from metabrowser.plugin_api import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ContentReadError,
    ContentRef,
    read_content_window,
    resolve_content,
)

_MARKDOWN_METADATA_FENCE = re.compile(rb"^---[^\S\r\n]*(?:\r\n|\n|\r)")


@dataclass(frozen=True)
class _Selection:
    document: int
    path: tuple[str | int, ...]
    offset: int
    limit: int
    depth: int
    copy_row: bool
    tree: bool


def _parse_selection(query: QueryParams) -> _Selection:
    path = json.loads(query.get("node", "[]"))
    if not isinstance(path, list) or any(type(segment) not in (str, int) for segment in path):
        raise ValueError("node must be a JSON array of object keys or array indexes")
    return _Selection(
        document=int(query.get("document", "0")),
        path=tuple(path),
        offset=int(query.get("offset", "0")),
        limit=int(query.get("limit", "50")),
        depth=int(query.get("depth", "1")),
        copy_row=query.get("copy") == "row",
        tree=query.get("tree") == "1",
    )


def _frontmatter_projection(
    data: bytes, selection: _Selection, *, truncated: bool, show_source: bool
) -> dict[str, Any]:
    from frontmatter_format import FmFormatError, fmf_split_frontmatter

    opening = _MARKDOWN_METADATA_FENCE.match(data)
    if opening is None:
        return {"status": "missing"}
    try:
        metadata, _, _ = fmf_split_frontmatter(data.decode("utf-8", "surrogateescape"))
    except FmFormatError:
        return {
            "status": "too_large" if truncated else "invalid",
            "diagnostic": "Unclosed frontmatter",
        }
    if metadata is None:
        return {"status": "missing"}
    excerpt = metadata.encode("utf-8", "surrogateescape")
    response = _excerpt_projection(
        excerpt, "yaml", opening.end(), 2, selection, show_source=show_source
    )
    if show_source and response.get("status") == "ready" and excerpt.lstrip().startswith(b"{"):
        # A JSON object can also be YAML frontmatter. Choose its Source grammar
        # from the whole metadata block, even when Source shows a single field.
        try:
            json.loads(excerpt)
        except (ValueError, RecursionError):
            pass
        else:
            response["format"] = "json"
    return response


def _fence_projection(
    data: bytes, line: int, selection: _Selection, *, show_source: bool
) -> dict[str, Any]:
    from metabrowser.markdown_fences import structured_fences

    fence = next((f for f in structured_fences(data) if f.opening_line == line), None)
    if fence is None:
        return {"status": "missing"}
    response = _excerpt_projection(
        data[fence.start_byte : fence.end_byte],
        fence.format,
        fence.start_byte,
        fence.opening_line + 1,
        selection,
        show_source=show_source,
    )
    response["format"] = fence.format
    return response


def _excerpt_projection(
    excerpt: bytes,
    format: Literal["json", "yaml"],
    start: int,
    first_line: int,
    selection: _Selection,
    *,
    show_source: bool,
) -> dict[str, Any]:
    from metabrowser.structured_nodes import project_structured

    response = project_structured(
        excerpt,
        format,
        document=selection.document,
        path=selection.path,
        offset=selection.offset,
        limit=selection.limit,
        depth=selection.depth,
        copy_row=selection.copy_row,
        tree=selection.tree,
    )
    response["record_table"] = False
    response["excerpt"] = {"start_byte": start, "end_byte": start + len(excerpt)}
    summary = response.get("node", {})
    if show_source:
        selected_node = bool(selection.path) or response.get("document_count", 0) > 1
        source_range = summary.get("source_range") if selected_node else None
        source_start = source_range["start_byte"] if source_range else 0
        source_end = source_range["end_byte"] if source_range else len(excerpt)
        if source_range is not None or (not selected_node and response.get("status") != "missing"):
            raw = excerpt[source_start:source_end]
            with suppress(UnicodeDecodeError):
                response["source_text"] = raw.decode("utf-8")
            prefix = excerpt[:source_start]
            response["source_start_line"] = len(re.findall(rb"\r\n|\r|\n", prefix)) + first_line
    nodes = [summary, *(child["node"] for child in response.get("children", []))]
    while nodes:
        node = nodes.pop()
        if source_range := node.get("source_range"):
            source_range["start_byte"] += start
            source_range["end_byte"] += start
        nodes.extend(child["node"] for child in node.get("children", []))
    if "error_byte" in response:
        response["error_byte"] += start
    return response


async def read_projection(ref: ContentRef, query: QueryParams) -> JSONResponse:
    from metabrowser.structured_nodes import project_structured, projection_byte_limit

    address = {
        "type": "structured_nodes",
        "path": ref.identity,
        "ext": ref.logical_ext,
        "mtime_hash": ref.fingerprint,
        "size": ref.stored_size,
    }
    expected_revision = query.get("mtime_hash")
    if expected_revision is not None and expected_revision != ref.fingerprint:
        return JSONResponse({**address, "status": "changed"}, status_code=409)
    try:
        selection = _parse_selection(query)
        fence_line = int(query["fence_line"]) if "fence_line" in query else None
        if fence_line is not None and (
            ref.logical_ext != ".md" or fence_line < 1 or query.get("frontmatter") == "1"
        ):
            raise ValueError("fence_line selects a positive line in a Markdown body")
    except (ValueError, RecursionError) as exc:
        return JSONResponse(
            {**address, "status": "bad_request", "error": str(exc)}, status_code=400
        )

    frontmatter = ref.logical_ext == ".md"
    format: Literal["json", "yaml"] = "json" if ref.logical_ext == ".json" else "yaml"
    max_bytes = (
        FRONTMATTER_MAX_BYTES
        if frontmatter
        else min(STRUCTURED_PARSE_MAX_BYTES, projection_byte_limit(format))
    )
    if fence_line is not None:
        from metabrowser.markdown_limits import MARKDOWN_DIFF_MAX_BYTES

        max_bytes = MARKDOWN_DIFF_MAX_BYTES
    if max_bytes < 0:
        return JSONResponse({**address, "status": "too_large"})
    try:
        window = await read_content_window(ref, max_bytes=max_bytes)
    except ArtifactDecompressionLimitError:
        return JSONResponse({**address, "status": "too_large"})
    except ArtifactCompressionError as exc:
        return JSONResponse({**address, "status": "invalid", "diagnostic": str(exc)})
    except ContentReadError as exc:
        if exc.http_status == 413:
            return JSONResponse({**address, "status": "too_large"})
        raise
    # A filesystem ref captures its fingerprint before its reader opens the path.
    # Refuse a replacement during that read before publishing ranges or copy text.
    after = await resolve_content(ref.identity)
    if after is None or after.fingerprint != ref.fingerprint:
        return JSONResponse({**address, "status": "changed"}, status_code=409)
    if fence_line is not None:
        if window.has_more:
            return JSONResponse({**address, "status": "too_large"})
        projection = await asyncio.to_thread(
            _fence_projection,
            window.data,
            fence_line,
            selection,
            show_source=query.get("source") == "1",
        )
        return JSONResponse({**address, **projection})
    if frontmatter:
        projection = await asyncio.to_thread(
            _frontmatter_projection,
            window.data,
            selection,
            truncated=window.has_more,
            show_source=query.get("source") == "1",
        )
        return JSONResponse({**address, **projection})
    # Beyond the exact-range parser's budget, keep the existing record grid when
    # its bounded prefix offer found a record list.
    if window.has_more:
        record_table = not selection.path and await asyncio.to_thread(
            offers_table, window.data, ref.logical_ext
        )
        return JSONResponse({**address, "status": "too_large", "record_table": record_table})
    projection = await asyncio.to_thread(
        project_structured,
        window.data,
        format,
        document=selection.document,
        path=selection.path,
        offset=selection.offset,
        limit=selection.limit,
        depth=selection.depth,
        copy_row=selection.copy_row,
        tree=selection.tree,
    )
    return JSONResponse({**address, **projection})
