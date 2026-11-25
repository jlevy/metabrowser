---
type: is
id: is-01m8904xcs87fd4pv93m2sfyg7
title: "PR #829 A4: the drawn comparison is not kept when the stack moves"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m8904gng5mvmjcwexd5z2vqe
hold: null
hold_until: null
created_at: 2026-11-25T09:21:20.791Z
updated_at: 2026-11-25T09:21:35.333Z
started_at: 2026-11-25T09:21:35.330Z
---
Medium. stack-page.js:641-651 disposes the drawn body while pending; sidekick.py:1021-1030 and pull_snapshot.py:264-278 serve only the current pair. Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
