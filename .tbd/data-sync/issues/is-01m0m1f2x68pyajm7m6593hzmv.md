---
type: is
id: is-01m0m1f2x68pyajm7m6593hzmv
title: "H18: batch walker entry emission per directory instead of per file"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0m5vwxj193b0g8djjf9ba83
  - type: blocks
    target: is-01m0k5xha8rmnc747e64g6a5wa
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T06:10:26.853Z
updated_at: 2026-11-15T07:01:10.793Z
---
The walk costs ~43 us/file (300k files in 12,871 ms warm). Structure: one to_thread per directory is cheap (972 hops), but every entry is yielded one at a time through an async generator onto the event loop, and each write moves the rollup revision. Attribute first (profile one walk), then batch emission per directory as its own experiment. Metric: 'inventory walker complete: elapsed=' in the server log at 300k warm. Also slows the revision churn H8 depends on. Plan Backlog H18.

## Notes

2026-11-14 audit: in the plan's Next table this bead is the profile step before H22 (mb-tip8, the batch change), which its title does not say. mb-migx (Measure walk throughput and find where the ~50 us per file goes, no description) covers the same attribution, and the plan's H13 row cites mb-kp6c instead. Exp-024 (H65-H67) cut per-entry construction but did not batch emission.
