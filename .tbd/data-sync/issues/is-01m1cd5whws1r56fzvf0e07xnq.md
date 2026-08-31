---
type: is
id: is-01m1cd5whws1r56fzvf0e07xnq
title: "PR #90 PLAN-03: The delivery map's \"measured\" normalizer claim is false against this PR's own code"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:54.715Z
updated_at: 2026-08-31T17:16:54.715Z
---
The map says no envelope carries an elapsed or duration field and that the table was measured. normalize.py in this same PR has ELAPSED_PATHS and CURSOR_PATHS, and two transcripts pin <ELAPSED> and <CURSOR>. The surrounding module map is also fiction: UNSTABLE_FIELDS, keep_revisions, and wait_for_index -> bool do not exist.
