---
type: is
id: is-01m7k4erjd783k6vzcveqp2d8w
title: "PR #481 A1: a real focus move after a rebuild that dropped focus is taken for a repair"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hdc0y0089a7fe07b2y7v6v
hold: null
hold_until: null
created_at: 2026-11-16T21:33:20.332Z
updated_at: 2026-11-16T22:25:12.261Z
started_at: 2026-11-16T21:33:28.093Z
closed_at: 2026-11-16T22:25:12.260Z
close_reason: "Fixed in 59c868bef (head 26cfb6c87): capture-phase keydown/pointerdown endTooltipFocusRepair lets a disconnected owner go; session cases fail with the release made a no-op or unconditional; Chrome probe and Files tab loop (10/10 ambient, 30/30 at 6x) on the merged head. Dispositions: https://github.com/jlevy/metabrowser/pull/481#issuecomment-6931212114"
resolution: null
duplicate_of: null
---
Medium. PR #481 review A (https://github.com/jlevy/metabrowser/pull/481#pullrequestreview-5928039255). src/metabrowser/static/app.js:3321-3345, docs/design-system.md:4276-4281. tooltipFocusOwner updates only on focusin; a rebuild that removes the focused element and refocuses nothing leaves a disconnected owner, so the reader's next Tab or click is taken for a repair and the pointer's tooltip stays beside the focus ring. Fix (coordinator: first option): a capture-phase keydown and pointerdown listener clears a disconnected owner; add a session case; narrow the doc's wording; re-run the Files tab Chrome loop.
