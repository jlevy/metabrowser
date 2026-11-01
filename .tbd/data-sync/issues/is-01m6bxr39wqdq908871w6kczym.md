---
type: is
id: is-01m6bxr39wqdq908871w6kczym
title: Review comments show the whole diff hunk, so a long conversation is mostly hunks
kind: task
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-11-01T16:05:43.355Z
updated_at: 2026-11-01T17:59:44.621Z
started_at: 2026-11-01T16:06:25.357Z
---
Found 2026-11-01 on pallets/click#3030: 37 hunks up to 253 lines take 35,104 px of a 62,117 px page, with no addition or deletion colouring. github.com shows only the end of the hunk, where the comment anchors. Show the tail, keep a multi-line comment's whole range visible, offer the earlier lines through a stateless disclosure, and colour added and deleted lines with existing design tokens.

## Notes

2026-11-01: fixed in PR #273, open, CI green at its last read. Close when it merges; its required review has not run.
