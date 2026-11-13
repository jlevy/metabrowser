---
type: is
id: is-01m79wdkqq5fx9x8arr8f54674
title: "PR #387 B1: the two startup ceilings no longer keep shell-tools scripts off the critical path, and the docs say they do"
kind: bug
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m79wdk13cx3t1thfws6s9yjr
hold: null
hold_until: null
created_at: 2026-11-13T07:19:44.118Z
updated_at: 2026-11-13T07:48:20.589Z
started_at: 2026-11-13T07:19:53.586Z
---
Medium. docs/web-performance-framework.md:151-152, tests/test_check_startup_scripts.py:122-125, performance-budgets.toml request comment. A variant with five shell-tools scripts eager passed the check. Fix: exact membership test, reword docs. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 5da33d70 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
