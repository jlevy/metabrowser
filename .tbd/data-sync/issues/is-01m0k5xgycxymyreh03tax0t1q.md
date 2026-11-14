---
type: is
id: is-01m0k5xgycxymyreh03tax0t1q
title: Measure walk throughput and find where the ~50 us per file goes
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k5xha8rmnc747e64g6a5wa
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:59.852Z
updated_at: 2026-11-14T18:45:43.097Z
---
Phase 3 of the load-time plan, H13: attribute the walk's per-file cost by layer before changing the walker or the 500,000-file cap. mb-s5p6 waits on this, because a cap is a claim about cost.

The 43-50 us per file figures are from August, before the inventory engine. Since then the cProfile in mb-kicj, exp-024 and exp-025 attributed the provider's per-entry construction on a 60,000-file corpus (H65-H71). The flat-tree plan records bare traversal at 0.87 s warm against a 12.9-15.5 s detached walk on the 300k flat corpus, about 93% Python above the filesystem, and a 13.86 us per-entry delivery decomposition.

Still missing: a per-layer split of the current build's detached walk at the cap size, which pricing the cap needs. H18 (mb-nbc6) asks for the same profile before batching (mb-tip8).
