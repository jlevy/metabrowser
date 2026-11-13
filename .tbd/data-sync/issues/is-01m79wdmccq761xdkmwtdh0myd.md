---
type: is
id: is-01m79wdmccq761xdkmwtdh0myd
title: "PR #387 B2: the budget comment derives 220 KB from a 0.28 ms/KB slope its own validation contradicts"
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
created_at: 2026-11-13T07:19:44.779Z
updated_at: 2026-11-13T08:59:45.057Z
started_at: 2026-11-13T07:19:54.051Z
closed_at: 2026-11-13T08:59:45.056Z
close_reason: "fixed in 5da33d70 (PR #392)"
resolution: null
duplicate_of: null
---
Medium. performance-budgets.toml:211-227 and the brief's Option B. Rest both on the direct 220 KB validation; say how the slopes were paired. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 5da33d70 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
