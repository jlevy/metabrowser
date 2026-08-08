---
type: is
id: is-01kzffvfd2ha49pzr8t6b1rcdx
title: "fdu phase 1: replace dua-core scaffolding with getdents64/statx walk layer"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-08T01:29:58.937Z
updated_at: 2026-08-08T01:29:58.937Z
---
Goal 1 exit criterion from research-2026-08-06-file-rollup-engine.md (Goal Coverage and Deviations): bootstrapping traversal from dua-core is acceptable scaffolding, but its stat path is std-based. Goal 1 (fastest walker) is not met or claimed until the raw getdents64 + dirfd-relative statx layer (dut/bfs techniques) replaces it and the benchmark gate vs dut and gdu passes.
