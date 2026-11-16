---
type: is
id: is-01m7kbr0fe467vajdbw6njqb71
title: "PR #485 B8: The removed inventory is still in the branch history (42f236d)"
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:43.373Z
updated_at: 2026-11-16T23:48:29.372Z
started_at: 2026-11-16T23:40:44.114Z
---
Low, the owner's call. Merging with a merge commit would put 42f236d into main's history. Fix: squash, or squash-merge. Coordinator decision: the coordinator squash-merges #485; say so in the PR body; do not rewrite the branch. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549

## Notes

Deferred (PR #485 review B, B8): the coordinator squash-merges #485, which keeps 42f236d out of main's history; the PR description says so (updated 2026-11-16 at 9e7d362). The branch is not rewritten. Close once #485 is squash-merged.
