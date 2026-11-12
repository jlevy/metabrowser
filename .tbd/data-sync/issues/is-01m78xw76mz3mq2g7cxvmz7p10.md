---
type: is
id: is-01m78xw76mz3mq2g7cxvmz7p10
title: "PR #383 B2: view-composition safety net misses self-removing dispose and late renders"
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
created_at: 2026-11-12T22:25:56.947Z
updated_at: 2026-11-12T22:39:56.227Z
started_at: 2026-11-12T22:37:06.042Z
closed_at: 2026-11-12T22:39:56.226Z
close_reason: "fixed in e85218f1: view-composition.js runs releaseShortcutsWithin(container) before the view's dispose, again after a render that resolves after cancellation, and before a failed render's error state; confirmed by three new steps in tests/dom/plugin-shortcuts-session.js pinned by cli-ui-plugin-shortcuts.tryscript.md (each listed its key as not live before the fix)"
resolution: null
duplicate_of: null
---
Low. PR #383, review B (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882937219). view-composition.js:162-176, 183-186 runs releaseShortcutsWithin(container) after the view's dispose; plugin-shortcuts.js:530-536 releases only attachments still inside container, so a dispose that removes its own root escapes, and a render resolving after cancellation attaches after the net with no net after its late dispose. Fix: collect/release before and after the view's dispose, run the net after the late dispose, session step with dispose() { root.remove(); }.
