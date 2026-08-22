---
type: is
id: is-01m0nhc76fxcrhvxrvtag7w4qr
title: "Attribute and cut build_gitignore_check: 19-23s before any row (H30)"
kind: task
status: open
priority: 0
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:44.575Z
updated_at: 2026-08-22T20:07:44.575Z
---
On a real 241k-file tree, build_gitignore_check takes 19.4-23.3s before the walk starts and therefore before any row can exist — larger than the 21.0s walk it precedes. Nothing in the plan accounted for it; it is not a scan cost, not a request cost, and invisible in browser metrics (the page loads fine with nothing to show). Attribute first: how many .gitignore files, pathspec compile vs read, is it O(files) or O(patterns). Then candidates: compile lazily per directory as the walk reaches it, cache compiled specs, or overlap it with the walk instead of gating on it. exp-005.
