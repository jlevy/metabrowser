---
type: is
id: is-01m0fvhdwh9f4a283repc7x8wr
title: "Git graph: tighter lanes, smaller dots"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T15:09:54.448Z
updated_at: 2026-08-20T15:28:42.687Z
closed_at: 2026-08-20T15:28:42.686Z
close_reason: "Landed in 4554983: 9px lane pitch, 3px dots, midline decoupled from pitch so arcs and dots stay centered; graph behavior suite green"
---
The commit graph spends too much width: lane spacing too wide and dots too large, pushing subjects right. Reduce dot radius and lane pitch in git_graph.js (and any matching CSS), keeping hit targets and label legibility; verify against this repo's own multi-lane history.
