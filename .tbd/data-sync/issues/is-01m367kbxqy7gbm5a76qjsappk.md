---
type: is
id: is-01m367kbxqy7gbm5a76qjsappk
title: A stale subject-ref lock makes every later pin of that revision fail
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-23T04:15:21.983Z
updated_at: 2026-09-23T04:15:23.316Z
---
Found while writing the mb-dg00 goldens (2026-09-22). lease_revision (src/metabrowser/cache/repository_store.py, the update-ref of refs/metabrowser/subjects/<oid>) runs a plain update-ref while holding the shared store lease. If Git is killed mid-update-ref it leaves refs/metabrowser/subjects/<oid>.lock. Reproduced by creating the lock by hand, not by killing Git. Every later --show/--api pin of that revision then fails. Before codex/v012-foundation-stabilization the failure printed the raw argument vector; after d06e4b58 it is the path-free 'a Git command failed while opening the pinned revision'. There is still no recovery. Removing the lock under a shared lease is unsafe, because a concurrent lease of the same OID legitimately holds it. Options: skip update-ref when the ref already resolves to the OID (fixes repeat pins, not first creation), and treat a lock older than the Git deadline as stale under the exclusive maintenance lock, with a repair path and golden. Coordinate with the Phase 2B CAS ref publication (publish_refs).
