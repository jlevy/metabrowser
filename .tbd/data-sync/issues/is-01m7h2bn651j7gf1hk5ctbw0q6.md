---
type: is
id: is-01m7h2bn651j7gf1hk5ctbw0q6
title: "PR #442 B4: frames read while milestones are awaited have their read cost recorded in the page and never collected"
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
created_at: 2026-11-16T02:18:12.549Z
updated_at: 2026-11-16T02:28:57.668Z
started_at: 2026-11-16T02:28:56.995Z
closed_at: 2026-11-16T02:28:57.668Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Medium finding B4 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: explorations/performance-loop/transitions-recorder.mjs:2223-2248, :2326-2349, :1724; README.md:983-985; transitions-journeys.mjs:269-278
