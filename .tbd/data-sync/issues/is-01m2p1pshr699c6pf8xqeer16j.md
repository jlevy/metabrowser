---
type: is
id: is-01m2p1pshr699c6pf8xqeer16j
title: "Repository library Phase 1B-a review: publish worktree-free acquisition PR"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2nz8q666pwqcbxbn7d5jr6x
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.927Z
updated_at: 2026-09-16T21:27:34.196Z
started_at: 2026-09-16T21:24:54.760Z
---
Independently review GitCommandTarget, worktree-free acquisition, source/store alias publication, ref/object validation, crash recovery, cross-process CAS behavior, CLI parity, and acquisition goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 1A head. Record exact stack evidence and final green CI. Do not merge.
