---
type: is
id: is-01m8bcw7enkhsj6h92wrdmr24x
title: "CI flake: stale delete reconciliation loses recreated directory on Python 3.14t"
kind: bug
status: open
priority: 2
version: 2
refs:
  - kind: web
    url: https://github.com/jlevy/metabrowser/actions/runs/45776141240/job/139760248940
    at: 2026-11-26T07:42:17.698Z
labels:
  - flake
dependencies: []
created_at: 2026-11-26T07:42:16.519Z
updated_at: 2026-11-26T07:42:17.701Z
---
test_stale_delete_event_reconciles_recreated_directory failed on main at c0ea08948 because the tree contained dist without dist/new.whl. PR #871 merge does not modify watcher or inventory code. The prior main run passed, and the isolated test passed 12 consecutive local runs on CPython 3.14.7 free-threaded. Investigate the event and refresh ordering on Linux under parallel CI.
