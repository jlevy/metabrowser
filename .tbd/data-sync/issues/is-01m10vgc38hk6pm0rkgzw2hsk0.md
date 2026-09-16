---
type: is
id: is-01m10vgc38hk6pm0rkgzw2hsk0
title: "Repository library Phase 0: measure and freeze cache contracts"
kind: task
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01kzsb4jzq5a37evdz4bk0dqg4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-27T05:36:25.191Z
updated_at: 2026-09-16T21:11:13.023Z
started_at: 2026-09-16T21:10:44.778Z
---
Remeasure full, blobless, and blobless-plus-backfill acquisition into a worktree-free Git database. Measure full-OID ls-tree inventory, batched cat-file blob reads, concurrent subjects, fetch coalescing, cancellation, multi-process contention, maintenance, and object retention against v0.10 history, commit detail, diff, and canonical path routes. Freeze safe URL grammar, source/store identity and aliasing, patched-Git floors, lazy-fetch behavior, and lock, publication, quarantine, trash, lease, and reclamation state machines before constants or bare-versus-no-checkout layout are chosen.
