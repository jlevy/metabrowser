---
type: is
id: is-01m7k4etjs4vb384yjq91w5e7r
title: "PR #481 A5: MetabrowserTooltip.hide checks instanceof Node, the type says Element"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hdc0y0089a7fe07b2y7v6v
hold: null
hold_until: null
created_at: 2026-11-16T21:33:22.392Z
updated_at: 2026-11-16T22:25:13.793Z
started_at: 2026-11-16T21:33:29.704Z
closed_at: 2026-11-16T22:25:13.792Z
close_reason: "Fixed in aa1d2e71e: MetabrowserTooltip.hide checks instanceof Element; SDK doc says a scoped hide never reaches an anchorless tooltip. Dispositions: https://github.com/jlevy/metabrowser/pull/481#issuecomment-6931212114"
resolution: null
duplicate_of: null
---
Low suggestion. PR #481 review A (https://github.com/jlevy/metabrowser/pull/481#pullrequestreview-5928039255). src/metabrowser/static/app.js:3362-3366. hide(document) takes the scoped path and bypasses the header exception. Fix: instanceof Element; state in the SDK doc that a scoped hide never reaches an anchorless tooltip.
