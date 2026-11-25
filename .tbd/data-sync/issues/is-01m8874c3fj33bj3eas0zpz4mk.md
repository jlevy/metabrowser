---
type: is
id: is-01m8874c3fj33bj3eas0zpz4mk
title: Guide notes render as sanitized Markdown
kind: feature
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T02:04:08.616Z
updated_at: 2026-11-25T14:08:31.594Z
started_at: 2026-11-25T03:08:03.188Z
closed_at: 2026-11-25T14:08:31.593Z
close_reason: "Merged in #822 with stack 809 (1d6bae3)"
resolution: null
duplicate_of: null
---

## Notes

Built on claude/stack-review in 8cbded16b (Phase 0 of plan-2026-11-24-stack-review.md); no PR yet.
- Route: guided-review answers note_html beside note, and group_note_html on the step that opens a group with a note; null when the render is refused or fails, and the page shows the note as typed.
- Render: pull_markdown.render_text, the description's own path (KPress sanitized, then inert_html.harden, in the Markdown child under its deadline), factored out of render_part. Renders kept with the parse in _READS within _MAX_KEPT_NOTE_CHARS (guided_review.py), measured.
- Page: inertProse in pull-page.js (DrawProse in guided-review.js) inserts it through the description's allowlist; titles stay text. Line breaks follow the description: a single break joins lines. Mermaid in a note shows as code.
- Parity: route golden Notes section (stand-in variant "markdown"), browserless page session line, Chrome check in tests/dom/github-guided-review-chrome.mjs.
- Cost: every guided-review step read now waits for the Markdown child (cold start seconds under load).
