---
type: is
id: is-01kxj00bff0d3j8jzqef465w93
title: "PR #1 review A8: avoid cold-start inventory snapshot churn"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:21.199Z
updated_at: 2026-07-15T06:02:32.542Z
closed_at: 2026-07-15T06:02:32.542Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7b: api_tree repeatedly allocates and scans the full inventory snapshot every 5 ms during cold start. Add a cheap readiness predicate/event and verify the wait loop does not copy the inventory.

## Notes

Cold-start tree waiting now uses a cheap readiness boundary instead of repeatedly copying inventory snapshots. Focused regression and full gate pass.
