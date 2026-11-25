---
type: is
id: is-01m85azcjx7bnsywxddhmbw2w6
title: "Treemap: break equal-value ties by type, then name"
kind: feature
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T23:13:36.341Z
updated_at: 2026-11-25T02:16:20.156Z
started_at: 2026-11-23T23:14:02.704Z
closed_at: 2026-11-24T00:47:57.626Z
close_reason: Merged in the treemap stack (#722–#769) into main at 7c42f45
resolution: null
duplicate_of: null
---
Within one folder, children of equal value (every file by Files; same-sized files by Bytes) sort by extension (a folder's dominant one), then name case-folded, then path, so cells of one color sit together. Value stays the primary order, so no cell's size or the map's shape changes.
