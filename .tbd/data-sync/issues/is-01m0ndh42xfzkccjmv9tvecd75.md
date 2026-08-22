---
type: is
id: is-01m0ndh42xfzkccjmv9tvecd75
title: Build the nav tree progressively from the SSE stream (H28)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T19:00:30.941Z
updated_at: 2026-08-22T19:00:30.941Z
---
The tree is delivered as snapshots the client re-fetches on a poll and re-renders wholesale, while the walker already publishes fs.change ops on the open SSE stream at root-depth-2 scope — exactly the rows the nav renders. Insert rows as discovered; drop the poll-triggered refetch loop. Absorbs H11 (patch-not-replace) and H24 (two progress channels). Metrics: renderTreeNodes:root span count during scan -> bounded per-batch inserts; snapshot refetches during scan -> 0. Large; do after H27 proves the decoupling.
