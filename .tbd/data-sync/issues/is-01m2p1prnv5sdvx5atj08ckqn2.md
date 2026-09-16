---
type: is
id: is-01m2p1prnv5sdvx5atj08ckqn2
title: "Shared repository/provider mirror design review: publish formal stacked PR"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - design
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2nz8zzgxsw9yzsgekxy82sr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.034Z
updated_at: 2026-09-16T21:26:54.322Z
started_at: 2026-09-16T21:24:54.275Z
---
Independently review the corrected repository-subject, shared worktree-free store, provider-mirror, capability, locking, lease, and phased-delivery architecture. Resolve every finding through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on exact green Phase 0C.2 PR #136 head. Record PR URL, base/head branches and immutable OIDs, formal stack view, review evidence, and final green CI. Do not merge; mb-n2ro alone owns explicit-approval landing and retargeting.
