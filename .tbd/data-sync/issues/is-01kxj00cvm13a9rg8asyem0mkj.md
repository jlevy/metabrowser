---
type: is
id: is-01kxj00cvm13a9rg8asyem0mkj
title: "PR #1 review B1: refresh live root totals"
kind: bug
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:22.611Z
updated_at: 2026-07-17T21:16:37.905Z
closed_at: 2026-07-15T06:02:32.458Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Fresh end-to-end review R1: live fs.change inserts/removes tree rows but leaves the root file count, byte total, and tooltip stale. Update root aggregate presentation from FileStore changes and add behavioral DOM coverage for create/delete.

## Notes

Live root counts, byte totals, tooltips, and direct-child presentation now update across create/delete and type transitions. Browser/inventory regressions and live fixture create/delete check pass.
