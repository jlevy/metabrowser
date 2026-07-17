---
type: is
id: is-01kxj530jzsgrnhvd38ntd3a0g
title: "Final audit: remove known files without prefix scans"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T05:48:11.231Z
updated_at: 2026-07-17T21:16:49.333Z
closed_at: 2026-07-15T06:02:32.777Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Final reconciliation found that removing a known file unnecessarily scanned inventory prefixes. Preserve a direct dictionary fast path for files, restrict descendant scans to directories, and cover a large-inventory complexity regression.

## Notes

Known-file removal uses a direct dictionary fast path; only directory removal scans descendants. A 20,000-entry no-prefix-scan regression passes.
