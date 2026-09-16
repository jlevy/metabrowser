---
type: is
id: is-01m2p38vk3d6gkv2ts21bzfzw3
title: "Repository Phase 2B review: publish provider-job and selected-ref foundation PR"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:51:52.418Z
updated_at: 2026-09-16T21:54:38.859Z
started_at: 2026-09-16T21:54:38.858Z
---
Independently review and publish one formal provider-job and selected-ref foundation pull request after the worktree-free acquisition PR is green. Base it on the exact green mb-k900 head; review the exact diff for job-key isolation, no network under locks, staged fetch validation, full-OID verification, cancellation, and attached-checkout non-mutation. Run make verify, synchronize beads, use gh stack submit, watch every required check to final green, and register the PR and immutable head with mb-n2ro. Do not merge.
