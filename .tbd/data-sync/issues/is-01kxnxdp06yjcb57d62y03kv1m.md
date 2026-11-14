---
type: is
id: is-01kxnxdp06yjcb57d62y03kv1m
title: Include directories in Recent results
kind: feature
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md
labels: []
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:51:09.957Z
updated_at: 2026-11-14T18:44:39.503Z
extensions:
  linear:
    id: 036f4bb2-e240-412d-a8c6-fa6547a2c03c
    linked_at: 2026-08-16T08:06:10.134Z
---
Remaining work from the scanning-state plan. Scan progress already ships: /api/index/progress reports status, indexed_files, max_files, truncated, complete, and active, and pending directory aggregates arrive as null until finalized. Recent still returns file leaves only (src/metabrowser/recent.py), with ancestor directories used only for presentation. Include directories as Recent items with stable kind, path, and modification time; keep ordering deterministic while new items arrive; and show incomplete state without layout jumps.
