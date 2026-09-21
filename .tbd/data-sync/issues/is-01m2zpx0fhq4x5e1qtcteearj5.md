---
type: is
id: is-01m2zpx0fhq4x5e1qtcteearj5
title: "S216-12: latent lifecycle: store lock held across await, pool close race orphans an actor, two subject identities"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:05.615Z
updated_at: 2026-09-21T03:17:08.046Z
closed_at: 2026-09-21T03:17:08.045Z
close_reason: "All three items done. The colliding store_identity default and the pool close race were fixed earlier on this layer; the store lock held across an await is fixed in ce07942f by moving the lock and its update-ref into one synchronous section reached through asyncio.to_thread, with a new run_git_blocking that keeps the same isolation, ceiling, umask and error translation. Two concurrent leases of one store and of two stores both pass, having failed with LockOrderError before. The per-thread order check was deliberately NOT re-keyed to the task: the flock is blocking, so the thread is the unit that can wait, and a per-task notion would permit a genuine cross-process deadlock to go undetected; proven still honest by a new test that a worker thread is its own holder and still refuses a descending key and a descending rank. Two further blocking locks found and tracked separately."
resolution: null
duplicate_of: null
---
Finding S216-12 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-12.
