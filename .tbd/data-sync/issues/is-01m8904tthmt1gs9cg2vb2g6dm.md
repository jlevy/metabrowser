---
type: is
id: is-01m8904tthmt1gs9cg2vb2g6dm
title: "PR #829 A1: a cold stack with more than eight recordless members says Fetching indefinitely"
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
created_at: 2026-11-25T09:21:18.160Z
updated_at: 2026-11-25T10:09:07.097Z
started_at: 2026-11-25T09:21:33.001Z
closed_at: 2026-11-25T10:09:07.095Z
close_reason: "Fixed in 614f81a (PR #829): asks re-sent with backoff on 429, failure, or an ended fetch; members carry fetching; a failed recordless member shows Retry. Session cold case. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7159282117"
resolution: null
duplicate_of: null
---
High. stack-page.js:121-133, :255-270 ignore 429 too_many (MAX_PULL_JOBS, mirror_refresh.py:114) and never re-ask a <n>: key; a failed or empty fetch also leaves Fetching forever. Fix: re-ask refused members with backoff, say when a fetch ended without a record, with Retry. Review: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6054749709 (PR #829).
