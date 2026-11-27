---
type: is
id: is-01m8d7qe087mjkep5t4t8mxtgg
title: Reuse admitted exact compare responses for repeat checkout commit views
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-27T00:50:45.377Z
updated_at: 2026-11-27T00:50:45.377Z
---
H139 candidate. Exp-122 actual server timings and subprocess spans show every checked repeat comparison on the checkout launches both rev-parse and diff. The first prepared click spent 67–87 ms in Git; initial preparation paid configuration discovery too. The comparison cache currently admits repository stores only. Test whether routing an exact full revision through an already attached, complete store preserves the response, worktree semantics and fallback when the object is local-only. Require matching objects, config behavior and diffs, no additional startup work, and fewer post-click Git processes in a golden-backed HTTP replay.
