---
type: is
id: is-01m76qxj4apwmjny1nb5p5n5s0
title: "Source view: split appended text into nodes of at most 64 KiB"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T02:03:20.585Z
updated_at: 2026-11-12T05:42:32.826Z
started_at: 2026-11-12T05:42:32.825Z
---
From the WebKit gate (mb-gvtw, docs/large-content-rendering.md 'Measured in WebKit'): the source view's Load more lays out 4.5-5.8x slower in WebKit than Chrome; the extra time is style and layout of one text node per chunk. A bare-page experiment with text nodes of at most 65,536 characters measured 0.53-0.56x Chrome. Change source-append.js to split appended text, measure both engines back to back (Chrome must not regress), and rerun the gate's source cases. Core metab change: its own PR to main.
