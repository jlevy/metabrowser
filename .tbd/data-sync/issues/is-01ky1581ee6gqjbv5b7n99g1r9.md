---
type: is
id: is-01ky1581ee6gqjbv5b7n99g1r9
title: "PR13/R7: layout culling and maxCells silently drop area"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:32.429Z
updated_at: 2026-07-21T02:01:47.986Z
closed_at: 2026-07-21T02:01:47.986Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R7: culled slivers vanish without an input rest cell; rest value bumped after geometry; maxCells break drops the tail. Fix: per-level two-pass — determine survivors (top weights within remaining budget), synthesize/extend one remainder item, re-squarify final weights; vm assertions for area conservation and represented totals with no input rest, slivers, and cap exhaustion.
