---
type: is
id: is-01m1mv98ekved1wk8ffs8qbm1d
title: "PR #101 R5b: the discovery-skip comment overclaims what the code does"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:20.722Z
updated_at: 2026-09-04T02:07:13.394Z
closed_at: 2026-09-04T02:07:13.393Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
The comment says everything after discovery still invalidates, but the watcher starts before the walk (PythonInventoryBackend.open calls start_watcher first), so real watcher and refresh() invalidations landing during the initial walk are skipped too. Safe only because MtimeCache.read re-stats and hash-compares, an invariant in another module with nothing binding them. Also the all_dirty branch still fires during discovery.
