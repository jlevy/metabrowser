---
type: is
id: is-01m10z5s3nhwmdyp1dcbwfwc33
title: "Git status Phase 1: measured status and comparison backend"
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10z5zm6bknq2q57dsfjfv31
  - type: blocks
    target: is-01m1389tccq35y5z8ya6dpycwn
parent_id: is-01m10z5hmf2m2tndf00k0jznx8
created_at: 2026-08-27T06:40:32.370Z
updated_at: 2026-11-14T18:46:57.183Z
---
Implement the measured porcelain-v2 status service, typed API, record-aware bounds, and one-file File Diff Format working-tree adapter defined in Phase 1.

## Notes

2026-11-14 audit: mb-ian3 (metab --api) is closed, so that prerequisite is met. The repository library no longer depends on is_clean: Phase 1B-a (mb-h51g) landed with worktree-free stores that verify records, refs, objects, and leases instead (plan-2026-08-11, Phase Dependency Map). Git-version parsing exists in git/process.py (parse_git_version, detect_git_version); the 2.36 status gate does not. Spec updated to match.
