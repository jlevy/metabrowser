---
type: is
id: is-01m6f2m01txfr6ffj1r50wet5a
title: "PR #276 A2: the budget-drift gate's declaration regex cannot express a fractional divergence"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kp2dkv14cykagykcmqet
hold: null
hold_until: null
created_at: 2026-11-02T21:28:35.129Z
updated_at: 2026-11-02T21:29:09.610Z
started_at: 2026-11-02T21:29:09.609Z
---
Low. tests/test_performance_loop_gate.py:1564 and :1573-1575 read integers only; metrics.cls is maximum = 0.1 at explorations/performance-loop/performance-budgets-flat-stress.toml:267. Fails safe. Review: https://github.com/jlevy/metabrowser/pull/276#pullrequestreview-5743224957
