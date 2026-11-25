---
type: is
id: is-01m8904vvygcka3t4fdqg5s9m4
title: "PR #829 A2: on Changes at a file every changed answer scrolls back to the file"
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
created_at: 2026-11-25T09:21:19.226Z
updated_at: 2026-11-25T09:21:33.685Z
started_at: 2026-11-25T09:21:33.684Z
---
High. stack-page.js:653-658 scrolls to file on every render while file stays set. Fix: jump once on navigation. Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
