---
type: is
id: is-01m024s03n1vxyhxqm7dz7p5tp
title: "Binary preview: small unknown-extension files never reach the Bytes view"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-11-binary-byte-preview.md
labels: []
dependencies: []
parent_id: is-01kzt2pwbyj3rt7y2xhevg8ff5
created_at: 2026-08-15T07:21:57.621Z
updated_at: 2026-08-15T07:27:46.819Z
---
Found while verifying the Bytes view in a real browser.

`server._api_file_impl` routes a file to the text path when
`ext in _TEXT_EXTS or logical_size < _INLINE_TEXT_FALLBACK_BYTES` (512 KiB).
So a small file with unknown extension and genuinely binary content — a
19 KB `.bin` full of high bytes, a short `.pyc`, a truncated archive — is
read with `read_text(errors="replace")` and rendered as mojibake by the
text plugin. It is never classified `binary`, so the Bytes view never sees
it.

Verified: the same file at 19 KB reports `kind: "text"` and at 686 KB
reports `kind: "binary"` with the Bytes view. A zero-byte file likewise
reports `kind: "text"`.

This is pre-existing classifier behavior, not a regression from the byte
preview, and the byte-preview plan is scoped to files already classified
binary. But it leaves the plan's first goal — "open ordinary binary files
without blank output, broken glyphs, or uncontrolled browser work" — only
partly met, because the broken-glyph case most users hit is the small file.

Options to weigh, none free:
- Sniff a bounded prefix for NUL bytes or a high density of non-UTF-8
  sequences before taking the text fallback. Reroutes some files that
  render acceptably today, so it needs its own before/after corpus.
- Offer Bytes as a second view on the `text` kind when the decoded prefix
  contained replacement characters. Keeps classification alone but adds a
  conditional view, which the manifest cannot express today.
- Leave as is and document the boundary.

Needs a decision from the maintainer before implementation; the blast
radius is every small unknown-extension file in every served tree.
