---
type: is
id: is-01m0nw7vy19mscpp49m1fsqdb1
title: Replace the gitignore pre-walk with git ls-files on a git tree (H35/S2)
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:36.320Z
updated_at: 2026-09-14T01:29:18.802Z
closed_at: 2026-09-14T01:29:18.798Z
close_reason: "Superseded by mb-mnj1 (commit 2e9e2066). Both goals are met without git ls-files: the pre-walk is gone (first rows 1.0-1.8 s vs 7.1-13.2 s on a 146k-file repository), and hierarchical per-directory matching agrees with git check-ignore, including negations and nested patterns. Remaining walk speed is tracked by mb-8yqt and mb-nbvk."
resolution: null
duplicate_of: null
---
Review suggestion S2. exp-006 took the pre-walk 21.4s -> 2.2s but it is still a full Python traversal duplicating the indexing walk. 'git ls-files -co --exclude-standard -z' returns the visible set directly, in C, with git's exact semantics -- including the negation cases the current rel_dir prefixing gets wrong (see the F3 finding). Could take the remaining 2.2s to near zero AND fix correctness, with the existing walk kept as the non-git fallback.
