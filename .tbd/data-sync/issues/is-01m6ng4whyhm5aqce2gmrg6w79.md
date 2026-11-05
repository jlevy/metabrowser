---
type: is
id: is-01m6ng4whyhm5aqce2gmrg6w79
title: "PR #299 R1: Late selection cannot upgrade an active refresh"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6ng3rk55p8sm1970bqkvqmv
hold: null
hold_until: null
created_at: 2026-11-05T09:20:26.685Z
updated_at: 2026-11-05T09:20:27.544Z
started_at: 2026-11-05T09:20:27.543Z
---
Medium performance finding on served_pull.py:303. https://github.com/jlevy/metabrowser/pull/299#discussion_r4477558283. Normal missing selection opts in before starting. An explicit refresh started without wait_core may be joined but keeps its original provider mode; the read is bounded and wakes on settlement.
