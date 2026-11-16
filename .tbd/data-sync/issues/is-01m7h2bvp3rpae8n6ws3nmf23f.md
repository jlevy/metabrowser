---
type: is
id: is-01m7h2bvp3rpae8n6ws3nmf23f
title: "PR #442 C8: a missed frame is placed by its begin time, so the input's own frame is dropped when its read is missed"
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
created_at: 2026-11-16T02:18:19.202Z
updated_at: 2026-11-16T02:28:57.797Z
started_at: 2026-11-16T02:28:57.108Z
closed_at: 2026-11-16T02:28:57.797Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding C8 of review C on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914165678

References: explorations/performance-loop/transitions-recorder.mjs:974-978, :1601; README.md:1282-1283
