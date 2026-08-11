---
type: is
id: is-01kzsbr4x0jjge2fg0s979q5g2
title: "PR #24: adopt the .btn control family for the Git panel Refresh button"
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:39.903Z
updated_at: 2026-08-11T21:30:48.231Z
closed_at: 2026-08-11T21:30:48.230Z
close_reason: Fixed on feat/git-graph-view; covered by tests that fail without the fix.
---
The v0.3.0 release branch (#30) established one role-based control family (.btn / .icon-btn) with structural tests enumerating its call sites. The Git panel predates it and hand-rolled .git-panel-refresh as a near-duplicate that also had no :focus-visible ring, so the Refresh button lost the family's focus affordance. Fixed by riding .btn and keeping only the local margin.
