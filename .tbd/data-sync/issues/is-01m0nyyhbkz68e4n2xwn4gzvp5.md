---
type: is
id: is-01m0nyyhbkz68e4n2xwn4gzvp5
title: "H39: price the gitignore matcher — walk with and without gitignore_check"
kind: task
status: open
priority: 0
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0nyyhrqgc6sks99h538m4te
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:56.295Z
updated_at: 2026-11-14T18:43:31.721Z
---
Load-time hypothesis H39 (plan-2026-08-21-load-time-performance.md, Hypotheses). What remains of the walk may be gitignore matching rather than traversal: exp-006 cut the compiled pattern set from 10,668 to 327 without measuring what the matcher still costs. Price it before replacing the walker. Metric: walk_elapsed_ms with and without gitignore_check. Gates H40 (mb-nbvk).
