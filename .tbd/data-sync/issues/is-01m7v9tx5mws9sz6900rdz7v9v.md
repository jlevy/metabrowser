---
type: is
id: is-01m7v9tx5mws9sz6900rdz7v9v
title: "PR #617 B2: rollback-journal policy locks when the owner writes; contention test cannot fail"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v9tw8y6ssgdghdyks2p5ty
hold: null
hold_until: null
created_at: 2026-11-20T01:41:16.595Z
updated_at: 2026-11-20T01:57:19.715Z
started_at: 2026-11-20T01:50:14.478Z
closed_at: 2026-11-20T01:57:19.715Z
close_reason: "fixed in 74df98ad5/7ef20c2f6: wait out live journal or failed validation to the lock deadline, then lock for key page alone, no count; Decision 10 restated; contention.json measures the policy at three paces"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:418-419, 722-733, 818-819. Measure the plan's policy, back off on a journal, skip count under lock, test a bound per owner pace. Severity: Medium. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
