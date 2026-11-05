---
type: is
id: is-01m6mv2e96yj34gqsra4f0prmz
title: Test whether connected Git staging avoids drawing every hydrated file
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T03:12:06.437Z
updated_at: 2026-11-05T07:18:59.313Z
started_at: 2026-11-05T03:12:07.043Z
closed_at: 2026-11-05T07:18:59.313Z
close_reason: "Implemented or diagnosed in Metabrowser PR #299 at 0d1b132d. Independent review, paired evidence, local make verify and all nine GitHub CI jobs passed; PR is mergeable. Merge remains with the owner."
resolution: null
duplicate_of: null
---
H79 / exp-047. Three unchanged db52 Git selection traces on the same 55-file public comparison show 229–240 ms Long Tasks and 539–619 ms trusted-click readiness. Source inspection finds the Git host mounts detached: no screen geometry, infinite first-screen budget, 50 initial hydrated file models and synchronous first-width layout below the100-file batch threshold. This is not proved by the faster PR path, which hydrates only8files. Before changing product code, render the SAME held raw Git comparison with exact production diff renderer in connected versus detached staging, using identical layout, width, header and assets. Record first correct doubleRAF text/viewport, file projection counts, Long Tasks, DOM/heap and request counts. Require at least3serial cases each; retain failures. Only adopt a connected-stage fix if this causal probe and repeated complete Git navigation confirm improvement without weakening retention, ownership or cancellation. Coordinate shared generic preview staging with PR-core work; no duplicate lifecycle framework.
