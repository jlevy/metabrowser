---
type: is
id: is-01m7h2bf5s6jhqj81y5bz8fwxd
title: "PR #442 A4: accountFrames lets a frame read before the input into the window when it follows a missed frame stamped after the input"
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
created_at: 2026-11-16T02:18:06.392Z
updated_at: 2026-11-16T02:28:57.574Z
started_at: 2026-11-16T02:28:56.918Z
closed_at: 2026-11-16T02:28:57.574Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding A4 of review A on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5913924421

References: explorations/performance-loop/transitions-recorder.mjs:1622-1636, :1763, :1592-1601
