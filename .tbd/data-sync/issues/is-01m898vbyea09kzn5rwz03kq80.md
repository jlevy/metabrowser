---
type: is
id: is-01m898vbyea09kzn5rwz03kq80
title: "PR #834 A3: a {commit} is checked in the store but linked to a page that reads the served checkout"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m898v9wsv87ksj602asv16mq
hold: null
hold_until: null
created_at: 2026-11-25T11:53:25.194Z
updated_at: 2026-11-25T13:15:00.472Z
started_at: 2026-11-25T12:13:04.976Z
closed_at: 2026-11-25T13:15:00.472Z
close_reason: "fixed in 138c1f8bb (PR #834 head fc78dc2b3); dispositions: https://github.com/jlevy/metabrowser/pull/834#issuecomment-7163499407"
resolution: null
duplicate_of: null
---
Medium. guided_review.py:1082-1118 and 1157-1163; git/routes.py:73-76 and 354: on a served checkout a commit only the overlay store holds answers ready but /commit/<sha> says not found. Fix: decide availability where the link reads it, or link to GitHub as timelineCommitHref does; a served-checkout test. Review: https://github.com/jlevy/metabrowser/pull/834#pullrequestreview-6057087093
