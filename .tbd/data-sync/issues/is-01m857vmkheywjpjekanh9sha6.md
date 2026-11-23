---
type: is
id: is-01m857vmkheywjpjekanh9sha6
title: "Treemap icons: one rule for every cell size, scaled down, painted on the canvas"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T22:19:07.756Z
updated_at: 2026-11-23T22:19:20.931Z
started_at: 2026-11-23T22:19:20.925Z
---
Same-sized cells drew differently: a file wide enough for its name but not name plus icon drew its name with no icon, beside slightly smaller neighbours that drew the icon alone. Fix: a file's name always follows its icon (room judged at the smallest label), a cell without room for both shows the icon alone scaled from 16 px down to ICON_MIN_PX 8, icons painted on the canvas (2,400 icon elements took the map to 17k elements and a measure switch from ~0.4 s to 1.5 s), files only (folders have no icon, as in the nav).
