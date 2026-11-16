---
type: is
id: is-01m7h2beqhyk79se7dptnhr52s
title: "PR #442 A3: the hit test's budget is wall time, so whether on-screen content is found depends on load"
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
created_at: 2026-11-16T02:18:05.936Z
updated_at: 2026-11-16T02:28:57.567Z
started_at: 2026-11-16T02:28:56.907Z
closed_at: 2026-11-16T02:28:57.567Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Medium finding A3 of review A on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5913924421

References: explorations/performance-loop/transitions-recorder.mjs:429-436, :571-591; transitions-stats.mjs:718-724
