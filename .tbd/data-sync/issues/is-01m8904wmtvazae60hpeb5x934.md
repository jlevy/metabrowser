---
type: is
id: is-01m8904wmtvazae60hpeb5x934
title: "PR #829 A3: start() during a read starts a second poll loop"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m8904gng5mvmjcwexd5z2vqe
hold: null
hold_until: null
created_at: 2026-11-25T09:21:20.025Z
updated_at: 2026-11-25T10:09:14.333Z
started_at: 2026-11-25T09:21:34.341Z
closed_at: 2026-11-25T10:09:14.318Z
close_reason: "Fixed in 614f81a (PR #829): polling flag and readAgain. Session one_loop case. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7159282117"
resolution: null
duplicate_of: null
---
Medium. stack-page.js:282-333 has no polling guard (pull-page.js:2730-2733 has one). Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
