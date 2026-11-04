---
type: is
id: is-01m6j7skbs2g4sb2fhb6sfx38n
title: Keep branch-copy icons legible on filled trunk chips during keyboard focus
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
hold: null
hold_until: null
created_at: 2026-11-04T02:56:44.920Z
updated_at: 2026-11-04T03:05:02.166Z
started_at: 2026-11-04T03:03:55.153Z
---
Independent actual Tab/focus-visible test finds inverse trunk-chip copy foreground over shared icon-button neutral focus background: contrast1.011:1light and1.255:1dark from computed colors. Fix branch-copy interactive background/foreground as shared tokens without changing other icon controls; recheck real focused control in both themes, plus normal/hover as supported. Evidence design-tokens-14433032/copy-clip-and-trunk-result.json. Preserve clippingfix and cleanup.

## Notes

Independent final v5 recheck CLEAN: actual Tab-focus contrast15.284:1light and10.284:1dark; all14 frontend hashes match v5,26 focused checks passed. Original failure contrast1.011/1.255 retained in independent raw evidence. Fix keeps live semantic resting ink and scopes text ink to branch-copy neutral hover/focus plate; generic controls unchanged. Raw hover-labelled samples had hover=false, so no actual browser hover claim. Final all-files-handoff.json records exact hashes; coordinator owns commit/fullgate/installed acceptance and closure.
