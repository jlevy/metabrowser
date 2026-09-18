---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 repository and hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: open
priority: 1
version: 28
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
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-18T01:15:37.534Z
started_at: 2026-09-16T21:24:51.532Z
---
After explicit approval and after every publication bead records a green formal PR, land and retarget the v0.11 stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, shared repository/provider mirror design, Hosted Review 0D, repository Phase 1A, worktree-free acquisition, content-source boundary, immutable Git-tree source, untrusted-content profile, URL open, provider-job and selected-ref foundation, selected branch, provider foundation, direct PR cache, direct PR view, PR index/navigation, and anchors. Retarget each next PR to its landed base, inspect the exact new-base through HEAD diff, resolve only stacking conflicts, rerun make verify, obtain final green CI, and confirm main contains each layer. This is the sole landing owner; it never blocks constructing a later stack layer and never merges without explicit user approval.

## Notes

Stack tip as of 2026-09-18 is PR #140 (claude/v011-cache-format-foundation@18ec8870). Layers now include #138 shared-mirror design, #139 Phase 0D, and #140 Phase 1A cache foundation in addition to #125/#130/#132-#136. Landing remains approval-gated. Next implementation layer is mb-dxmb (file:// grammar) then mb-h51g (1B-a acquisition), stacked on #140. Trust lane mb-cun0 remains parallel and must be evaluated before 1B-a publication writes the first cache entries.
