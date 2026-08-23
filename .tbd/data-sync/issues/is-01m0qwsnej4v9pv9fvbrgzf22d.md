---
type: is
id: is-01m0qwsnej4v9pv9fvbrgzf22d
title: Research FDU and MetaBrowser backend alignment
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/research/research-2026-08-23-fdu-metabrowser-inventory-engine.md
labels:
  - research
dependencies: []
child_order_hints:
  - is-01m0qyzmmmym17nxw6m7964xcp
created_at: 2026-08-23T18:05:48.369Z
updated_at: 2026-08-23T18:58:11.074Z
closed_at: 2026-08-23T18:58:11.072Z
close_reason: Research brief completed, reviewed, verified, committed, published in PR 74, and CI passed; the discovered rollup payload/ETag race remains tracked in child bug mb-2cvn.
---
Validate and design the interface among FDU, the file walker, the rollup engine, and MetaBrowser. Produce a dated research brief covering semantic parity, a pluggable Python/Rust backend boundary, reliability, performance measurement, migration sequencing, and cross-repository changes.

## Notes

Reviewed Metabrowser architecture, performance goals, walker/inventory/rollup/query/event code, and fdu PR 44 at commit 64398b7. Draft recommends a stateful inventory-engine provider boundary, shared semantic contract, coherent bounded query bundles, one data/trust cursor, runtime File Rollup registry, sparse application overlays, cross-provider oracles, and an end-to-end floor-aware benchmark campaign. Discovered rollup ETag/version race tracked separately.
