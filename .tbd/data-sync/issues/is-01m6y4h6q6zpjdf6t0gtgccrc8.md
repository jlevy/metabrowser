---
type: is
id: is-01m6y4h6q6zpjdf6t0gtgccrc8
title: Explain the startup inventory work-counter delta
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m3wgefqnj91f8avyyv4x8t5w
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
created_at: 2026-11-08T17:50:37.284Z
updated_at: 2026-11-08T18:04:48.038Z
closed_at: 2026-11-08T18:04:48.037Z
close_reason: "Independent exact-source/raw review establishes that equal absolute cumulative startup work is not a valid unconditional invariant. Current five-read accounting is106+K visited, with early activity-catalog K1/0 consistent with A107/B106; original per-call cardinalities were not recorded, so this remains source-derived inference, not observed causality. Provider/tracker bytes match across builds, final metadata is identical, raw current/historical values remain intact, and no mask/equality/speed claim was added. Evidence: debug-counter-426-independent-20261108/review.txt, accounting.json, source-proof.json and frozen manifests. Exp057 uses cumulative inventory_work only as named context, not an absolute-equality metric. No production change or further probe is required for this scoped disposition; full data/browser/release acceptance remains open."
resolution: null
duplicate_of: null
---
The final exact426 data run retains two bigfiles/env-debug /_debug/inventory observations with control rows_visited/maintained_index_work107 and candidate106 (read_requests5/6, complete true, version59). Historical e204 observed the reverse106/107. Do not dismiss either as noise or add a mask. Frozen readiness probes use DiagnosticsQuery, not RollupQuery, so the initial-rollup-health hypothesis was falsified. Review the cumulative counter contract and actual startup background CatalogQuery/NavigationQuery call shapes; determine whether absolute equality is a valid assertion across asynchronous initial indexing. Preserve both raw values and observability limits. Any supplemental probe must be isolated from the running DATA servers/counters and separately authorized; no profile/source changes or performance claims. Parent mb-2g6f owns complete data acceptance. Independent agent is reviewing source/raw evidence.
