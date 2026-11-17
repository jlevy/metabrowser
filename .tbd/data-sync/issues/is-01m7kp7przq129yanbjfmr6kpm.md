---
type: is
id: is-01m7kp7przq129yanbjfmr6kpm
title: refresh() returns before the host relay publishes the receipt's version (R27)
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
hold: null
hold_until: null
created_at: 2026-11-17T02:44:03.487Z
updated_at: 2026-11-17T17:17:39.204Z
started_at: 2026-11-17T08:09:56.141Z
---
A route read right after refresh can see an older host version; the rollup validator test fails with a multi-commit refresh. Make refresh read-your-writes at the host. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R27.

## Notes

Implemented in layer 3a, jlevy/metabrowser#518 (claude/cool-edison-avg57h-3a-host-consistency).
