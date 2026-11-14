---
type: is
id: is-01m0nyyhrqgc6sks99h538m4te
title: "H40: native parallel walker over ripgrep's ignore crate"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:56.727Z
updated_at: 2026-11-14T18:45:58.573Z
---
Load-time hypothesis H40 (plan-2026-08-21-load-time-performance.md, Hypotheses). A native parallel walker over ripgrep's ignore crate would cut the scan by an order of magnitude, because the walk is per-entry Python competing with itself under one GIL. Metric: walk_elapsed_ms on the real tree. Blocked on H39 (mb-8yqt). Overlaps mb-hej8, the fdu inventory provider, which plans native parallel traversal with full gitignore semantics; decide whether mb-hej8 answers this.
