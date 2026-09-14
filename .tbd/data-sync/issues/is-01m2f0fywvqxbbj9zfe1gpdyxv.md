---
type: is
id: is-01m2f0fywvqxbbj9zfe1gpdyxv
title: "PR #114 review R4: a truncated catalog pin never re-resolves catalog-truncated links when a later walk completes"
kind: bug
status: open
priority: 2
version: 1
labels:
  - markdown
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:38.426Z
updated_at: 2026-09-14T03:48:38.426Z
---
PR #114 review R4 (Low). src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js:156,193-197,281,310. After pinning a truncated snapshot the coordinator unsubscribes, so a later complete snapshot (e.g. reconnect after --max-files raised) never re-runs catalog-truncated jobs. Fix: keep listening; re-run only catalog-truncated jobs when a complete snapshot arrives; no re-runs on truncated revisions. Test truncated -> partial -> complete.
