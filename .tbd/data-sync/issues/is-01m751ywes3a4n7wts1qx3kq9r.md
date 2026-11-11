---
type: is
id: is-01m751ywes3a4n7wts1qx3kq9r
title: "PR #346 C4: pin the walk teardowns that call walkCancelled (dispose, collapse, page hidden)"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m751ytvafc561t05kr196g8y
hold: null
hold_until: null
created_at: 2026-11-11T10:20:20.824Z
updated_at: 2026-11-11T10:34:28.259Z
started_at: 2026-11-11T10:20:28.796Z
closed_at: 2026-11-11T10:34:28.258Z
close_reason: "Fixed in 6d924fd3: github-pull-files-tree-session.js pins walkCancelled from a hidden page, a collapse, and dispose; the three reviewer mutants (clearWalk replaced by walkPath = null) are killed."
resolution: null
duplicate_of: null
---
Suggestion. Mutations dropping the notice from dispose (pull-files-tree.js:1428), collapse (:1237), and onVisibilityChange (:1261) survive all 8 DOM scripts. Add one step each. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5857164511 (PR #346, review C, follow-up round 3, head 4318e80).
