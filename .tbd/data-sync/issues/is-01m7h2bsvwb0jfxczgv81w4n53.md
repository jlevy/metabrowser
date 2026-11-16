---
type: is
id: is-01m7h2bsvwb0jfxczgv81w4n53
title: "PR #442 C4: content positioned out of a block collapsed to height 0 is never found, at any size"
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
created_at: 2026-11-16T02:18:17.339Z
updated_at: 2026-11-16T02:28:57.749Z
started_at: 2026-11-16T02:28:57.075Z
closed_at: 2026-11-16T02:28:57.749Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding C4 of review C on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914165678

References: explorations/performance-loop/transitions-recorder.mjs:478, :239-264; README.md:1290-1293
