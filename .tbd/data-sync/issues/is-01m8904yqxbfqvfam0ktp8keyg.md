---
type: is
id: is-01m8904yqxbfqvfam0ktp8keyg
title: "PR #829 A5: the stack page's body state machine is untested"
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
created_at: 2026-11-25T09:21:22.171Z
updated_at: 2026-11-25T09:21:36.086Z
started_at: 2026-11-25T09:21:36.079Z
---
Medium. mountStackPage holds drawn, bodyKey, file, the take offer, and the body plan outside the browserless session (stack-page.js:608-721). Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
