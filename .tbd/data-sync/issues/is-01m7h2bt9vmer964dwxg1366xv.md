---
type: is
id: is-01m7h2bt9vmer964dwxg1366xv
title: "PR #442 C5: the hit-test grid is cut at 60 points before its rows reach the bottom of the area"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h2ampfg7a32dp0rx5hpwra
hold: null
hold_until: null
created_at: 2026-11-16T02:18:17.786Z
updated_at: 2026-11-16T02:28:57.758Z
started_at: 2026-11-16T02:28:57.085Z
closed_at: 2026-11-16T02:28:57.758Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding C5 of review C on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914165678

References: explorations/performance-loop/transitions-recorder.mjs:545-556, :576-582, :585-587; README.md:867-871
