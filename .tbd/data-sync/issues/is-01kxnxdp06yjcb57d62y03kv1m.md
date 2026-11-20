---
type: is
id: is-01kxnxdp06yjcb57d62y03kv1m
title: Include directories in Recent results
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-07-16T16:51:09.957Z
updated_at: 2026-11-20T19:15:57.155Z
extensions: {}
---
Remaining work from the scanning-state plan. Scan progress already ships: /api/index/progress reports status, indexed_files, max_files, truncated, complete, and active, and pending directory aggregates arrive as null until finalized. Recent still returns file leaves only (src/metabrowser/recent.py), with ancestor directories used only for presentation. Include directories as Recent items with stable kind, path, and modification time; keep ordering deterministic while new items arrive; and show incomplete state without layout jumps.
