---
type: is
id: is-01ky1580rrser66cjagdp3qqa4
title: "PR13/R5: folder header goes stale while treemap updates"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:31.736Z
updated_at: 2026-07-21T02:01:47.981Z
closed_at: 2026-07-21T02:01:47.981Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R5: header renders envelope aggregates once; treemap refreshes independently. Fix: shell-side debounced envelope refetch on inventory-change events affecting the current folder (same ancestor-bubble predicate as watchRollup), patching header numbers in place; one authority for aggregates.
