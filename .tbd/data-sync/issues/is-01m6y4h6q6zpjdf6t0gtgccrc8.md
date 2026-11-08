---
type: is
id: is-01m6y4h6q6zpjdf6t0gtgccrc8
title: Explain the startup inventory work-counter delta
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m3wgefqnj91f8avyyv4x8t5w
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
created_at: 2026-11-08T17:50:37.284Z
updated_at: 2026-11-08T17:50:48.301Z
---
The final exact426 data run retains two bigfiles/env-debug /_debug/inventory observations with control rows_visited/maintained_index_work107 and candidate106 (read_requests5/6, complete true, version59). Historical e204 observed the reverse106/107. Do not dismiss either as noise or add a mask. Frozen readiness probes use DiagnosticsQuery, not RollupQuery, so the initial-rollup-health hypothesis was falsified. Review the cumulative counter contract and actual startup background CatalogQuery/NavigationQuery call shapes; determine whether absolute equality is a valid assertion across asynchronous initial indexing. Preserve both raw values and observability limits. Any supplemental probe must be isolated from the running DATA servers/counters and separately authorized; no profile/source changes or performance claims. Parent mb-2g6f owns complete data acceptance. Independent agent is reviewing source/raw evidence.
