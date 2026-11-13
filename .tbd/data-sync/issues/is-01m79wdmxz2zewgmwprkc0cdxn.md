---
type: is
id: is-01m79wdmxz2zewgmwprkc0cdxn
title: "PR #387 B3: the careful 1.1x is claimed from loaded-host single series with no A/A control"
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
created_at: 2026-11-13T07:19:45.342Z
updated_at: 2026-11-13T08:59:44.671Z
started_at: 2026-11-13T07:19:54.505Z
closed_at: 2026-11-13T08:59:44.670Z
close_reason: "fixed in 5da33d70 and c58b53fd (PR #392)"
resolution: null
duplicate_of: null
---
Medium. README.md:518-521 reserves 1.1x for quiet machines. Re-run on a quiet host or label the evidence a rough cut. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245

## Notes

Fixed in 5da33d70 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
