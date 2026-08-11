---
type: is
id: is-01kxj52zpha3d2w4ve3j8xdgj3
title: "Final audit: maintain direct-child newest indexes and compact heaps"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T05:48:10.321Z
updated_at: 2026-07-17T21:16:48.822Z
closed_at: 2026-07-15T06:02:32.761Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Final reconciliation found that live directory newest-child presentation needed an incrementally maintained direct-child index and bounded heap compaction. Preserve newest timestamps without full inventory scans, compact stale heap entries, and cover type transitions and repeated updates.

## Notes

Inventory maintains direct-child newest indexes, compacts stale heaps, and handles repeated updates/type transitions without global scans. Focused inventory regressions pass.
