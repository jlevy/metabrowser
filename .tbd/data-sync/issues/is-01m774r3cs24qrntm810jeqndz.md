---
type: is
id: is-01m774r3cs24qrntm810jeqndz
title: "Git: comparison cache by commit ID; route memo by refs fingerprint"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:33.134Z
updated_at: 2026-11-12T06:57:29.098Z
started_at: 2026-11-12T05:53:04.459Z
---
Browser cache of diff comparisons keyed by full commit ID; server memo of git refs, log pages, and summary keyed by a refs fingerprint. Measured as commit revisit requests and painted-ready, and route server time.

## Notes

Implemented on claude/perf-caches (3594c291, a627d915, 45f2b8d3, 9e1630db), draft PR #368; 135 focused tests re-run and passing. Accepted: served-checkout comparisons depending on working-tree .gitattributes refresh only on Refresh; render invalidation is structural via a WeakMap on the envelope object. Awaiting the transition-scenario round (exp-061 for mb-8a8g, exp-063 for mb-mbd3).
