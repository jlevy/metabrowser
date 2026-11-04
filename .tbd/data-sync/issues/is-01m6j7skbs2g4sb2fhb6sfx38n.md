---
type: is
id: is-01m6j7skbs2g4sb2fhb6sfx38n
title: Keep branch-copy icons legible on filled trunk chips during keyboard focus
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
hold: null
hold_until: null
created_at: 2026-11-04T02:56:44.920Z
updated_at: 2026-11-04T03:03:55.446Z
started_at: 2026-11-04T03:03:55.153Z
---
Independent actual Tab/focus-visible test finds inverse trunk-chip copy foreground over shared icon-button neutral focus background: contrast1.011:1light and1.255:1dark from computed colors. Fix branch-copy interactive background/foreground as shared tokens without changing other icon controls; recheck real focused control in both themes, plus normal/hover as supported. Evidence design-tokens-14433032/copy-clip-and-trunk-result.json. Preserve clippingfix and cleanup.

## Notes

Fixed only branch-copy interactive ink: SDK375dd6a2c31359d2e6e80031ff7cb5c140cab6cc561969856bba0e647b99af0d sets a live semantic --git-ref-copy-ink resting role; global CSS26359edba6a3f01fd00c5a09e118dbd731458fa1858f0e4f5b171601dc27b6c7 uses text ink on the existing neutral hover/focus plate. Generic icon buttons unchanged. Focused actual helper controls and new design assertion pass; full68 focused tests/13 DOM cases/both browser type gates pass. Original real-Tab/light-dark probe recheck pending independent reviewer; keep open until final installed acceptance.
