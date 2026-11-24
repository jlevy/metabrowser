---
type: is
id: is-01m862k0n2b2tp4rmq7kpt28a1
title: Use an info icon for the sidebar folder details menu
kind: task
status: in_progress
priority: 2
version: 5
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T06:06:16.737Z
updated_at: 2026-11-24T06:37:38.587Z
started_at: 2026-11-24T06:37:09.489Z
---
Replace the root folder details trigger chevron with a minimal shared Info icon. Keep Home on the folder name, common menu dismissal and labeled link actions. Document how the Info button, ref chip and ref chooser differ.

## Notes

Combined PR 783. Original exact review 6034662701 and 182 focused checks passed. Initial CI 45340552689 found stale shell, modified-key, hook and focus contracts plus a checkout startup import. Fixed the contracts and moved unchanged ref-name validation out of cache acquisition. Scoped regressions and parity passed. Final head 4cdcf856f77750bf3e28531ad8aa1221c463f691 includes merged PR 782. Current ordinary CI 45341711474 and full verify 45341734830.
