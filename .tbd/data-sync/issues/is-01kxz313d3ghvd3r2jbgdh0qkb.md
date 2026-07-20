---
type: is
id: is-01kxz313d3ghvd3r2jbgdh0qkb
title: "P3: live refresh end to end"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz313qt7zrvvc4rymbjxnhs
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:22:19.043Z
updated_at: 2026-07-20T06:22:33.168Z
---
Wire mb.watchRollup into the treemap renderer with dispose on view teardown; debounced relayout on refetch; verify chain filesystem mutation -> walker/watcher upsert -> ancestor aggregate bubble (depth<=2) -> metabrowser:inventory-change -> debounced /api/rollup refetch -> relayout. Integration test from a real filesystem mutation (pattern: test_e2e_filesystem_to_sse.py); cover resync (fs.resync_required drops store and refetches) and scan-in-progress fill-in (pending cells resolve as dirs finalize).
