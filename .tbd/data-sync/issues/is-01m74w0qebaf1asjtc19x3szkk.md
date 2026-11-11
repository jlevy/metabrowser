---
type: is
id: is-01m74w0qebaf1asjtc19x3szkk
title: "PR #348 A8: _prepare_comparison spreads the job mode across several flags"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:29.770Z
updated_at: 2026-11-11T09:24:57.002Z
started_at: 2026-11-11T09:24:55.900Z
closed_at: 2026-11-11T09:24:57.001Z
close_reason: "Fixed in c5fc056d: explicit idle/foreground mode changed only by promotion, separate idle and foreground phases, _Prepared result (done/refresh_metadata), recovery_pending applied once in the foreground loop; cached-record check moved to served_pull.cached_comparison_record beside record_revision."
resolution: null
duplicate_of: null
---
Medium. checkout.py:453-522, 461. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
