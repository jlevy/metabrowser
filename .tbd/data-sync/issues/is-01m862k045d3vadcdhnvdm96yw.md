---
type: is
id: is-01m862k045d3vadcdhnvdm96yw
title: Place the Files branch chip beside a separate revision chooser
kind: feature
status: closed
priority: 2
version: 6
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T06:06:16.196Z
updated_at: 2026-11-24T07:13:37.355Z
started_at: 2026-11-24T06:37:09.480Z
closed_at: 2026-11-24T07:13:37.354Z
close_reason: "Merged #783 at c5ebd6a3c after exact independent review 6034754728, passing PR CI 45341711474 and full verify 45341734830. Post-merge main CI 45345226133 passed. Rebuilt and restarted the active development app and verified all four restored windows and their servers on the exact runtime."
resolution: null
duplicate_of: null
---
Put the selected ref on its own row immediately below Files. Keep its chip clickable for the selected ref actions, and give the chevron next to it the separate job of choosing another branch or tag. Remove the duplicate branch action from folder details and preserve working tree, tags, pins and PR refs.

## Notes

Combined PR 783. Original exact review 6034662701 and 182 focused checks passed. Initial CI 45340552689 found stale shell, modified-key, hook and focus contracts plus a checkout startup import. Fixed the contracts and moved unchanged ref-name validation out of cache acquisition. Scoped regressions and parity passed. Final head 4cdcf856f77750bf3e28531ad8aa1221c463f691 includes merged PR 782. Current ordinary CI 45341711474 and full verify 45341734830.
