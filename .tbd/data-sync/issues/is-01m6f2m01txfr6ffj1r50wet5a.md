---
type: is
id: is-01m6f2m01txfr6ffj1r50wet5a
title: "PR #276 A2: the budget-drift gate's declaration regex cannot express a fractional divergence"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kp2dkv14cykagykcmqet
hold: null
hold_until: null
created_at: 2026-11-02T21:28:35.129Z
updated_at: 2026-11-02T21:49:01.148Z
started_at: 2026-11-02T21:29:09.609Z
closed_at: 2026-11-02T21:49:01.147Z
close_reason: "Fixed in 4f85418: declared budget values read as whole or fractional, compared by number. CI run 41530107623 green at 5c6567e. Disposition: https://github.com/jlevy/metabrowser/pull/276#issuecomment-6589319967"
resolution: null
duplicate_of: null
---
Low. tests/test_performance_loop_gate.py:1564 and :1573-1575 read integers only; metrics.cls is maximum = 0.1 at explorations/performance-loop/performance-budgets-flat-stress.toml:267. Fails safe. Review: https://github.com/jlevy/metabrowser/pull/276#pullrequestreview-5743224957
