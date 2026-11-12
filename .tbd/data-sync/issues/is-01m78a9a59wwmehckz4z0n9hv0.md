---
type: is
id: is-01m78a9a59wwmehckz4z0n9hv0
title: "PR #374 A2: Quick Search session claims Shift+Enter is checked but does not check it"
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
created_at: 2026-11-12T16:43:34.440Z
updated_at: 2026-11-12T16:43:43.675Z
started_at: 2026-11-12T16:43:43.674Z
---
Low. Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. tests/dom/search-palette-behavior.js:694-697 says Shift+Enter and Shift+Escape still act (checked below); only Shift+Escape is checked (lines 837-845). Fix: add a Shift+Enter case beside the plain-Enter acceptance case at line 731 asserting the result opens and the palette closes, and correct the comment.
