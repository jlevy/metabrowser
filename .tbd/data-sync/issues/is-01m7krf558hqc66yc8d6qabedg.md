---
type: is
id: is-01m7krf558hqc66yc8d6qabedg
title: Publish a refresh's provider batches as one host change (D8, R2, R27)
kind: task
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
created_at: 2026-11-17T03:23:04.744Z
updated_at: 2026-11-17T17:17:39.597Z
started_at: 2026-11-17T08:09:56.480Z
---
fdu's refresh is several commits, the first of which only changes state (fresh to reconciling); the host emits it as its own capability.update before the data change, so a touch test failed 20 of 32 runs with fdu and 0 of 32 with Python. Fold every provider batch up to the refresh receipt's version into one host change, alongside read-your-writes refresh (R27); outside a refresh, tests assert convergence rather than envelope counts. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, D8.

## Notes

Implemented in layer 3a, jlevy/metabrowser#518 (claude/cool-edison-avg57h-3a-host-consistency).
