---
type: is
id: is-01m76qxj4apwmjny1nb5p5n5s0
title: "Source view: split appended text into nodes of at most 64 KiB"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T02:03:20.585Z
updated_at: 2026-11-12T08:01:11.851Z
started_at: 2026-11-12T05:42:32.825Z
closed_at: 2026-11-12T08:01:11.849Z
close_reason: "Done in PR #367 (head d047a2ce, unmerged): appended source text is split into nodes of at most 64 KiB at grapheme boundaries; WebKit Load more 0.22-0.39x its old time, Chrome unchanged; reviews A-C, the last approving; CI green. Remaining gate failure on the first Load more is mb-dl7d."
resolution: null
duplicate_of: null
---
From the WebKit gate (mb-gvtw, docs/large-content-rendering.md 'Measured in WebKit'): the source view's Load more lays out 4.5-5.8x slower in WebKit than Chrome; the extra time is style and layout of one text node per chunk. A bare-page experiment with text nodes of at most 65,536 characters measured 0.53-0.56x Chrome. Change source-append.js to split appended text, measure both engines back to back (Chrome must not regress), and rerun the gate's source cases. Core metab change: its own PR to main.
