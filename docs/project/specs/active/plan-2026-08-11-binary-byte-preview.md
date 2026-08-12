# Feature: Bounded Binary Byte Preview

**Date:** 2026-08-11 (last updated 2026-08-11)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Add a minimal, generic byte view for files Metabrowser classifies as binary.
The view will preserve printable ASCII, make every other byte visible, use bounded
reads, and wrap in a full-width monospace surface.

The default preview ceiling will be 20 MiB. That ceiling determines which files are
eligible for this view; it does not cause the browser to fetch or render 20 MiB eagerly.
The first request will use the existing 128 KiB preview chunk size, and the user may
load more bytes up to the ceiling.

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
- Rendering files above the preview ceiling or placing an entire 20 MiB expansion in the
  DOM at once.
- Making the transformed display a lossless copy or download format.
  Existing raw-file behavior remains the source of the original bytes.

## Background

The built-in binary plugin currently declares no views, so the shell reports that no
preview is available.
Text previews already use bounded chunks and explicit truncation state.
Installed plugins can fetch bounded server data through declared data hooks without
reaching into the shell’s private JavaScript.

Unicode defines Control Pictures U+2400 through U+241F for the C0 control range and
U+2421 for delete. These glyphs provide compact, standardized visible forms for those
bytes. The browser must not use `TextDecoder("ascii")`: the web encoding standard maps
the `ascii` label to Windows-1252, which would turn bytes above 0x7F into characters and
break the byte-preserving contract.

## Design

### Approach

The existing `binary` plugin will gain one default `bytes` view, one bounded Python data
hook, and plugin-owned styles.
The renderer will fetch the first byte chunk only when its view mounts, append later
chunks on request, and ignore stale completions after the shell disposes the view.

The view will use a full-width `<pre><code>` surface with no prose-width constraint.
It will preserve consecutive spaces, wrap long runs at the available pane width, and
avoid horizontal scrolling as its default layout.
All colors, borders, typography, and controls will use the shared design system.

### Byte Display Contract

The renderer will transform each input byte independently:

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

Control pictures and hexadecimal tokens share one semantic special-byte treatment with a
theme-aware accent color and modestly stronger weight.
The renderer will coalesce adjacent ordinary and special output into runs; it must not
create an element for every ordinary byte.
A pathological alternating-byte fixture will guard against excessive DOM node count and
rendering time. If that test shows the 128 KiB chunk is too large, the binary chunk size
may be lowered without changing the 20 MiB eligibility ceiling.

### Size and Loading Policy

- `BINARY_PREVIEW_MAX_BYTES` defaults to 20 MiB and is the single server-side authority
  for binary-preview eligibility.
- The initial and subsequent requests default to 128 KiB, matching the current text
  preview chunk size. Each request is clamped to a bounded maximum.
- The data hook never returns bytes beyond the 20 MiB ceiling, even if the caller alters
  query parameters.
- The user-facing action says `Load more`; it appends a chunk instead of rerendering the
  bytes already mounted.
- Files above the ceiling receive one concise state:
  `Preview unavailable. Binary previews are limited to 20 MB.` No initial payload is
  read.
- Supported compressed files use logical, decompressed bytes and logical size.
  Existing compressed-input, decompressed-output, and CPU bounds still apply.
- Every response carries a file fingerprint.
  If the file changes between chunks, the renderer discards the partial view and
  restarts at byte zero rather than combining bytes from different file versions.

### Components

- `builtin_plugins/binary/manifest.toml`: declare the default `bytes` view and the
  installed data hook.
- `builtin_plugins/binary/sidekick.py`: validate the path and integer parameters, use
  `ArtifactPath`, perform a bounded binary read off the event loop, and return a chunk
  envelope.
- `builtin_plugins/binary/index.js`: fetch, decode, format, append, and dispose binary
  preview state through `window.metabrowser` only.
- `builtin_plugins/binary/styles.css`: provide the full-width wrapping surface and
  theme-token special-byte styling.
- Focused Python, Node contract, and browser tests: pin the resource, byte-mapping,
  lifecycle, and layout behavior.

No dependency is required.

### API Changes

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
  "bytes_read": 131072,
  "next_offset": 131072,
  "logical_size": 240000,
  "max_preview_bytes": 20971520,
  "has_more": true,
  "mtime_hash": "...",
  "content_base64": "..."
}
```

Base64 keeps the JSON transport exact and portable.
The browser converts it directly to a `Uint8Array`; it never runs the content through a
text decoder. Missing paths, directories, invalid ranges, oversize files, decompression
failures, and file-change races receive bounded, public-safe 4xx responses that the view
turns into concise inline states.

## Implementation Plan

### Phase 1: Bounded Byte View

- [ ] Add server constants, the binary chunk data hook, strict range validation, file
  fingerprinting, and regression tests for safe paths, boundaries, compression, exact
  byte transport, and failures.
- [ ] Add the default binary view, a pure byte-formatting function, chunked loading,
  disposal, and tests covering all 256 byte values and an explicit multibyte UTF-8
  example.
- [ ] Add full-width wrapping and theme-aware special-byte styles using shared tokens
  and button primitives.
- [ ] Add browser coverage for loading, loading more, file replacement, light and dark
  themes, narrow and wide panes, and the 20 MiB boundary.
- [ ] Measure the all-special and alternating-byte fixtures, keep DOM growth bounded,
  and document any binary-specific chunk adjustment.
- [ ] Update user and plugin documentation, run the public-hygiene check, and pass
  `make verify`.

## Testing Strategy

Python tests will exercise both sides of every size boundary, reject traversal and bad
ranges, confirm offsets and fingerprints, and prove that compressed and uncompressed
responses contain the exact requested bytes.
Node tests will cover the complete byte mapping, escaping, run coalescing, incremental
append behavior, disposal during a request, and errors.

Browser tests will open a small mixed-byte fixture in both themes, load multiple chunks,
resize the pane, and confirm that no Markdown-style maximum width or unexpected
horizontal overflow appears.
A file above 20 MiB will confirm that the renderer does not request preview content.
Performance coverage will include all-special and alternating printable/special data
rather than only realistic, favorable input.

## Rollout Plan

Ship the view enabled for the existing built-in `binary` kind.
More-specific plugins continue to win classification and are unaffected.
The initial release needs no feature flag because reads, expansion, and DOM work are
bounded independently.
Server warnings and client errors should include the relative path, offsets, sizes, and
elapsed time but never raw byte content or an absolute local path.

## Open Questions

No blocking design questions remain.
Encoding detection, a traditional hex-dump mode, and richer format viewers can be
evaluated separately after the fallback has real-world use.

## References

- [Plugin system](../../../plugins.md)
- [Development guide](../../../development.md)
- [Unicode Control Pictures names list](https://www.unicode.org/charts/nameslist/n_2400.html)
- [Unicode Control Pictures chart](https://www.unicode.org/charts/PDF/U2400.pdf)
- [WHATWG Encoding Standard](https://encoding.spec.whatwg.org/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
