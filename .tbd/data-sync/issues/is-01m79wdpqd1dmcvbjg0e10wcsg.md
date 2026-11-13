---
type: is
id: is-01m79wdpqd1dmcvbjg0e10wcsg
title: "PR #387 A1: tier-probe.mjs startupCost counts compiles and evaluations after the first row"
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
created_at: 2026-11-13T07:19:47.180Z
updated_at: 2026-11-13T07:48:19.142Z
started_at: 2026-11-13T07:19:55.709Z
---
Low. tier-probe.mjs:380-386 sums v8.compile and EvaluateScript at any time; the lazy sums stop at firstRowAt. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302055

## Notes

Fixed in 0c924857 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
