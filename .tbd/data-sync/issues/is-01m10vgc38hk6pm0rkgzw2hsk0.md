---
type: is
id: is-01m10vgc38hk6pm0rkgzw2hsk0
title: "Repository library Phase 0: measure and freeze cache contracts"
kind: task
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01kzsb4jzq5a37evdz4bk0dqg4
  - type: blocks
    target: is-01m2p1ps48qjh1qt3wmk8s63ra
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-27T05:36:25.191Z
updated_at: 2026-09-17T15:23:28.190Z
started_at: 2026-09-16T21:10:44.778Z
closed_at: 2026-09-17T15:23:28.189Z
close_reason: "Measured and froze cache contracts: explorations/repository-cache/ harness and results; fixtures in tests/fixtures/repository-cache/ (url-grammar, source-identity, git-version-gates, object-requests, state-machines) pinned by tests/test_repository_cache_contract_fixtures.py with an exhaustive lock/lease/crash interleaving check (481-state existing-store model safe; old designs and move-order mutants caught). Decisions recorded in the repository plan and arch-repository-sources-and-provider-mirrors.md. Two independent review rounds (12 then 8 findings) all fixed: b9523344, c317eb61, 4335ba17, a8ec81e2 on claude/v011-cache-format-foundation. Full CI green on draft PR #140 at a8ec81e2."
resolution: null
duplicate_of: null
---
Remeasure full, blobless, and blobless-plus-backfill acquisition into a worktree-free Git database. Measure full-OID ls-tree inventory, batched cat-file blob reads, concurrent subjects, fetch coalescing, cancellation, multi-process contention, maintenance, and object retention against v0.10 history, commit detail, diff, and canonical path routes. Freeze safe URL grammar, source/store identity and aliasing, patched-Git floors, lazy-fetch behavior, and lock, publication, quarantine, trash, lease, and reclamation state machines before constants or bare-versus-no-checkout layout are chosen.
