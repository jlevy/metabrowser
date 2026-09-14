---
type: is
id: is-01m2f0fywvqxbbj9zfe1gpdyxv
title: "PR #114 review R4: a truncated catalog pin never re-resolves catalog-truncated links when a later walk completes"
kind: bug
status: closed
priority: 2
version: 2
labels:
  - markdown
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:38.426Z
updated_at: 2026-09-14T04:45:54.652Z
closed_at: 2026-09-14T04:45:54.650Z
close_reason: "Fixed in de282ce5: coordinator pins only complete snapshots; a truncated revision is kept through truncated/partial revisions (no re-runs) and only catalog-truncated jobs re-run when a complete revision arrives. Coordinator, wiki-enhancer, link-enhancer tests and functional golden cover truncated -> partial -> complete."
resolution: null
duplicate_of: null
---
PR #114 review R4 (Low). src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js:156,193-197,281,310. After pinning a truncated snapshot the coordinator unsubscribes, so a later complete snapshot (e.g. reconnect after --max-files raised) never re-runs catalog-truncated jobs. Fix: keep listening; re-run only catalog-truncated jobs when a complete snapshot arrives; no re-runs on truncated revisions. Test truncated -> partial -> complete.
