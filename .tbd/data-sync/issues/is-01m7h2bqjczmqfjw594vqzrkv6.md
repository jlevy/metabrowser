---
type: is
id: is-01m7h2bqjczmqfjw594vqzrkv6
title: "PR #442 B9: on a source view the search's hit is the line-number gutter, not the code"
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
created_at: 2026-11-16T02:18:14.987Z
updated_at: 2026-11-16T02:28:57.708Z
started_at: 2026-11-16T02:28:57.036Z
closed_at: 2026-11-16T02:28:57.708Z
close_reason: "Fixed in 5f1639a82 on PR #442; disposition replies https://github.com/jlevy/metabrowser/pull/442#issuecomment-6905624598 (A), #issuecomment-6905624937 (B), #issuecomment-6905625167 (C)"
resolution: null
duplicate_of: null
---
Low finding B9 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: src/metabrowser/static/plugin-sdk-views.js:1591, :319-326; explorations/performance-loop/transitions-recorder.mjs:480
