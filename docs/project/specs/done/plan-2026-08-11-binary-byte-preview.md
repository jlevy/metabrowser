# Feature: Bounded Binary Byte Preview

**Date:** 2026-08-11 (last updated 2026-08-15)

**Author:** Metabrowser maintainers

**Status:** Implemented and validated.

## Overview

Add a minimal, generic byte view for files Metabrowser classifies as binary.
The view preserves printable ASCII, makes every other byte visible, uses bounded reads,
and wraps in a full-width monospace surface.

The preview ceiling is 20 MiB for uncompressed files and 8 MiB of logical bytes for
compressed ones. The ceiling decides which files are eligible; it never causes the
browser to fetch or render that much eagerly.
The first request reads 64 KiB, and the user may load further 64 KiB chunks up to the
ceiling.

## Goals

- Open ordinary binary files without blank output, broken glyphs, or uncontrolled
  browser work.
- Preserve a one-byte-to-one-display-unit contract instead of guessing an encoding.
- Keep printable ASCII readable and make control and high bytes visually distinct.
- Reuse Metabrowser’s safe-path, compression, plugin, lifecycle, button, and
  design-token contracts.
- Keep the implementation small enough to serve as a dependable fallback for richer
  format-specific plugins.

## Non-Goals

- Detecting or decoding UTF-8, UTF-16, locale encodings, or other multibyte text.
- Replacing format-specific image, archive, database, media, or document viewers.
- Providing a traditional offset-and-column hex dump, binary editing, or binary search.
- Rendering files above the preview ceiling or placing an entire ceiling-sized expansion
  in the DOM at once.
- Making the transformed display a lossless copy or download format.
  `/raw` remains the source of the original bytes, so the view carries no copy frame.

## Background

### Where the Gap Is

The built-in `binary` plugin declares no views, so `_views_for_kind("binary")` returns
an empty list and the preview pane falls through to its static branch in
`static/app.js`: “No preview is available for this binary file (…).” The plugin
directory and manifest already exist and document that ownership for a future renderer
lives there.

`_api_file_impl` in `server.py` emits a `binary` envelope from four places: two
`OSError` degradations that carry only compression identity, the malformed-gzip text
fallback, and the final catch-all.
Only the last two carry `mtime_hash`, so a renderer must not treat `ctx.raw.mtime_hash`
as present.

### Seams This Reuses

- `ArtifactPath` (`gz_io.py`) provides `logical_size`, `logical_ext`, and a
  compression-transparent `open_binary(max_output_bytes=…)`.
- `_read_artifact_text_chunk` (`server.py`) is the precedent for an offset read: seek
  for a plain file, read-and-discard for a compressed stream, request `limit + 1` bytes
  to detect “more remains”.
- `plugin_api.resolve_path` wraps `_safe_path`, so a sidekick gets served-root
  containment without importing private names.
- The data-hook dispatcher in `plugin_loader/static_assets.py` runs a synchronous
  sidekick through `run_in_threadpool`, so a plain `def` handler is already off the
  event loop. Only operator-supplied directory plugins have their hooks disabled;
  built-ins may declare them.
- The shell mounts the default view immediately and defers others to
  `container._metabrowserMount`, so lazy mounting and `dispose` come from the existing
  contract.

### Scope Boundary: Which Files Reach This View

`_api_file_impl` takes the text path when
`ext in _TEXT_EXTS or logical_size < _INLINE_TEXT_FALLBACK_BYTES` (512 KiB), so a small
file with an unknown extension and genuinely binary content is read with
`read_text(errors="replace")` and rendered as replacement characters by the text plugin.
It is never classified `binary` and this view never sees it.
The same content at 686 KB reports `kind: "binary"` and gets the Bytes view; at 19 KB it
reports `kind: "text"`.

That boundary is pre-existing classifier behavior, and moving it would reroute every
small unknown-extension file in every served tree, so it is out of scope here.
It does mean the first goal is only partly met: the broken-glyph case a user is most
likely to hit is the small file.
Bead `mb-p992` carries the options and the decision.

### Byte Rendering Constraints

Unicode defines Control Pictures U+2400 through U+241F for the C0 control range and
U+2421 for delete. These glyphs provide compact, standardized visible forms for those
bytes.
The browser must not use `TextDecoder("ascii")`: the WHATWG Encoding Standard maps
the `ascii` label to Windows-1252, which would turn bytes above 0x7F into characters and
break the byte-preserving contract.
The renderer therefore never runs content through a text decoder at all.

## Design

### Approach

The `binary` plugin gains one default `bytes` view, one bounded Python data hook, and
plugin-owned styles.
The renderer fetches the first byte chunk when its view mounts, appends later chunks on
request, and ignores stale completions after the shell disposes the view.

The view uses a full-width `<pre class="code-block"><code>` surface with no prose-width
constraint. Reusing the existing `.code-block` primitive means monospace and
`--mono-block-font-size` arrive from the already-classified `.code-block code` rule
rather than a new `--font-mono` use site.
The surface preserves consecutive spaces and never scrolls horizontally, but it does not
ask CSS to wrap: lines are broken in JavaScript at the measured pane width, for the
reason set out under Rendering Strategy.

### Byte Display Contract

The renderer transforms each input byte independently:

| Input byte | Display |
| --- | --- |
| 0x20 through 0x7E | The literal ASCII character, HTML-safe in the DOM |
| 0x00 through 0x1F | The corresponding Unicode Control Picture |
| 0x7F | `␡` (Symbol for Delete) |
| 0x80 through 0xFF | Uppercase hexadecimal in compact delimiters, such as `‹C3›` |

Spaces remain ordinary spaces; U+2420 is not substituted.
A line feed is displayed as `␊`, not as a decoded line break.
CSS wrapping supplies layout breaks without inventing byte values.
For example, UTF-8 bytes C3 A9 are displayed as `‹C3›‹A9›`, not as `é`. This is
deliberate in the first version.

The guillemet delimiters and the control pictures are what identify a transformed byte;
color is supplementary, so the contract holds when the accent is absent.

### Rendering Strategy

The binding constraint is browser layout, not reading.
Measured against Chromium 141 with software raster, so absolute numbers are pessimistic
while the scaling shape is what matters.

Letting CSS wrap one large run is quadratic, because the line breaker searches for break
opportunities across the whole run:

| Payload | Wrapped lines | Layout and paint | Growth |
| --- | --- | --- | --- |
| 32 KiB | 206 | 43 ms |  |
| 64 KiB | 412 | 146 ms | 3.4x |
| 128 KiB | 824 | 560 ms | 3.8x |
| 256 KiB | 1,648 | 2.17 s | 3.9x |
| 512 KiB | 3,295 | 8.41 s | 3.9x |
| 1 MiB | 6,600 | 33.3 s | ~4x |

Every doubling costs about four times as much.
The wrap mode is not the variable: `overflow-wrap: break-word`, `anywhere`, and
`word-break: break-all` all landed within 3% of each other at 256 KiB.

Three strategies were compared at 1 MiB:

| Strategy | First paint | Scroll | DOM nodes | Native find, selection, print |
| --- | --- | --- | --- | --- |
| One wrapped run | 33,333 ms | 32 ms | 12,006 | preserved |
| Pre-broken lines | 633 ms | 33 ms | 16,389 | preserved |
| Pre-broken plus `content-visibility` | 50 ms | 38 ms | 16,420 | preserved |
| Virtualized window | 33 ms | 33 ms | 132 | lost |

A virtualized window is flat at any size, 33 ms from 1 MiB through 8 GiB, and is the
only option beyond a few tens of MB. It also gives up browser find-in-page and
select-all over the file, needs scrollbar downscaling above Chrome’s measured 33,554,428
px element-height clamp, and is substantially more code.
This view takes the third row instead and keeps the native behaviors; the virtualized
path stays available if a later need justifies the trade.

So lines are broken in JavaScript, the surface uses `white-space: pre`, and the lines
are grouped into `content-visibility: auto` blocks of 128 lines.

The block, not the chunk, is the unit of deferred layout: the browser pays for a block
when it scrolls in. One 4 MiB chunk as a single block measured 1.8 s to scroll into; at
512 lines that fell to 204 ms and at 128 lines to 105 ms, while 64 lines regressed to
127 ms on element overhead.

Each block carries `contain-intrinsic-size` derived from its line count and the measured
line box, so the scrollbar stays proportional while layout is skipped.
Omitting it is the documented failure mode for this technique: scrollbar thrash and
broken deep links.

### Accent Degradation

The renderer coalesces adjacent bytes of the same class into runs and emits one element
per special run, never one element per byte.

Run count tracks entropy, not file size.
High-entropy content alternates classes roughly every 1.6 bytes, so a chunk of it yields
tens of thousands of runs, while content with embedded strings yields far fewer.
The view therefore accents special runs while a chunk stays under
`DEFAULT_ACCENT_RUN_BUDGET` (12,000 runs), and past that renders the remainder of the
chunk as one plain run.

The glyphs are byte-for-byte identical and only the accent is dropped, which loses
nothing: at that density every token is special, so the color distinguishes nothing.
The budget spans the whole chunk rather than resetting per line, and once spent it stays
spent so the treatment does not flicker back on partway down.
The degradation is visible, as the design system requires.

### Size and Loading Policy

Reading is not the constraint.
An 8 MiB plain read measured 4.6 ms and seeking to any offset is O(1), so a plain file
is bounded only by what the browser can hold.

Compressed artifacts differ in kind but not enough to warrant their own ceiling.
`open_binary` returns a non-seekable stream, so reaching offset *N* costs decompressing
*N* bytes and each request restarts from zero — but gzip decodes at roughly 500 MB/s
here, and a read at a 12 MiB offset measured 29 ms, far inside the 5-second per-open CPU
budget in `gz_io`. The total cost of walking a compressed file is `S²/2C` for size *S*
in chunks of *C*, so a **larger** chunk makes compressed files cheaper, not dearer.
Both kinds therefore share one ceiling.

- `BINARY_PREVIEW_MAX_BYTES` defaults to 32 MiB and is the single server-side authority
  for eligibility, compressed or not.
  It is a browser memory budget rather than a server one: the view keeps every loaded
  byte as real text in the DOM so find-in-page, select-all, and print cover the whole
  file. Loading 32 MiB to completion measured 87k DOM nodes and about 306 MB of JS heap
  with scrolling between 22 ms and 107 ms, which is the largest size actually measured.
- `BINARY_PREVIEW_CHUNK_BYTES` defaults to 1 MiB and is the fallback for callers that do
  not pass a `limit`. Requests are clamped to `BINARY_PREVIEW_MAX_CHUNK_BYTES` (16 MiB).
  Both read their defaults from the environment, and neither reaches into `server.py`’s
  private text-preview constants.
- The view opens with a 1 MiB request and doubles each `Load more` up to 8 MiB.
  Formatting is main-thread work — 4 MiB measured about 550 ms against 145 ms for 1 MiB
  — so a small first chunk keeps opening a file prompt, while growth keeps the click
  count low: a 32 MiB file loads completely in six clicks at 120 ms to 1.2 s each.
- Every read passes `max_output_bytes=offset + limit + 1` to `open_binary`, so a
  compressed artifact cannot expand past the window the caller asked for.
- The data hook never returns bytes beyond the ceiling, whatever query parameters the
  caller supplies.
- `Load more` appends its chunk’s blocks instead of rerendering the bytes already
  mounted. Appending into one shared surface is what made repeated clicks degrade before,
  because every append relaid out everything already there.
- The server is the only place the ceiling is expressed.
  The renderer always issues the first request and paints the oversize state from the
  hook’s 413 response, which reads no file content.
  Duplicating the ceiling in JavaScript to skip that request would create a second
  source of truth for one small round trip.
- Supported compressed files use logical, decompressed bytes and logical size.
  Existing compressed-input, decompressed-output, and CPU bounds still apply.
- Every response carries `mtime_hash`. The renderer compares it against the value from
  its first response; on a mismatch it discards the partial view and restarts at byte
  zero rather than combining bytes from different file versions.
  The comparison is client-side, so no extra request parameter needs validating, and the
  discarded payload is bounded at one chunk.
- Line width is measured from the mounted pane, and a debounced `ResizeObserver`
  re-breaks the loaded bytes when the pane changes.
  The decoded chunks are retained for that, which is also why the ceiling is a memory
  budget.

### Errors and States

| Condition | Response | View |
| --- | --- | --- |
| Missing path, directory, or unreadable | 404 | `This file is no longer available.` |
| Negative or non-integer `offset` / `limit` | 400 | `Could not load these bytes.` |
| Logical size above the applicable ceiling | 413 | `Preview unavailable. Binary previews are limited to <ceiling>.` |
| Decompression limit or CPU timeout | 413 | Same oversize state |
| Requested window beyond the applicable ceiling | 416 | Same oversize state |
| Malformed compressed stream | 422 | `This file could not be decompressed.` |
| Zero-byte file | 200, `bytes_read: 0` | `This file is empty.` |
| File changed between chunks | 200, new `mtime_hash` | Restart at byte zero |
| Any other failure | — | `Could not load these bytes.` |

413 and 416 share one message because they differ only in whose fault the refusal is,
which is not something to explain to a reader: 413 means the file is past the ceiling,
416 means the request was, and a client that stops at `has_more: false` never produces
the latter. `<ceiling>` is `mb.formatSize(max_preview_bytes)`, so the copy states the
cutoff that actually applied — 20 MiB for a plain file, 8 MiB for a compressed one — and
matches every other byte readout in the app.

Reaching those states requires the refusal to survive the fetch, so `fetchPluginData`
attaches `status` and the parsed body to the error it throws, the way
`fetchKpressRender` already does.
Without that a hook can explain a refusal in its body and no caller can read it.

Warnings logged server-side include the relative path, offsets, sizes, and elapsed time,
never raw byte content or an absolute local path.

The zero-byte and empty states are defensive rather than routinely reachable: a file
that small takes the shell’s `_INLINE_TEXT_FALLBACK_BYTES` path and is classified
`text`, not `binary`. See the scope boundary below.

### Design System Contract

- Monospace and type size arrive from the shared `.code-block code` rule.
  The plugin stylesheet declares no `font-family` and no font-size literal.
- `Load more` is a labelled action and therefore uses `.btn` with `type="button"`.
- The oversize, empty, and error states use `.preview-empty`; error and failure states
  carry `role="alert"`.
- The initial load placeholder uses the shared `.mb-delayed-loading` utility rather than
  a local timer.
- Special-byte color is a plugin-owned domain token pair defined in the plugin
  stylesheet: `--binary-special-text` on `:root` with a `[data-theme="dark"]` override,
  in OKLCH, derived from the host `--muted` family so it reads as de-emphasized
  structure rather than as status.
  Weight uses `--weight-bold`.
- The byte surface carries `no-highlight`, the shell’s opt-out in `highlightCode()`.
  Reusing `.code-block` otherwise opts the view into syntax highlighting, which rewrites
  the byte runs into `hljs-*` token spans and claims these bytes are source code.
- Byte content stays selectable; the view sets no `user-select`.
- The view declares neither `printable` nor a `print_profile`. A bounded partial byte
  window is not a complete print projection, so the shell’s print button stays hidden.
- `container_class` is `content-body metabrowser-binary-host`.

### Lifecycle

`render(container, ctx)` returns an instance handle with an idempotent `dispose()`. The
handle aborts the in-flight fetch through an `AbortController`, drops the `Load more`
listener with the container, and marks the mount disposed so a late completion paints
nothing. State lives in the renderer closure, keyed per mounted container, so a second
mount of the same view never shares an offset or fingerprint with the first.
`bytes` is the only view for the `binary` kind, so the shell renders no tab bar and
mounts it immediately; the lazy-mount path is still covered because the shell may mount
the view from `container._metabrowserMount` when a preferred view is requested.

## API Changes

The binary manifest adds this plugin-owned route:

```text
GET /api/plugin/binary/chunk?path=<relative>&offset=<bytes>&limit=<bytes>
```

The JSON response contains:

```json
{
  "type": "binary_chunk",
  "path": "relative/file.bin",
  "offset": 0,
  "bytes_read": 65536,
  "next_offset": 65536,
  "logical_size": 240000,
  "max_preview_bytes": 20971520,
  "has_more": true,
  "mtime_hash": "...",
  "content_base64": "..."
}
```

`logical_size` is a plugin-local field name.
The core envelope convention pairs `size` with `size_uncompressed`, but this route
returns one number for both compressed and plain artifacts, so it names that number
directly and the renderer does not reuse core helpers that expect the other shape.

Base64 keeps the JSON transport exact and portable.
The browser converts it directly to a `Uint8Array`; it never runs the content through a
text decoder. Missing paths, directories, invalid ranges, oversize files, decompression
failures, and file-change races receive bounded, public-safe 4xx responses that the view
turns into the concise inline states above.

## Implementation Architecture

### Server Function Map

#### `src/metabrowser/builtin_plugins/binary/sidekick.py` — new

The directory gains an `__init__.py`, and so does `agent_log/`. Pytest collects every
`.py` under `src` (`python_files = ["*.py"]`), and two plugin directories shipping a
`sidekick.py` without package markers collide on the bare basename `sidekick`. Import at
runtime worked either way through implicit namespace packages; the marker is what keeps
the module name unique under collection.

- `BINARY_PREVIEW_MAX_BYTES`, `BINARY_PREVIEW_COMPRESSED_MAX_BYTES`,
  `BINARY_PREVIEW_CHUNK_BYTES`, `BINARY_PREVIEW_MAX_CHUNK_BYTES` — module constants read
  from `METABROWSER_BINARY_*` environment variables with the defaults above.
- `_preview_ceiling(artifact) -> int` — returns the compressed or uncompressed ceiling
  for one artifact. Single expression of the branch, so the response field, the 413
  check, and the tests cannot drift.
- `_query_bounded_int(request, name, default, minimum, maximum) -> int` — local mirror
  of the server helper; a value that does not parse as an integer is a 400 rather than a
  silent fallback, because a bad range on a byte window should not quietly return the
  wrong bytes.
- `read_byte_chunk(artifact, offset, limit) -> tuple[bytes, bool]` — pure read helper.
  Opens with `max_output_bytes=offset + limit + 1`, seeks for a plain file, reads and
  discards for a compressed stream, reads `limit + 1` bytes, and returns the clipped
  payload plus whether more remains.
  Exported so Python tests exercise it without a request double.
- `chunk_handler(request) -> JSONResponse` — synchronous Starlette handler.
  Resolves through `plugin_api.resolve_path`, rejects directories and non-files,
  computes `logical_size` and the ceiling, applies the error table above, calls
  `read_byte_chunk`, and returns the envelope with `ETag: "<mtime_hash>"`.

#### `src/metabrowser/builtin_plugins/binary/manifest.toml`

Adds one `[[view]]` (`kind = "binary"`, `id = "bytes"`, `label = "Bytes"`,
`default = true`, `container_class = "content-body metabrowser-binary-host"`,
`render_runtime = "client"`) and one `[[data_hook]]` (`route = "chunk"`,
`sidekick = "metabrowser.builtin_plugins.binary.sidekick:chunk_handler"`). No `[[kind]]`
block: the `binary` kind is assigned by `server.py`’s fallback, and the existing
manifest comment explaining that stays.

### Browser Function Map

Every new module sits under the fully strict `tsconfig.json` gate.
`binary/index.js` is already absent from the legacy allowlist, and nothing is added to
it.

#### `src/metabrowser/static/plugin_sdk.js`

`fetchPluginData(plugin, route, params, options?)` gains two things every data hook
needs and none had: `options.signal` is forwarded to `fetch` so a disposed view can
abort its request, and a non-ok response rejects with an `Error` carrying `status` and
the parsed `payload` instead of a bare status string.
`fetchKpressRender` already threw that shape; this is the same contract for the plugin
data plane, and it is what makes a hook’s structured refusal readable by its caller.
`static/types.d.ts` records the new parameter.

#### `src/metabrowser/builtin_plugins/binary/byte_format.js` — new

Pure, DOM-free, and exported for Node tests.

- `DISPLAY_TABLE` / `DISPLAY_WIDTH` — the 256-entry unit and column tables, built once
  from `String.fromCharCode(0x2400 + byte)` for the C0 range.
- `displayForByte(byte) -> string` — the four-row contract above.
- `displayWidthForByte(byte) -> number` — 1 for a glyph, 4 for a hex token.
- `isSpecialByte(byte) -> boolean`.
- `lineRanges(bytes, charsPerLine) -> Array<[from, to]>` — byte ranges that each fit the
  column budget, never splitting a byte’s token across a break.
- `formatByteRuns(bytes, escapeHtml, runBudget) -> {html, accentDropped}` — one unbroken
  run, retained for callers that own their own breaking and for the display-contract
  tests.
- `formatByteLines(bytes, escapeHtml, {charsPerLine, runBudget}) -> {html, lines, accentDropped, lineCount}`
  — the shipping path.
  Returns `lines` as well as the joined `html` because the view groups lines into render
  blocks.

#### `src/metabrowser/builtin_plugins/binary/bytes_view.js` — new

- `decodeBase64(value) -> Uint8Array` — `atob` plus a byte-wise copy; no text decoder.
- `measureSurface(surface) -> {charsPerLine, lineHeightPx}` — measures the mounted pane
  with a hidden probe and falls back to fixed values wherever the environment cannot
  measure, so the renderer stays usable under a container double.
- `mountBytesView(container, ctx, mb, options) -> Promise<{dispose}>` — the lifecycle
  described above, plus the progressive chunk sizing and the debounced `ResizeObserver`
  that re-breaks loaded bytes on a width change.
  Takes `mb` and an optional `{signal}` by parameter, mirroring `markdown/rendered.js`.
- `blocksHtml(bytes)` (closure) — formats one chunk into lines and groups them into
  128-line `content-visibility: auto` blocks, each carrying a `contain-intrinsic-size`
  derived from its line count and the measured line box.
- `renderChunkState(state, mb) -> string` — builds the surface, the loaded/total
  readout, the `Load more` button, and the accent-dropped note from one state object, so
  every visible state is reachable in a pure test.

#### `src/metabrowser/builtin_plugins/binary/index.js`

Replaces the placeholder IIFE with an ES module that imports `mountBytesView` and calls
`mb.registerView("binary", "bytes", { render })`.

#### `src/metabrowser/builtin_plugins/binary/styles.css` — new

`:root` and `[data-theme="dark"]` blocks for `--binary-special-text`, the
`.metabrowser-binary-host` surface, `.binary-bytes-content` at `white-space: pre`,
`.binary-bytes-block` at `content-visibility: auto`, `.binary-byte-special`, and the
control row. The surface deliberately does **not** set `pre-wrap`, `overflow-wrap`, or
`word-break`: handing the browser a large run to wrap is the quadratic case measured
above. No color literals outside the token blocks, no font-family, no font-size literal.

### Documentation

- `docs/plugins.md` — note that a built-in plugin may own a bounded chunked data hook,
  using the binary route as the worked example.
- `docs/e2e-testing.md` — the manual browser checklist already names the binary view;
  extend it to cover loading more and the oversize state.
- `docs/project/README.md` — the plan is already linked from Active Feature Plans.

No dependency is required.

## Testing Strategy

Coverage follows the layering in `docs/e2e-testing.md`: this repository has Python route
tests and Node `vm` contract tests, and deliberately has no automated browser or
visual-regression layer.

### Python — `tests/test_binary_preview_sidekick.py` — new

- `read_byte_chunk` returns exact bytes at offset 0, at an interior offset, and at the
  final partial chunk, for plain, gzip, and zlib inputs.
- Both sides of every boundary: `logical_size` exactly at and one byte above each
  ceiling; `offset + limit` exactly at and one byte above the compressed budget.
- Traversal (`../`), a directory path, and a missing path are rejected without leaking
  an absolute path.
- A negative offset, a non-integer limit, and a limit above
  `BINARY_PREVIEW_MAX_CHUNK_BYTES` produce the documented status codes.
- A malformed gzip yields 422; a decompression bomb inside the ceiling yields 413 rather
  than allocating past `max_output_bytes`.
- The envelope round-trips base64 to the exact source bytes for a fixture containing all
  256 values.
- A zero-byte file returns `bytes_read: 0`, `has_more: false`.

### Python — existing suites

- `tests/test_api_file_plugin_views.py` gains a case asserting `/api/file` now reports a
  default `bytes` view for a binary file, so the shell no longer takes its no-preview
  branch.
- `tests/test_chrome_typography.py` adds `binary/styles.css` to `STYLE_FILES`. The
  plugin declares no monospace of its own, so no `MONO_ALLOWED_SELECTORS` entry is
  needed and the test proves it stays that way.
- `tests/test_plugin_e2e_render.py` already fails when a declared `[[view]]` has no
  matching `registerView`; the new view is covered by that existing assertion.

### Node — `tests/dom/binary_byte_format_behavior.js` + `tests/test_binary_byte_format_js.py` — new

- All 256 byte values map to the documented display, asserted exhaustively.
- The explicit UTF-8 example: `C3 A9` renders `‹C3›‹A9›` and never `é`.
- HTML metacharacters in the printable range (`<`, `>`, `&`, `"`, `'`) are escaped.
- Run coalescing: a run of ordinary bytes produces one text run and a run of special
  bytes produces one element.
- Budget exhaustion sets `accentDropped` and stops emitting elements while leaving the
  glyph sequence identical to the unbudgeted result.
- `displayWidthForByte` agrees with the rendered unit for all 256 values.
- `lineRanges` packs single-column bytes to the limit and never splits a byte’s token
  across a break.
- No rendered line exceeds the column budget once tags are stripped, and breaking
  changes no glyph — only where the breaks sit.
- The accent budget spans the whole chunk rather than resetting per line, and once spent
  stays spent.

### Node — `tests/dom/binary_bytes_view_behavior.js` + `tests/test_binary_bytes_view_js.py` — new

- First mount requests offset 0 and paints the decoded chunk.
- `Load more` requests `next_offset` and appends without re-rendering mounted bytes.
- A response whose `mtime_hash` differs from the first restarts the view at byte zero.
- `dispose()` aborts the in-flight request, is idempotent, and a late completion paints
  nothing.
- Two concurrent mounts keep independent offsets and fingerprints.
- Each documented error state renders its copy from `renderChunkState` without a network
  call.
- Each loaded chunk becomes its own set of blocks, each declaring a
  `contain-intrinsic-size`, so an append never relays out what is already mounted.
- The surface markup asks CSS to wrap nowhere, which is the regression that would
  silently restore quadratic layout.
- `measureSurface` degrades to fixed metrics rather than throwing when the environment
  cannot measure.

### Performance fixtures

The all-special and alternating printable/special fixtures are asserted through
`formatByteRuns`, which is where element count is decided.
The assertion is a bounded element count and a preserved glyph sequence, not a
wall-clock threshold, so the test does not become machine-dependent.

### Manual browser check

`tests/manual-fixtures/opaque.bin` already exercises the binary view.
The release checklist adds: load a second chunk, confirm no horizontal overflow at
narrow and wide panes in both themes, and confirm the oversize state on a file above the
ceiling.

## Rollout Plan

Ship the view enabled for the existing built-in `binary` kind.
More-specific plugins continue to win classification and are unaffected.
The initial release needs no feature flag because reads, expansion, and DOM work are
bounded independently.

## Open Questions

No blocking design questions remain.
Encoding detection, a traditional hex-dump mode, and richer format viewers can be
evaluated separately after the fallback has real-world use.

## References

- [Plugin system](../../../plugins.md)
- [Development guide](../../../development.md)
- [End-to-end testing](../../../e2e-testing.md)
- [Design system](../../../design-system.md)
- [Unicode Control Pictures names list](https://www.unicode.org/charts/nameslist/n_2400.html)
- [Unicode Control Pictures chart](https://www.unicode.org/charts/PDF/U2400.pdf)
- [WHATWG Encoding Standard](https://encoding.spec.whatwg.org/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
