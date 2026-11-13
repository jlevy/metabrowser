---
type: is
id: is-01m79wdnkb5tskm7mt5fz647zw
title: "PR #387 B4: the numbers beside the 220 KB constant cannot be regenerated from what was committed"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m79wdk13cx3t1thfws6s9yjr
hold: null
hold_until: null
created_at: 2026-11-13T07:19:46.026Z
updated_at: 2026-11-13T07:41:10.448Z
started_at: 2026-11-13T07:19:54.909Z
---
Low. No raw records, no committed interval/slope computation, --fraction 0.54 and the prose source undocumented, README calls it a round with no exp record. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 94102722 (summary intervals, --summarize) and cde89af5 (exp-081 samples, H107, --fraction/prose docs) on branch claude/eager-budget-strict-followup.
