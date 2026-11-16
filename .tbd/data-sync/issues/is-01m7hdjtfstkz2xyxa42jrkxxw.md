---
type: is
id: is-01m7hdjtfstkz2xyxa42jrkxxw
title: "PR #461 A4: state in REVIEW_STATES walks the prototype chain"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjhzg676034x3900gjvgd
hold: null
hold_until: null
created_at: 2026-11-16T05:34:21.688Z
updated_at: 2026-11-16T06:45:47.633Z
started_at: 2026-11-16T05:34:31.119Z
closed_at: 2026-11-16T06:45:47.633Z
close_reason: "Fixed in 2bb1236 (PR #461 A4): Object.hasOwn; constructor-state probe throws with in. Disposition: https://github.com/jlevy/metabrowser/pull/461#issuecomment-6909470016"
resolution: null
duplicate_of: null
---
Low. pull-page.js:548. Use Object.hasOwn(REVIEW_STATES, state). PR #461, review A: https://github.com/jlevy/metabrowser/pull/461#pullrequestreview-5915431885
