---
type: is
id: is-01kxj00b9021n6dpspfsc8qer4
title: "PR #1 review A7: move plugin classification I/O off event loop"
kind: bug
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:20.991Z
updated_at: 2026-07-17T21:16:45.390Z
closed_at: 2026-07-15T06:02:32.522Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7a: plugin file-kind rules may synchronously read JSON from async request handlers. Run classification and FileContext parsing through a bounded worker boundary and add a responsiveness/dispatch regression.

## Notes

Plugin classification and JSON/YAML inspection run in worker threads with cached complete-JSON and bounded YAML prefixes. Responsiveness and cap regressions plus full gate pass.
