---
type: is
id: is-01m27v4gtr2kfwzvkns4ezvpsj
title: Eliminate settled 300k catalog double-pass release gate failure
kind: bug
status: closed
priority: 0
version: 3
labels:
  - release-hardening
  - performance
dependencies: []
parent_id: is-01m26s72hwqbm3076hxa0p5z4c
created_at: 2026-09-11T09:00:19.664Z
updated_at: 2026-09-13T16:43:21.202Z
closed_at: 2026-09-13T16:43:21.200Z
close_reason: "Fixed in 4fe3dfae (guarded direct adoption of the settled catalog). Accepted in exp-032 final series at 863dcd9c: 5/5 candidate runs pass every hard gate, batches <=4,096 items, delivery 1.3-1.4% of window, full attribution."
resolution: null
duplicate_of: null
---
Exact immutable feda3db8 browser capture on the fixed 300k corpus recorded 600,000 bulk-snapshot work items, 155ms total catalog delivery work, 8.7% of the 1.786s measurement window, and a missing steady-state catalog-change label. Diagnose the settled-start catalog path, avoid redundant projection work while preserving UTF-16 canonical ordering and atomicity, make attribution conditional on operations that actually occurred, add browserless/golden coverage, and require repeated exact-wheel hard-gate evidence before installation.

## Notes

Root cause confirmed with exact wheel evidence: one /api/catalog request was processed as a 300k ingest plus a redundant 300k empty-projection merge. Implemented a guarded direct-adoption fast path for an empty projection and added CLI golden coverage pinning one fetch, 300003 work items including three concurrent mutations, <=4096 items per slice, and callback attribution. Focused validation: 76 pytest tests, navigation golden, full lint/type/parity checks. Awaiting repeated exact-wheel headed-browser gate evidence.
