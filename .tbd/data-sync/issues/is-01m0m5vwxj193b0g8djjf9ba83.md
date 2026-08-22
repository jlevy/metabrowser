---
type: is
id: is-01m0m5vwxj193b0g8djjf9ba83
title: Batch the walker pipeline per directory, not per entry (H22)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T07:27:21.009Z
updated_at: 2026-08-22T07:27:21.009Z
---
43us/file is mostly per-entry Python by construction: one async-generator yield per entry (300k loop iterations/scan), per-entry _store_walker_entry on the serving event loop, O(depth) ancestor-aggregate update per FILE while finalize already computes per-directory aggregates (double bookkeeping), one to_thread hop per directory. Batch end-to-end: yield lists per directory, store lists, one ancestor update per directory. Run mb-nbc6's profile first so the before is attributed. Predicted: walk elapsed down 2x+, event-loop availability during scan up.
