---
type: is
id: is-01m7h2brfrb59679aar2c8ppds
title: "PR #442 C1: pairs beyond the tolerance are counted only in the median's direction, so two worse pairs can exit 0"
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
created_at: 2026-11-16T02:18:15.927Z
updated_at: 2026-11-16T02:28:57.722Z
started_at: 2026-11-16T02:28:57.052Z
closed_at: 2026-11-16T02:28:57.722Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Medium finding C1 of review C on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914165678

References: explorations/performance-loop/transitions-stats.mjs:441-447, :449-452, :468-489, :456-467, :410-416, :783-788; README.md:554-556, :1156, :1175-1177
