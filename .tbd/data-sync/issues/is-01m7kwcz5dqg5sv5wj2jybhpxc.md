---
type: is
id: is-01m7kwcz5dqg5sv5wj2jybhpxc
title: "PR #496 review C1: the verdict names the head red at planning, not main's current red head"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kwcymkyzy307gn8bvwhx18
created_at: 2026-11-17T04:31:47.373Z
updated_at: 2026-11-17T04:32:08.867Z
closed_at: 2026-11-17T04:32:08.867Z
close_reason: "Fixed in 66170948: the procedure is the review's three checks: merge only when the latest attempt of main's newest run has completed; while not green, only on a passing ci-ok whose verdict says tested=yes and names that run's head SHA; a rerun never qualifies, update or push instead. In the plan and mb-oz36."
resolution: null
duplicate_of: null
---
plan:268-270, :277-281, :583-584, :801-802; mb-oz36. Make the equality of the verdict's head with main's newest run's head the rule; define finished as the latest attempt completed; a qualifying run comes from updating or pushing, never a rerun.
