---
type: is
id: is-01m2ktj7tvearg7zwk2nkz6cry
title: "Hosted review Phase 0B.1g: generalize provider resource profiles and collection pages"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
  - type: blocks
    target: is-01m2kb6031dk9t2pzt5d35fvyd
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-16T00:41:13.818Z
updated_at: 2026-09-16T01:31:33.797Z
closed_at: 2026-09-16T01:31:33.797Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Before the provider-storage schemas are frozen, remove PR-only seams from the storage kernel. Use provider-neutral contract IDs for storage records; generic provider-object and provider-collection targets; CollectionPage pagination evidence; namespaced ResourceProfileId values; and trusted immutable ResourceProfileSpec declarations outside cached data with per-collection contract, cardinality, pagination, and required-for-last-complete rules. Update manifest closure, pointer eligibility, repository/index binders, portable corpora, distribution proof, architecture/specs, and a synthetic release-index profile test proving a new provider collection requires no storage-kernel variant. No route, view, network, filesystem store, manifest registration, or dependency change.

## Notes

Implemented generic provider-object/provider-collection targets, CollectionPage, trusted ResourceProfileSpec declarations, exact slots/cardinality/pagination rules, and a synthetic hosted-release profile proving extensibility.
