---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 repository and hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: open
priority: 1
version: 37
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
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-18T02:53:03.178Z
started_at: 2026-09-16T21:24:51.532Z
---
After explicit approval and after every publication bead records a green formal PR, land and retarget the v0.11 stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, shared repository/provider mirror design, Hosted Review 0D, repository Phase 1A, worktree-free acquisition, content-source boundary, immutable Git-tree source, untrusted-content profile, URL open, provider-job and selected-ref foundation, selected branch, provider foundation, direct PR cache, direct PR view, PR index/navigation, and anchors. Retarget each next PR to its landed base, inspect the exact new-base through HEAD diff, resolve only stacking conflicts, rerun make verify, obtain final green CI, and confirm main contains each layer. This is the sole landing owner; it never blocks constructing a later stack layer and never merges without explicit user approval.

## Notes

Stack construction as of 2026-09-18: reviewed tip remains PR #140. Construction continues with #141–#145 all CI green (#145 prefetch+crash recovery, mb-h5jw). Landing remains approval-gated. Trust lane mb-cun0 remains parallel and must be evaluated before mb-k900 serves acquired content.
