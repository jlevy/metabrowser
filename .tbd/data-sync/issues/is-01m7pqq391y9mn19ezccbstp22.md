---
type: is
id: is-01m7pqq391y9mn19ezccbstp22
title: "Projection-thread budget: in-budget projections take 1.1-1.3 s in the server thread (#527 E6)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m75fzpspek15x7d5dqhnc2yw
created_at: 2026-11-18T07:07:39.680Z
updated_at: 2026-11-18T07:07:39.680Z
---
From PR #527 review E6: 250-256 [ then % to 48 KiB takes 1,073-1,339 ms in the server thread, against 222-268 ms recorded beside the budget. Re-measure and set the projection budget, or always project in the child.
