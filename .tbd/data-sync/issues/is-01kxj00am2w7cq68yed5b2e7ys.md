---
type: is
id: is-01kxj00am2w7cq68yed5b2e7ys
title: "PR #1 review A4: dispose agent-log chart instances"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:20.321Z
updated_at: 2026-07-15T06:02:32.318Z
closed_at: 2026-07-15T06:02:32.318Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 4 at builtin_plugins/agent_log: charts register no view disposer, leaving Chart.js instances and observers alive after unmount. Add an explicit chart runtime disposal contract and behavioral coverage.

## Notes

Agent-log chart views now register disposal and ignore stale async renders through generation guards. Browser DOM lifecycle regressions and full gate pass.
