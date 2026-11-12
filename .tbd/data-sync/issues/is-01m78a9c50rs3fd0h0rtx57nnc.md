---
type: is
id: is-01m78a9c50rs3fd0h0rtx57nnc
title: "PR #374 A5: Quick Search hint row rebuilds on every registry publication"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78a8v8t7c3wp1sv22v0gqa8
hold: null
hold_until: null
created_at: 2026-11-12T16:43:36.476Z
updated_at: 2026-11-12T16:43:45.122Z
started_at: 2026-11-12T16:43:45.121Z
---
Low (suggestion). Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. src/metabrowser/static/search-palette.js:841 subscribes renderShortcutHints to every registry event; each event rebuilds the closed palette's hint row (snapshot('quick-file') plus new spans). Fix: rebuild only when the event's kinds include registration or scope, the strip's HINT_EVENT_KINDS rule in keyboard-help.js; pin it with a counter like keyboard-help-behavior.js.
