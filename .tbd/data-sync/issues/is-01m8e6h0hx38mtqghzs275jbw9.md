---
type: is
id: is-01m8e6h0hx38mtqghzs275jbw9
title: Bound the optional first-visible-hunk probe on large hydrated diffs
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-27T09:49:00.853Z
updated_at: 2026-11-27T09:49:00.853Z
---
Review of performance PR #905. The opt-in milestone scans all candidate diff lines for geometry until a visible one is found. The production predicate touched geometry 40,000 times in one synthetic all-offscreen frame. Measure Chrome overhead with large diffs and bound the search without missing the first useful visible hunk. Keep the present samples diagnostic. This probe runs in performance tooling only.
