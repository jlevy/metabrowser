---
type: is
id: is-01m832rs4ryhw09n31ah5haztf
title: "Rollup: spend the node budget on the heaviest folders first"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T02:11:42.351Z
updated_at: 2026-11-23T02:12:04.872Z
started_at: 2026-11-23T02:12:04.870Z
---
/api/rollup emitted levels breadth-first, so a wide shallow tree (node_modules) spent ROLLUP_MAX_NODES on tiny entries a few levels down and large folders elsewhere came back unexpanded. Expand the heaviest pending directory first (largest share of the root across files/bytes, all/unignored), break ties by path, and raise ROLLUP_MAX_DEPTH to 12. Stack layer 1.
