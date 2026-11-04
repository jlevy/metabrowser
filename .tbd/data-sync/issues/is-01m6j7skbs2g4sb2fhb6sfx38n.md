---
type: is
id: is-01m6j7skbs2g4sb2fhb6sfx38n
title: Keep branch-copy icons legible on filled trunk chips during keyboard focus
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
created_at: 2026-11-04T02:56:44.920Z
updated_at: 2026-11-04T02:56:44.920Z
---
Independent actual Tab/focus-visible test finds inverse trunk-chip copy foreground over shared icon-button neutral focus background: contrast1.011:1light and1.255:1dark from computed colors. Fix branch-copy interactive background/foreground as shared tokens without changing other icon controls; recheck real focused control in both themes, plus normal/hover as supported. Evidence design-tokens-14433032/copy-clip-and-trunk-result.json. Preserve clippingfix and cleanup.
