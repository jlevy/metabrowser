---
type: is
id: is-01m2gv1af5w404zxdq8vxedm86
title: Catalog sort and Recent pass hold the GIL without cooperative yields during a walk
kind: task
status: open
priority: 2
version: 1
labels:
  - performance
dependencies: []
created_at: 2026-09-14T20:51:44.740Z
updated_at: 2026-09-14T20:51:44.740Z
---
Two whole-index passes that overlap the inventory walk still hold the GIL without a cooperative yield.

Found in the PR #122 review (R4): the catalog read's filtering loop now yields every 1,024 entries, but the sort that follows it does not; for the browser's `/api/catalog` read on a 300,000-file tree the sort took 81-169 ms of CPU. The Recent pass (`_recent_projection`) has no yields either. Neither is new in #122.

Measure first (engine performance model: counts before times), then bound or yield: e.g. sort keys precomputed and a chunked merge with cooperative yields, or a bounded top-N selection for Recent, with a deterministic work-between-yields test like tests/test_inventory_walk_work.py.
