---
type: is
id: is-01m79wdnkb5tskm7mt5fz647zw
title: "PR #387 B4: the numbers beside the 220 KB constant cannot be regenerated from what was committed"
kind: bug
status: closed
priority: 2
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m79wdk13cx3t1thfws6s9yjr
hold: null
hold_until: null
created_at: 2026-11-13T07:19:46.026Z
updated_at: 2026-11-13T08:59:45.405Z
started_at: 2026-11-13T07:19:54.909Z
closed_at: 2026-11-13T08:59:45.404Z
close_reason: "fixed in 0c924857 and 5da33d70 (PR #392)"
resolution: null
duplicate_of: null
---
Low. No raw records, no committed interval/slope computation, --fraction 0.54 and the prose source undocumented, README calls it a round with no exp record. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 0c924857 (summary intervals, --summarize) and 5da33d70 (exp-084 samples, H107, --fraction/prose docs) on branch claude/eager-budget-strict-followup.
