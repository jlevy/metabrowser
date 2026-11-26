---
type: is
id: is-01m8bcaza30awvzeav7agsqwxs
title: "Changes tab: content shifts 43 px when a Markdown layer lands after the first-screen hold"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T07:32:51.138Z
updated_at: 2026-11-26T08:20:29.693Z
started_at: 2026-11-26T08:20:29.692Z
---
Review A of #872, A2: pull-page.js:149 shows the diff after CHANGES_FIRST_SCREEN_MS whether or not a rendered Markdown layer is in; when it lands, its card grows (75 to 118 px in the stand-in) and everything below moves, so a reader's press can miss. Hold its height or reserve room so nothing moves.
