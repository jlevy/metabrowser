---
type: is
id: is-01m79wdp66d6hd00pnyd87s6g2
title: "PR #387 B5: tier-probe.mjs order reversal balances position only for two builds"
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
created_at: 2026-11-13T07:19:46.629Z
updated_at: 2026-11-13T07:48:20.154Z
started_at: 2026-11-13T07:19:55.322Z
---
Low. tier-probe.mjs:658. Rotate by pair index or shuffle with a seed; record each load's position. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 0c924857 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
