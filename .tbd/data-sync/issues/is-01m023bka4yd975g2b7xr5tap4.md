---
type: is
id: is-01m023bka4yd975g2b7xr5tap4
title: "Binary preview: bytes view renderer, chunked loading, and disposal"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies:
  - type: blocks
    target: is-01m023c0gqd8ccpx9nr7rpbrp3
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T06:57:09.955Z
updated_at: 2026-08-15T07:27:45.506Z
closed_at: 2026-08-15T07:27:10.253Z
close_reason: null
---
The mounted view: fetch, decode, paint, append, dispose.

## `src/metabrowser/builtin_plugins/binary/bytes_view.js` (new)

Strict-gate module.

- `decodeBase64(value) -> Uint8Array` — `atob` plus a byte-wise copy. No
  `TextDecoder`, no `TextEncoder`.
- `renderChunkState(state, mb) -> string` — every visible state from one state
  object, so each is reachable without a network call: loading, loaded-partial,
  loaded-complete, empty, oversize, compressed-window, decompress-failure,
  unavailable, accent-dropped note.
- `mountBytesView(container, ctx, mb, options) -> Promise<{dispose}>` — takes
  `mb` and an optional `{signal}` by parameter, mirroring
  `builtin_plugins/markdown/rendered.js`, so Node tests drive it with a fake SDK
  and a container double.

Behavior:
- Fetches through `mb.fetchPluginData("binary", "chunk", {path, offset, limit})`.
- Always issues the first request; the oversize state is painted from the hook's
  413 response. The ceiling is expressed only server-side — duplicating it in JS
  would create a second source of truth to save one small round trip that reads
  no file content.
- `Load more` requests `next_offset` and appends without re-rendering mounted
  bytes.
- Compares each response's `mtime_hash` against the first response's; on a
  mismatch it discards the partial view and restarts at byte zero. The
  comparison is client-side, so no extra request parameter needs validating and
  the discarded payload is bounded at one chunk. Note that `ctx.raw.mtime_hash`
  is absent on two of the four `binary` envelopes `server._api_file_impl` emits,
  so the fingerprint must come from the hook response.
- Ceiling copy renders through `mb.formatSize(max_preview_bytes)` so it tracks
  the constant and matches every other byte readout.
- Returns an idempotent `dispose()` that aborts the in-flight fetch via
  `AbortController` and marks the mount disposed so a late completion paints
  nothing. State lives in the renderer closure keyed per container, so two
  mounts never share an offset or fingerprint.

## `tests/dom/binary_bytes_view_behavior.js` + `tests/test_binary_bytes_view_js.py` (new)

First mount requests offset 0 and paints the decoded chunk. `Load more` requests
`next_offset` and appends. A differing `mtime_hash` restarts at byte zero.
`dispose()` aborts the in-flight request, is idempotent, and a late completion
paints nothing. Two concurrent mounts keep independent offsets and fingerprints.
Every documented error state renders its copy from `renderChunkState`.
