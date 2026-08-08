---
type: is
id: is-01kzffvgay2h41pb2199wx1yjf
title: "fdu phase 1: index concurrency — single-writer RwLock, escalate only on measured contention"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T01:29:59.902Z
updated_at: 2026-08-08T07:32:08.791Z
closed_at: 2026-08-08T07:32:08.790Z
close_reason: null
---
Resolved design decision (research doc, Goal Coverage and Deviations): the index uses a single-writer model with parking_lot::RwLock for phase 1 — writes are short (O(depth) delta applies), reads are cheap (rollups are pre-computed state, not queries-that-walk), and the delta contract remains the only mutation path so upgrading to epoch/arc-swap snapshots later is contained. Phase-1 task: implement, and measure read contention under watch churn before considering anything fancier. Retrofitting concurrency later would be a rewrite, hence settled now.
