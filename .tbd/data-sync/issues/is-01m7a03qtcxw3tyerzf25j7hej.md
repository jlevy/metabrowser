---
type: is
id: is-01m7a03qtcxw3tyerzf25j7hej
title: "PR #392 A8: balance carryover as well as position (Williams design)"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7a03hpjqv8fp6qx0f4ne19b
hold: null
hold_until: null
created_at: 2026-11-13T08:24:14.923Z
updated_at: 2026-11-13T08:59:48.800Z
started_at: 2026-11-13T08:24:15.610Z
closed_at: 2026-11-13T08:59:48.797Z
close_reason: "declined: B5 asked for position balance, which rotation gives; carryover balance needs 2n orderings for odd n and the probe's comparisons are normally two builds"
resolution: null
duplicate_of: null
---
Suggestion. tier-probe.mjs:866-867. Review: https://github.com/jlevy/metabrowser/pull/392#pullrequestreview-5888093145
