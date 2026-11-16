---
type: is
id: is-01m7k4erjd783k6vzcveqp2d8w
title: "PR #481 A1: a real focus move after a rebuild that dropped focus is taken for a repair"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hdc0y0089a7fe07b2y7v6v
hold: null
hold_until: null
created_at: 2026-11-16T21:33:20.332Z
updated_at: 2026-11-16T21:33:28.096Z
started_at: 2026-11-16T21:33:28.093Z
---
Medium. PR #481 review A (https://github.com/jlevy/metabrowser/pull/481#pullrequestreview-5928039255). src/metabrowser/static/app.js:3321-3345, docs/design-system.md:4276-4281. tooltipFocusOwner updates only on focusin; a rebuild that removes the focused element and refocuses nothing leaves a disconnected owner, so the reader's next Tab or click is taken for a repair and the pointer's tooltip stays beside the focus ring. Fix (coordinator: first option): a capture-phase keydown and pointerdown listener clears a disconnected owner; add a session case; narrow the doc's wording; re-run the Files tab Chrome loop.
