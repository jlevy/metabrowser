---
type: is
id: is-01m78xw76mz3mq2g7cxvmz7p10
title: "PR #383 B2: view-composition safety net misses self-removing dispose and late renders"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
created_at: 2026-11-12T22:25:56.947Z
updated_at: 2026-11-12T22:25:56.947Z
---
Low. PR #383, review B (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882937219). view-composition.js:162-176, 183-186 runs releaseShortcutsWithin(container) after the view's dispose; plugin-shortcuts.js:530-536 releases only attachments still inside container, so a dispose that removes its own root escapes, and a render resolving after cancellation attaches after the net with no net after its late dispose. Fix: collect/release before and after the view's dispose, run the net after the late dispose, session step with dispose() { root.remove(); }.
