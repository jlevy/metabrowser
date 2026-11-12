---
type: is
id: is-01m78xw7ztj7m9x8xmkdd87456
title: "PR #383 B3: eager queue keeps detached and aborted attachments until the facade loads"
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
created_at: 2026-11-12T22:25:57.753Z
updated_at: 2026-11-12T22:46:42.563Z
started_at: 2026-11-12T22:39:56.625Z
closed_at: 2026-11-12T22:46:42.562Z
close_reason: "fixed in 2f5970d2 as the review's Fix suggested: the eager queue is a Set; a queued detach() and view composition's pre-load net delete the entry, element and all (0 eager bytes, plugin-sdk.js stays 17,314). Confirmed by tests/dom/plugin-shortcuts-session.js pinned in cli-ui-plugin-shortcuts.tryscript.md: queued 4 -> 3, queuedAfterDispose 1 -> 0. The abort-before-load half is not fixed (24 eager bytes, 6 over budget with B1) and is tracked as mb-1cev."
resolution: null
duplicate_of: null
---
Low. PR #383, review B (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882937219). plugin-sdk.js:157-174: queued detach() only nulls options and leaves the entry and element in _shortcutQueue; an aborted signal is not observed; view-composition.js:36-42 pre-load net does the same. Entries leave only when plugin-shortcuts.js:546-556 drains. Fix: remove the entry on detach/abort; keep the eager code minimal and report the eager byte delta.
