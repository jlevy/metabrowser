---
type: is
id: is-01m7h2bq3thbvd0mjnqa5c9zwx
title: "PR #442 B8: read costs are printed to 0.01 ms, but the page clock resolves 0.1 ms"
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
created_at: 2026-11-16T02:18:14.521Z
updated_at: 2026-11-16T02:28:57.698Z
started_at: 2026-11-16T02:28:57.028Z
closed_at: 2026-11-16T02:28:57.698Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding B8 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: explorations/performance-loop/transitions-recorder.mjs:968, :1724, :1729
