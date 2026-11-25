---
type: is
id: is-01m89etp7pw797vzt2a2bsrtj8
title: "PR #834 B2: pin the batched git log with an ID that names no commit; fall back to one ID a run on failure"
kind: task
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89etmssv0xtt5xwa2qm5h2q
hold: null
hold_until: null
created_at: 2026-11-25T13:37:54.421Z
updated_at: 2026-11-25T14:05:21.459Z
started_at: 2026-11-25T13:37:58.771Z
closed_at: 2026-11-25T14:05:21.458Z
close_reason: "Fixed in 03a57880e on #834: _commit_rows falls back to one ID a run when the batched git log is refused; test_an_id_that_names_no_commit_leaves_the_steps_other_commits_ready pins a tree, blob, tag, and missing ID beside a commit in both modes. Disposition: https://github.com/jlevy/metabrowser/pull/834#issuecomment-7164727608"
resolution: null
duplicate_of: null
---
_commit_rows: a tree, blob, annotated tag, or missing ID beside a commit must not blank the step's other commits.
