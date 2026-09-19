---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 repository and hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: open
priority: 1
version: 41
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:pr125
  - stack:pr132
  - stack:pr133
  - stack:pr134
  - stack:pr135
  - stack:pr136
  - stack:pr140
  - stack:pr141
  - stack:pr142
  - stack:pr146
  - stack:pr147
  - stack:pr148
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-19T16:42:28.047Z
started_at: 2026-09-16T21:24:51.532Z
---
After explicit approval and after every publication bead records a green formal PR, land and retarget the v0.11 stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, shared repository/provider mirror design, Hosted Review 0D, repository Phase 1A, worktree-free acquisition, content-source boundary, immutable Git-tree source, untrusted-content profile, URL open, provider-job and selected-ref foundation, selected branch, provider foundation, direct PR cache, direct PR view, PR index/navigation, and anchors. Retarget each next PR to its landed base, inspect the exact new-base through HEAD diff, resolve only stacking conflicts, rerun make verify, obtain final green CI, and confirm main contains each layer. This is the sole landing owner; it never blocks constructing a later stack layer and never merges without explicit user approval.

## Notes

Landing remains approval-gated. Do not merge. Construction 2026-09-19: formal stack 131 is #125→#130→#132→#133→#134→#135→#136→#138→#139→#140. Implementation layers ready as branches, PRs blocked on pull_requests=write: 1B-a `cursor/v011-cache-acquire-cli-bd04` @ `b09c01e0`, 1B-b #156 @ `19507616`, 1B-c `cursor/v011-git-revision-pin-bd04` @ `cd33e023`. HTML #209 parallel on main. Official append: `gh stack link --remote origin 131 cursor/v011-cache-acquire-cli-bd04 cursor/v011-source-boundary-bd04 cursor/v011-git-revision-pin-bd04`. Do not land until explicit approval after each phase PR exists, CI is green, and the runbook section for that phase passes.
