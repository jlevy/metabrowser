---
type: is
id: is-01m79wdqe8bzpp1cqatv4yp201
title: "PR #387 A2: tier-probe.mjs --cpu/--warm and eager-comments.mjs --fraction accept anything"
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
created_at: 2026-11-13T07:19:47.911Z
updated_at: 2026-11-13T08:59:43.645Z
started_at: 2026-11-13T07:19:56.102Z
closed_at: 2026-11-13T08:59:43.644Z
close_reason: "fixed in 0c924857 (PR #392)"
resolution: null
duplicate_of: null
---
Low. tier-probe.mjs:101-104, eager-comments.mjs:61-62 take Number(value) unchecked. Review: https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302055

## Notes

Fixed in 0c924857 on branch claude/eager-budget-strict-followup (follow-up PR to #387).
