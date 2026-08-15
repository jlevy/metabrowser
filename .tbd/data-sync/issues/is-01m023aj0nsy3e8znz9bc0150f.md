---
type: is
id: is-01m023aj0nsy3e8znz9bc0150f
title: "Binary preview: bounded chunk data hook and server constants"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies:
  - type: blocks
    target: is-01m023bka4yd975g2b7xr5tap4
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T06:56:35.861Z
updated_at: 2026-08-15T07:27:44.859Z
closed_at: 2026-08-15T07:27:10.241Z
close_reason: null
---
Add the server side of the byte preview. New file, no core changes.

## `src/metabrowser/builtin_plugins/binary/sidekick.py` (new)

The directory stays an implicit namespace package, matching
`builtin_plugins/agent_log/sidekick.py`. Do not add `__init__.py`.

Constants, each reading its default from a `METABROWSER_BINARY_*` environment
variable:
- `BINARY_PREVIEW_MAX_BYTES` = 20 MiB — uncompressed eligibility ceiling.
- `BINARY_PREVIEW_COMPRESSED_MAX_BYTES` = 8 MiB — compressed eligibility and
  reachable-window ceiling. `ArtifactPath.open_binary` returns a non-seekable
  stream, so offset N costs decompressing N bytes and every request restarts
  from zero; without this bound a 20 MiB gzip walked in chunks decompresses
  ~1.3 GiB and trips the 5 s per-open CPU budget in `gz_io`.
- `BINARY_PREVIEW_CHUNK_BYTES` = 64 KiB — default request size.
- `BINARY_PREVIEW_MAX_CHUNK_BYTES` = 1 MiB — per-request clamp.

Functions:
- `_preview_ceiling(artifact) -> int` — one expression of the compressed vs
  uncompressed branch, consumed by the 413 check and the response field so
  they cannot drift.
- `_query_bounded_int(request, name, default, *, minimum, maximum)` — a value
  that does not parse as an integer raises rather than silently falling back;
  a bad range on a byte window must not quietly return the wrong bytes.
- `read_byte_chunk(artifact, offset, limit) -> tuple[bytes, bool]` — opens with
  `max_output_bytes=offset + limit + 1`, seeks for a plain file and
  reads-and-discards for a compressed stream (mirroring
  `server._read_artifact_text_chunk`), reads `limit + 1`, returns the clipped
  payload plus whether more remains. Exported for direct testing.
- `chunk_handler(request) -> JSONResponse` — synchronous; the data-hook
  dispatcher already runs sync sidekicks through `run_in_threadpool`, so no
  `asyncio.to_thread` is needed. Resolves through `plugin_api.resolve_path`,
  returns the `binary_chunk` envelope with `ETag: "<mtime_hash>"`.

Status table: 404 missing/dir/unreadable, 400 bad range, 413 over ceiling or
decompression limit/timeout, 416 compressed window past the budget, 422
malformed compressed stream. No absolute paths in any message.

## `tests/test_binary_preview_sidekick.py` (new)

Write these first. Exact bytes at offset 0, an interior offset, and the final
partial chunk, for plain / gzip / zlib. Both sides of every ceiling and of the
compressed window. Traversal, directory, and missing paths. Negative offset,
non-integer limit, over-max limit. Malformed gzip -> 422. Decompression bomb
inside the ceiling -> 413 without allocating past `max_output_bytes`. Base64
round-trips a fixture containing all 256 byte values. Zero-byte file returns
`bytes_read: 0`, `has_more: false`.
