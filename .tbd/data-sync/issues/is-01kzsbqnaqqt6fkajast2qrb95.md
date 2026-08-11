---
type: is
id: is-01kzsbqnaqqt6fkajast2qrb95
title: "PR #24 review R14: Refresh keeps a stale commit-detail cache"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:23.958Z
updated_at: 2026-08-11T21:30:47.462Z
closed_at: 2026-08-11T21:30:47.461Z
close_reason: Fixed on feat/git-graph-view; covered by tests that fail without the fix.
---
refreshHistory reset graph state and reloaded log pages but never cleared detailCache. A commit object id is immutable but its payload is not — refs move as branches and tags do — so hover cards and the commit detail view could serve pre-refresh refs and file lists for a row the graph had just redrawn. Fixed by clearing the cache as part of the refresh reset.
