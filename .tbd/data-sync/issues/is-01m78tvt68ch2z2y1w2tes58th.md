---
type: is
id: is-01m78tvt68ch2z2y1w2tes58th
title: "PR #379 D2: commitViewTabs() re-registers unchanged letters on every navigation, in a second publication"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:17.884Z
updated_at: 2026-11-12T22:38:59.028Z
started_at: 2026-11-12T21:33:43.436Z
closed_at: 2026-11-12T22:38:59.027Z
close_reason: "Fixed in a28083ed: commitViewTabs(nextBar) diffs held letters; same-kind navigation publishes one batch(target), no registration, no strip rebuild. Reply: https://github.com/jlevy/metabrowser/pull/379#issuecomment-6837880767"
resolution: null
duplicate_of: null
---
Low. PR #379, review D (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899935). static/shell-keymap.js:435-445 releases every outgoing letter before syncViewTabs(), so the retarget path (:391-393) never runs on a navigation; finishRetainedPullPage() then publishes a second batch through syncPane() (app.js:3812). README.md -> README.md publishes batch(target,registration) and batch(target) and rebuilds the resting strip.
