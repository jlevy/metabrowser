---
type: is
id: is-01m2kb410hgwb52hxrvxfnwc65
title: "Hosted review Phase 0B.1d: model resource publication and tombstones"
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb505pj16mgj8secgn4dex
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
  - type: blocks
    target: is-01m2ktj7tvearg7zwk2nkz6cry
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:19.440Z
updated_at: 2026-09-16T01:31:32.342Z
closed_at: 2026-09-16T01:31:32.341Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Add closed transaction, collection coverage, truncation, continuation, snapshot, failure, ResourceSet, ProviderSyncManifest, ProviderViewPointer, and discriminated tombstone proof models to hosted_review/models.py with validate/dump entry points and relational closure validators. ResourceSet owns immutable logical collection coverage and pagination evidence; the manifest owns transaction state and closes over retrieval/resource-set snapshots; the pointer names a committed manifest and resource set. Enforce auth/repository consistency, unique references, current/last-complete eligibility, explicit partial/unavailable/not-requested semantics, and same-context tombstone evidence. A lone 404/null, filtered index absence, auth failure, permission loss, rate limit, or never-fetched state must not prove deletion.

## Notes

Implemented ResourceSet, ProviderSyncManifest, ProviderViewPointer, collection coverage, exact pagination closure, current/last-complete eligibility, tombstone evidence, and relational validators with focused tests.
