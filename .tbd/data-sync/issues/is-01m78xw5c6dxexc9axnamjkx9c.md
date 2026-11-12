---
type: is
id: is-01m78xw5c6dxexc9axnamjkx9c
title: "PR #383 A1: malformed-input throw holds only after the facade loads"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
hold: null
hold_until: null
created_at: 2026-11-12T22:25:55.077Z
updated_at: 2026-11-12T22:47:37.884Z
started_at: 2026-11-12T22:46:42.931Z
closed_at: 2026-11-12T22:47:37.882Z
close_reason: "fixed in 88ca5216: docs/plugins.md's malformed-input bullet and the CHANGELOG entry now say an attachment made before the keyboard support loads is checked when it loads and a malformed one is logged with console.error under the shortcuts.attach: prefix; Testing Checklist item 5 asks for no warning or error. The behavior is pinned by the plugin shortcuts session step 'the facade loads and takes the queue; the malformed one is logged'."
resolution: null
duplicate_of: null
---
Low. PR #383, review A (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882935821). docs/plugins.md:691, CHANGELOG.md:21, types.d.ts:1232 say malformed input always throws; an attachment queued before plugin-shortcuts.js loads (plugin-sdk.js:157-174) is only logged with console.error when the facade drains the queue (plugin-shortcuts.js:544-556). Fix: document that pre-load malformed input is logged with the same shortcuts.attach: prefix; widen Testing Checklist item 5 (plugins.md:947); same clause in CHANGELOG.
