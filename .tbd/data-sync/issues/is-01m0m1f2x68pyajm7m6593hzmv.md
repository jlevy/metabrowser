---
type: is
id: is-01m0m1f2x68pyajm7m6593hzmv
title: "H18: batch walker entry emission per directory instead of per file"
kind: task
status: open
priority: 1
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01m0m5vwxj193b0g8djjf9ba83
created_at: 2026-08-22T06:10:26.853Z
updated_at: 2026-08-22T07:27:21.009Z
---
The walk costs ~43 us/file (300k files in 12,871 ms warm). Structure: one to_thread per directory is cheap (972 hops), but every entry is yielded one at a time through an async generator onto the event loop, and each write moves the rollup revision. Attribute first (profile one walk), then batch emission per directory as its own experiment. Metric: 'inventory walker complete: elapsed=' in the server log at 300k warm. Also slows the revision churn H8 depends on. Plan Backlog H18.
