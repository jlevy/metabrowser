---
type: is
id: is-01m2nz79vrjb2vpp5ydxra84e5
title: Correct repository-source and shared provider-mirror architecture
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - design
dependencies:
  - type: blocks
    target: is-01m2p1prnv5sdvx5atj08ckqn2
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:41:07.187Z
updated_at: 2026-09-16T22:20:43.132Z
started_at: 2026-09-16T20:41:25.748Z
closed_at: 2026-09-16T22:20:43.131Z
close_reason: "Completed the corrected repository-source and provider-mirror architecture and refreshed both implementation plans at file- and function-level detail. Independent architecture and bead-graph re-reviews report no actionable findings. The design now defines one active subject per session, worktree-free shared Git stores, deterministic provider-store convergence, provider mirrors for attached or managed repositories, closed fetch authorization contexts, broker-pinned gh credentials, lock/lease/CAS rules, and the formal 2A through 2C phase chain. Final make verify passed: 2349 tests, 1 skipped, 124 goldens, lint, types, parity, audits, builds, and distribution checks."
resolution: null
duplicate_of: null
---
Correct the unreleased architecture and plans: replace pinned checkouts, detached worktrees, and entry-owned provider caches with one active RepositorySubject per server session, a shared worktree-free Git object store, and stable-repository/auth/profile-scoped provider mirrors. Specify source capabilities, plugin and Git consumer seams, cross-process publication and leases, staged fetches, alias convergence, exact phase boundaries, acceptance tests, and the corrected bead graph. Hand independent review and formal stacked publication to mb-c0m0.
