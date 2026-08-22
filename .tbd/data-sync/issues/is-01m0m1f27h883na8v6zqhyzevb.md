---
type: is
id: is-01m0m1f27h883na8v6zqhyzevb
title: "H8: root /api/tree pays a full nav-tally pass on every request during a scan"
kind: task
status: open
priority: 0
version: 1
labels: []
dependencies: []
created_at: 2026-08-22T06:10:26.160Z
updated_at: 2026-08-22T06:10:26.160Z
---
Measured at 300k build_corpus files: /api/tree costs 1,567 ms while the walk runs and 15 ms settled, for the same 7,537-byte gz answer; ?depth=1 (987 bytes) costs the same 1,563 ms; a subtree read stays ~10 ms throughout. Mechanism: navigation_tallies memoizes on the index revision (inventory.py), the walker moves that revision with every write, so during a scan the memo never hits and every root request redoes the O(index) pass (~486 ms/100k per its own comment) plus an entries() snapshot copy. load_tree_ms is 837-1,490 ms of a 1,017-1,660 ms first row, so this is ~85% of time-to-first-row in the scanning regime. Candidate fix: serve slightly stale tallies during a scan (recompute at most every N ms or per M files indexed). Metric: tree_reprobe_ms with index_status_at_probe=scanning, floor 15 ms; explorations/probe.js records all three. Plan: docs/project/specs/active/plan-2026-08-21-load-time-performance.md Backlog H8.
