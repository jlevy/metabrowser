---
type: is
id: is-01m7hdz9szb8nq69wdm5ny153x
title: "PR #464 A5: a waiting commit reveal can scroll the Files tree"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:10.590Z
updated_at: 2026-11-16T05:41:18.593Z
started_at: 2026-11-16T05:41:18.592Z
---
Low. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). git-panel.js:3379-3389, 3359-3363, 2216-2227: cancelPending does not clear waitingReveal; revealWaitingCommit checks only selectedId.
