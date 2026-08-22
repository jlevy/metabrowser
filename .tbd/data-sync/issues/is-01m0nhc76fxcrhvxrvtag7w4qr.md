---
type: is
id: is-01m0nhc76fxcrhvxrvtag7w4qr
title: "Attribute and cut build_gitignore_check: 19-23s before any row (H30)"
kind: task
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:44.575Z
updated_at: 2026-08-22T21:12:39.460Z
closed_at: 2026-08-22T21:12:39.459Z
close_reason: "Landed: load_gitignore prunes ignored subtrees and hidden directories during its pre-walk. Both are semantics -- git does not read a .gitignore inside an ignored directory either. Measured interleaved, 3 repeats: real tree A 21.37s -> 2.54s, real tree B 0.75s -> 0.00s, reproducible corpus 1.65s -> 1.25s. Compiled patterns 10,668 -> 327. Verified no verdict changed for any visible path (341,872 checked on the largest tree). exp-006."
---
On a real 241k-file tree, build_gitignore_check takes 19.4-23.3s before the walk starts and therefore before any row can exist — larger than the 21.0s walk it precedes. Nothing in the plan accounted for it; it is not a scan cost, not a request cost, and invisible in browser metrics (the page loads fine with nothing to show). Attribute first: how many .gitignore files, pathspec compile vs read, is it O(files) or O(patterns). Then candidates: compile lazily per directory as the walk reaches it, cache compiled specs, or overlap it with the walk instead of gating on it. exp-005.
