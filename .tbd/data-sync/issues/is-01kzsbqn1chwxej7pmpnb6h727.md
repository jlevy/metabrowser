---
type: is
id: is-01kzsbqn1chwxej7pmpnb6h727
title: "PR #24 review R13: Git tab skips HEAD refresh on reopen"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:23.659Z
updated_at: 2026-08-11T21:30:47.174Z
closed_at: 2026-08-11T21:30:47.173Z
close_reason: Fixed on feat/git-graph-view; covered by tests that fail without the fix.
---
ensureHistory only reloaded when the graph was empty or a page fetch had failed with a cursor, so after the first load it never re-read /api/git/repo. HEAD is an input to lane layout and is baked into each row by computeSwimlanes, so a checkout made while another tab was showing left headRevision and the HEAD row marker pinned to the first paint. Fixed by re-reading repository identity on every activation (TTL-cached server-side) and recomputing the graph when the revision moved.
