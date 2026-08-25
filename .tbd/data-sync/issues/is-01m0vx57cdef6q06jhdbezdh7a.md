---
type: is
id: is-01m0vx57cdef6q06jhdbezdh7a
title: "PR #76 review 76-1: measure layout switching at the manifest bound"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - review
  - diff
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-25T07:29:04.908Z
updated_at: 2026-08-25T07:57:28.484Z
closed_at: 2026-08-25T07:57:28.476Z
close_reason: "Fixed 76-1: a durable 1,000-ready-file Chrome 151 benchmark measured a 223.7 ms unbatched cold switch. The renderer now preserves immediate persisted control/root state, reprojects above 100 ready files in measured 100-file tasks, and invalidates stale batches by generation. Two batched runs held maximum blocking work to 140.3 ms and 133.7 ms; focused rapid-switch/disposal tests and make verify pass."
resolution: null
duplicate_of: null
---
PR #76 finding 76-1 (Medium), src/metabrowser/builtin_plugins/diff/diff-view.js setLayout/renderFileBody. Measure unified/split layout switching in a real browser at a file count near GIT_COMMIT_MAX_FILES, record the evidence beside existing measurements, and add yielding only if the measured interactive cost requires it. Acceptance: repeatable fixture, recorded timing, no re-lex/refetch, focused tests.
