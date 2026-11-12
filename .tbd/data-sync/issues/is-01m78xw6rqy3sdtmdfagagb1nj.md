---
type: is
id: is-01m78xw6rqy3sdtmdfagagb1nj
title: "PR #383 B1: Git commit view keeps L attached after another owner takes the pane"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xvnbykdp66qwvmwnrfzdp
hold: null
hold_until: null
created_at: 2026-11-12T22:25:56.502Z
updated_at: 2026-11-12T22:26:03.088Z
started_at: 2026-11-12T22:26:03.087Z
---
Medium. PR #383, review B (https://github.com/jlevy/metabrowser/pull/383#pullrequestreview-5882937219). app.js:3646-3649 claimPreview calls MetabrowserGitPanel.cancelPending(), git-panel.js:1747-1754 calls the commit diff's cancelPending() (diff-view.js:2931-2935), which leaves the diff and its L attachment (diff-view.js:2954) mounted; disposal happens only at git-panel.js:2186-2188, 2043, 2545-2551. Help lists plugin commands with any attachment (plugin-shortcuts.js:378, keyboard-help.js:392), so L Toggle diff layout stays in Help on later pages. Fix: dispose the relinquished commit diff on takeover; re-showing the same commit must remount.
