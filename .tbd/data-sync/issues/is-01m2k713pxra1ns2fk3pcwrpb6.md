---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: in_progress
priority: 1
version: 23
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - stack:pr125
  - stack:pr132
  - stack:pr133
  - stack:pr134
  - stack:pr135
  - stack:pr136
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-16T21:51:22.267Z
started_at: 2026-09-16T21:24:51.532Z
---
After explicit approval and after every publication bead records a green formal PR, land and retarget the v0.11 stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, shared repository/provider mirror design, Hosted Review 0D, repository Phase 1A, worktree-free acquisition, content-source boundary, immutable Git-tree source, URL open, selected branch, provider foundation, direct PR view, PR index/navigation, and anchors. Retarget each next PR to its landed base, inspect exact new-base...HEAD diff, resolve only stacking conflicts, rerun make verify, obtain final green CI, and confirm main contains each layer. This is the sole landing owner; it never blocks constructing a later stack layer and never merges without explicit user approval.

## Notes

PRs #125, #130, #132, #133, #134, #135, and #136 are open draft stack layers. PR #136 is the completed Phase 0C.2 installed artifact/profile inventory and distribution-evidence layer at b907bb2734929cd0858207ba5d73639aee168636, based exactly on green PR #135 head 614fef15793ff7cffd0c4e85a577342472fd9686. All seven PR #136 checks are green: lint, distribution, Python 3.12, 3.13, 3.14, 3.14t, and stack integration. Fourteen independently reviewed findings were tracked as beads and fixed; disposition map: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401. PR: https://github.com/jlevy/metabrowser/pull/136. Continue stacking the next phase without landing; ordered landing and retargeting still require explicit approval and exact-diff revalidation for every PR.
