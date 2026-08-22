---
type: is
id: is-01m0nw7ww543gqmwjyvnb33hm6
title: Avoid relpath per directory in the prune loop (H37/S4)
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:37.284Z
updated_at: 2026-08-22T23:17:37.284Z
---
Review suggestion S4. ignore_filter.py builds two Path objects and normalizes a path for every directory considered. os.walk is top-down so the parent's relative path is already in hand and the child's is a string concat. On a tree with hundreds of thousands of directories that is a real fraction of what is left after the prune.
