---
type: is
id: is-01m78xw5c6dxexc9axnamjkx9c
title: "PR #383 A1: malformed-input throw holds only after the facade loads"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
created_at: 2026-11-12T22:25:55.077Z
updated_at: 2026-11-12T22:25:55.077Z
---
Low. PR #383, review A (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882935821). docs/plugins.md:691, CHANGELOG.md:21, types.d.ts:1232 say malformed input always throws; an attachment queued before plugin-shortcuts.js loads (plugin-sdk.js:157-174) is only logged with console.error when the facade drains the queue (plugin-shortcuts.js:544-556). Fix: document that pre-load malformed input is logged with the same shortcuts.attach: prefix; widen Testing Checklist item 5 (plugins.md:947); same clause in CHANGELOG.
