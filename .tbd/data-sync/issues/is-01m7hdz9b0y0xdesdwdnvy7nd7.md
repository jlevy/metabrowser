---
type: is
id: is-01m7hdz9b0y0xdesdwdnvy7nd7
title: "PR #464 A4: the Commits reveal's decisions have no browserless session"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:10.111Z
updated_at: 2026-11-16T05:41:17.789Z
started_at: 2026-11-16T05:41:17.786Z
---
Medium. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). git-panel.js:3351-3401 revealWaitingCommit/loadedOrdinalOf; arch-views-models-routes.md:1005 navigation.reveal-item-paint claims every decision runs browserlessly. Add steps to tests/dom/git-commit-history-session.js.
