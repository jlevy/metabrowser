---
type: is
id: is-01m0nyyjxbp58dwgp0g5msfafs
title: "H43: viewport-first walk ordering so the visible subtree settles first"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:57.899Z
updated_at: 2026-11-14T18:47:12.241Z
---
Load-time hypothesis H43 (plan-2026-08-21-load-time-performance.md, Hypotheses). Walking the viewport's subtree first makes the visible tree correct long before the scan ends. Metric: time until the on-screen subtree stops changing. Composes with H33 (mb-6yh2), which orders tracked files before ignored ones.
