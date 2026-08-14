---
type: is
id: is-01m018n1hjmf8yjprjkzbjn8gs
title: Make folder Files and Ignored totals disjoint
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T23:10:27.889Z
updated_at: 2026-08-14T23:16:54.657Z
closed_at: 2026-08-14T23:16:54.654Z
close_reason: Implemented disjoint Files and Ignored rows in the shared Overview/Treemap totals model, updated design and architecture docs, added conservation and boundary coverage, and passed make verify.
---
Align the folder totals table with the navigation population summary. Rename the first row from Total to Files and render only the unignored population; keep Ignored as the excluded population so Files plus Ignored exactly conserves the directory total for both file count and bytes. Each row percentage remains measured against the complete directory population, Files is 100% only when nothing is ignored, and empty or all-ignored directories remain explicit. Apply the same reusable totals model to Overview and Treemap, update design documentation, and cover both metrics with TDD. Acceptance: for total=100 files/500 B and unignored=80 files/300 B, Files shows 80 files/80% or 300 B/60%, Ignored shows 20 files/20% or 200 B/40%, and row values sum to the complete population in either metric. Detailed Show ignored behavior remains unchanged.
