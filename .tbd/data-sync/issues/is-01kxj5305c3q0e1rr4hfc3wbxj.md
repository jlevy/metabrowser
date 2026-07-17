---
type: is
id: is-01kxj5305c3q0e1rr4hfc3wbxj
title: "Final audit: repair pending inventory aggregates incrementally"
kind: bug
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T05:48:10.795Z
updated_at: 2026-07-17T21:16:38.462Z
closed_at: 2026-07-15T06:02:32.498Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Final reconciliation found that boot-walk pending directory aggregate repair could fall back to O(N) event-loop scans and fail to propagate repaired descendant mtimes into parent heaps. Use incremental pending indexes, process deepest-first, propagate parent mtime state, and add responsiveness regressions.

## Notes

Pending aggregate repair uses incremental indexes, processes deepest-first, propagates repaired mtimes into parent heaps, and avoids full inventory scans on the event loop. Responsiveness and nested-newest regressions pass.
