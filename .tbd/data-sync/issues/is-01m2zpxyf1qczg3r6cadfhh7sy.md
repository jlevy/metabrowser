---
type: is
id: is-01m2zpxyf1qczg3r6cadfhh7sy
title: "WS-1: workspace hygiene: gh stack metadata, unpushed feat/git-graph-view and pr13-folder-treemap, .pnpm-store ignore"
kind: chore
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:36.309Z
updated_at: 2026-09-21T02:08:52.602Z
---
Finding WS-1 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under WS-1.

## Notes

Done 2026-09-20: pruned 14 stale worktree registrations whose directories no longer existed (0 prunable remain); fast-forwarded every local stack branch and the metabrowser-v011-phase1a sibling worktree to their pushed heads, so 'gh stack view' now reports the real heads instead of the pre-restack ones; discarded the long-carried .tbd/config.yml working-tree edit, which became obsolete once the restack merged main's tbd 0.9.0 config (both docs_cache entries it added are present upstream; the named stash review216-preserve-preexisting-tbd-config remains as a backup). Verified by patch-equivalence (git cherry) that every commit on the stab/* fix branches reached its pushed branch; the one apparent miss (3bda1068, arch-external-resources-and-views.md) landed with a different patch id through the merge, and its content is confirmed present. REMAINING: .pnpm-store/ is untracked, empty and not ignored (a one-line .gitignore addition on main); local branches feat/git-graph-view (179 commits) and pr13-folder-treemap (6 commits) are unpushed and are the only at-risk work left, so decide whether to push or drop them; the stab/* and restack/* local branches are now fully contained upstream and can be deleted whenever.
