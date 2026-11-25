---
type: is
id: is-01m832rs4ryhw09n31ah5haztf
title: "Rollup: spend the node budget on the heaviest folders first"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/722
    at: 2026-11-23T02:52:12.334Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T02:11:42.351Z
updated_at: 2026-11-25T02:16:20.156Z
started_at: 2026-11-23T02:12:04.870Z
closed_at: 2026-11-25T02:10:23.537Z
close_reason: "Landed in #722 (treemap stack layer 1), merged to main."
resolution: null
duplicate_of: null
---
/api/rollup emitted levels breadth-first, so a wide shallow tree (node_modules) spent ROLLUP_MAX_NODES on tiny entries a few levels down and large folders elsewhere came back unexpanded. Expand the heaviest pending directory first (largest share of the root across files/bytes, all/unignored), break ties by path, and raise ROLLUP_MAX_DEPTH to 12. Stack layer 1.
