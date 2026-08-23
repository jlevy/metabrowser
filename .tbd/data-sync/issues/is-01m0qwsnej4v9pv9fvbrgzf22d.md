---
type: is
id: is-01m0qwsnej4v9pv9fvbrgzf22d
title: Research FDU and MetaBrowser backend alignment
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/research/research-2026-08-23-fdu-metabrowser-inventory-engine.md
labels:
  - research
dependencies: []
child_order_hints:
  - is-01m0qyzmmmym17nxw6m7964xcp
created_at: 2026-08-23T18:05:48.369Z
updated_at: 2026-08-23T21:26:03.806Z
closed_at: 2026-08-23T21:26:03.805Z
close_reason: "Reconciled the research with the fdu-side review, extracted and indexed the active three-phase pluggable inventory-engine plan, created implementation feature mb-8127, pushed Metabrowser PR #74 with green CI, and posted the final linked proposal to fdu PR #44."
---
Validate and design the interface among FDU, the file walker, the rollup engine, and MetaBrowser. Produce a dated research brief covering semantic parity, a pluggable Python/Rust backend boundary, reliability, performance measurement, migration sequencing, and cross-repository changes.

## Notes

Reconciled the Metabrowser research with the fdu-side review at bd1dcf8. Resolved the provider boundary as a sealed two-backend contract, v1 invalidation/read-on-dirty changes, snapshot bulk-load before measurement-gated lazy blocks, a vendored revision-pinned File Rollup packet, combined reducer-cost measurement, and design-first cross-seam spikes. Added an active Metabrowser plan spec and implementation feature mb-8127.
