---
type: is
id: is-01m7hh0sx2pjjkcz2twced4nzn
title: "PR #466 B1: overlapping grouped reads evict each other's page memos and fail"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:25.569Z
updated_at: 2026-11-16T06:34:36.803Z
started_at: 2026-11-16T06:34:36.802Z
---
Medium. python_inventory.py:2506-2510, :2392-2420, :1728-1746; tree_page_assembly.py:190-275. Review B https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915875839. Coordinator: option 1, a per-runtime semaphore around assemble_grouped_tree; provider test; name eviction in the error.
