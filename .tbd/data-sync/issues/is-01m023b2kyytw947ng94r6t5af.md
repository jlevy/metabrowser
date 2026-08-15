---
type: is
id: is-01m023b2kyytw947ng94r6t5af
title: "Binary preview: pure byte formatter with run coalescing and accent budget"
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
created_at: 2026-08-15T06:56:52.861Z
updated_at: 2026-08-15T07:27:45.173Z
closed_at: 2026-08-15T07:27:10.248Z
close_reason: null
---
The display contract as a pure, DOM-free module so it is exhaustively testable.

## `src/metabrowser/builtin_plugins/binary/byte_format.js` (new)

Under the fully strict `tsconfig.json` gate; nothing is added to the legacy
allowlist in `tsconfig.legacy.json`.

- `CONTROL_PICTURES` — built once from `String.fromCharCode(0x2400 + byte)` for
  0x00-0x1F, plus U+2421 for 0x7F.
- `displayForByte(byte) -> string` — 0x20-0x7E literal ASCII, 0x00-0x1F control
  picture, 0x7F delete picture, 0x80-0xFF uppercase hex in guillemets (`‹C3›`).
  Space stays a space; U+2420 is not substituted. LF displays as `␊`.
- `isSpecialByte(byte) -> boolean`.
- `formatByteRuns(bytes, escapeHtml, runBudget) -> {html, accentDropped}` —
  single pass over the `Uint8Array`, coalescing adjacent same-class bytes,
  emitting one `<span class="binary-byte-special">` per special run and routing
  ordinary runs through the SDK escaper. Past `runBudget` the remainder renders
  as one plain run with `accentDropped = true`; the glyph sequence stays
  byte-for-byte identical.

Budget rationale: run count tracks entropy, not file size. High-entropy content
switches class roughly every 1.6 bytes, so 64 KiB of it yields ~25,000 runs,
while mixed content with embedded strings yields far fewer. At the dense end the
accent distinguishes nothing, so dropping it loses no information and bounds the
element count. Default `BINARY_ACCENT_RUN_BUDGET` is 12,000.

Never use a text decoder anywhere in this path: the WHATWG Encoding Standard
maps the `ascii` label to Windows-1252, which would turn bytes above 0x7F into
characters.

## `tests/dom/binary_byte_format_behavior.js` + `tests/test_binary_byte_format_js.py` (new)

Follow `tests/dom/markdown_mount_behavior.js` and `tests/test_markdown_mount_js.py`:
import the ES module from a base64 data URL, assert, exit nonzero with a
failure list.

All 256 byte values map to the documented display, asserted exhaustively. UTF-8
`C3 A9` renders `‹C3›‹A9›` and never `é`. HTML metacharacters in the printable
range are escaped. A run of ordinary bytes is one text run; a run of special
bytes is one element. Budget exhaustion sets `accentDropped`, stops emitting
elements, and leaves the glyph sequence identical to the unbudgeted result.
All-special and alternating fixtures assert a bounded element count rather than
a wall-clock threshold, so the test is not machine-dependent.
