---
type: is
id: is-01m8904vvygcka3t4fdqg5s9m4
title: "PR #829 A2: on Changes at a file every changed answer scrolls back to the file"
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
created_at: 2026-11-25T09:21:19.226Z
updated_at: 2026-11-25T10:09:10.827Z
started_at: 2026-11-25T09:21:33.684Z
closed_at: 2026-11-25T10:09:10.825Z
close_reason: "Fixed in 614f81a (PR #829): a one-time jump in bodyPlan; later answers keep. Session body case and headless Chrome on stack 809. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7159282117"
resolution: null
duplicate_of: null
---
High. stack-page.js:653-658 scrolls to file on every render while file stays set. Fix: jump once on navigation. Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
