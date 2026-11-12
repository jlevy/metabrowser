---
type: is
id: is-01m78xw7ztj7m9x8xmkdd87456
title: "PR #383 B3: eager queue keeps detached and aborted attachments until the facade loads"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
hold: null
hold_until: null
created_at: 2026-11-12T22:25:57.753Z
updated_at: 2026-11-12T22:39:56.626Z
started_at: 2026-11-12T22:39:56.625Z
---
Low. PR #383, review B (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882937219). plugin-sdk.js:157-174: queued detach() only nulls options and leaves the entry and element in _shortcutQueue; an aborted signal is not observed; view-composition.js:36-42 pre-load net does the same. Entries leave only when plugin-shortcuts.js:546-556 drains. Fix: remove the entry on detach/abort; keep the eager code minimal and report the eager byte delta.
