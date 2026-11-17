---
type: is
id: is-01m7kp7przq129yanbjfmr6kpm
title: refresh() returns before the host relay publishes the receipt's version (R27)
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:03.487Z
updated_at: 2026-11-17T02:44:03.487Z
---
A route read right after refresh can see an older host version; the rollup validator test fails with a multi-commit refresh. Make refresh read-your-writes at the host. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R27.
