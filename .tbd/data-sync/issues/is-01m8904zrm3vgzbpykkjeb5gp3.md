---
type: is
id: is-01m8904zrm3vgzbpykkjeb5gp3
title: "PR #829 A6: Files' summary handle is not checked after its await"
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
created_at: 2026-11-25T09:21:23.219Z
updated_at: 2026-11-25T10:09:23.946Z
started_at: 2026-11-25T09:21:37.054Z
closed_at: 2026-11-25T10:09:23.939Z
close_reason: "Fixed in 614f81a (PR #829): every mount, the Files summary included, goes through adopt(), which checks owns() and disposes a stale handle. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7159282117"
resolution: null
duplicate_of: null
---
Low. stack-page.js:683-690. Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
