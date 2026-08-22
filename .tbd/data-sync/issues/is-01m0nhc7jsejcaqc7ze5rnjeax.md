---
type: is
id: is-01m0nhc7jsejcaqc7ze5rnjeax
title: Break the scan/serve contention loop (H31)
kind: task
status: open
priority: 0
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:44.984Z
updated_at: 2026-08-22T20:07:44.984Z
---
Measured on a real tree, warm cache: walk 21.0s unattached vs 258.3s with ONE client polling /api/tree?depth=1 every 2s — 12x. Mechanism is a feedback loop: each nav request costs a tally pass that grows with the index (0.75s at 120k indexed, 1.5s at 241k), that work competes with the walker for the GIL, the walk slows, the window lengthens, more polls land in it. A real browser is a heavier client than the probe. H27 is the first lever (make requests cheap); others: bound total serving CPU during a scan, or move the walk off the serving process. Metric: walk_elapsed_ms attached vs unattached. exp-005.
