---
type: is
id: is-01m2k1jj8edebds7zv8abfc917
title: "Hosted review Phase 0B.1: complete provider storage and repository records"
kind: task
status: in_progress
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
  - stack:pr130
dependencies:
  - type: blocks
    target: is-01m2k1jkq9cvxx9db7a0z14b0z
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2kb2nga7qt6kw5a07s2x7m1
  - is-01m2kb31dhpy38zhaf2f42b71r
  - is-01m2kb3g6wktd1ns9zhdcqk6d9
  - is-01m2kb410hgwb52hxrvxfnwc65
  - is-01m2kb4fa0swgkhrvw3qq21gtq
  - is-01m2kb505pj16mgj8secgn4dex
  - is-01m2ktj7tvearg7zwk2nkz6cry
  - is-01m2kb5g8pf551djgfmf9kcm87
  - is-01m2kb6031dk9t2pzt5d35fvyd
created_at: 2026-09-15T17:24:30.089Z
updated_at: 2026-09-16T00:41:51.693Z
---
Complete the provider-neutral, no-network storage/repository/index record family through nine reviewable child beads: freeze namespace and publication semantics; keep Python/JavaScript provider namespace scalars aligned; add AuthorizationContextRef and Retrieval; add ResourceSet, ProviderSyncManifest, and Tombstone; add auth-independent ProviderBinding and HostedRepository identity; add query-keyed ChangeRequestIndex; generalize provider-object/provider-collection targets, collection pages, and trusted resource profiles; package portable corpora; then run independent reviews, full verification, and publish the formal stack. No provider acquisition, filesystem store, route, view, manifest registration, or new dependency. Phase 0C owns compiled SoftSchema, installed contract/profile registries, and full browser parsers for the new records.

## Notes

Phase 0B.1 is one formal stacked pull request based on PR #130. Its child beads are implementation subtasks, not separate pull requests. Contract freeze, Python and JavaScript provider namespace parity, authorization/retrieval, publication and tombstone records, repository identity/binding, query-keyed indexes, portable corpus, independent review, make verify, gh publication, and final CI all land together. Phase 0A landing remains separately tracked by mb-n2ro and does not block construction of this stack layer.
